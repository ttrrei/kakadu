# src/scrapers/list_scraper.py
from __future__ import annotations
import logging
from typing import Any, List, Dict, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ListScraper(BaseScraper):
    """
    Scraper for the ASX Ticker List.
    Implements Bulk Mode: Fetches the entire market list in one pass.
    """

    def __init__(self, db_op=None):
        super().__init__(db_op)
        # ADR-008: This is a high-density page, use Bulk Mode
        self.is_bulk_task = True 
        self.needs_driver = True
        # The target table in ODS (defined in SAD)
        self.target_table = "ODS_COMPANY_MASTER"

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Extracts the full ASX ticker list from the provided URL.
        
        Args:
            driver: Headless Chrome driver provided by BaseScraper.
            symbols: Not used for Bulk mode, but passed by the orchestrator.
        """
        if not driver:
            logger.error("WebDriver is required for ListScraper but was not provided.")
            return []

        # Note: The URL should ideally come from config.yaml, 
        # but for this first version, we use the target URL.
        # In a real scenario, we'd use self.config.list_link
        target_url = "https://www.asx.com.au/markets/trade-our-shares/company-directory" # 请根据实际URL修改
        
        try:
            logger.info(f"Navigating to ASX Company Directory: {target_url}")
            driver.get(target_url)
            
            # Wait for the table to load (Simple implementation, consider WebDriverWait for production)
            # Based on the old extractList.py logic:
            scroll_overlay = driver.find_element(By.CLASS_NAME, "scroll-overlay")
            tbody = scroll_overlay.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            logger.info(f"Found {len(rows)} companies in the list.")
            
            extracted_data = []
            for row in rows:
                try:
                    # Extracting data based on the old extractList.py logic
                    # We map them to the ODS_COMPANY_MASTER business columns
                    code = row.find_element(By.TAG_NAME, "a").get_attribute("innerHTML").strip()
                    sector = row.find_element(By.CLASS_NAME, "text-left").get_attribute("innerHTML").strip()
                    
                    # Market Cap is usually the last element in the 'text-right' group
                    infos = row.find_elements(By.CLASS_NAME, "text-right")
                    mcap = infos[-1].get_attribute("innerHTML").strip() if infos else "N/A"
                    
                    # We return a Dict. DbOperator will handle BATCH_ID and LOAD_TIME.
                    extracted_data.append({
                        "CODE": code,
                        "SECTOR": sector,
                        "MARKET_CAP": mcap
                    })
                except Exception as e:
                    logger.warning(f"Skipping a row due to extraction error: {e}")
                    continue
            
            return extracted_data

        except Exception as e:
            logger.error(f"Failed to scrape ASX list: {e}")
            return []

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Dict[str, Any]]:
        """Not used in Bulk Mode."""
        raise NotImplementedError("ListScraper operates in Bulk Mode only.")