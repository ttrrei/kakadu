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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestListScraper(unittest.TestCase):

    def setUp(self):
        # Initialize scraper. It will now automatically load self.config from BaseScraper
        self.scraper = ListScraper()

    @patch('src.scrapers.list_scraper.requests.get')
    def test_scrape_all_logic_with_mock(self, mock_get):
        """Unit Test: Verify that the scraper correctly parses CSV content using config URL."""
        # Mock the API response
        mock_response = MagicMock()
        mock_csv_content = (
            '"ASX code","Company name","GICs industry group","Listing date","Market Cap"\n'
            '"CBA","Commonwealth Bank","Financials","1991-09-12",289040418474\n'
            '"4DS","4DS Memory","Semiconductors","2010-12-09","--"'
        )
        mock_response.text = mock_csv_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Execute scrape_all
        results = self.scraper.scrape_all(None, [])

        # Verify parsing logic
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["CODE"], "CBA")
        self.assertIsNone(results[1]["MARKET_CAP"])
        
        # Verify that the request was made to the URL defined in config.yaml
        expected_url = config.get('scrapers', {}).get('company_master', {}).get('url')
        mock_get.assert_called_once_with(expected_url, timeout=30, headers=unittest.mock.ANY)
        
        logger.info("✅ Mock API parsing and Config URL test PASSED")

    def test_end_to_end_integration(self):
        """Integration Test: API -> Parse -> DbOperator -> Oracle with BATCH_ID verification."""
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for ListScraper...")
            
            # 1. Use the real scraper (which now uses the verified config.yaml)
            real_scraper = ListScraper(db_op=db_operator)
            
            # 2. Get target table from config to ensure consistency
            target_table = config.get('scrapers', {}).get('company_master', {}).get('target_table', "ODS_COMPANY_MASTER")
            job_name = "TEST_LIST_E2E"
            
            # 3. Execute full pipeline: scrape_all -> backup -> insert_batch
            # Note: symbols=[] is passed because ListScraper is bulk and ignores the list
            real_scraper.run([], target_table, job_name)
            
            # 4. Verify BATCH_ID matching data exists in Oracle
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # Use the table name from config
            sql = f"SELECT COUNT(*) FROM {target_table} WHERE BATCH_ID = :bid"
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name} in {target_table}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            logger.exception("Integration test failed with exception:")
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()