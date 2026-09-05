# test/test_upload_manager.py
import os
import shutil
import logging
import sys
from unittest.mock import patch, MagicMock

# 确保 src 目录在路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backup_manager import BackupManager
from src.upload_manager import UploadManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_upload_manager():
    """
    Comprehensive test for UploadManager:
    1. ZIP archive creation
    2. OCI PAR URL construction
    3. Sync lifecycle (Compress -> Upload -> Purge)
    """
    test_root = "/home/ubuntu/backup_test_upload"
    table_name = "TEST_TABLE"
    par_url = "https://objectstorage.ap-sydney-1.oraclecloud.com/p/mock_par/n/namespace/b/bucket/o/"
    
    bm = BackupManager(base_backup_dir=test_root)
    um = UploadManager(backup_manager=bm, oci_par_url=par_url)

    try:
        logger.info("--- Starting UploadManager Test ---")

        # 准备测试数据：创建几个本地文件
        task_dir = bm.get_task_dir(table_name)
        with open(os.path.join(task_dir, "S1.json"), "w") as f: f.write('{"val": 1}')
        with open(os.path.join(task_dir, "S2.json"), "w") as f: f.write('{"val": 2}')
        logger.info(f"Prepared test files in {task_dir}")

        # 使用 patch 模拟 requests.put，避免真实网络请求
        with patch('requests.put') as mock_put:
            # 模拟 HTTP 200 OK 响应
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_put.return_value = mock_response

            logger.info("Test 1: Executing sync_to_cloud...")
            um.sync_to_cloud(table_name)

            # 1. 验证是否调用了 requests.put
            if not mock_put.called:
                logger.error("❌ FAILED: requests.put was never called.")
                return
            
            # 2. 验证 URL 构造 (ADR-013: {TABLE}/{DATE}/{FILE})
            called_url = mock_put.call_args[0][0]
            logger.info(f"Constructed URL: {called_url}")
            if table_name not in called_url or ".zip" not in called_url:
                logger.error(f"❌ FAILED: URL construction is incorrect: {called_url}")
                return
            logger.info("✅ SUCCESS: OCI PAR URL constructed correctly.")

            # 3. 验证清理逻辑
            if os.path.exists(task_dir):
                logger.error("❌ FAILED: Local directory was not purged after successful upload.")
                return
            logger.info("✅ SUCCESS: Local directory purged after upload.")

        logger.info("--- ALL UPLOAD MANAGER TESTS PASSED ---")

    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE during test: {e}")
    finally:
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            logger.info(f"Cleaned up test directory {test_root}")

if __name__ == "__main__":
    test_upload_manager()