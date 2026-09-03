# test/test_base_scraper.py
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# 确保 src 目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.base_scraper import BaseScraper
import src.base_scraper 

# 1. 创建模拟子类
class MockBulkScraper(BaseScraper):
    scraper_name = "mock_bulk"
    is_bulk_task = True
    needs_driver = True
    def scrape_all(self, driver, symbols):
        return [{"CODE": s, "VAL": "Bulk"} for s in symbols]
    def scrape_one(self, driver, symbol):
        return {"CODE": symbol, "VAL": "Single"}

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
        return [
            {"CODE": symbol, "TIME": "10:00", "VAL": "V1"},
            {"CODE": symbol, "TIME": "11:00", "VAL": "V2"},
            {"CODE": symbol, "TIME": "12:00", "VAL": "V3"},
        ]

class TestBaseScraper(unittest.TestCase):

    def setUp(self):
        # --- 核心修复：Mock 全局配置，为所有 Mock 爬虫提供 symbol_source ---
        self.mock_config = {
            'system': {'max_workers': 1, 'batch_size': 50},
            'mock_bulk': {'symbol_source': 'MOCK_TABLE_BULK', 'max_workers': 1},
            'mock_iter': {'symbol_source': 'MOCK_TABLE_ITER', 'max_workers': 1},
            'mock_otm': {'symbol_source': 'MOCK_TABLE_OTM', 'max_workers': 1},
        }
        # 使用 patch 替换 src.base_scraper 中的 config 对象
        self.config_patcher = patch('src.base_scraper.config', self.mock_config)
        self.config_patcher.start()

        self.mock_db = MagicMock()
        
        # 实例化
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
        # 临时修改 mock_config 验证优先级
        with patch('src.base_scraper.config', {
            'system': {'max_workers': 5, 'batch_size': 100},
            'mock_iter': {'max_workers': 20}
        }):
            scraper = MockIterativeScraper(db_op=self.mock_db)
            self.assertEqual(scraper.max_workers, 20)
            self.assertEqual(scraper.batch_size, 100)

    def test_missing_symbol_source_raises_error(self):
        """验证强制校验：缺失 symbol_source 必须报错"""
        # 模拟一个缺失 symbol_source 的配置
        bad_config = {'mock_iter': {'max_workers': 10}} 
        with patch('src.base_scraper.config', bad_config):
            scraper = MockIterativeScraper(db_op=self.mock_db)
            with self.assertRaises(KeyError) as cm:
                scraper.run(None, "TABLE_B", "JOB_FAIL")
            self.assertIn("symbol_source' is missing", str(cm.exception))

    @patch('src.base_scraper.SymbolProvider')
    @patch('selenium.webdriver.Chrome')
    def test_bulk_run(self, mock_chrome, mock_provider_class):
        """验证 Bulk 模式"""
        mock_provider_inst = mock_provider_class.return_value
        mock_provider_inst.get_target_symbols.return_value = iter(["S1", "S2"])
        
        job_name = "JOB_BULK"
        self.bulk_scraper.run(None, "TABLE_A", job_name)
        
        mock_chrome.assert_called_once()
        self.mock_db.insert_batch.assert_called_once()
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)

    @patch('src.base_scraper.SymbolProvider')
    def test_iterative_run(self, mock_provider_class):
        """验证 Iterative 模式"""
        mock_provider_inst = mock_provider_class.return_value
        mock_provider_inst.get_target_symbols.return_value = iter(["S1", "FAIL", "S3"])
        
        job_name = "JOB_ITER"
        self.iter_scraper.max_workers = 1 
        self.iter_scraper.run(None, "TABLE_B", job_name)
        
        self.assertEqual(self.mock_db.insert_batch.call_count, 2)
        self.assertEqual(self.iter_scraper.backup_manager.save_record.call_count, 2)

    @patch('src.base_scraper.SymbolProvider')
    def test_iterative_run_one_to_many(self, mock_provider_class):
        """验证 OTM 模式"""
        mock_provider_inst = mock_provider_class.return_value
        mock_provider_inst.get_target_symbols.return_value = iter(["AAPL", "MSFT"])
        
        job_name = "JOB_OTM"
        self.otm_scraper.max_workers = 1
        self.otm_scraper.run(None, "TABLE_OTM", job_name)
        
        self.assertEqual(self.mock_db.insert_batch.call_count, 2)
        found_otm = any(len(call[0][1]) == 3 for call in self.mock_db.insert_batch.call_args_list)
        self.assertTrue(found_otm)

    @patch('selenium.webdriver.Chrome')
    def test_driver_lazy_loading(self, mock_chrome):
        """验证 Driver 延迟加载逻辑"""
        self.assertIsNone(self.bulk_scraper._driver)
        self.bulk_scraper.get_driver()
        self.assertIsNotNone(self.bulk_scraper._driver)
        mock_chrome.assert_called_once()

if __name__ == "__main__":
    unittest.main()