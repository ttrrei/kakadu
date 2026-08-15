# src/scrapers/short_scraper.py
from __future__ import annotations
import logging
import requests
import csv
from io import StringIO
from typing import Any, List, Dict, Optional
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper
from ..db_operator import db as db_operator

logger = logging.getLogger(__name__)

class ShortPositionScraper(BaseScraper):
    """
    Scraper for ASX Short Positions via Shortman CSV export.
    Implements Bulk Mode: Fetches the entire market short position list.
    """

    def __init__(self, db_op: Optional[Any] = None):
        actual_db = db_op if db_op is not None else db_operator
        super().__init__(actual_db)
        
        self.is_bulk_task = True 
        self.needs_driver = False
        self.target_table = "ODS_SHORT_POSITIONS"

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the Shortman CSV and parses it into a list of dicts.
        All extracted values are converted to strings to align with ODS VARCHAR design.
        """
        target_url = "https://www.shortman.com.au/downloadeddata/latest.csv"
        
        try:
            logger.info(f"Fetching Short Positions CSV from: {target_url}")
            response = requests.get(target_url, timeout=30)
            response.raise_for_status()
            
            f = StringIO(response.text)
            reader = csv.DictReader(f)
            
            extracted_data = []
            for row in reader:
                # Mapping based on the CSV structure provided
                # We use str(row.get(...) or "") to ensure that None values become empty strings
                # and all data is stored as VARCHAR in ODS.
                
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