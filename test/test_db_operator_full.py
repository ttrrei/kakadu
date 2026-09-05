import sys
from pathlib import Path
import logging
import uuid

# -------------------------------------------------------------------------
# 路径处理：确保 src 文件夹在 Python 的搜索路径中
# -------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.db_operator import DbOperator

# 配置日志，以便观察 DbOperator 的 fallback 机制
logging.basicConfig(
    level=logging.INFO, 
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def test_db_operator_full():
    print("\n====================================================")
    print("🚀 STARTING DB_OPERATOR FULL ROBUSTNESS TEST (ALIGNED)")
    print("====================================================")
    
    db_op = DbOperator()
    # 使用 SQL 定义中的实际表名
    test_table = "ODS_PRICE_OHLCV_PRE" 
    
    try:
        # -----------------------------------------------------------------
        # 场景 1: 正常批量写入 (Happy Path)
        # 验证：列名必须与 SQL 一致 (CODE, CLOSE_PRICE, VOLUME)
        # -----------------------------------------------------------------
        print("\n--- Scenario 1: Normal Batch Insert ---")
        normal_records = [
            {"CODE": "AAPL.AX", "CLOSE_PRICE": "150.00", "VOLUME": "1000"},
            {"CODE": "MSFT.AX", "CLOSE_PRICE": "300.00", "VOLUME": "2000"},
        ]
        batch_id_1 = str(uuid.uuid4())
        db_op.insert_batch(test_table, normal_records, batch_id=batch_id_1)
        print("✅ Normal batch insert executed.")

        # -----------------------------------------------------------------
        # 场景 2: 脏数据容忍度测试 (Robustness/Fallback Path)
        # 验证：当某一行数据导致 ORA 错误时，是否能自动降级为单条写入并跳过坏行
        # -----------------------------------------------------------------
        print("\n--- Scenario 2: Dirty Data Fallback Test ---")
        dirty_records = [
            {"CODE": "GOOD1.AX", "CLOSE_PRICE": "10.0", "VOLUME": "100"},
            # 故意制造错误：CODE 长度远超 VARCHAR2(4000) 或 注入非法字符
            {"CODE": "BAD_DATA" * 1000, "CLOSE_PRICE": "ERROR", "VOLUME": "NaN"}, 
            {"CODE": "GOOD2.AX", "CLOSE_PRICE": "20.0", "VOLUME": "200"},
        ]
        batch_id_2 = str(uuid.uuid4())
        
        print("Attempting to insert dirty records... (Expect some WARNINGs in logs)")
        db_op.insert_batch(test_table, dirty_records, batch_id=batch_id_2)
        print("✅ Dirty batch insert executed. Check logs for 'Retrying individually'.")

        # -----------------------------------------------------------------
        # 场景 3: 审计列验证 (Audit Column Verification)
        # 验证：BATCH_ID 和 LOAD_TIME 是否由 DbOperator 自动注入
        # -----------------------------------------------------------------
        print("\n--- Scenario 3: Audit Column Verification ---")
        conn = None
        try:
            conn = db_op.get_connection()
            cursor = conn.cursor()
            
            # 查询场景 2 中应该成功入库的记录
            cursor.execute(
                f"SELECT BATCH_ID, LOAD_TIME FROM {test_table} WHERE CODE = :c AND BATCH_ID = :bid", 
                c='GOOD1.AX', bid=batch_id_2
            )
            row = cursor.fetchone()
            
            if row:
                batch_id, load_time = row
                print(f"✅ Audit BATCH_ID found: {batch_id}")
                print(f"✅ Audit LOAD_TIME found: {load_time}")
            else:
                print("❌ Failed to find the record. Audit columns might not be injected correctly.")
            
            cursor.close()
        finally:
            if conn:
                # 必须先释放连接，否则 db_op.close() 会报 DPY-1005
                db_op._pool.release(conn)
                logger.info("Connection released back to pool.")

    except Exception as e:
        print(f"💥 CRITICAL ERROR during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭连接池
        db_op.close()
        logger.info("Connection pool shut down.")

    print("\n====================================================")
    print("✅ DB_OPERATOR TEST COMPLETE")
    print("====================================================")

if __name__ == "__main__":
    test_db_operator_full()