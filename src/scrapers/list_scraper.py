# src/scrapers/list_scraper.py
from __future__ import annotations
import logging
import requests
import csv
from io import StringIO
from typing import Any, List, Dict, Optional
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ListScraper(BaseScraper):
    """
    Scraper for the ASX Ticker List via API CSV export.
    Implements Bulk Mode: Fetches the entire market list via HTTP request.
    
    Adheres to ADR-009 (API CSV Pivot) and ADR-015 (Identity-based Config).
    """

    # Identity for configuration mapping in config.yaml
    scraper_name = "company_master"
    
    # Default task attributes (can be overridden by config.yaml)
    is_bulk_task = True
    needs_driver = False

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the ASX company directory CSV and parses it into a list of dicts.
        """
        # ADR-015: Retrieve URL from the top-level scraper node in config.yaml
        cfg = self.config.get(self.scraper_name, {})
        target_url = cfg.get('url')
        
        if not target_url:
            logger.error(f"Configuration Error: 'url' for {self.scraper_name} not found in config.yaml")
            return []
        
        try:
            logger.info(f"Fetching ASX Company Directory CSV from API: {target_url}")
            
            # Use a browser-like User-Agent to avoid being blocked by API
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            response = requests.get(target_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Decode CSV content
            csv_content = response.text
            f = StringIO(csv_content)
            
            # Use DictReader to automatically use the first row as keys
            reader = csv.DictReader(f)
            
            extracted_data = []
            for row in reader:
                # Mapping based on ASX CSV structure:
                # "ASX code" -> CODE
                # "Company name" -> COMPANY_NAME
                # "GICs industry group" -> SECTOR
                # "Listing date" -> LISTING_DATE
                # "Market Cap" -> MARKET_CAP
                
                mcap_raw = row.get("Market Cap", "").strip()
                # Handle the "--" case found in the CSV
                mcap = None if mcap_raw == "--" or not mcap_raw else mcap_raw
                
                extracted_data.append({
                    "CODE": row.get("ASX code", "").strip(),
                    "COMPANY_NAME": row.get("Company name", "").strip(),
                    "SECTOR": row.get("GICs industry group", "").strip(),
                    "LISTING_DATE": row.get("Listing date", "").strip(),
                    "MARKET_CAP": mcap
                })
            
            logger.info(f"Successfully extracted {len(extracted_data)} companies from CSV.")
            return extracted_data

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed while fetching ASX list: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing ASX CSV: {e}")
            return []

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Dict[str, Any]]:
        """
        This scraper is strictly Bulk Mode per ADR-009.
        """
        raise NotImplementedError("ListScraper operates in Bulk Mode only.")