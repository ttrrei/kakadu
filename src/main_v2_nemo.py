# src/main.py
"""
Kakadu Main Orchestrator (Production Hardened)
==============================================
Implements: ADR-018 (Service Orchestration), ADR-019 (Master Shell Contract),
            ADR-020 (Config-Driven ETL), ADR-021 (BATCH_ID Decoupling),
            ADR-005 (Audit Lineage), ADR-006 (Dual-Config), ADR-010 (Task=Session).

Architecture Invariants (Red Lines):
- NO sys.exit() inside handlers -> return int exit codes only.
- DB Connection Pool lifecycle managed ONLY in main() finally block.
- Audit Status: RUNNING -> (Scrape -> CloudSync -> PostETL) -> SUCCESS/FAILED.
- Session Type encoded in Task Name (e.g., price_ohlcv_pre), NO --session-type flag.
- BATCH_ID generated in Python, logged to SYS_BATCH_LOG, NEVER passed to PL/SQL.
"""

import sys
import uuid
import argparse
import logging
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
            # Ensure directory exists
            import os
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except Exception as e:
            # Fallback to stdout only if file setup fails
            print(f"[WARN] Failed to initialize file logging at {log_file}: {e}", file=sys.stderr)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True  # Override any prior basicConfig (critical for re-runs in tests)
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
    Resolve OCI PAR URL with strict priority:
    1. config.yaml -> system.oci_par_url (Non-sensitive override)
    2. .env -> OCI_PAR_URL (mapped to config.env.oci.config_path by EnvConfig loader)
    Returns None if not configured (Cloud Sync becomes NO-OP with Warning).
    """
    # 1. YAML (Preferred for non-secret full PAR URL)
    par_url = config.get("system", {}).get("oci_par_url")
    if par_url and isinstance(par_url, str) and par_url.startswith("http"):
        return par_url.strip()

    # 2. Env (Sensitive full PAR URL stored in OCI_CONFIG_PATH per .env.example convention)
    env_par = getattr(config.env.oci, "config_path", "")
    if env_par and isinstance(env_par, str) and env_par.startswith("http"):
        return env_par.strip()

    return None

def _sync_cloud_backup(target_table: str) -> bool:
    """
    Executes Batch-Compress-Upload via UploadManager.
    Failure is NON-FATAL (Tier 1 Warning): Logs error, retains local backup, returns False.
    Does NOT update batch status to FAILED.
    """
    par_url = _resolve_oci_par_url()
    if not par_url:
        logger.info(f"Cloud sync skipped for {target_table}: OCI PAR URL not configured (checked system.oci_par_url & env.OCI_PAR_URL).")
        return True  # Not an error, just not configured

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
        logger.warning(f"[TIER-1] Cloud sync FAILED for {target_table} (Backup retained locally): {e}")
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
    2. Audit: SYS_BATCH_LOG INSERT (RUNNING, SOURCE_SYSTEM=task_name)
    3. Instantiate Scraper & Run (injects batch_id into ODS via DbOperator)
    4. Cloud Sync (Best effort, Tier-1 on fail)
    5. Post-Action ETL (Config driven: post_{task_name})
    6. Audit: SYS_BATCH_LOG UPDATE (SUCCESS/FAILED)
    """
    batch_id = uuid.uuid4().hex
    logger.info(f"=== SCRAPE START | Task: {task_name} | Batch: {batch_id} ===")

    # 1. Audit Entry (RUNNING)
    # SOURCE_SYSTEM uses Task Name (e.g., 'price_ohlcv_pre') for audit context per ADR-010
    try:
        db_operator.create_batch_record(
            batch_id=batch_id, 
            task_name=task_name, 
            source_system=task_name
        )
    except Exception as e:
        # Non-fatal: Audit failure shouldn't stop ingestion, but log loudly
        logger.error(f"Failed to create batch audit record (Non-fatal): {e}")

    scraper = None
    target_table = None

    try:
        # 2. Factory & Execution
        scraper_cls = ScraperFactory.get_scraper(task_name)
        # Dependency Injection: Pass singleton db_operator
        scraper = scraper_cls(db_op=db_operator)
        target_table = scraper.target_table

        if not target_table:
            raise KeyError(f"Scraper '{task_name}' missing 'target_table' in config.yaml")

        logger.info(f"Executing Scraper: {scraper_cls.__name__} -> Target Table: {target_table}")
        # BaseScraper.run() handles driver lifecycle internally (finally block)
        scraper.run(job_name=task_name, batch_id=batch_id)

        # 3. Cloud Sync (Post-Ingestion, Tier-1 Tolerance)
        _sync_cloud_backup(target_table)

        # 4. Post-Action ETL (ADR-020: Mapping Driven)
        # Convention: "post_{task_name}" e.g. "post_price_ohlcv_pre"
        post_group = f"post_{task_name}"
        etl_groups = config.get("etl_groups", {})
        if post_group in etl_groups:
            _trigger_etl_group(post_group)
        else:
            logger.info(f"No post-action ETL group defined for '{post_group}'. Skipping.")

        # 5. Audit Success (ONLY after ALL steps succeed)
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
        except: pass
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
        except: pass
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
    
    # Global Flags
    parser.add_argument(
        "--skip-health-check", 
        action="store_true", 
        help="Bypass startup health probe (Wallet, DB, Env). USE WITH CAUTION."
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Execution Mode")

    # 1. Scrape Command (Primary Data Ingestion)
    # Task name INCLUDES session context (e.g., price_ohlcv_pre, price_ohlcv_post)
    p_scrape = subparsers.add_parser("scrape", help="Execute a data scraper task")
    p_scrape.add_argument("--task", "-t", required=True, help="Task name (key in config.yaml & ScraperFactory, e.g., price_ohlcv_pre, annc, afr)")

    # 2. Transform Command (PL/SQL ETL Execution)
    p_transform = subparsers.add_parser("transform", help="Execute PL/SQL transformation group")
    p_transform.add_argument("--group", "-g", required=True, help="ETL Group name from config.yaml -> etl_groups (e.g., full_pipeline, post_price_ohlcv_pre)")

    # 3. Maintain Command (System Maintenance)
    p_maintain = subparsers.add_parser("maintain", help="Execute maintenance routines")
    p_maintain.add_argument("--group", "-g", required=True, help="Maintenance Group name from config.yaml -> etl_groups (e.g., daily_maintenance, cleanup_old_data)")

    return parser

# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    exit_code = 1  # Default to failure

    try:
        # 1. Startup Health Check (Global, unless skipped)
        if not args.skip_health_check:
            try:
                _run_health_check()
            except Exception as e:
                logger.critical(f"Startup Health Check Failed: {e}")
                alert_manager.send_tier2_alert(f"Kakadu Startup Failure: {e}")
                return 1  # Exit immediately, no pool cleanup needed yet (not initialized)
        else:
            logger.warning("Startup health check BYPASSED via CLI flag.")

        # 2. Command Dispatch
        if args.command == "scrape":
            exit_code = handle_scrape(args.task)
        elif args.command == "transform":
            exit_code = handle_transform(args.group)
        elif args.command == "maintain":
            exit_code = handle_maintain(args.group)
        else:
            # Should not happen due to required=True, but defensive
            parser.print_help()
            exit_code = 2

    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user (SIGINT).")
        exit_code = 130
    except SystemExit as e:
        # argparse calls sys.exit on --help or invalid args
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception as e:
        logger.critical(f"Unhandled orchestration error: {e}", exc_info=True)
        alert_manager.send_tier2_alert(f"Kakadu Orchestrator Crash: {e}")
        exit_code = 1
    finally:
        # 3. Global Resource Stewardship (ADR-019 / Connection Pool Stewardship)
        # ONLY place in entire codebase where pool is closed.
        try:
            db_operator.close()
            logger.debug("Database connection pool closed.")
        except Exception as e:
            logger.debug(f"DbOperator cleanup ignored: {e}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())