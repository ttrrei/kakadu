# src/base_scraper.py
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Import the singleton instance of DbOperator
from .db_operator import db as db_operator

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract Base Class for all scrapers.
    Implements the 'Orchestrator' pattern to handle resource lifecycle,
    execution strategies (Bulk vs Iterative), and DB buffering.
    """

    def __init__(self, db_op=db_operator):
        # Composition: Hold a reference to the DbOperator
        self.db = db_op
        
        # --- Configuration Flags (To be overridden by subclasses) ---
        self.is_bulk_task: bool = False   # True: scrape_all, False: scrape_one
        self.needs_driver: bool = True    # True: Use Selenium, False: Use API/CSV/Requests
        self.batch_size: int = 50        # Buffer size for iterative mode
        
        # Internal state
        self._driver: Optional[webdriver.Chrome] = None

    def _create_driver(self) -> webdriver.Chrome:
        """
        Creates a standardized headless Chrome driver optimized for 1GB RAM VM.
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
        )
        
        try:
            logger.info("Initializing Headless Chrome Driver...")
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_driver(self) -> Optional[webdriver.Chrome]:
        """
        Lazy-loads the WebDriver. 
        Returns None if the task does not require a driver or if initialization fails.
        """
        if not self.needs_driver:
            return None
            
        if self._driver is None:
            self._driver = self._create_driver()
            
        return self._driver

    def run(self, symbols: List[str], table_name: str, job_name: str):
        """
        Main entry point. Manages the resource lifecycle and selects execution strategy.
        """
        try:
            logger.info(f"Starting job {job_name} on table {table_name}...")
            
            if self.is_bulk_task:
                self._run_bulk(symbols, table_name)
            else:
                self._run_iterative(symbols, table_name)
                
            logger.info(f"Job {job_name} completed successfully.")
            
        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            # Cleanup: Only quit if a driver was actually instantiated
            if self._driver:
                self._driver.quit()
                self._driver = None
                logger.info("WebDriver closed.")

    def _run_bulk(self, symbols: List[str], table_name: str):
        """
        Strategy for Bulk Mode: One-time fetch -> One-time write.
        """
        logger.info("Executing in BULK mode...")
        
        # Get driver if needed (returns None if needs_driver=False)
        driver = self.get_driver()
        
        # Subclasses implement scrape_all
        data = self.scrape_all(driver, symbols)
        
        if data:
            self.db.insert_batch(table_name, data)
            logger.info(f"Bulk insert completed: {len(data)} records.")
        else:
            logger.warning("No data extracted in bulk mode.")

    def _run_iterative(self, driver_init_symbols: List[str], table_name: str):
        """
        Strategy for Iterative Mode: Fetch -> Buffer -> Flush.
        Implements the 'Shield' pattern to isolate failures of single symbols.
        """
        logger.info("Executing in ITERATIVE mode...")
        buffer = []
        success_count = 0
        fail_count = 0

        # Initialize driver once for the entire loop if needed
        driver = self.get_driver()

        for symbol in driver_init_symbols:
            try:
                # Subclasses implement scrape_one
                record = self.scrape_one(driver, symbol)
                if record:
                    buffer.append(record)
                    success_count += 1
            except Exception as e:
                # Shield Pattern: Log error and continue to next symbol
                logger.error(f"Failed to scrape symbol {symbol}: {e}")
                fail_count += 1
                continue

            # Flush buffer to DB when batch size is reached to save memory
            if len(buffer) >= self.batch_size:
                self.db.insert_batch(table_name, buffer)
                buffer.clear()

        # Final flush for remaining records
        if buffer:
            self.db.insert_batch(table_name, buffer)

        logger.info(f"Iterative run finished. Success: {success_count}, Failed: {fail_count}")

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Must be implemented by Bulk scrapers.
        Note: 'driver' will be None if needs_driver=False.
        """
        pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Dict[str, Any]]:
        """
        Must be implemented by Iterative scrapers.
        Note: 'driver' will be None if needs_driver=False.
        """
        pass