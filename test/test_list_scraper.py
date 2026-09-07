# test/test_list_scraper.py
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.list_scraper import ListScraper
from src.db_operator import db as db_operator
from src.config import config

# Configure logging to see the process clearly
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestListScraper(unittest.TestCase):

    def setUp(self):
        """Initialize scraper. It will automatically load config via BaseScraper."""
        self.scraper = ListScraper()

    @patch('src.scrapers.list_scraper.requests.get')
    def test_scrape_all_logic_with_mock(self, mock_get):
        """
        Unit Test: Verify that the scraper correctly parses CSV content 
        using the URL defined in the top-level config.yaml node.
        """
        # 1. Mock the API response
        mock_response = MagicMock()
        mock_csv_content = (
            '"ASX code","Company name","GICs industry group","Listing date","Market Cap"\n'
            '"CBA","Commonwealth Bank","Financials","1991-09-12",289040418474\n'
            '"4DS","4DS Memory","Semiconductors","2010-12-09","--"'
        )
        mock_response.text = mock_csv_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 2. Execute scrape_all
        # Note: symbols=[] is passed because ListScraper is bulk and ignores it
        results = self.scraper.scrape_all(None, [])

        # 3. Verify parsing logic
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["CODE"], "CBA")
        self.assertEqual(results[0]["COMPANY_NAME"], "Commonwealth Bank")
        self.assertIsNone(results[1]["MARKET_CAP"], "Market Cap '--' should be converted to None")
        
        # 4. Verify that the request was made to the URL defined in top-level config.yaml
        # Correct path: config.get('company_master')
        expected_url = config.get('company_master', {}).get('url')
        mock_get.assert_called_once_with(expected_url, timeout=30, headers=unittest.mock.ANY)
        
        logger.info("✅ Unit Test: Mock API parsing and Config URL test PASSED")

    def test_end_to_end_integration(self):
        """
        Integration Test: API -> Parse -> Local Backup -> DbOperator -> Oracle.
        Verifies that real data enters the database with the correct BATCH_ID.
        """
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for ListScraper...")
            
            # 1. Setup parameters
            # Use the real scraper instance
            real_scraper = ListScraper()
            
            # Retrieve target table from top-level config
            target_table = config.get('company_master', {}).get('target_table', "ODS_COMPANY_MASTER")
            job_name = "TEST_LIST_E2E_RUN"
            
            # 2. Execute full pipeline
            # BaseScraper.run(job_name) handles: scrape_all -> backup -> insert_batch
            real_scraper.run(job_name=job_name)
            
            # 3. Verify data in Oracle
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # Check if any records exist for this specific job_name
            sql = f'SELECT COUNT(*) FROM {target_table} WHERE "BATCH_ID" = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name} in {target_table}")
            logger.info(f"✅ Integration test PASSED: {count} records successfully ingested into {target_table}")
            
        except Exception as e:
            logger.exception("Integration test failed with exception:")
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()