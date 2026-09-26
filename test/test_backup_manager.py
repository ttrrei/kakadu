# test/test_backup_manager_v2.py
import os
import json
import shutil
import logging
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backup_manager import BackupManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_backup_manager_v2():
    # 使用跨平台路径
    test_root = os.path.join(os.path.expanduser("~"), "kakadu_backup_test")
    bm = BackupManager(base_backup_dir=test_root)
    
    table_name = "TEST_TABLE"
    batch_id = "test-batch-123"
    test_data = [
        {"CODE": "CBA.AX", "PRICE": "100.5"},
        {"CODE": "BHP.AX", "PRICE": "45.2"},
    ]

    try:
        logger.info("--- Starting New BackupManager V2 Test ---")

        # 1. 测试上下文管理器链路
        logger.info("Test 1: Testing BatchBackupContext lifecycle...")
        with bm.start_batch(table_name, batch_id) as ctx:
            written = ctx.append_records(test_data)
            logger.info(f"Written {written} records to JSONL")
            
            # 验证文件是否立即生成
            if not os.path.exists(ctx.records_path):
                logger.error("❌ FAILED: records.jsonl not created")
                return

            # 执行 finalize 生成 manifest
            manifest = ctx.finalize()
            logger.info(f"Manifest generated: {manifest['checksum_sha256'][:10]}...")

        # 2. 验证 Manifest 内容
        logger.info("Test 2: Validating manifest.json...")
        with open(ctx.manifest_path, 'r') as f:
            m_data = json.load(f)
            if m_data['record_count'] != 2:
                logger.error(f"❌ FAILED: Record count mismatch. Expected 2, got {m_data['record_count']}")
                return

        # 3. 验证目录结构 (table/date/batch_id)
        logger.info("Test 3: Verifying directory structure...")
        expected_dir = bm.get_batch_dir(table_name, batch_id)
        if not os.path.exists(expected_dir):
            logger.error("❌ FAILED: Directory structure is incorrect")
            return

        # 4. 测试清理功能
        logger.info("Test 4: Testing clear_batch_dir...")
        bm.clear_batch_dir(table_name, batch_id)
        if os.path.exists(expected_dir):
            logger.error("❌ FAILED: Batch directory not purged")
            return

        logger.info("✅ ALL BACKUP MANAGER V2 TESTS PASSED")

    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE: {e}")
    finally:
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            logger.info(f"Cleaned up {test_root}")

if __name__ == "__main__":
    test_backup_manager_v2()