# test/test_yahoo.py
import unittest
from unittest.mock import MagicMock, patch
import logging
from src.scrapers.yahoo_scraper import YahooScraper
from src.db_operator import db as db_operator
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestYahooScraper(unittest.TestCase):

    def setUp(self):
        # We test both sessions to ensure routing is correct
        self.mock_db = MagicMock()
        # Test with 'pre_close' by default
        self.scraper_pre = YahooScraper(db_op=self.mock_db, session_type='pre_close')
        self.scraper_post = YahooScraper(db_op=self.mock_db, session_type='post_close')

    def test_session_routing(self):
        """Verify that different sessions route to different tables as per config.yaml."""
        self.assertEqual(self.scraper_pre.target_table, "ODS_PRICE_OHLCV_PRE")
        self.assertEqual(self.scraper_post.target_table, "ODS_PRICE_OHLCV_POST")
        self.assertEqual(self.scraper_pre.interval, "1h")
        self.assertEqual(self.scraper_post.range, "3d")

    @patch('requests.get')
    def test_scrape_one_data_filtering(self, mock_get):
        """Verify that scrape_one correctly filters timestamps and handles missing values."""
        # Valid: exactly on the hour
        ts_valid = 1699999200 
        # Invalid: offset by 1 second
        ts_invalid = 1699999201
        # Invalid: missing close price
        ts_none_close = 1699999200 + 3600
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": [ts_valid, ts_invalid, ts_none_close], 
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 10.1, 10.2],
                                "high": [11.0, 11.1, 11.2],
                                "low": [9.0, 9.1, 9.2],
                                "close": [10.5, 10.6, None],
                                "volume": [1000, 1100, 1200]
                            }
                        ]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response

        symbol = "CBA"
        # Use the pre_close scraper
        result = self.scraper_pre.scrape_one(None, symbol)

        self.assertIsNotNone(result)
        # Should only contain 1 record (ts_valid). 
        # ts_invalid is filtered by %3600, ts_none_close is filtered by None check.
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["CODE"], "CBA")
        self.assertEqual(result[0]["RAW_TIMESTAMP"], str(ts_valid))
        self.assertEqual(result[0]["CLOSE_PRICE"], "10.5")

    @patch('requests.get')
    def test_api_failure_handling(self, mock_get):
        """Verify that HTTP errors and timeouts are handled gracefully."""
        # Test 404 (Symbol not found)
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_resp_404.raise_for_status.side_effect = Exception("404 Client Error")
        mock_get.return_value = mock_resp_404
        
        result = self.scraper_pre.scrape_one(None, "NONEXISTENT")
        self.assertIsNone(result)

        # Test Timeout/Connection Error
        mock_get.side_effect = Exception("Connection Timeout")
        result = self.scraper_pre.scrape_one(None, "CBA")
        self.assertIsNone(result)

    def test_end_to_end_integration(self):
        """
        Integration Test: Trigger full pipeline (SymbolProvider -> YahooScraper -> DbOperator)
        Verify that data lands in the CORRECT session table.
        """
        conn = None
        try:
            logger.info("Starting E2E Integration Test for YahooScraper (Pre-Close)...")
            
            # 1. Use real db_operator
            real_scraper = YahooScraper(db_op=db_operator, session_type='pre_close')
            
            # 2. Define test parameters
            # We use the target_table determined by the session_type
            target_table = real_scraper.target_table # Should be ODS_PRICE_OHLCV_PRE
            job_name = "TEST_YAHOO_E2E_PRE"
            
            # 3. Execute real run
            # Note: run() will now use SymbolProvider to get symbols automatically
            real_scraper.run(table_name=target_table, job_name=job_name)
            
            # 4. Query database to verify
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # Check if records exist in the PRE table specifically
            sql = f"SELECT COUNT(*) FROM EQUITY.{target_table} WHERE BATCH_ID = :bid"
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database table {target_table} should contain records for {job_name}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()