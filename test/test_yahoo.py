# test/test_yahoo.py
import unittest
from unittest.mock import MagicMock, patch
import logging
from src.scrapers.yahoo_scraper import YahooScraper
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestYahooScraper(unittest.TestCase):

    def setUp(self):
        # 为单元测试提供 Mock DB
        self.mock_db = MagicMock()
        self.scraper = YahooScraper(db_op=self.mock_db)

    @patch('requests.get')
    def test_scrape_one_success(self, mock_get):
        """Unit Test: Verify that scrape_one correctly filters and maps Yahoo API data."""
        # Guaranteed multiple of 3600: 3600 * 472222 = 1699999200
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
        result = self.scraper.scrape_one(None, symbol)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["CODE"], "CBA")
        self.assertEqual(result[0]["RAW_TIMESTAMP"], ts_valid)
        self.assertEqual(result[0]["CLOSE_PRICE"], 10.5)

    @patch('requests.get')
    def test_scrape_one_api_failure(self, mock_get):
        """Unit Test: Test that the scraper handles HTTP errors gracefully."""
        mock_get.side_effect = Exception("Connection Timeout")
        result = self.scraper.scrape_one(None, "CBA")
        self.assertIsNone(result)

    def test_end_to_end_integration(self):
        """
        Integration Test: Trigger full pipeline (API -> Buffer -> DB) 
        and verify data presence in Oracle.
        """
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for YahooScraper...")
            
            # 1. 使用真实的 db_operator 重新实例化
            real_scraper = YahooScraper(db_op=db_operator)
            
            # 2. 定义测试参数
            symbols = ["CBA"] # 使用少量 symbol 快速验证
            target_table = "ODS_PRICE_OHLCV"
            job_name = "TEST_YAHOO_E2E"
            
            # 3. 执行真实运行
            real_scraper.run(symbols, target_table, job_name)
            
            # 4. 直接查询数据库验证结果
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # 检查该 Job ID 下是否有记录
            sql = f"SELECT COUNT(*) FROM EQUITY.{target_table} WHERE BATCH_ID = :bid"
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