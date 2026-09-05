# test/test_symbol_provider.py
import logging
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 将 src 加入路径以便导入
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.symbol_provider import SymbolProvider
from src.db_operator import DbOperator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSymbolProvider(unittest.TestCase):

    def setUp(self):
        # 使用虚拟表名，避免在 Mock 测试中产生误导
        self.mock_source = "VW_TEST_SYMBOLS"

    def test_real_db_integration(self):
        """
        【集成测试】验证真实数据库连通性
        验证：能否从真实表 ODS_COMPANY_MASTER 获取数据并正确格式化。
        """
        logger.info("--- Testing Real DB Integration ---")
        try:
            # 使用真实主表进行连通性测试
            provider = SymbolProvider(source_table="ODS_COMPANY_MASTER")
            symbols = list(provider.get_target_symbols())
            
            if not symbols:
                logger.warning("ODS_COMPANY_MASTER is empty. Integration test passed but no data found.")
            else:
                for s in symbols:
                    self.assertTrue(s.endswith(".AX"), f"Symbol {s} should be formatted with .AX")
                logger.info(f"Successfully retrieved {len(symbols)} symbols from real DB.")
        except Exception as e:
            self.fail(f"Real DB integration failed: {e}")

    def test_missing_source_table_raises_error(self):
        """验证：未提供 source_table 时必须抛出 KeyError"""
        logger.info("--- Testing Missing Source Table Validation ---")
        with self.assertRaises(KeyError):
            SymbolProvider(source_table=None)
        logger.info("Verified: KeyError raised when source_table is missing.")

    @patch('src.symbol_provider.DbOperator')
    def test_data_cleaning_and_formatting(self, MockDbOperator):
        """
        【逻辑测试】验证数据清洗与补全逻辑
        验证：处理各种脏数据（空格、大小写、缺失后缀、None值）的能力。
        """
        logger.info("--- Testing Data Cleaning & Formatting ---")
        
        # 模拟数据库返回的原始数据
        # 1. 标准格式 -> 保持不变
        # 2. 缺少后缀 -> 补全 .AX
        # 3. 带有空格且大小写混乱 -> 清洗并补全
        # 4. None 值 -> 应该被跳过
        # 5. 空字符串 -> 应该被跳过
        mock_raw_data = [
            ("CBA.AX",), 
            ("NAB",), 
            (" wbc .ax ",), 
            (None,), 
            ("",), 
            ("ANZ",)
        ]
        
        # Mock DB 基础设施
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = mock_raw_data + [None] # 最后返回 None 结束迭代
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock DbOperator 实例
        instance = MockDbOperator.return_value
        instance.get_connection.return_value = mock_conn
        
        provider = SymbolProvider(db_operator=instance, source_table=self.mock_source)
        results = list(provider.get_target_symbols())
        
        # 预期结果
        expected = ["CBA.AX", "NAB.AX", "WBC.AX", "ANZ.AX"]
        self.assertEqual(results, expected)
        logger.info(f"Logic Test Passed: {results} == {expected}")

    @patch('src.symbol_provider.DbOperator')
    def test_connection_lifecycle(self, MockDbOperator):
        """
        【资源测试】验证连接释放
        验证：无论迭代是否成功，连接必须被释放回连接池。
        """
        logger.info("--- Testing Connection Lifecycle ---")
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None # 立即结束
        mock_conn.cursor.return_value = mock_cursor
        
        instance = MockDbOperator.return_value
        instance.get_connection.return_value = mock_conn
        
        provider = SymbolProvider(db_operator=instance, source_table=self.mock_source)
        
        # 执行迭代
        for _ in provider.get_target_symbols():
            pass
        
        # 验证 release 方法被调用，防止连接泄漏
        instance._pool.release.assert_called_with(mock_conn)
        logger.info("Verified: Connection released back to pool.")

    @patch('src.symbol_provider.DbOperator')
    def test_exception_handling(self, MockDbOperator):
        """
        【异常测试】验证错误处理
        验证：当数据库查询崩溃时，连接依然能被释放且异常能被正确抛出。
        """
        logger.info("--- Testing Exception Handling ---")
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # 模拟执行查询时发生数据库异常
        mock_cursor.execute.side_effect = Exception("DB Connection Lost")
        mock_conn.cursor.return_value = mock_cursor
        
        instance = MockDbOperator.return_value
        instance.get_connection.return_value = mock_conn
        
        provider = SymbolProvider(db_operator=instance, source_table=self.mock_source)
        
        with self.assertRaises(Exception) as cm:
            for _ in provider.get_target_symbols():
                pass
        
        self.assertEqual(str(cm.exception), "DB Connection Lost")
        # 关键：即使崩溃，连接也必须释放
        instance._pool.release.assert_called_with(mock_conn)
        logger.info("Verified: Connection released even after exception.")

if __name__ == "__main__":
    unittest.main()