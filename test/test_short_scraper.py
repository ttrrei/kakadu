# test/test_short_scraper.py
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.short_scraper import ShortPositionScraper
from src.db_operator import db as db_operator
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestShortScraper(unittest.TestCase):

    def setUp(self):
        """Initialize scraper. BaseScraper handles config loading."""
        self.scraper = ShortPositionScraper()

    def test_scrape_all_success(self):
        """Unit Test: Verify basic parsing logic with standard CSV content."""
        mock_csv = """Product,Product Code,Reported Short Positions,Total Product in Issue,% of Total Product in Issue Reported as Short Positions
3D ENERGI LTD ORDINARY,TDO,181029,524226804,.03453257
4DMEDICAL LIMITED ORDINARY,4DX,70928934,599638859,11.82860866"""

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = mock_csv
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            results = self.scraper.scrape_all(driver=None, symbols=[])

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["CODE"], "TDO")
            self.assertEqual(results[1]["SHORT_POSITIONS"], "70928934")

    def test_scrape_all_with_commas_and_empty_values(self):
        """Unit Test: Verify that commas are removed and empty values are handled."""
        mock_csv = """Product,Product Code,Reported Short Positions,Total Product in Issue,% of Total Product in Issue Reported as Short Positions
COMMA CORP,COM,"1,234,567","10,000,000",1.23
EMPTY CORP,EMP,,,0.0"""

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = mock_csv
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            results = self.scraper.scrape_all(driver=None, symbols=[])

            self.assertEqual(results[0]["SHORT_POSITIONS"], "1234567")
            self.assertEqual(results[1]["SHORT_POSITIONS"], "")

    def test_end_to_end_integration(self):
        """Integration Test: Real API -> Parse -> DbOperator -> Oracle with BATCH_ID verification."""
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for ShortPositionScraper...")
            
            # 1. Use the real scraper
            real_scraper = ShortPositionScraper()
            
            # 2. Get target table from config
            target_table = config.get('short', {}).get('target_table', "ODS_SHORT_POSITION")
            job_name = "TEST_SHORT_E2E_RUN"
            
            # 3. Execute full pipeline (Corrected method signature)
            real_scraper.run(job_name=job_name)
            
            # 4. Verify BATCH_ID matching data exists in Oracle
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            sql = f'SELECT COUNT(*) FROM {target_table} WHERE "BATCH_ID" = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()