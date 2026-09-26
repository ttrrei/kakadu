# src/main.py
import uuid
import logging
import os
from typing import List

from .config import config
from .db_operator import db as db_operator
from .alert_manager import AlertManager
from .scraper_factory import ScraperFactory

# 假设这些是你的辅助函数
from .utils import _sync_cloud_backup, _trigger_etl_group 

logger = logging.getLogger(__name__)
alert_manager = AlertManager()

def handle_scrape(task_name: str) -> int:
    """
    Orchestrates the scrape process with a strict Fail-Fast and Anti-Silent-Failure policy.
    Returns 0 on success, 1 on failure.
    """
    # 1. Generate a unique Batch ID for this run
    batch_id = uuid.uuid4().hex
    logger.info(f"=== SCRAPE START | Task: {task_name} | Batch: {batch_id} ===")

    try:
        # ---------------------------------------------------------------------
        # STEP 1: Audit Entry (RUNNING)
        # 🔴 CRITICAL: Must be inside the try block. If DB is down, Fail-Fast immediately.
        # ---------------------------------------------------------------------
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=task_name, 
            source_system=task_name
        )

        # ---------------------------------------------------------------------
        # STEP 2: Execution
        # ---------------------------------------------------------------------
        scraper_cls = ScraperFactory.get_scraper(task_name)
        scraper = scraper_cls(db_op=db_operator)
        
        if not scraper.target_table:
            raise KeyError(f"Scraper '{task_name}' is missing 'target_table' in config.yaml")

        logger.info(f"Executing Scraper: {scraper_cls.__name__} -> Target Table: {scraper.target_table}")
        
        # This call now handles:
        # - Bounded memory usage (O(1))
        # - Circuit Breaker (throws RuntimeError if success_count == 0)
        scraper.run(job_name=task_name, batch_id=batch_id)

        # ---------------------------------------------------------------------
        # STEP 3: Pragmatic Tier-1 Validation (Anti-Empty-Run)
        # Instead of complex row-counting, we check if any backup files were created.
        # ---------------------------------------------------------------------
        _check_tier1_backup_existence(scraper)

        # ---------------------------------------------------------------------
        # STEP 4: Cloud Sync & Post-ETL
        # These are treated as "Best Effort". Failure here logs Warning but doesn't crash the pipeline.
        # ---------------------------------------------------------------------
        try:
            _sync_cloud_backup(scraper.target_table)
        except Exception as e:
            logger.warning(f"[TIER-1] Cloud sync failed for {scraper.target_table}: {e}")

        post_group = f"post_{task_name}"
        etl_groups = config.get("etl_groups", {})
        if post_group in etl_groups:
            try:
                _trigger_etl_group(post_group)
            except Exception as e:
                logger.error(f"Post-ETL group {post_group} failed: {e}")
                # We don't necessarily return 1 here unless the business requires ETL success for a "Success" mark.

        # ---------------------------------------------------------------------
        # STEP 5: Audit Success
        # ---------------------------------------------------------------------
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== SCRAPE SUCCESS | Task: {task_name} | Batch: {batch_id} ===")
        return 0

    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== SCRAPE FAILED | Task: {task_name} | Batch: {batch_id} | Error: {err_msg} ===")
        
        # 🔴 CRITICAL: Attempt to record FAILED status in DB. 
        # If this also fails (e.g., DB is totally dead), log as CRITICAL.
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except Exception as db_err:
            logger.critical(f"FATAL: Could not record FAILED status to SYS_BATCH_LOG: {db_err}")

        # 🔴 CRITICAL: Trigger Tier 2 Pushover Alert
        alert_manager.send_tier2_alert(
            f"Kakadu Scrape Failure\nTask: {task_name}\nBatch: {batch_id}\nError: {err_msg}"
        )
        return 1

def _check_tier1_backup_existence(scraper):
    """
    Pragmatic Tier-1 check: Ensure the backup directory for this task is not empty.
    This prevents 'silent success' where the scraper runs but produces no files.
    """
    backup_path = config.get('system', {}).get('backup_dir', '/home/ubuntu/backup')
    task_dir = os.path.join(backup_path, scraper.target_table)
    
    if not os.path.exists(task_dir) or not os.listdir(task_dir):
        # We log this as a Tier-1 Warning. 
        # According to BRD, this shouldn't necessarily crash the pipeline, but must be visible.
        logger.warning(f"[TIER-1] No backup files found in {task_dir}. Data might be missing.")
        # If you want to be stricter, you could raise a RuntimeError here to trigger a FAILED status.

# =========================================================================
# Entry point for the shell/crontab
# =========================================================================
if __name__ == "__main__":
    import sys
    # Example: python main.py price_ohlcv_pre
    if len(sys.argv) < 2:
        print("Usage: python main.py <task_name>")
        sys.exit(1)
    
    task = sys.argv[1]
    exit_code = handle_scrape(task)
    sys.exit(exit_code)