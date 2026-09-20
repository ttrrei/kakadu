"""
Kakadu Main Orchestrator (Production Version)
Implements ADR-018, ADR-019, ADR-020, ADR-021 and MAIN_ORCHESTRATOR_REVIEW_GUIDELINES.md.

Architecture:
- Service-oriented orchestration (HealthCheck -> Factory -> Scraper -> Sync -> Transformer)
- UUID v4 Batch ID Lineage tracking (SYS_BATCH_LOG)
- Config-driven ETL triggers via etl_groups
- Batch-Compress-Upload Cloud Sync (UploadManager)
- Tier-2 Pushover Alerting & Fail-Fast Defense
- Strict Exit Code Contract for Master Shell (run_task.sh)
"""

import sys
import uuid
import argparse
import logging
from typing import Optional

# Core Services
from src.config import config
from src.health_checker import StartupHealthChecker
from src.factory import ScraperFactory
from src.db_operator import db as db_operator
from src.db_transformer import db_transformer
from src.alert_manager import alert_manager
from src.backup_manager import BackupManager
from src.upload_manager import UploadManager

# -----------------------------------------------------------------------------
# Logging Configuration (ADR-006: Centralized via config singleton)
# -----------------------------------------------------------------------------
log_level_str = getattr(config.env, "log_level", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

handlers = [logging.StreamHandler(sys.stdout)]
log_file = config.get("system", {}).get("log_file")
if log_file:
    handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=handlers,
    force=True
)
logger = logging.getLogger("kakadu.main")

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _run_health_check() -> None:
    """ADR-018.2: Fail-fast startup probe."""
    logger.info("Initiating startup health probe...")
    checker = StartupHealthChecker(config)
    checker.run()
    logger.info("Health probe passed.")

def _get_oci_par_url() -> Optional[str]:
    """
    Safely resolve OCI PAR URL from config.yaml or .env.
    PAR URLs are pre-authenticated tokens and cannot be constructed from bucket names.
    """
    # 1. Check YAML system section (Non-sensitive override)
    par_url = config.get("system", {}).get("oci_par_url")
    if par_url and par_url.startswith("http"):
        return par_url
    
    # 2. Check .env via OCIConfig (Sensitive/Default)
    # Using config_path as the storage for the PAR URL per .env.example convention
    env_par = getattr(config.env.oci, "config_path", "")
    if env_par and env_par.startswith("http"):
        return env_par
        
    return None

def _sync_cloud_backup(target_table: str) -> bool:
    """
    Executes Batch-Compress-Upload via UploadManager.
    Failure is NON-FATAL (Tier 1 Warning), pipeline continues.
    """
    par_url = _get_oci_par_url()
    if not par_url:
        logger.info(f"Cloud sync skipped for {target_table}: OCI PAR URL not configured.")
        return True

    try:
        backup_dir = config.get("system", {}).get("backup_dir", "/home/ubuntu/backup")
        backup_mgr = BackupManager(base_backup_dir=backup_dir)
        upload_mgr = UploadManager(backup_manager=backup_mgr, oci_par_url=par_url)
        
        logger.info(f"Triggering cloud sync for table: {target_table}...")
        upload_mgr.sync_to_cloud(table_name=target_table)
        logger.info(f"Cloud sync successful for {target_table}.")
        return True
    except Exception as e:
        # Tier 1 Logic: Log warning, retain local backup, do NOT crash pipeline
        logger.warning(f"Cloud sync FAILED for {target_table} (Backup retained locally): {e}")
        return False

def _trigger_etl_group(group_name: str) -> None:
    """
    Executes a named ETL group from config.yaml -> etl_groups.
    Raises Exception on failure (halts pipeline, triggers Tier 2 Alert).
    """
    logger.info(f"Triggering ETL Group: [{group_name}]")
    db_transformer.trigger_group(group_name)
    logger.info(f"ETL Group [{group_name}] completed successfully.")

# -----------------------------------------------------------------------------
# Command Handlers (Returning Exit Codes per Guidelines)
# -----------------------------------------------------------------------------

def handle_scrape(task_name: str) -> int:
    """
    Scrape Pipeline:
    1. Generate BATCH_ID
    2. Audit: SYS_BATCH_LOG INSERT (RUNNING)
    3. Instantiate Scraper & Run
    4. Cloud Sync (Best effort - Tier 1)
    5. Post-Action ETL (Config driven: post_{task_name})
    6. Audit: SYS_BATCH_LOG UPDATE (SUCCESS/FAILED)
    """
    batch_id = uuid.uuid4().hex
    logger.info(f"=== SCRAPE START | Task: {task_name} | Batch: {batch_id} ===")

    # 1. Audit Entry
    try:
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=task_name, 
            source_system=task_name 
        )
    except Exception as e:
        logger.error(f"Failed to create batch audit record (Non-fatal): {e}")

    try:
        # 2. Factory & Execution
        scraper_cls = ScraperFactory.get_scraper(task_name)
        scraper = scraper_cls(db_op=db_operator)
        target_table = scraper.target_table

        if not target_table:
            raise KeyError(f"Scraper '{task_name}' missing 'target_table' in config.yaml")

        logger.info(f"Executing Scraper: {scraper_cls.__name__} -> Table: {target_table}")
        scraper.run(job_name=task_name, batch_id=batch_id)

        # 3. Cloud Sync (Post-Ingestion)
        _sync_cloud_backup(target_table)

        # 4. Post-Action ETL (ADR-020: Mapping Driven)
        # Must happen BEFORE marking SUCCESS
        post_group = f"post_{task_name}"
        etl_groups = config.get("etl_groups", {})
        if post_group in etl_groups:
            _trigger_etl_group(post_group)
        else:
            logger.info(f"No post-action ETL group defined for '{post_group}'. Skipping.")

        # 5. Audit Success
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== SCRAPE SUCCESS | Task: {task_name} | Batch: {batch_id} ===")
        return 0

    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== SCRAPE FAILED | Task: {task_name} | Batch: {batch_id} | Error: {err_msg} ===")
        
        # Audit Failure
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except Exception as db_err:
            logger.critical(f"Failed to update batch status to FAILED: {db_err}")

        # Tier 2 Alert (Systemic Failure)
        alert_manager.send_tier2_alert(
            f"Kakadu Scrape Failure\nTask: {task_name}\nBatch: {batch_id}\nError: {err_msg}"
        )
        return 1

def handle_transform(group_name: str, source_label: str) -> int:
    """Transform/Maintain Pipeline: Audit -> Trigger ETL -> Audit Update."""
    batch_id = uuid.uuid4().hex
    logger.info(f"=== {source_label.upper()} START | Group: {group_name} | Batch: {batch_id} ===")

    try:
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=f"{source_label}:{group_name}", 
            source_system=f"CLI_{source_label.upper()}"
        )
        _trigger_etl_group(group_name)
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== {source_label.upper()} SUCCESS | Group: {group_name} ===")
        return 0
    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== {source_label.upper()} FAILED | Group: {group_name} | Error: {err_msg} ===")
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except: pass
        alert_manager.send_tier2_alert(f"Kakadu {source_label.capitalize()} Failure\nGroup: {group_name}\nBatch: {batch_id}\nError: {err_msg}")
        return 1

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kakadu Data Acquisition & Quantitative Intelligence Engine",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--skip-health-check", 
        action="store_true", 
        help="Bypass startup health probe (Wallet, DB, Env). USE WITH CAUTION."
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Execution Mode")

    # 1. Scrape Command
    p_scrape = subparsers.add_parser("scrape", help="Execute a data scraper task")
    p_scrape.add_argument("--task", "-t", required=True, help="Task name (e.g., price_ohlcv_pre, annc, afr)")

    # 2. Transform Command
    p_transform = subparsers.add_parser("transform", help="Execute PL/SQL transformation group")
    p_transform.add_argument("--group", "-g", required=True, help="ETL Group name from config.yaml")

    # 3. Maintain Command
    p_maintain = subparsers.add_parser("maintain", help="Execute maintenance routines")
    p_maintain.add_argument("--group", "-g", required=True, help="Maintenance Group name from config.yaml")

    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 1. Startup Health Check (Global, unless skipped)
    if not args.skip_health_check:
        try:
            _run_health_check()
        except Exception as e:
            logger.critical(f"Startup Health Check Failed: {e}")
            alert_manager.send_tier2_alert(f"Kakadu Startup Failure: {e}")
            return 1
    else:
        logger.warning("Startup health check BYPASSED via CLI flag.")

    # 2. Dispatch
    exit_code = 1
    try:
        if args.command == "scrape":
            exit_code = handle_scrape(args.task)
        elif args.command == "transform":
            exit_code = handle_transform(args.group, "transform")
        elif args.command == "maintain":
            exit_code = handle_transform(args.group, "maintain")
        else:
            parser.print_help()
            exit_code = 2
    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user (SIGINT).")
        exit_code = 130
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 1
    except Exception as e:
        logger.critical(f"Unhandled orchestration error: {e}", exc_info=True)
        alert_manager.send_tier2_alert(f"Kakadu Orchestrator Crash: {e}")
        exit_code = 1

    return exit_code

if __name__ == "__main__":
    # Global Connection Pool Stewardship: Ensure pool is closed on process exit
    try:
        sys.exit(main())
    finally:
        try:
            db_operator.close()
            logger.debug("Oracle connection pool closed successfully.")
        except Exception as e:
            logger.debug(f"DbOperator cleanup ignored: {e}")