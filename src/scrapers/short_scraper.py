# src/scrapers/short_position_scraper.py
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
                # "Product" -> PRODUCT_NAME
                # "Product Code" -> CODE
                # "Reported Short Positions" -> SHORT_POSITIONS
                # "Total Product in Issue" -> TOTAL_SHARES
                # "% of Total Product in Issue Reported as Short Positions" -> SHORT_PERCENT
                
                extracted_data.append({
                    "PRODUCT_NAME": row.get("Product", "").strip(),
                    "CODE": row.get("Product Code", "").strip(),
                    "SHORT_POSITIONS": row.get("Reported Short Positions", "0").replace(",", ""),
                    "TOTAL_SHARES": row.get("Total Product in Issue", "0").replace(",", ""),
                    "SHORT_PERCENT": row.get("% of Total Product in Issue Reported as Short Positions", "0")
                })
            
            logger.info(f"Successfully extracted {len(extracted_data)} short position records.")
            return extracted_data

        except Exception as e:
            logger.error(f"Error parsing Shortman CSV: {e}")
            return []

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("ShortPositionScraper operates in Bulk Mode only.")