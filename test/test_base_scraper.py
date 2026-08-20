# test/test_base_scraper.py
import unittest
from unittest.mock import MagicMock, patch
from src.base_scraper import BaseScraper

# 1. 创建模拟子类，用于测试基类逻辑
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
        """测试全量模式且需要 Driver 的情况，并验证 job_name 传递"""
        mock_driver_instance = mock_chrome.return_value
        job_name = "JOB_BULK_TEST"
        
        self.bulk_scraper.run(["S1"], "TABLE_A", job_name)
        
        mock_chrome.assert_called_once()
        mock_driver_instance.quit.assert_called_once()
        
        # 验证：insert_batch 被调用，且 batch_id 正确
        self.mock_db.insert_batch.assert_called_once()
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)

    @patch('src.base_scraper.webdriver.Chrome') 
    def test_bulk_run_without_driver(self, mock_chrome):
        """测试全量模式但不需要 Driver 的情况 (如 CSV)"""
        self.csv_scraper.needs_driver = False 
        job_name = "JOB_CSV_TEST"
        
        self.csv_scraper.run(["S1"], "TABLE_B", job_name)
        
        mock_chrome.assert_not_called()
        self.mock_db.insert_batch.assert_called_once()
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)

    @patch('selenium.webdriver.Chrome')
    def test_iterative_run_with_shield(self, mock_chrome):
        """测试迭代模式的 'Shield' 容错机制，并验证 job_name 传递"""
        symbols = ["SUCCESS1", "FAIL", "SUCCESS2"]
        job_name = "JOB_ITER_TEST"
        
        self.iter_scraper.run(symbols, "TABLE_C", job_name)
        
        self.mock_db.insert_batch.assert_called()
        # 检查最后一次调用是否传递了正确的 batch_id
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)
        
        records = args[1]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["CODE"], "SUCCESS1")

    def test_iterative_run_one_to_many(self):
        """测试迭代模式处理 One-to-Many (List[Dict]) 的情况，并验证 job_name"""
        symbols = ["AAPL", "MSFT"]
        job_name = "JOB_OTM_TEST"
        self.otm_scraper.run(symbols, "TABLE_OTM", job_name)
        
        self.mock_db.insert_batch.assert_called()
        args, kwargs = self.mock_db.insert_batch.call_args
        self.assertEqual(kwargs.get('batch_id'), job_name)
        
        records = args[1]
        self.assertEqual(len(records), 6)
        self.assertIsInstance(records[0], dict)
        self.assertEqual(records[0]["CODE"], "AAPL")

    @patch('selenium.webdriver.Chrome')
    def test_driver_lazy_loading(self, mock_chrome):
        """测试 Driver 的延迟加载逻辑"""
        self.assertIsNone(self.bulk_scraper._driver)
        driver = self.bulk_scraper.get_driver()
        self.assertIsNotNone(driver)
        mock_chrome.assert_called_once()
        self.bulk_scraper.get_driver()
        mock_chrome.assert_called_once()

if __name__ == "__main__":
    unittest.main()