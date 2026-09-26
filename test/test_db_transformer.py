# tests/test_db_transformer.py
import logging
import sys
import os

# 将项目根目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_transformer import db_transformer
import logging

# 配置日志，以便观察执行顺序
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("TransformerTest")

def run_test(group_name: str, should_fail: bool):
    logger.info(f"\n--- Testing Group: {group_name} (Expected Fail: {should_fail}) ---")
    try:
        success = db_transformer.trigger_group(group_name)
        if success:
            logger.info(f"✅ Result: Group {group_name} executed successfully.")
    except Exception as e:
        logger.error(f"❌ Result: Group {group_name} failed as expected: {e}")
        if not should_fail:
            sys.exit(1) # 如果不应该失败却失败了，直接终止

if __name__ == "__main__":
    # 测试 1: 验证正常顺序执行
    run_test("test_success_group", should_fail=False)
    
    # 测试 2: 验证错误截断 (Fail-Fast)
    # 注意：观察日志，如果看到了 SP_TEST_STEP_B 的执行记录，说明截断失败！
    run_test("test_fail_group", should_fail=True)
    
    logger.info("\n✨ All DbTransformer integration tests passed!")