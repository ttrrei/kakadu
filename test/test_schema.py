# test/test_schema.py
import logging
import uuid
from src.db_operator import db

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_schema():
    """
    Comprehensive verification of the Equity Database Schema.
    Checks:
    1. Table existence (SYS_BATCH_LOG)
    2. Index existence (IDX_SYS_BATCH_LOG_BID)
    3. Read/Write permissions
    4. Check Constraints (LAYER validation)
    """
    logger.info("🚀 Starting Database Schema Verification...")
    
    conn = None
    try:
        # 从连接池获取连接
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # ----------------------------------------------------------------------
        # 1. 验证基础表和索引是否存在
        # ----------------------------------------------------------------------
        logger.info("Checking for SYS_BATCH_LOG table and its index...")
        
        # 检查表是否存在
        cursor.execute("""
            SELECT table_name 
            FROM all_tables 
            WHERE owner = 'EQUITY' AND table_name = 'SYS_BATCH_LOG'
        """)
        if not cursor.fetchone():
            logger.error("❌ FAILED: Table SYS_BATCH_LOG not found. Please run install_equity_schema.sql")
            return False
        
        # 检查索引是否存在 (验证你手动修复的结果)
        cursor.execute("""
            SELECT index_name 
            FROM all_indexes 
            WHERE owner = 'EQUITY' AND index_name = 'IDX_SYS_BATCH_LOG_BID'
        """)
        if not cursor.fetchone():
            logger.error("❌ FAILED: Index IDX_SYS_BATCH_LOG_BID not found. Please create it manually.")
            return False
            
        logger.info("✅ SUCCESS: Table and Index both exist.")

        # ----------------------------------------------------------------------
        # 2. 验证读写权限 (Insert & Select)
        # ----------------------------------------------------------------------
        test_batch_id = f"TEST_{uuid.uuid4().hex[:8]}"
        logger.info(f"Testing Write/Read access with Batch ID: {test_batch_id}...")
        
        try:
            # 插入一条测试数据
            cursor.execute("""
                INSERT INTO EQUITY.SYS_BATCH_LOG 
                (BATCH_ID, LAYER, PIPELINE_NAME, STEP_NAME, STATUS, SOURCE_SYSTEM) 
                VALUES (:1, :2, :3, :4, :5, :6)
            """, (test_batch_id, 'SYS', 'SCHEMA_TEST', 'VERIFY', 'SUCCESS', 'INTERNAL'))
            conn.commit()
            
            # 回读数据验证
            cursor.execute("SELECT STATUS FROM EQUITY.SYS_BATCH_LOG WHERE BATCH_ID = :1", (test_batch_id,))
            result = cursor.fetchone()
            if result and result[0] == 'SUCCESS':
                logger.info("✅ SUCCESS: Read/Write access verified.")
            else:
                logger.error("❌ FAILED: Data verification failed (inserted data not found or incorrect).")
                return False
        except Exception as e:
            logger.error(f"❌ FAILED: Write/Read access error: {e}")
            return False

        # ----------------------------------------------------------------------
        # 3. 验证约束 (Check Constraint - LAYER 字段)
        # ----------------------------------------------------------------------
        logger.info("Testing Layer Constraint (Invalid value should be blocked)...")
        try:
            # 尝试插入一个非法的 LAYER 值 'INVALID' (不在 SYS, ODS, REF, BDI, DMT 中)
            cursor.execute("""
                INSERT INTO EQUITY.SYS_BATCH_LOG 
                (BATCH_ID, LAYER, PIPELINE_NAME, STATUS) 
                VALUES (:1, 'INVALID', 'CONSTRAINT_TEST', 'FAILED')
            """, (f"FAIL_{uuid.uuid4().hex[:8]}",))
            conn.commit()
            # 如果执行到这里没报错，说明约束失效了
            logger.error("❌ FAILED: Constraint check bypassed! 'INVALID' layer was accepted.")
            return False
        except Exception as e:
            # 检查错误信息中是否包含约束相关的关键词
            err_msg = str(e).lower()
            if "sys_batch_log_layer_ck" in err_msg or "check constraint" in err_msg:
                logger.info("✅ SUCCESS: Constraint correctly blocked invalid layer.")
            else:
                logger.error(f"⚠️ Unexpected error during constraint test: {e}")
                return False

        # ----------------------------------------------------------------------
        # 4. 清理测试数据
        # ----------------------------------------------------------------------
        cursor.execute("DELETE FROM EQUITY.SYS_BATCH_LOG WHERE BATCH_ID = :1", (test_batch_id,))
        conn.commit()
        logger.info("Cleaning up test data... Done.")

    except Exception as e:
        logger.error(f"❌ Unexpected error during schema test: {e}")
        return False
    finally:
        if conn:
            # 确保释放连接回池
            cursor.close()
            db._pool.release(conn)

    logger.info("\n" + "="*50)
    logger.info("🎉 ALL SCHEMA TESTS PASSED!")
    logger.info("Infrastructure is ready for data ingestion.")
    logger.info("="*50)
    return True

if __name__ == "__main__":
    success = test_schema()
    if not success:
        exit(1)