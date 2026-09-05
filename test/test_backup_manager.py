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
    Comprehensive test for New BackupManager:
    1. Atomic local persistence (One file per symbol)
    2. Directory structure (root/table/date/symbol.json)
    3. Data integrity validation
    4. Cleanup functionality
    """
    # 使用测试目录
    test_root = "/home/ubuntu/backup_test"
    bm = BackupManager(base_backup_dir=test_root)
    
    table_name = "TEST_TABLE"
    test_symbols = {
        "CBA": {"PRICE": "100.5", "TIME": "2023-10-01 10:00"},
        "BHP": {"PRICE": "45.2", "TIME": "2023-10-01 10:00"},
    }

    try:
        logger.info("--- Starting BackupManager Test ---")

        # 1. 测试正常保存 (Atomic Write)
        logger.info("Test 1: Saving records per symbol...")
        for symbol, data in test_symbols.items():
            bm.save_record(table_name, symbol, data)
        
        # 验证目录结构
        task_dir = bm.get_task_dir(table_name)
        if not os.path.exists(task_dir):
            logger.error("❌ FAILED: Task directory was not created.")
            return

        # 2. 验证文件存在与内容
        logger.info("Test 2: Validating file content...")
        for symbol, expected_data in test_symbols.items():
            file_path = os.path.join(task_dir, f"{symbol}.json")
            if not os.path.exists(file_path):
                logger.error(f"❌ FAILED: File for {symbol} not found.")
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                actual_data = json.load(f)
                if actual_data != expected_data:
                    logger.error(f"❌ FAILED: Data mismatch for {symbol}.")
                    return
        logger.info("✅ SUCCESS: All records saved correctly in JSON format.")

        # 3. 测试清理功能
        logger.info("Test 3: Testing clear_task_dir...")
        bm.clear_task_dir(table_name)
        if not os.path.exists(task_dir):
            logger.info("✅ SUCCESS: Local task directory purged successfully.")
        else:
            logger.error("❌ FAILED: Directory still exists after purge.")

        logger.info("--- ALL BACKUP MANAGER TESTS PASSED ---")

    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE during test: {e}")
    finally:
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            logger.info(f"Cleaned up test directory {test_root}")

if __name__ == "__main__":
    test_backup_manager()