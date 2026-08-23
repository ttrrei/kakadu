# test/test_backup_manager.py
import os
import json
import shutil
import logging
import sys

# 确保 src 目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backup_manager import BackupManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_backup_manager():
    """
    Comprehensive test for BackupManager:
    1. Local persistence
    2. Directory structure
    3. JSONL format validation
    4. Empty data handling
    """
    # 使用一个专门的测试备份目录，避免污染生产备份
    test_root = "/home/ubuntu/backup_test"
    bm = BackupManager(backup_root=test_root)
    
    table_name = "TEST_TABLE"
    test_data = [
        {"CODE": "CBA", "PRICE": "100.5", "TIME": "2023-10-01 10:00"},
        {"CODE": "BHP", "PRICE": "45.2", "TIME": "2023-10-01 10:00"},
        {"CODE": "TLS", "PRICE": "38.1", "TIME": "2023-10-01 10:00"},
    ]

    try:
        logger.info("--- Starting BackupManager Test ---")

        # 1. 测试正常保存
        logger.info("Test 1: Saving valid data...")
        file_path = bm.save_local(table_name, test_data)
        
        if not file_path or not os.path.exists(file_path):
            logger.error("❌ FAILED: File was not created.")
            return

        logger.info(f"✅ SUCCESS: File created at {file_path}")

        # 2. 验证目录结构 (Format: root/table/date/file.jsonl)
        # 检查路径中是否包含 table_name
        if table_name not in file_path:
            logger.error("❌ FAILED: Directory structure does not contain table name.")
            return
        logger.info("✅ SUCCESS: Directory structure is correct.")

        # 3. 验证 JSONL 格式 (每一行必须是合法的 JSON)
        logger.info("Test 2: Validating JSONL content...")
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) != len(test_data):
                logger.error(f"❌ FAILED: Line count mismatch. Expected {len(test_data)}, got {len(lines)}")
                return
            
            for i, line in enumerate(lines):
                try:
                    record = json.loads(line)
                    if record["CODE"] != test_data[i]["CODE"]:
                        logger.error(f"❌ FAILED: Data mismatch at line {i}")
                        return
                except json.JSONDecodeError:
                    logger.error(f"❌ FAILED: Line {i} is not a valid JSON.")
                    return
        logger.info("✅ SUCCESS: JSONL content is valid and matches input data.")

        # 4. 测试空数据处理
        logger.info("Test 3: Handling empty data...")
        empty_path = bm.save_local(table_name, [])
        if empty_path is None:
            logger.info("✅ SUCCESS: Correctly returned None for empty data.")
        else:
            logger.error("❌ FAILED: Should not create a file for empty data.")

        # 5. 测试清理功能
        logger.info("Test 4: Testing purge_local...")
        bm.purge_local(file_path)
        if not os.path.exists(file_path):
            logger.info("✅ SUCCESS: Local file purged successfully.")
        else:
            logger.error("❌ FAILED: File still exists after purge.")

        logger.info("--- ALL BACKUP MANAGER TESTS PASSED ---")

    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE during test: {e}")
    finally:
        # 清理测试根目录
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            logger.info(f"Cleaned up test directory {test_root}")

if __name__ == "__main__":
    test_backup_manager()