# test/test_base_scraper.py
import logging
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call
from typing import Any, List, Dict, Optional, Union

# 确保 src 目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.base_scraper import BaseScraper
from src.db_operator import DbOperator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# Mock Scrapers for Testing
# ==============================================================================

class MockBulkScraper(BaseScraper):
    scraper_name = "mock_bulk"
    is_bulk_task = True
    needs_driver = True
    def scrape_all(self, driver, symbols):
        return [{"CODE": "S1", "VAL": "Bulk"}]
    def scrape_one(self, driver, symbol):
        return None

class MockIterativeScraper(BaseScraper):
    scraper_name = "mock_iter"
    is_bulk_task = False
    needs_driver = False
    def scrape_all(self, driver, symbols):
        return []
    def scrape_one(self, driver, symbol):
        if symbol == "FAIL":
            raise Exception("Simulated Scrape Error")
        return {"CODE": symbol, "VAL": "Iter"}

class MockOneToManyScraper(BaseScraper):
    scraper_name = "mock_otm"
    is_bulk_task = False
    needs_driver = False
    def scrape_all(self, driver, symbols):
        return []
    def scrape_one(self, driver, symbol):
        # 模拟一个符号产生多条记录 (例如 OHLCV 历史数据)
        return [
            {"CODE": symbol, "TIME": "10:00", "VAL": "V1"},
            {"CODE": symbol, "TIME": "11:00", "VAL": "V2"},
            {"CODE": symbol, "TIME": "12:00", "VAL": "V3"},
        ]

# ==============================================================================
# Test Suite
# ==============================================================================

class TestBaseScraper(unittest.TestCase):

    def setUp(self):
        # 模拟全局配置
        self.mock_config = {
            'system': {'max_workers': 1, 'batch_size': 50, 'backup_dir': '/tmp/backup'},
            'mock_bulk': {'symbol_source': 'MOCK_TABLE_BULK', 'target_table': 'ODS_BULK', 'max_workers': 1},
            'mock_iter': {'symbol_source': 'MOCK_TABLE_ITER', 'target_table': 'ODS_ITER', 'max_workers': 1, 'batch_size': 3},
            'mock_otm': {'symbol_source': 'MOCK_TABLE_OTM', 'target_table': 'ODS_OTM', 'max_workers': 1},
        }
        self.config_patcher = patch('src.base_scraper.config', self.mock_config)
        self.config_patcher.start()

        self.mock_db = MagicMock()
        
        # 实例化 Mock 爬虫
        self.bulk_scraper = MockBulkScraper(db_op=self.mock_db)
        self.bulk_scraper.backup_manager = MagicMock()
        
        self.iter_scraper = MockIterativeScraper(db_op=self.mock_db)
        self.iter_scraper.backup_manager = MagicMock()
        
        self.otm_scraper = MockOneToManyScraper(db_op=self.mock_db)
        self.otm_scraper.backup_manager = MagicMock()

    def tearDown(self):
        self.config_patcher.stop()

    def test_config_loading_priority(self):
        """验证配置加载优先级: Scraper-specific > System-global > Default"""
        with patch('src.base_scraper.config', {
            'system': {'max_workers': 5, 'batch_size': 100},
            'mock_iter': {'max_workers': 20}
        }):
            scraper = MockIterativeScraper(db_op=self.mock_db)
            self.assertEqual(scraper.max_workers, 20)
            self.assertEqual(scraper.batch_size, 100)
        logger.info("Verified: Config priority honored.")

    def test_missing_config_raises_error(self):
        """验证缺失 target_table 或 symbol_source 时必须报错"""
        # 模拟缺失 target_table
        with patch('src.base_scraper.config', {'mock_iter': {'symbol_source': 'T1'}}):
            scraper = MockIterativeScraper(db_op=self.mock_db)
            with self.assertRaises(KeyError):
                scraper.run(job_name="fail_job")
        
        # 模拟缺失 symbol_source
        with patch('src.base_scraper.config', {'mock_iter': {'target_table': 'T1'}}):
            scraper = MockIterativeScraper(db_op=self.mock_db)
            with self.assertRaises(KeyError):
                scraper.run(job_name="fail_job")
        logger.info("Verified: KeyError raised on missing critical config.")

    @patch('src.base_scraper.SymbolProvider')
    @patch('selenium.webdriver.Chrome')
    def test_bulk_run(self, mock_chrome, mock_provider_class):
        """验证 Bulk 模式：Driver 加载 -> scrape_all -> DB 写入"""
        mock_provider_inst = mock_provider_class.return_value
        mock_provider_inst.get_target_symbols.return_value = iter(["S1", "S2"])
        
        job_name = "JOB_BULK"
        self.bulk_scraper.run(job_name=job_name)
        
        mock_chrome.assert_called_once()
        self.mock_db.insert_batch.assert_called_once()
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)
        logger.info("Verified: Bulk run flow completed.")

    @patch('src.base_scraper.SymbolProvider')
    def test_iterative_buffering_and_errors(self, mock_provider_class):
        """验证迭代模式：内存安全迭代 -> 错误隔离 -> DB 缓冲写入"""
        mock_provider_inst = mock_provider_class.return_value
        # 5个符号，其中一个 FAIL。batch_size=3
        mock_provider_inst.get_target_symbols.return_value = iter(["S1", "S2", "FAIL", "S3", "S4"])
        
        job_name = "JOB_ITER"
        self.iter_scraper.run(job_name=job_name)
        
        # 成功 4 个，FAIL 1 个。
        # 写入时机：S1,S2,S3 (batch 3) -> 写入1次； S4 -> 写入1次。总共 2 次。
        self.assertEqual(self.mock_db.insert_batch.call_count, 2)
        # 备份应被调用 4 次 (S1, S2, S3, S4)
        self.assertEqual(self.iter_scraper.backup_manager.save_record.call_count, 4)
        logger.info("Verified: Iterative mode handles errors and buffering correctly.")

    @patch('src.base_scraper.SymbolProvider')
    def test_iterative_one_to_many(self, mock_provider_class):
        """验证 OTM 模式：单个符号产生多条记录且正确缓冲"""
        mock_provider_inst = mock_provider_class.return_value
        # 2个符号，每个产生 3 条记录 = 6 条记录。batch_size=3
        mock_provider_inst.get_target_symbols.return_value = iter(["AAPL", "MSFT"])
        
        job_name = "JOB_OTM"
        # 强制设置 batch_size 为 3
        self.otm_scraper.batch_size = 3
        self.otm_scraper.run(job_name=job_name)
        
        # 6 条记录 / batch_size 3 = 2 次写入
        self.assertEqual(self.mock_db.insert_batch.call_count, 2)
        # 验证最后一次写入的数据量
        last_call_records = self.mock_db.insert_batch.call_args[0][1]
        self.assertEqual(len(last_call_records), 3)
        logger.info("Verified: One-to-Many records are buffered and flushed correctly.")

    @patch('selenium.webdriver.Chrome')
    def test_driver_lifecycle(self, mock_chrome):
        """验证 Driver 延迟加载与强制关闭"""
        mock_driver_inst = MagicMock()
        mock_chrome.return_value = mock_driver_inst
        
        # 1. 验证延迟加载
        self.assertIsNone(self.bulk_scraper._driver)
        self.bulk_scraper.get_driver()
        self.assertIsNotNone(self.bulk_scraper._driver)
        
        # 2. 验证 run 结束后的关闭
        with patch('src.base_scraper.SymbolProvider') as mock_sp:
            mock_sp.return_value.get_target_symbols.return_value = iter([])
            self.bulk_scraper.run(job_name="driver_test")
            mock_driver_inst.quit.assert_called_once()
        logger.info("Verified: Driver lazy-loading and lifecycle management.")

if __name__ == "__main__":
    unittest.main()