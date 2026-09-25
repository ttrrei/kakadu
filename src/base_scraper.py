# src/base_scraper.py
from __future__ import annotations
import logging
import os
import uuid
import concurrent.futures
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Union, Iterable
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .db_operator import db as db_operator, InsertResult
from .backup_manager import BackupManager, BatchBackupContext
from .alert_manager import alert_manager, AlertManager
from .config import config
from .symbol_provider import SymbolProvider

logger = logging.getLogger(__name__)

@dataclass
class RunReport:
    """Represents the complete execution metrics of a scraper run."""
    target_table: str
    batch_id: str = ""
    extracted_records_count: int = 0
    backed_up_count: int = 0
    attempted_db_count: int = 0
    inserted_db_count: int = 0
    dropped_db_count: int = 0
    success_symbols: int = 0
    failed_symbols: int = 0
    backup_path: str = ""
    manifest: Dict[str, Any] = field(default_factory=dict)

    def merge_insert_result(self, res: InsertResult):
        self.attempted_db_count += res.attempted_count
        self.inserted_db_count += res.inserted_count
        self.dropped_db_count += res.dropped_count
        if not self.batch_id and res.batch_id:
            self.batch_id = res.batch_id


class BaseScraper(ABC):
    """
    Abstract Base Class for all scrapers.
    Implements the Template Method pattern to decouple orchestration from extraction.
    
    Concurrency Safety (P0 Fix):
    - Workers ONLY return raw data (symbol, records, error).
    - Main thread serializes: Backup Write -> Counting -> DB Buffer -> Flush.
    - Selenium tasks forced to single-thread (effective_workers=1).
    """

    def __init__(self, db_op=db_operator, alert_mgr: AlertManager = alert_manager):
        self.db = db_op
        self.alert_manager = alert_mgr
        self.config = config
        
        backup_path = self.config.get('system', {}).get('backup_dir', '/home/ubuntu/backup')
        self.backup_manager = BackupManager(base_backup_dir=backup_path)
        
        scraper_name = getattr(self, 'scraper_name', None)
        scraper_cfg = self.config.get(scraper_name, {}) if scraper_name else {}
        system_cfg = self.config.get('system', {})

        self.batch_size = scraper_cfg.get('batch_size', system_cfg.get('batch_size', 50))
        self.max_workers = scraper_cfg.get('max_workers', system_cfg.get('max_workers', 1))
        self.is_bulk_task = getattr(self, 'is_bulk_task', scraper_cfg.get('is_bulk', False))
        self.needs_driver = getattr(self, 'needs_driver', scraper_cfg.get('needs_driver', True))
        
        self.target_table = scraper_cfg.get('target_table')
        self._driver: Optional[webdriver.Chrome] = None

    def _create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
        try:
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_driver(self) -> Optional[webdriver.Chrome]:
        if not self.needs_driver: return None
        if self._driver is None: self._driver = self._create_driver()
        return self._driver

    def run(self, job_name: str = "", batch_id: str | None = None) -> RunReport:
        """
        Main execution entry point with P0 Decision & Circuit Breaker Logic.
        """
        effective_batch_id = batch_id or uuid.uuid4().hex
        report = RunReport(target_table=self.target_table or "UNKNOWN", batch_id=effective_batch_id)

        try:
            if not self.target_table:
                raise KeyError(f"Scraper {getattr(self, 'scraper_name', 'unknown')} is missing 'target_table' in config.yaml")

            report.target_table = self.target_table
            logger.info(f"Starting job {job_name} on table {self.target_table} [Batch: {effective_batch_id}]...")

            # ===== Batch-level Backup Context (Single File per Batch) =====
            date_str = datetime.now().strftime("%Y-%m-%d")
            with self.backup_manager.start_batch(self.target_table, effective_batch_id, date_str) as batch_bak:
                if self.is_bulk_task:
                    report = self._run_bulk(job_name, effective_batch_id, batch_bak, report)
                else:
                    report = self._run_iterative(job_name, effective_batch_id, batch_bak, report)

                report.backup_path = batch_bak.batch_dir

                # Explicit finalize to generate manifest.json
                manifest = batch_bak.finalize()
                report.manifest = manifest
                logger.info(f"Backup finalized successfully: {manifest}")

            # =========================================================================
            # P0 Circuit Breaker & Tiered Alerting (Adhering to Review Guidelines)
            # =========================================================================

            # 1. Tier 2: Extracted > 0 but Inserted == 0 -> Systemic Failure
            if report.extracted_records_count > 0 and report.inserted_db_count == 0:
                crit_msg = (
                    f"Tier 2 CRITICAL FAILURE in job '{job_name}' [{self.target_table}]: "
                    f"Extracted {report.extracted_records_count} records but inserted 0 into database."
                )
                logger.critical(crit_msg)
                self.alert_manager.send_tier2_alert(crit_msg, priority=1)
                raise RuntimeError(crit_msg)

            # 2. Tier 1: Local Backup Count != DB Inserted Count
            if report.backed_up_count != report.inserted_db_count:
                self.alert_manager.check_tier1_mismatch(
                    local_count=report.backed_up_count,
                    db_count=report.inserted_db_count,
                    task_name=job_name,
                    backup_path=report.backup_path
                )

            logger.info(f"Job {job_name} successfully validated. Report: {report}")
            return report

        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

    def _get_symbol_generator(self) -> Iterable[str]:
        scraper_name = getattr(self, 'scraper_name', None)
        scraper_cfg = self.config.get(scraper_name, {}) if scraper_name else {}
        symbol_source = scraper_cfg.get('symbol_source')
        
        if not symbol_source:
            raise KeyError(
                f"Configuration Error: 'symbol_source' is missing for scraper '{scraper_name}'."
            )
            
        provider = SymbolProvider(source_table=symbol_source)
        return provider.get_target_symbols()

    def _run_bulk(self, job_name: str, batch_id: str, batch_bak: BatchBackupContext, report: RunReport) -> RunReport:
        logger.info("Executing in BULK mode...")
        driver = self.get_driver()
        data = self.scrape_all(driver, []) 
        if data:
            report.extracted_records_count = len(data)
            
            # Real-time backup & precise counting (Single Thread)
            written = batch_bak.append_records(data)
            report.backed_up_count += written
            
            ins_result = self.db.insert_batch(self.target_table, data, batch_id=batch_id)
            report.merge_insert_result(ins_result)
        else:
            raise RuntimeError(f"Bulk scrape yielded ZERO records for {self.target_table}. Potential API/HTML structure change.")
            
        report.backup_path = batch_bak.batch_dir
        return report

    def _run_iterative(self, job_name: str, batch_id: str, batch_bak: BatchBackupContext, report: RunReport) -> RunReport:
        logger.info(f"Executing in ITERATIVE mode (max_workers={self.max_workers})...")
        
        driver = self.get_driver()
        symbols_gen = self._get_symbol_generator()
        
        # --- Concurrency Safety: Selenium forces Single Thread ---
        effective_workers = 1 if self.needs_driver else self.max_workers
        if self.needs_driver and self.max_workers > 1:
            logger.warning(f"Scraper '{getattr(self, 'scraper_name', 'unknown')}' uses Selenium. Forcing single-thread execution (max_workers=1).")

        buffer: List[Dict[str, Any]] = []
        
        # Helper to flush buffer to DB
        def flush_buffer():
            nonlocal buffer
            if buffer:
                ins_result = self.db.insert_batch(self.target_table, buffer, batch_id=batch_id)
                report.merge_insert_result(ins_result)
                buffer = []

        if effective_workers == 1:
            # --- Serial Execution (Selenium or Low Concurrency) ---
            for symbol in symbols_gen:
                try:
                    result = self.scrape_one(driver, symbol)
                    if result:
                        records = result if isinstance(result, list) else [result]
                        report.extracted_records_count += len(records)
                        report.success_symbols += 1
                        
                        # Main Thread: Serial Backup Write
                        written = batch_bak.append_records(records)
                        report.backed_up_count += written
                        
                        # Main Thread: Buffer for DB
                        buffer.extend(records)
                        if len(buffer) >= self.batch_size:
                            flush_buffer()
                    else:
                        # scrape_one returned None/Empty -> treat as symbol failure but continue
                        report.failed_symbols += 1
                        logger.warning(f"Symbol {symbol} returned no data.")
                except Exception as e:
                    logger.error(f"Failed to process symbol {symbol}: {e}")
                    report.failed_symbols += 1
        else:
            # --- Parallel Fetch / Serial Write Pattern (Thread Pool) ---
            max_in_flight = min(effective_workers * 2, self.config.get('system', {}).get('max_in_flight', 8))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
                future_to_symbol = {}
                
                # Initial Submit
                for symbol in symbols_gen:
                    future = executor.submit(self._safe_scrape_one, driver, symbol)
                    future_to_symbol[future] = symbol
                    if len(future_to_symbol) >= max_in_flight:
                        break

                while future_to_symbol:
                    done, _ = concurrent.futures.wait(future_to_symbol, return_when=concurrent.futures.FIRST_COMPLETED)
                    
                    for future in done:
                        symbol = future_to_symbol.pop(future)
                        try:
                            # Worker returns (symbol, records, error)
                            # Main Thread handles ALL side effects
                            _, records, error = future.result()
                            
                            if error:
                                logger.error(f"Scrape error for {symbol}: {error}")
                                report.failed_symbols += 1
                            elif records:
                                report.extracted_records_count += len(records)
                                report.success_symbols += 1
                                
                                # Main Thread: Serial Backup Write
                                written = batch_bak.append_records(records)
                                report.backed_up_count += written
                                
                                # Main Thread: Buffer for DB
                                buffer.extend(records)
                                if len(buffer) >= self.batch_size:
                                    flush_buffer()
                            else:
                                report.failed_symbols += 1
                                logger.warning(f"Symbol {symbol} returned no data.")
                        except Exception as e:
                            logger.error(f"Unexpected future error for {symbol}: {e}")
                            report.failed_symbols += 1

                    # Refill Pool
                    try:
                        while len(future_to_symbol) < max_in_flight:
                            next_symbol = next(symbols_gen)
                            new_future = executor.submit(self._safe_scrape_one, driver, next_symbol)
                            future_to_symbol[new_future] = next_symbol
                    except StopIteration:
                        pass
        
        # Final Flush
        flush_buffer()

        logger.info(
            f"Iterative run finished. Symbols Success: {report.success_symbols}, Failed: {report.failed_symbols} | "
            f"Extracted: {report.extracted_records_count}, Backed Up: {report.backed_up_count}, Inserted DB: {report.inserted_db_count}, Dropped DB: {report.dropped_db_count}"
        )

        if report.success_symbols == 0:
            raise RuntimeError(
                f"Iterative scrape FAILED COMPLETELY for {self.target_table}. "
                f"Success: 0, Failures: {report.failed_symbols}. Bulk missingness detected!"
            )

        report.backup_path = batch_bak.batch_dir
        return report

    def _safe_scrape_one(self, driver, symbol) -> tuple[str, Optional[List[Dict]], Optional[Exception]]:
        """
        Wrapper for ThreadPoolExecutor.
        Returns: (symbol, records_list_or_None, exception_or_None)
        NEVER raises. All side effects (backup, db, counting) handled by caller (Main Thread).
        """
        try:
            result = self.scrape_one(driver, symbol)
            if result:
                records = result if isinstance(result, list) else [result]
                return symbol, records, None
            return symbol, None, None
        except Exception as e:
            return symbol, None, e

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]: 
        pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]: 
        pass