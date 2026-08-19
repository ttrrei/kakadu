# test/test_base_scraper.py
import unittest
from unittest.mock import MagicMock, patch
from src.base_scraper import BaseScraper

# 1. 创建一个模拟子类，用于测试基类逻辑
class MockBulkScraper(BaseScraper):
    is_bulk_task = True
    needs_driver = True

    def scrape_all(self, driver, symbols):
        # 模拟返回数据
        return [{"CODE": "TEST1", "VAL": "A"}, {"CODE": "TEST2", "VAL": "B"}]

    def scrape_one(self, driver, symbol):
        return {"CODE": symbol, "VAL": "Single"}

class MockCsvScraper(BaseScraper):
    is_bulk_task = True
    needs_driver = False # 测试不需要 Driver 的情况

    def scrape_all(self, driver, symbols):
        return [{"CODE": "CSV1", "VAL": "C"}]

    def scrape_one(self, driver, symbol):
        return {"CODE": symbol, "VAL": "Single"}

class MockIterativeScraper(BaseScraper):
    is_bulk_task = False
    needs_driver = True

    def scrape_all(self, driver, symbols):
        return []

    def scrape_one(self, driver, symbol):
        if symbol == "FAIL":
            raise Exception("Simulated Scrape Error")
        return {"CODE": symbol, "VAL": "Iterative"}

class MockOneToManyScraper(BaseScraper):
    """模拟像 Yahoo 这样一个 Symbol 返回多条记录的 Scraper"""
    is_bulk_task = False
    needs_driver = False

    def scrape_all(self, driver, symbols):
        return []

    def scrape_one(self, driver, symbol):
        # 模拟为每个 symbol 返回 3 条历史数据
        return [
            {"CODE": symbol, "TIME": "10:00", "VAL": "V1"},
            {"CODE": symbol, "TIME": "11:00", "VAL": "V2"},
            {"CODE": symbol, "TIME": "12:00", "VAL": "V3"},
        ]

class TestBaseScraper(unittest.TestCase):

    def setUp(self):
        # 模拟 DbOperator，避免真实连接数据库
        self.mock_db = MagicMock()
        # 实例化模拟子类
        self.bulk_scraper = MockBulkScraper(db_op=self.mock_db)
        self.csv_scraper = MockCsvScraper(db_op=self.mock_db)
        self.iter_scraper = MockIterativeScraper(db_op=self.mock_db)
        self.otm_scraper = MockOneToManyScraper(db_op=self.mock_db)

    @patch('selenium.webdriver.Chrome')
    def test_bulk_run_with_driver(self, mock_chrome):
        """测试全量模式且需要 Driver 的情况"""
        # 设置 mock driver
        mock_driver_instance = mock_chrome.return_value
        
        self.bulk_scraper.run(["S1"], "TABLE_A", "JOB_BULK")
        
        # 验证：Driver 应该被创建且最终被关闭
        mock_chrome.assert_called_once()
        mock_driver_instance.quit.assert_called_once()
        # 验证：DbOperator.insert_batch 应该被调用
        self.mock_db.insert_batch.assert_called_once()

    @patch('src.base_scraper.webdriver.Chrome') # 明确 patch 导入到 base_scraper 里的那个 Chrome
    def test_bulk_run_without_driver(self, mock_chrome):
        """测试全量模式但不需要 Driver 的情况 (如 CSV)"""
        # 确保 needs_driver 为 False
        self.csv_scraper.needs_driver = False 
        
        self.csv_scraper.run(["S1"], "TABLE_B", "JOB_CSV")
        
        # 验证：Chrome 绝对不应该被调用
        mock_chrome.assert_not_called()
        # 验证：数据依然能写入 DB
        self.mock_db.insert_batch.assert_called_once()

    @patch('selenium.webdriver.Chrome')
    def test_iterative_run_with_shield(self, mock_chrome):
        """测试迭代模式的 'Shield' 容错机制"""
        # 模拟 symbols，其中一个会触发异常
        symbols = ["SUCCESS1", "FAIL", "SUCCESS2"]
        
        self.iter_scraper.run(symbols, "TABLE_C", "JOB_ITER")
        
        # 验证：即使中间有 FAIL，最终成功的记录依然被写入
        # 预期写入 2 条记录 (SUCCESS1, SUCCESS2)
        # 注意：因为 batch_size 默认 50，这里会一次性写入
        self.mock_db.insert_batch.assert_called()
        args, _ = self.mock_db.insert_batch.call_args
        records = args[1]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["CODE"], "SUCCESS1")
        self.assertEqual(records[1]["CODE"], "SUCCESS2")

    def test_iterative_run_one_to_many(self):
        """测试迭代模式处理 One-to-Many (List[Dict]) 的情况"""
        symbols = ["AAPL", "MSFT"]
        # 每个 symbol 返回 3 条，共 6 条
        self.otm_scraper.run(symbols, "TABLE_OTM", "JOB_OTM")
        
        # 验证：DbOperator.insert_batch 应该被调用
        self.mock_db.insert_batch.assert_called()
        args, _ = self.mock_db.insert_batch.call_args
        records = args[1]
        
        # 关键验证：buffer 应该是扁平的 List[Dict]，而不是 List[List[Dict]]
        self.assertEqual(len(records), 6)
        self.assertIsInstance(records[0], dict)
        self.assertEqual(records[0]["CODE"], "AAPL")
        self.assertEqual(records[5]["CODE"], "MSFT")

    @patch('selenium.webdriver.Chrome')
    def test_driver_lazy_loading(self, mock_chrome):
        """测试 Driver 的延迟加载逻辑"""
        # 初始状态 driver 应该是 None
        self.assertIsNone(self.bulk_scraper._driver)
        
        # 调用 get_driver 应该触发创建
        driver = self.bulk_scraper.get_driver()
        self.assertIsNotNone(driver)
        mock_chrome.assert_called_once()
        
        # 第二次调用不应再次创建
        self.bulk_scraper.get_driver()
        mock_chrome.assert_called_once()

if __name__ == "__main__":
    unittest.main()