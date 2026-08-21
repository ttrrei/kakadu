# test/test_annc_scraper.py
import unittest
from unittest.mock import MagicMock, patch
import logging
from src.scrapers.annc_scraper import AnncScraper
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAnncScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = AnncScraper()

    def test_scrape_all_success(self):
        # 模拟 Driver 和 DOM 结构
        mock_driver = MagicMock()
        mock_table = MagicMock()
        mock_tbody = MagicMock()
        
        mock_row = MagicMock()
        mock_cols = [
            MagicMock(text="ABC"),          # CODE
            MagicMock(text="2023-10-27\n10:00"), # DATE
            MagicMock(text=""),             # PSENSITIVE (should be True)
            MagicMock(text="Title\nInfo")   # TITLE
        ]
        mock_row.find_elements.return_value = mock_cols
        mock_tbody.find_elements.return_value = [mock_row]
        mock_table.find_element.return_value = mock_tbody
        mock_driver.find_element.return_value = mock_table

        results = self.scraper.scrape_all(mock_driver)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["CODE"], "ABC")
        self.assertEqual(results[0]["PSENSITIVE"], "True")

    def test_scrape_all_empty_table(self):
        mock_driver = MagicMock()
        mock_driver.find_element.side_effect = Exception("No element")
        results = self.scraper.scrape_all(mock_driver)
        self.assertEqual(results, [])

    def test_end_to_end_db_integration(self):
        """
        Integration Test: 验证数据能通过 Scraper -> DbOperator 成功落地到 Oracle。
        这里我们 Mock 掉 Selenium 的抓取部分，但使用真实的 DB 写入链路。
        """
        conn = None
        try:
            logger.info("Starting DB Integration Test for AnncScraper...")
            
            # 1. 定义测试参数
            target_table = "ODS_MARKET_ANNC" 
            job_name = "TEST_ANNC_E2E"
            
            # 2. 模拟 scrape_all 返回的数据
            # 我们 patch 掉 scrape_all，让它直接返回测试数据，而不需要启动真实的 Chrome
            mock_data = [
                {"CODE": "TEST01", "RELEASE_DATE": "2023-10-27 10:00", "PSENSITIVE": "True", "TITLE": "Integration Test Title 1"},
                {"CODE": "TEST02", "RELEASE_DATE": "2023-10-27 11:00", "PSENSITIVE": "False", "TITLE": "Integration Test Title 2"},
            ]
            
            with patch.object(AnncScraper, 'scrape_all', return_value=mock_data):
                # 执行 run 方法。因为 is_bulk_task=True，它会调用 scrape_all -> insert_batch
                # 注意：这里 symbols 传空列表即可，因为我们 mock 了 scrape_all
                self.scraper.run(symbols=[], table_name=target_table, job_name=job_name)
            
            # 3. 直接查询数据库验证结果
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # 检查该 Job ID (BATCH_ID) 下是否有记录落地
            sql = f"SELECT COUNT(*) FROM {target_table} WHERE BATCH_ID = :bid"
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name}")
            logger.info(f"✅ DB Integration test PASSED: {count} records found in {target_table}")
            
        except Exception as e:
            self.fail(f"DB Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()