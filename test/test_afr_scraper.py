# test/test_afr_scraper.py
import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

# 确保能找到 src 目录
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.afr_scraper import AfrScraper
from src.db_operator import db as db_operator
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAfrScraper(unittest.TestCase):

    def setUp(self):
        """
        为单元测试准备 Mock 环境。
        注意：对于单元测试，我们传递 mock_db 以避免连接真实数据库。
        """
        self.mock_db = MagicMock()
        self.scraper = AfrScraper(db_op=self.mock_db)

    @patch('requests.get')
    def test_scrape_one_success(self, mock_get):
        """
        Unit Test: 验证 AfrScraper 正确解析 GraphQL 返回的 JSON 数据。
        """
        symbol = "CBA.AX"
        
        # 模拟 AFR GraphQL 的返回结构
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "FIVE_MINUTES_1_DAY": {
                    "quotes": [
                        {
                            "open": 100.50,
                            "high": 101.00,
                            "low": 100.00,
                            "close": 100.75,
                            "time": "2023-11-01T10:00:00Z"
                        },
                        {
                            "open": 100.75,
                            "high": 102.00,
                            "low": 100.50,
                            "close": 101.50,
                            "time": "2023-11-01T10:05:00Z"
                        }
                    ]
                }
            }
        }
        mock_get.return_value = mock_response

        # 执行抓取
        result = self.scraper.scrape_one(None, symbol)

        # 断言验证
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["CODE"], symbol)
        self.assertEqual(result[0]["OPEN"], "100.5")  # 验证是否转为了字符串
        self.assertEqual(result[1]["CLOSE"], "101.5")
        self.assertEqual(result[1]["TICK_TIME"], "2023-11-01T10:05:00Z")

    @patch('requests.get')
    def test_scrape_one_api_failure(self, mock_get):
        """
        Unit Test: 验证当 API 请求失败时，scraper 能优雅处理（返回 None）。
        """
        mock_get.side_effect = Exception("AFR API Down")
        result = self.scraper.scrape_one(None, "CBA.AX")
        self.assertIsNone(result)

    def test_end_to_end_integration(self):
        """
        Integration Test: 触发全链路逻辑 (SymbolProvider -> API -> Buffer -> DB)
        验证真实数据是否成功存入 Oracle 数据库。
        """
        conn = None
        try:
            logger.info("Starting E2E Integration Test for AfrScraper...")
            
            # 1. 实例化真实 Scraper (使用单例 db_operator)
            # 此时它会从 config.yaml 加载 target_table="ODS_PRICE_TICK" 和 symbol_source
            real_scraper = AfrScraper() 
            job_name = "TEST_AFR_E2E"
            
            # 2. 执行真实运行
            # 此时 run() 内部会自动调用 SymbolProvider 获取 symbols 并执行循环
            real_scraper.run(job_name=job_name)
            
            # 3. 直接查询数据库验证结果
            target_table = real_scraper.target_table
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # 使用双引号处理表名，防止 Oracle 关键字冲突
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