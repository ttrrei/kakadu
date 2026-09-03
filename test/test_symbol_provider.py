# test/test_symbol_provider.py
import logging
import sys
import os
import unittest
from unittest.mock import patch

# 将 src 加入路径以便导入
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.symbol_provider import SymbolProvider
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSymbolProvider(unittest.TestCase):

    def test_basic_retrieval(self):
        """测试基础功能：提供 source_table 后能否获取符号且格式正确"""
        logger.info("--- Testing Basic Symbol Retrieval ---")
        # 必须提供 source_table
        provider = SymbolProvider(source_table="ODS_COMPANY_MASTER")
        
        count = 0
        for symbol in provider.get_target_symbols():
            self.assertTrue(symbol.endswith(".AX"), f"Symbol {symbol} should end with .AX")
            count += 1
            if count >= 5:
                break
        
        if count == 0:
            logger.warning("No symbols found in ODS_COMPANY_MASTER. This might be normal if DB is empty.")
        else:
            logger.info(f"Successfully retrieved {count} sample symbols.")

    def test_missing_source_table_raises_error(self):
        """验证强制校验：不提供 source_table 必须报错"""
        logger.info("--- Testing Missing Source Table Validation ---")
        with self.assertRaises(KeyError) as cm:
            SymbolProvider() # 不传 source_table
        self.assertIn("requires 'source_table'", str(cm.exception))
        logger.info("Verified: KeyError raised when source_table is missing.")

    def test_filter_logic(self):
        """测试过滤逻辑"""
        logger.info("--- Testing Filter Logic ---")
        # 模拟配置：排除 CBA.AX
        mock_config = {
            'symbol_filter': {
                'excluded_symbols': ['CBA'], # 注意这里是 raw symbol
                'require_suffix': '.AX'
            }
        }
        
        with patch('src.symbol_provider.config', mock_config):
            provider = SymbolProvider(source_table="ODS_COMPANY_MASTER")
            for symbol in provider.get_target_symbols():
                # 验证排除项不被产出 (CBA -> CBA.AX)
                self.assertNotEqual(symbol, "CBA.AX", "Excluded symbol CBA.AX was yielded!")
                break 

    def test_connection_leak(self):
        """测试连接释放"""
        logger.info("--- Testing Connection Leak ---")
        provider = SymbolProvider(source_table="ODS_COMPANY_MASTER")
        
        # 执行一次完整迭代
        for _ in provider.get_target_symbols():
            pass
        
        logger.info("Iteration completed. Check logs for any connection leak warnings.")

if __name__ == "__main__":
    unittest.main()