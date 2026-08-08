# test/test_list_scraper.py
import unittest
from unittest.mock import MagicMock, patch
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
        # 初始化 Scraper，使用单例 db_operator
        self.scraper = ListScraper()

    def test_scrape_all_logic_with_mock(self):
        """
        Unit Test: Verify that the scraper correctly parses HTML elements 
        into the expected List[Dict] format without needing a real browser.
        """
        # 1. Mock the WebDriver and its elements
        mock_driver = MagicMock()
        mock_row = MagicMock()
        
        # Mock the 'a' tag for CODE
        mock_a = MagicMock()
        mock_a.get_attribute.return_value = "CBA"
        mock_row.find_element.return_value = mock_a
        
        # Mock the 'text-left' class for SECTOR
        mock_sector = MagicMock()
        mock_sector.get_attribute.return_value = "Financials"
        
        # Mock the 'text-right' elements for MCAP
        mock_mcap = MagicMock()
        mock_mcap.get_attribute.return_value = "100B"
        
        # Setup the row's find_element and find_elements behavior
        def side_effect_find_element(by, value=None):
            if by == "a": return mock_a
            if by == "text-left": return mock_sector # Simplified for mock
            return MagicMock()

        # This is a simplified mock of the row's internal structure
        mock_row.find_element.side_effect = lambda by, val=None: \
            mock_a if by == "a" else mock_sector if "text-left" in str(by) else MagicMock()
        
        mock_row.find_elements.return_value = [MagicMock(), mock_mcap]
        
        # Mock the table structure: scroll-overlay -> tbody -> tr
        mock_tbody = MagicMock()
        mock_tbody.find_elements.return_value = [mock_row]
        
        mock_overlay = MagicMock()
        mock_overlay.find_element.return_value = mock_tbody
        
        mock_driver.find_element.return_value = mock_overlay

        # 2. Execute the scraping logic
        results = self.scraper.scrape_all(mock_driver, [])

        # 3. Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["CODE"], "CBA")
        self.assertEqual(results[0]["SECTOR"], "Financials")
        self.assertEqual(results[0]["MARKET_CAP"], "100B")
        logger.info("✅ Mock parsing test PASSED")

    def test_end_to_end_integration(self):
        """
        Integration Test: Real Browser -> Real DB.
        WARNING: This requires a working .env and Oracle Wallet.
        """
        try:
            logger.info("Starting End-to-End Integration Test for ListScraper...")
            
            # 1. Run the scraper (this will launch headless chrome)
            # We use a dummy symbols list because it's a Bulk task
            # We manually call the internal _run_bulk to test the pipeline
            self.scraper._run_bulk([], "ODS_COMPANY_MASTER")
            
            # 2. Verify data in DB
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM EQUITY.ODS_COMPANY_MASTER")
            count = cursor.fetchone()[0]
            cursor.close()
            db._pool.release(conn)
            
            self.assertGreater(count, 0, "Database should contain records after scraping")
            logger.info(f"✅ Integration test PASSED: {count} records found in DB")
            
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")

if __name__ == "__main__":
    unittest.main()