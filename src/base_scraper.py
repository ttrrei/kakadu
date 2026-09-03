# src/base_scraper.py
from __future__ import annotations
import logging
import os
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .db_operator import db as db_operator
from .backup_manager import BackupManager
from .config import config
from .symbol_provider import SymbolProvider # 修改：导入类而非函数

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract Base Class for all scrapers.
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
        
        if not hasattr(self, 'is_bulk_task'):
            self.is_bulk_task = scraper_cfg.get('is_bulk', False)
            
        if not hasattr(self, 'needs_driver'):
            self.needs_driver = scraper_cfg.get('needs_driver', True)
        
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

    def run(self, symbols: Optional[List[str]] = None, table_name: str = "", job_name: str = ""):
        try:
            logger.info(f"Starting job {job_name} on table {table_name}...")
            if self.is_bulk_task:
                if symbols is None: 
                    # Bulk 模式如果没传 symbols，需要一个默认源，这里建议也改为动态加载
                    symbols = list(self._get_custom_symbol_generator())
                self._run_bulk(symbols, table_name, job_name)
            else:
                self._run_iterative(table_name, job_name)
            logger.info(f"Job {job_name} completed successfully.")
        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

    def _get_custom_symbol_generator(self):
        """
        Helper to create a SymbolProvider based on current scraper's config.
        """
        scraper_name = getattr(self, 'scraper_name', None)
        scraper_cfg = self.config.get(scraper_name, {}) if scraper_name else {}
        
        # --- 强制校验：必须在 yaml 中定义 symbol_source ---
        symbol_source = scraper_cfg.get('symbol_source')
        if not symbol_source:
            raise KeyError(
                f"Configuration Error: 'symbol_source' is missing for scraper '{scraper_name}'. "
                f"Please add 'symbol_source: TABLE_NAME' to the {scraper_name} section in config.yaml."
            )
            
        provider = SymbolProvider(source_table=symbol_source)
        return provider.get_target_symbols()

    def _run_bulk(self, symbols: List[str], table_name: str, job_name: str):
        logger.info("Executing in BULK mode...")
        driver = self.get_driver()
        data = self.scrape_all(driver, symbols)
        if data:
            self.backup_manager.save_record(table_name, "BULK_EXPORT", data)
            self.db.insert_batch(table_name, data, batch_id=job_name)
        else:
            logger.warning("No data extracted in bulk mode.")

    def _run_iterative(self, table_name: str, job_name: str):
        """
        Optimized Iterative Mode using ThreadPoolExecutor.
        """
        logger.info(f"Executing in ITERATIVE mode with {self.max_workers} threads...")
        
        success_count = 0
        fail_count = 0
        driver = self.get_driver()

        # --- 动态获取符号源 ---
        symbols = list(self._get_custom_symbol_generator())
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {
                executor.submit(self._process_single_symbol, driver, symbol, table_name, job_name): symbol 
                for symbol in symbols
            }

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Critical error processing symbol {symbol}: {e}")
                    fail_count += 1

        logger.info(f"Iterative run finished. Success: {success_count}, Failed: {fail_count}")

    def _process_single_symbol(self, driver, symbol, table_name, job_name):
        try:
            result = self.scrape_one(driver, symbol)
            if not result:
                return None
            self.backup_manager.save_record(table_name, symbol, result)
            records = result if isinstance(result, list) else [result]
            self.db.insert_batch(table_name, records, batch_id=job_name)
            return True
        except Exception as e:
            logger.error(f"Failed to process symbol {symbol}: {e}")
            raise e

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]: 
        pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]: 
        pass