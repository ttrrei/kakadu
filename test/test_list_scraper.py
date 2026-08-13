# test/test_list_scraper.py
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.list_scraper import ListScraper
from src.db_operator import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestListScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = ListScraper()

    @patch('src.scrapers.list_scraper.requests.get')
    def test_scrape_all_logic_with_mock(self, mock_get):
        """
        Unit Test: Verify that the scraper correctly parses CSV content 
        from the API response into the expected List[Dict] format.
        """
        # 1. Mock the API response
        mock_response = MagicMock()
        # 模拟真实的 CSV 内容，包含 Header 和两行数据（其中一行包含 "--"）
        mock_csv_content = (
            '"ASX code","Company name","GICs industry group","Listing date","Market Cap"\n'
            '"CBA","Commonwealth Bank","Financials","1991-09-12",289040418474\n'
            '"4DS","4DS Memory","Semiconductors","2010-12-09","--"'
        )
        mock_response.text = mock_csv_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 2. Execute the scraping logic
        results = self.scraper.scrape_all(None, [])

        # 3. Assertions
        self.assertEqual(len(results), 2)
        
        # Test first record (Normal)
        self.assertEqual(results[0]["CODE"], "CBA")
        self.assertEqual(results[0]["COMPANY_NAME"], "Commonwealth Bank")
        self.assertEqual(results[0]["SECTOR"], "Financials")
        self.assertEqual(results[0]["LISTING_DATE"], "1991-09-12")
        self.assertEqual(results[0]["MARKET_CAP"], "289040418474")
        
        # Test second record (Handle "--")
        self.assertEqual(results[1]["CODE"], "4DS")
        self.assertEqual(results[1]["COMPANY_NAME"], "4DS Memory")
        self.assertEqual(results[1]["LISTING_DATE"], "2010-12-09")
        self.assertIsNone(results[1]["MARKET_CAP"]) # 验证 "--" 被转换为 None
        
        logger.info("✅ Mock API parsing test PASSED")

    def test_end_to_end_integration(self):
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for ListScraper...")
            # 触发全链路：API -> Parse -> DbOperator -> Oracle
            self.scraper._run_bulk([], "ODS_COMPANY_MASTER")
            
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM EQUITY.ODS_COMPANY_MASTER")
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, "Database should contain records")
            logger.info(f"✅ Integration test PASSED: {count} records found")
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db._pool.release(conn)

if __name__ == "__main__":
    unittest.main()