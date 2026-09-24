# src/base_scraper.py
from __future__ import annotations
import logging
import os
import concurrent.futures  # <--- 【关键新增】用于访问 wait 和 FIRST_COMPLETED
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Union, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed  # 【保持不变】直接导入常用类和函数

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .db_operator import db as db_operator
from .backup_manager import BackupManager
from .config import config
from .symbol_provider import SymbolProvider

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract Base Class for all scrapers.
    Implements the Template Method pattern to decouple orchestration from extraction.
    """

    def __init__(self, db_op=db_operator):
        self.db = db_op
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
        
        # Direct target table from config (per simplified routing design)
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

    def run(self, job_name: str = "", batch_id: str | None = None):
        """
        Main execution entry point.
        
        Args:
            job_name: Human-readable name of the job.
            batch_id: The unique system batch ID (from SYS_BATCH_LOG). 
                      If None, the system will fallback to job_name or generate a UUID.
        """
        try:
            if not self.target_table:
                raise KeyError(f"Scraper {getattr(self, 'scraper_name', 'unknown')} is missing 'target_table' in config.yaml")

            logger.info(f"Starting job {job_name} on table {self.target_table}...")
            if self.is_bulk_task:
                self._run_bulk(job_name, batch_id)
            else:
                self._run_iterative(job_name, batch_id)
            logger.info(f"Job {job_name} completed successfully.")
        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

    def _get_symbol_generator(self) -> Iterable[str]:
        """
        Helper to create a SymbolProvider based on current scraper's config.
        """
        scraper_name = getattr(self, 'scraper_name', None)
        scraper_cfg = self.config.get(scraper_name, {}) if scraper_name else {}
        symbol_source = scraper_cfg.get('symbol_source')
        
        if not symbol_source:
            raise KeyError(
                f"Configuration Error: 'symbol_source' is missing for scraper '{scraper_name}'. "
                f"Please add 'symbol_source: TABLE_NAME' to the {scraper_name} section in config.yaml."
            )
            
        provider = SymbolProvider(source_table=symbol_source)
        return provider.get_target_symbols()

    def _run_bulk(self, job_name: str, batch_id: str | None = None):
        logger.info("Executing in BULK mode...")
        driver = self.get_driver()
        data = self.scrape_all(driver, []) 
        if data:
            self.backup_manager.save_record(self.target_table, "BULK_EXPORT", data)
            # Use batch_id if provided, otherwise fallback to job_name
            self.db.insert_batch(self.target_table, data, batch_id=batch_id or job_name)
        else:
            # --- CIRCUIT BREAKER: Zero data in bulk mode is a failure ---
            raise RuntimeError(f"Bulk scrape yielded ZERO records for {self.target_table}. Potential API/HTML structure change.")

    def _run_iterative(self, job_name: str, batch_id: str | None = None):
        """
        Optimized Iterative Mode with ThreadPoolExecutor and DB Buffering.
        Implements a bounded in-flight pattern for O(1) memory usage.
        """
        logger.info(f"Executing in ITERATIVE mode with {self.max_workers} threads...")
        
        success_count = 0
        fail_count = 0
        driver = self.get_driver()
        
        # Memory Safety: Iterate directly from generator
        symbols_gen = self._get_symbol_generator()
        buffer = []
        
        # --- BOUNDED IN-FLIGHT PATTERN FOR O(1) MEMORY ---
        max_in_flight = max(self.max_workers * 2, 4) # Ensure at least 4 in-flight for small worker counts

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {}
            
            # 1. Pre-fill the in-flight window
            for symbol in symbols_gen:
                future = executor.submit(self._process_single_symbol, driver, symbol)
                future_to_symbol[future] = symbol
                if len(future_to_symbol) >= max_in_flight:
                    break

            # 2. Consume-one, submit-one loop to maintain bounded memory
            while future_to_symbol:
                # Wait for the first future to complete
                done, _ = concurrent.futures.wait(future_to_symbol, return_when=concurrent.futures.FIRST_COMPLETED)
                
                for future in done:
                    symbol = future_to_symbol.pop(future)
                    try:
                        result = future.result()
                        if result:
                            # Handle both single dict and list of dicts (One-to-Many)
                            records = result if isinstance(result, list) else [result]
                            buffer.extend(records)
                            success_count += 1
                            
                            # Flush to DB when buffer reaches batch_size
                            if len(buffer) >= self.batch_size:
                                # Use batch_id if provided, otherwise fallback to job_name
                                self.db.insert_batch(self.target_table, buffer, batch_id=batch_id or job_name)
                                buffer = [] # Create new list to avoid reference issues
                    except Exception as e:
                        logger.error(f"Failed to process symbol {symbol}: {e}")
                        fail_count += 1

                # Submit new tasks to fill the in-flight window back up
                try:
                    while len(future_to_symbol) < max_in_flight:
                        next_symbol = next(symbols_gen)
                        new_future = executor.submit(self._process_single_symbol, driver, next_symbol)
                        future_to_symbol[new_future] = next_symbol
                except StopIteration:
                    # No more symbols to process, loop will exit when all futures are done
                    pass
        
        # Final flush for any remaining records in the buffer
        if buffer:
            # Use batch_id if provided, otherwise fallback to job_name
            self.db.insert_batch(self.target_table, buffer, batch_id=batch_id or job_name)

        logger.info(f"Iterative run finished. Success: {success_count}, Failed: {fail_count}")

        # --- CIRCUIT BREAKER: Zero successful symbols in iterative mode is a failure ---
        if success_count == 0:
            raise RuntimeError(
                f"Iterative scrape FAILED COMPLETELY for {self.target_table}. "
                f"Success: 0, Failures: {fail_count}. Bulk missingness detected!"
            )

    def _process_single_symbol(self, driver, symbol):
        """
        Extraction logic for a single symbol.
        """
        try:
            result = self.scrape_one(driver, symbol)
            if result:
                # Local backup is performed immediately to ensure zero data loss
                self.backup_manager.save_record(self.target_table, symbol, result)
            return result
        except Exception as e:
            logger.error(f"Scrape error for {symbol}: {e}")
            raise e

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]: 
        """Implement for Bulk mode"""
        pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]: 
        """Implement for Iterative mode"""
        pass