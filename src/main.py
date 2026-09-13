import argparse
import sys
import logging
import subprocess
import traceback
import os
from typing import Optional

from src.config import config
from src.health_checker import StartupHealthChecker  # 修正路径
from src.alert_manager import alert_manager           # 修正路径
from src.upload_manager import UploadManager           # 修正路径
from src.factory import ScraperFactory                 # 修正路径
from src.db_operator import db as db_operator         # 修正路径
from src.backup_manager import BackupManager           # 修正路径

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.get('system', {}).get('log_file', 'kakadu.log'), mode='a')
    ]
)
logger = logging.getLogger("KakaduOrchestrator")

def count_local_backups(table_name: str) -> int:
    """
    实现 Tier 1 检查所需的本地文件计数逻辑。
    """
    try:
        bm = BackupManager()
        task_dir = bm.get_task_dir(table_name)
        if not os.path.exists(task_dir):
            return 0
        return len([f for f in os.listdir(task_dir) if f.endswith('.json')])
    except Exception as e:
        logger.error(f"Failed to count local backups for {table_name}: {e}")
        return -1

def get_db_record_count(table_name: str, batch_id: str) -> int:
    """
    从数据库获取特定 BATCH_ID 的记录总数。
    """
    try:
        conn = db_operator.get_connection()
        cursor = conn.cursor()
        sql = f'SELECT COUNT(*) FROM "{table_name}" WHERE "BATCH_ID" = :bid'
        cursor.execute(sql, bid=batch_id)
        count = cursor.fetchone()[0]
        cursor.close()
        return count
    except Exception as e:
        logger.error(f"Failed to fetch DB count for {table_name}: {e}")
        return -1
    finally:
        if 'conn' in locals():
            db_operator._pool.release(conn)

def main():
    # 1. CLI Dispatcher
    parser = argparse.ArgumentParser(description="Kakadu Data Ingestion Orchestrator")
    parser.add_argument("--task", required=True, help="The scraping task to execute")
    parser.add_argument("--session-type", default="standard", help="Session type")
    args = parser.parse_args()

    task_name = args.task
    batch_id = f"{task_name}_{args.session_type}"
    scraper_instance = None
    
    try:
        # A. Fail-Fast Health Check
        logger.info(f"Performing startup health probe for task: {task_name}...")
        health_checker = StartupHealthChecker(config)
        health_checker.run()
        
        # B. Component Initialization
        ScraperClass = ScraperFactory.get_scraper(task_name)
        scraper_instance = ScraperClass(db_op=db_operator)
        
        # C. Execution Phase
        logger.info(f"Starting execution of task: {task_name}")
        scraper_instance.run(job_name=batch_id)
        
        # D. Post-Execution Validation (Tier 1 Alerting)
        local_count = count_local_backups(scraper_instance.target_table)
        db_count = get_db_record_count(scraper_instance.target_table, batch_id)
        
        if local_count != -1 and db_count != -1:
            backup_path = BackupManager().get_task_dir(scraper_instance.target_table)
            mismatch = alert_manager.check_tier1_mismatch(
                local_count=local_count, 
                db_count=db_count, 
                task_name=task_name, 
                backup_path=backup_path
            )
            if mismatch:
                logger.warning(f"Tier 1 mismatch detected for {task_name}. Backup retained.")
        
        # E. Cloud Synchronization & Local Purge
        oci_par_url = os.getenv("OCI_PAR_URL") 
        if not oci_par_url:
            # 在开发环境下，如果没设环境变量，我们记录警告而非直接崩溃，方便测试
            logger.warning("OCI_PAR_URL not set. Skipping cloud sync.")
        else:
            upload_manager = UploadManager(
                backup_manager=BackupManager(), 
                oci_par_url=oci_par_url
            )
            logger.info(f"Synchronizing backups for {task_name} to cloud...")
            upload_manager.sync_to_cloud(scraper_instance.target_table)
        
        logger.info(f"Task {task_name} completed successfully.")

    except (RuntimeError, ValueError) as e:
        logger.critical(f"Startup/Configuration failure: {e}")
        sys.exit(1)
    except Exception as e:
        error_msg = f"Systemic crash during task {task_name}: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        alert_manager.send_tier2_alert(message=error_msg, priority=1)
        sys.exit(1)
        
    finally:
        # G. Resource Sanitization (无条件清理)
        logger.info("Executing mandatory cleanup_vm.sh to ensure zero memory leakage...")
        try:
            # 注意：在 Windows 开发环境下，这个脚本可能不存在或无法运行，这里捕获异常
            subprocess.run(["/home/ubuntu/scripts/cleanup_vm.sh"], check=True)
        except Exception as e:
            logger.warning(f"Mandatory cleanup script not executed (expected in Windows dev env): {e}")

if __name__ == "__main__":
    main()