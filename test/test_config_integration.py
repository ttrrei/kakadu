# test/test_config_integration.py
import sys
import os
import unittest
from unittest.mock import MagicMock

# 确保 src 目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import config
from src.base_scraper import BaseScraper

class MockScraper(BaseScraper):
    """用于测试配置加载的模拟爬虫"""
    scraper_name = "price_ohlcv_pre" # 模拟一个真实存在的配置项
    def scrape_all(self, d, s): return []
    def scrape_one(self, d, s): return None

class TestConfigIntegration(unittest.TestCase):

    def test_env_secrets_loading(self):
        """验证 .env 敏感数据是否加载成功"""
        print("\n--- Testing .env Secrets ---")
        env = config.env
        self.assertTrue(env.database.user, "ORACLE_USER should be loaded")
        self.assertTrue(env.database.tns_alias, "ORACLE_TNS_ALIAS should be loaded")
        self.assertTrue(env.database.wallet_path, "ORACLE_WALLET_PATH should be loaded")
        print("✅ .env secrets loaded successfully.")

    def test_scraper_config_resolution(self):
        """
        验证 BaseScraper 能否正确解析配置。
        这是最关键的测试：验证 config.yaml 结构是否与 BaseScraper 代码匹配。
        """
        print("\n--- Testing Scraper Config Resolution ---")
        # 实例化模拟爬虫
        # 注意：这里不需要真实的 DB 连接，因为我们只测试 __init__ 阶段的配置加载
        scraper = MockScraper(db_op=MagicMock())
        
        # 1. 验证 target_table 是否正确加载 (验证顶级节点结构)
        # 如果 config.yaml 结构错误，这里会是 None
        self.assertIsNotNone(
            scraper.target_table, 
            f"Critical Error: target_table NOT FOUND for {scraper.scraper_name}. "
            f"Check if the scraper config is at the TOP LEVEL of config.yaml (not under 'scrapers:')"
        )
        print(f"✅ Target table found: {scraper.target_table}")

        # 2. 验证 batch_size 优先级 (Scraper > System > Default)
        # 假设 config.yaml 中 price_ohlcv_pre 定义了 batch_size: 50
        self.assertEqual(scraper.batch_size, 50)
        print(f"✅ Batch size resolved correctly: {scraper.batch_size}")

    def test_system_config_loading(self):
        """验证全局系统配置加载"""
        print("\n--- Testing System Config ---")
        system_cfg = config.get('system')
        self.assertIsNotNone(system_cfg, "System config node should exist")
        self.assertEqual(system_cfg.get('log_level'), "INFO")
        print("✅ System config loaded successfully.")

if __name__ == "__main__":
    unittest.main()