import logging
import uuid
import sys
import os

# 确保 src 目录在 python 路径中，以便导入 db_operator
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.db_operator import db
import oracledb

# 配置简单的日志输出
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BatchLogTest")

def test_batch_lifecycle():
    """
    End-to-End Integration Test for Batch Logging Lifecycle (Minimalist Version).
    Flow: Create Record -> Insert Data -> Update Status -> Verify in DB.
    """
    # 1. Setup Test Data
    test_batch_id = f"TEST_{uuid.uuid4().hex[:8]}"
    test_task_name = "TEST_SCRAPER_JOB"
    test_table = "EQUITY.ODS_PRICE_TICK"  # 使用一个已存在的 ODS 表
    test_records = [
        {"CODE": "TEST.AX", "CLOSE": "10.5", "TICK_TIME": "2023-10-01 10:00:00"},
        {"CODE": "TEST.AX", "CLOSE": "10.6", "TICK_TIME": "2023-10-01 10:01:00"},
    ]

    try:
        # --- STEP 1: Create Batch Record ---
        logger.info(f"Step 1: Creating batch record {test_batch_id}...")
        db.create_batch_record(
            batch_id=test_batch_id, 
            task_name=test_task_name, 
            source_system="TEST_SYSTEM"
        )

        # --- STEP 2: Insert some ODS data ---
        logger.info(f"Step 2: Inserting {len(test_records)} records into {test_table}...")
        db.insert_batch(
            table_name=test_table, 
            records=test_records, 
            batch_id=test_batch_id
        )

        # --- STEP 3: Update Batch Status to SUCCESS ---
        logger.info(f"Step 3: Updating batch status to SUCCESS...")
        # 注意：这里移除了 row_count 参数，以匹配最新的 db_operator.py
        db.update_batch_status(
            batch_id=test_batch_id, 
            status="SUCCESS"
        )

        # --- STEP 4: Database Verification ---
        logger.info("Step 4: Verifying records in SYS_BATCH_LOG...")
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 查询 SYS_BATCH_LOG 验证状态
        cursor.execute(
            "SELECT STATUS, PIPELINE_NAME FROM EQUITY.SYS_BATCH_LOG WHERE BATCH_ID = :bid", 
            bid=test_batch_id
        )
        log_row = cursor.fetchone()
        
        if log_row:
            status, pipeline = log_row
            logger.info(f"DB Verification -> Status: {status}, Pipeline: {pipeline}")
            
            # 断言验证
            assert status == "SUCCESS", f"Expected SUCCESS, got {status}"
            assert pipeline == test_task_name, f"Expected {test_task_name}, got {pipeline}"
            logger.info("✅ Integration Test Passed: SYS_BATCH_LOG status is correct.")
        else:
            raise Exception("❌ Verification Failed: No record found in SYS_BATCH_LOG!")

        # 验证 ODS 数据是否携带了正确的 BATCH_ID
        cursor.execute(
            f"SELECT COUNT(*) FROM {test_table} WHERE BATCH_ID = :bid", 
            bid=test_batch_id
        )
        ods_count = cursor.fetchone()[0]
        assert ods_count == len(test_records), f"Expected {len(test_records)} ODS rows, got {ods_count}"
        logger.info(f"✅ Integration Test Passed: {len(test_records)} rows found in {test_table} with BATCH_ID {test_batch_id}.")

        cursor.close()
        db._pool.release(conn)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_batch_lifecycle()