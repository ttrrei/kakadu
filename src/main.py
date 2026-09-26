# src/main.py
"""
Kakadu Main Orchestrator (Production Hardened & P0/P1 Aligned)
==============================================================
Implements: ADR-018 (Service Orchestration), ADR-019 (Master Shell Contract),
            ADR-020 (Config-Driven ETL), ADR-021 (BATCH_ID Decoupling),
            ADR-005 (Audit Lineage), ADR-006 (Dual-Config), ADR-010 (Task=Session).

Architecture Invariants (Red Lines):
- NO sys.exit() inside handlers -> return int exit codes only.
- DB Connection Pool lifecycle managed ONLY in main() finally block.
- Audit Status: RUNNING -> (Scrape -> CloudSync -> PostETL) -> SUCCESS/FAILED.
- Fail-Fast Audit: create_batch_record() failure immediately halts task and triggers Tier 2 alert.
- Session Type encoded in Task Name (e.g., price_ohlcv_pre), NO --session-type flag.
- BATCH_ID generated in Python, logged to SYS_BATCH_LOG, NEVER passed to PL/SQL.
- Cloud Sync failure is Tier-1 Warning (Local backup retained, pipeline continues).
"""

import sys
import os
import uuid
import argparse
import json
import logging
from datetime import datetime
from typing import Optional

# --- Core Services (Singleton Instances) ---
from src.config import config
from src.health_checker import StartupHealthChecker
from src.factory import ScraperFactory
from src.db_operator import db as db_operator
from src.db_transformer import db_transformer
from src.alert_manager import alert_manager
from src.backup_manager import BackupManager
from src.upload_manager import UploadManager
from src.base_scraper import RunReport

# =============================================================================
# Logging Configuration (ADR-006: Centralized via config singleton)
# =============================================================================
def _setup_logging() -> logging.Logger:
    """Configure root logger: Stdout + Optional File (from config.yaml)."""
    log_level_str = getattr(config.env, "log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    
    log_file = config.get("system", {}).get("log_file")
    if log_file:
        try:
            import os
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Failed to initialize file logging at {log_file}: {e}", file=sys.stderr)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True
    )
    return logging.getLogger("kakadu.main")

logger = _setup_logging()

# =============================================================================
# Helper Functions
# =============================================================================

def _run_health_check() -> None:
    """ADR-018.2: Fail-fast startup probe. Raises RuntimeError on failure."""
    logger.info("Initiating startup health probe...")
    checker = StartupHealthChecker(config)
    checker.run()
    logger.info("Health probe passed.")

def _resolve_oci_par_url() -> Optional[str]:
    """
    Resolve OCI PAR URL and check enabled status per P1 Review Guidelines:
    - If oci.enabled is false: Log INFO and return None (Explicitly disabled).
    - If oci.enabled is true and valid PAR URL exists: Return URL.
    - If oci.enabled is true but URL is missing/invalid: Log Warning (Tier 1) and return None.
    """
    yaml_oci = config.get("oci", {})
    is_enabled = yaml_oci.get("enabled", False) or config.env.oci.enabled

    if not is_enabled:
        logger.info("OCI cloud sync is explicitly disabled in configuration (oci.enabled = false).")
        return None

    # Resolve PAR URL priority:
    # 1. config.yaml -> oci.par_url (or system.oci_par_url for legacy fallback)
    # 2. .env -> OCI_PAR_URL (config.env.oci.par_url)
    par_url = (
        yaml_oci.get("par_url") 
        or config.get("system", {}).get("oci_par_url") 
        or config.env.oci.par_url
    )

    if par_url and isinstance(par_url, str) and par_url.startswith("http"):
        return par_url.strip()

    logger.warning("[TIER-1] OCI cloud sync is enabled (oci.enabled = true), but OCI_PAR_URL is missing or invalid.")
    return None

def _sync_cloud_backup(target_table: str, batch_id: str, allow_local_purge: bool = True) -> bool:
    """
    Executes Batch-Level Sync: Compress batch dir -> Upload to OCI -> Verify -> Purge local batch dir.
    Failure is NON-FATAL (Tier 1 Warning): Logs error, retains local backup, returns False.
    """
    par_url = _resolve_oci_par_url()
    if not par_url:
        logger.info(f"Cloud sync skipped for {target_table} [Batch: {batch_id}]: OCI PAR URL not configured or disabled.")
        return True

    try:
        backup_dir = config.get("system", {}).get("backup_dir", "/home/ubuntu/backup")
        backup_mgr = BackupManager(base_backup_dir=backup_dir)
        upload_mgr = UploadManager(backup_manager=backup_mgr, oci_par_url=par_url)
        
        logger.info(f"Triggering cloud sync for table: {target_table} [Batch: {batch_id}]...")
        # UploadManager.sync_to_cloud requires (table_name, batch_id, backup_path, manifest)
        # backup_path & manifest are retrieved inside UploadManager via BackupManager using batch_id/date
        # BUT: Our UploadManager.sync_to_cloud signature requires backup_path & manifest explicitly.
        # We need to reconstruct the backup_path to call it.
        # Pattern: /home/ubuntu/backup/{table_name}/{YYYY-MM-DD}/{batch_id}/
        date_str = datetime.now().strftime("%Y-%m-%d")
        backup_path = os.path.join(backup_dir, target_table, date_str, batch_id)
        
        # We need the manifest. Since BatchBackupContext.finalize() wrote it, we read it back.
        manifest_path = os.path.join(backup_path, "manifest.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found at {manifest_path}. Backup may be incomplete.")
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        upload_mgr.sync_to_cloud(
            table_name=target_table, 
            batch_id=batch_id, 
            backup_path=backup_path, 
            manifest=manifest,
            allow_local_purge=allow_local_purge   # <--- 新增参数
        )
        logger.info(f"Cloud sync & verified cleanup successful for {target_table} [Batch: {batch_id}].")
        return True
    except Exception as e:
        logger.warning(f"[TIER-1] Cloud sync FAILED for {target_table} [Batch: {batch_id}] (Backup retained locally): {e}")
        return False

def _trigger_etl_group(group_name: str) -> None:
    """
    Executes a named ETL group from config.yaml -> etl_groups.
    Raises Exception on failure (halts pipeline, triggers Tier 2 Alert in caller).
    Per ADR-021: Does NOT pass BATCH_ID to PL/SQL.
    """
    logger.info(f"Triggering ETL Group: [{group_name}]")
    db_transformer.trigger_group(group_name)
    logger.info(f"ETL Group [{group_name}] completed successfully.")

# =============================================================================
# Command Handlers (Return int exit codes ONLY)
# =============================================================================

def handle_scrape(task_name: str) -> int:
    """
    Scrape Pipeline:
    1. Generate BATCH_ID
    2. Audit: SYS_BATCH_LOG INSERT (RUNNING, SOURCE_SYSTEM=task_name) - FAIL FAST on DB error
    3. Instantiate Scraper & Run -> Returns RunReport (Metrics validated inside BaseScraper)
    4. Cloud Sync (Batch level upload + verified cleanup, Tier-1 on fail)
    5. Post-Action ETL (Config driven: post_{task_name})
    6. Audit: SYS_BATCH_LOG UPDATE (SUCCESS/FAILED)
    """
    batch_id = uuid.uuid4().hex
    logger.info(f"=== SCRAPE START | Task: {task_name} | Batch: {batch_id} ===")

    try:
        # 1. Audit Entry (RUNNING) - Fail Fast: DB error propagates and halts immediately
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=task_name, 
            source_system=task_name
        )

        # 2. Factory & Execution
        scraper_cls = ScraperFactory.get_scraper(task_name)
        scraper = scraper_cls(db_op=db_operator)
        target_table = scraper.target_table

        if not target_table:
            raise KeyError(f"Scraper '{task_name}' missing 'target_table' in config.yaml")

        logger.info(f"Executing Scraper: {scraper_cls.__name__} -> Target Table: {target_table}")
        
        # Execute run and capture the detailed RunReport
        report: RunReport = scraper.run(job_name=task_name, batch_id=batch_id)

        # 3. Cloud Sync (Post-Ingestion, Batch-level, Tier-1 Tolerance)
        _sync_cloud_backup(
            target_table=target_table, 
            batch_id=batch_id, 
            allow_local_purge=not report.has_tier1_mismatch
        )

        # 4. Post-Action ETL (ADR-020: Mapping Driven)
        post_group = f"post_{task_name}"
        etl_groups = config.get("etl_groups", {})
        if post_group in etl_groups:
            _trigger_etl_group(post_group)
        else:
            logger.info(f"No post-action ETL group defined for '{post_group}'. Skipping.")

        # 5. Audit Success (ONLY after ALL steps succeed)
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== SCRAPE SUCCESS | Task: {task_name} | Batch: {batch_id} | Inserted: {report.inserted_db_count} ===")
        return 0

    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== SCRAPE FAILED | Task: {task_name} | Batch: {batch_id} | Error: {err_msg} ===")
        
        # Audit Failure
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except Exception as db_err:
            logger.critical(f"FATAL: Failed to record FAILED status to SYS_BATCH_LOG: {db_err}")

        # Tier 2 Alert (Systemic Failure)
        alert_manager.send_tier2_alert(
            f"Kakadu Scrape Failure\nTask: {task_name}\nBatch: {batch_id}\nError: {err_msg}"
        )
        return 1

def handle_transform(group_name: str) -> int:
    """Transform Pipeline: Execute PL/SQL group directly (No Scraping). Full Audit Trail."""
    batch_id = uuid.uuid4().hex
    logger.info(f"=== TRANSFORM START | Group: {group_name} | Batch: {batch_id} ===")

    try:
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=f"transform:{group_name}", 
            source_system="CLI_TRANSFORM"
        )
        _trigger_etl_group(group_name)
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== TRANSFORM SUCCESS | Group: {group_name} ===")
        return 0
    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== TRANSFORM FAILED | Group: {group_name} | Error: {err_msg} ===")
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except Exception as db_err:
            logger.critical(f"FATAL: Failed to record FAILED status to SYS_BATCH_LOG: {db_err}")
        alert_manager.send_tier2_alert(f"Kakadu Transform Failure\nGroup: {group_name}\nBatch: {batch_id}\nError: {err_msg}")
        return 1

def handle_maintain(group_name: str) -> int:
    """Maintenance Pipeline: Semantic alias for Transform. Full Audit Trail."""
    batch_id = uuid.uuid4().hex
    logger.info(f"=== MAINTAIN START | Group: {group_name} | Batch: {batch_id} ===")

    try:
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=f"maintain:{group_name}", 
            source_system="CLI_MAINTAIN"
        )
        _trigger_etl_group(group_name)
        db_operator.update_batch_status(batch_id=batch_id, status="SUCCESS")
        logger.info(f"=== MAINTAIN SUCCESS | Group: {group_name} ===")
        return 0
    except Exception as e:
        err_msg = str(e)
        logger.error(f"=== MAINTAIN FAILED | Group: {group_name} | Error: {err_msg} ===")
        try:
            db_operator.update_batch_status(batch_id=batch_id, status="FAILED", error_message=err_msg)
        except Exception as db_err:
            logger.critical(f"FATAL: Failed to record FAILED status to SYS_BATCH_LOG: {db_err}")
        alert_manager.send_tier2_alert(f"Kakadu Maintenance Failure\nGroup: {group_name}\nBatch: {batch_id}\nError: {err_msg}")
        return 1

# =============================================================================
# CLI Parser
# =============================================================================

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

    p_scrape = subparsers.add_parser("scrape", help="Execute a data scraper task")
    p_scrape.add_argument("--task", "-t", required=True, help="Task name (key in config.yaml & ScraperFactory, e.g., price_ohlcv_pre, annc, afr)")

    p_transform = subparsers.add_parser("transform", help="Execute PL/SQL transformation group")
    p_transform.add_argument("--group", "-g", required=True, help="ETL Group name from config.yaml -> etl_groups (e.g., full_pipeline, post_price_ohlcv_pre)")

    p_maintain = subparsers.add_parser("maintain", help="Execute maintenance routines")
    p_maintain.add_argument("--group", "-g", required=True, help="Maintenance Group name from config.yaml -> etl_groups (e.g., daily_maintenance, cleanup_old_data)")

    return parser

# =============================================================================
# Main Entry Point
# =============================================================================
# ... existing code ...
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    exit_code = 1

    try:
        if not args.skip_health_check:
            try:
                _run_health_check()
            except Exception as e:
                logger.critical(f"Startup Health Check Failed: {e}")
                alert_manager.send_tier2_alert(f"Kakadu Startup Failure: {e}")
                return 1
        else:
            logger.warning("Startup health check BYPASSED via CLI flag.")

        if args.command == "scrape":
            exit_code = handle_scrape(args.task)
        elif args.command == "transform":
            exit_code = handle_transform(args.group)
        elif args.command == "maintain":
            exit_code = handle_maintain(args.group)
        else:
            parser.print_help()
            exit_code = 2

    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user (SIGINT).")
        exit_code = 130
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception as e:
        logger.critical(f"Unhandled critical exception in main: {e}", exc_info=True)
        alert_manager.send_tier2_alert(f"Kakadu Orchestrator Crash: {e}")
        exit_code = 1
    finally:
        try:
            db_operator.close()
            logger.debug("Database connection pool closed.")
        except Exception as e:
            logger.debug(f"DbOperator cleanup ignored: {e}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())