# src/scrapers/short_scraper.py
from __future__ import annotations
import logging
import requests
import csv
from io import StringIO
from typing import Any, List, Dict, Optional
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ShortPositionScraper(BaseScraper):
    """
    Scraper for ASX Short Positions via Shortman CSV export.
    Implements Bulk Mode: Fetches the entire market short position list.
    
    Adheres to ADR-015 (Identity-based Config).
    """

    # Identity for configuration mapping in config.yaml
    scraper_name = "short"
    
    # Default task attributes (can be overridden by config.yaml)
    is_bulk_task = True 
    needs_driver = False

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the Shortman CSV and parses it into a list of dicts.
        All extracted values are coerced to strings to align with ODS VARCHAR design.
        """
        # ADR-015: Retrieve URL from the top-level scraper node in config.yaml
        cfg = self.config.get(self.scraper_name, {})
        target_url = cfg.get('url')
        
        if not target_url:
            logger.error(f"Configuration Error: 'url' for {self.scraper_name} not found in config.yaml")
            return []
        
        try:
            logger.info(f"Fetching Short Positions CSV from: {target_url}")
            response = requests.get(target_url, timeout=30)
            response.raise_for_status()
            
            f = StringIO(response.text)
            reader = csv.DictReader(f)
            
            extracted_data = []
            for row in reader:
                # Mapping based on Shortman CSV structure
                # We ensure all values are stripped strings and remove thousands-separator commas
                extracted_data.append({
                    "PRODUCT_NAME": str(row.get("Product", "") or "").strip(),
                    "CODE": str(row.get("Product Code", "") or "").strip(),
                    "SHORT_POSITIONS": str(row.get("Reported Short Positions", "") or "").replace(",", "").strip(),
                    "TOTAL_SHARES": str(row.get("Total Product in Issue", "") or "").replace(",", "").strip(),
                    "SHORT_PERCENT": str(row.get("% of Total Product in Issue Reported as Short Positions", "") or "").strip()
                })
            
            logger.info(f"Successfully extracted {len(extracted_data)} short position records.")
            return extracted_data

        except Exception as e:
            logger.error(f"Error parsing Shortman CSV: {e}")
            return []

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("ShortPositionScraper operates in Bulk Mode only.")