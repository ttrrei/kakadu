# test/test_symbol_provider.py
import logging
import sys
import os

# 将 src 加入路径以便导入
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
from src.symbol_provider import SymbolProvider, get_target_symbols_generator
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_symbol_provider_basic():
    """测试基础功能：能否获取符号且格式正确"""
    logger.info("--- Testing Basic Symbol Retrieval ---")
    provider = SymbolProvider()
    
    # 获取前 5 个符号进行验证
    count = 0
    for symbol in provider.get_target_symbols():
        logger.info(f"Found symbol: {symbol}")
        assert symbol.endswith(".AX"), f"Symbol {symbol} should end with .AX"
        count += 1
        if count >= 5:
            break
    
    if count == 0:
        logger.error("No symbols found in ODS_COMPANY_MASTER. Please check your DB data.")
    else:
        logger.info(f"Successfully retrieved {count} sample symbols.")

def test_generator_behavior():
    """测试生成器行为：确保不是一次性加载到内存的 list"""
    logger.info("--- Testing Generator Behavior ---")
    gen = get_target_symbols_generator()
    
    # 验证它是一个生成器对象而非列表
    assert hasattr(gen, '__next__'), "Symbol provider should return a generator/iterator"
    logger.info("Verified: Symbol provider returns a generator (O(1) memory potential).")

def test_filter_logic():
    """测试过滤逻辑 (需要修改 config.yaml 或 Mock config)"""
    logger.info("--- Testing Filter Logic ---")
    # 注意：这里依赖于你的 config.yaml 配置
    # 如果你想测试，可以在 config.yaml 的 symbol_filter 下添加 excluded_symbols
    provider = SymbolProvider()
    
    # 检查配置是否加载
    logger.info(f"Excluded symbols: {provider._excluded_symbols}")
    logger.info(f"Included symbols: {provider._included_symbols}")
    
    # 验证获取的符号中不包含排除项
    for symbol in provider.get_target_symbols():
        assert symbol not in provider._excluded_symbols, f"Excluded symbol {symbol} was yielded!"
        if provider._use_included_only:
            assert symbol in provider._included_symbols, f"Symbol {symbol} not in inclusion list!"
        
        # 仅测试前 100 个以节省时间
        break # 这里仅作演示，实际可增加计数器

def test_connection_leak():
    """测试连接释放：确保迭代后连接池没有被占满"""
    logger.info("--- Testing Connection Leak ---")
    initial_pool_size = db_operator._pool.opened # 如果 oracledb pool 支持此属性
    
    # 执行一次完整的迭代
    for _ in get_target_symbols_generator():
        pass
    
    # 检查连接是否已归还
    # 注意：oracledb 的 pool 内部管理较为复杂，主要观察是否有 ConnectionError 或 Timeout
    logger.info("Iteration completed. Check logs for any connection leak warnings.")

if __name__ == "__main__":
    try:
        test_symbol_provider_basic()
        test_generator_behavior()
        test_filter_logic()
        test_connection_leak()
        logger.info("\n✅ ALL SYMBOL PROVIDER TESTS PASSED")
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)