import logging
import sys
from src.db_operator import db

# 配置日志，以便看到 DbOperator 内部的初始化信息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_db_connection():
    conn = None
    try:
        logger.info("Attempting to acquire connection from pool...")
        # 1. 测试连接获取
        conn = db.get_connection()
        logger.info("Successfully acquired connection!")

        # 2. 测试执行简单 SQL
        cursor = conn.cursor()
        cursor.execute("SELECT 'Connection Successful' FROM DUAL")
        result = cursor.fetchone()
        logger.info(f"Database response: {result[0]}")
        cursor.close()

        print("\n✅ Database connection test PASSED!")
        
    except Exception as e:
        logger.error(f"❌ Database connection test FAILED: {e}")
        sys.exit(1)
    finally:
        if conn:
            # 将连接还回池中
            db._pool.release(conn)
            logger.info("Connection released back to pool.")
        
        # 关闭连接池
        db.close()
        logger.info("Connection pool shut down.")

if __name__ == "__main__":
    test_db_connection()