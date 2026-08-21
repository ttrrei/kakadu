# test/test_afr_scraper.py
import unittest
from unittest.mock import MagicMock, patch
import logging
import json
from src.scrapers.afr_scraper import AfrScraper
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAfrScraper(unittest.TestCase):

    def setUp(self):
        # 为单元测试提供 Mock DB，避免单元测试阶段连接真实数据库
        self.mock_db = MagicMock()
        self.scraper = AfrScraper(db_op=self.mock_db)

    @patch('requests.get')
    def test_scrape_one_success(self, mock_get):
        """Unit Test: 验证 AfrScraper 正确解析 GraphQL 返回的 JSON 数据。"""
        symbol = "ASX_CBA"
        
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
        self.assertEqual(result[0]["OPEN"], "100.5")  # 验证是否转为了字符串（由业务逻辑或 DbOperator 处理）
        self.assertEqual(result[1]["CLOSE"], "101.5")
        self.assertEqual(result[1]["TICK_TIME"], "2023-11-01T10:05:00Z")

    @patch('requests.get')
    def test_scrape_one_api_failure(self, mock_get):
        """Unit Test: 验证当 API 请求失败时，scraper 能优雅处理（返回 None）。"""
        mock_get.side_effect = Exception("AFR API Down")
        result = self.scraper.scrape_one(None, "ASX_CBA")
        self.assertIsNone(result)

    def test_end_to_end_integration(self):
        """
        Integration Test: 触发全链路逻辑 (API -> Buffer -> DB)
        并验证数据是否成功存入 Oracle 数据库。
        """
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for AfrScraper...")
            
            # 1. 使用真实的 db_operator 实例化
            real_scraper = AfrScraper(db_op=db_operator)
            
            # 2. 定义测试参数
            test_symbols = ["ASX_CBA"] 
            target_table = "ODS_PRICE_TICK"  # 确保数据库中存在此表
            job_name = "TEST_AFR_E2E"
            
            # 3. 执行真实运行 (会发送网络请求并写入数据库)
            real_scraper.run(test_symbols, target_table, job_name)
            
            # 4. 直接查询数据库验证结果
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # 检查该 Job ID (BATCH_ID) 下是否有记录落地
            sql = f"SELECT COUNT(*) FROM {target_table} WHERE BATCH_ID = :bid"
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                # 释放连接回连接池
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()