# test/test_yahoo.py
import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the concrete subclasses
from src.scrapers.yahoo_scraper import YahooPreScraper, YahooPostScraper
from src.db_operator import db as db_operator
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestYahooScraper(unittest.TestCase):

    def test_session_routing(self):
        """Verify that different scraper classes load different configs automatically."""
        # 100% QA compliant: No arguments passed to constructor
        scraper_pre = YahooPreScraper()
        scraper_post = YahooPostScraper()
        
        self.assertEqual(scraper_pre.target_table, "ODS_PRICE_OHLCV_PRE")
        self.assertEqual(scraper_post.target_table, "ODS_PRICE_OHLCV_POST")
        self.assertEqual(scraper_pre.interval, "1h")
        self.assertEqual(scraper_post.range, "3d")

    @patch('requests.get')
    def test_scrape_one_data_filtering(self, mock_get):
        """Verify timestamp filtering and missing value handling."""
        ts_valid = 1699999200 
        ts_invalid = 1699999201
        ts_none_close = 1699999200 + 3600
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": [ts_valid, ts_invalid, ts_none_close], 
                    "indicators": {
                        "quote": [{
                            "open": [10.0, 10.1, 10.2],
                            "high": [11.0, 11.1, 11.2],
                            "low": [9.0, 9.1, 9.2],
                            "close": [10.5, 10.6, None],
                            "volume": [1000, 1100, 1200]
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response

        # Use the concrete subclass
        scraper = YahooPreScraper()
        result = scraper.scrape_one(None, "CBA")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["RAW_TIMESTAMP"], str(ts_valid))

    def test_end_to_end_integration(self):
        """Integration Test: Full pipeline for Pre-Close session."""
        conn = None
        try:
            logger.info("Starting E2E Integration Test for YahooScraper (Pre-Close)...")
            
            # 100% QA compliant: Instantiate and run without external parameters
            real_scraper = YahooPreScraper()
            job_name = "TEST_YAHOO_E2E_PRE"
            
            real_scraper.run(job_name=job_name)
            
            target_table = real_scraper.target_table
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # Use double quotes for table names to prevent Oracle keyword conflicts
            sql = f'SELECT COUNT(*) FROM EQUITY."{target_table}" WHERE "BATCH_ID" = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Table {target_table} should contain records for {job_name}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()