# tests/smoke_test_db_op.py
import logging
import sys
import os

# 将项目根目录添加到路径，确保能导入 src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_operator import db
import logging

# 配置简单的日志输出
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmokeTest")

def test_call_procedure():
    logger.info("🚀 Starting Smoke Test for DbOperator.call_procedure...")
    
    try:
        # 方案 A: 如果你已经有一个简单的测试 SP，请替换为 'EQUITY.SP_YOUR_TEST'
        # 方案 B: 使用 Oracle 的内置存储过程（例如 DBMS_OUTPUT 或简单的系统调用）
        # 这里我们尝试调用一个最简单的系统过程，或者你可以直接在 DB 里建一个简单的 SP
        
        # 为了 100% 成功，建议你在 Oracle 中执行一次这个简单的 DDL:
        # CREATE OR REPLACE PROCEDURE EQUITY.SP_SMOKE_TEST AS BEGIN NULL; END;
        
        proc_name = "EQUITY.SP_SMOKE_TEST"
        logger.info(f"Attempting to call {proc_name}...")
        
        db.call_procedure(proc_name)
        
        logger.info("✅ SUCCESS: DbOperator successfully connected, executed, and committed!")
        
    except Exception as e:
        logger.error(f"❌ FAILURE: Smoke test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_call_procedure()