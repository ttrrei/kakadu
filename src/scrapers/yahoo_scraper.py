# src/scrapers/yahoo_scraper.py
from __future__ import annotations
import logging
import requests
import time
from typing import Any, List, Dict, Optional, Union
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper
from ..db_operator import db as db_operator

logger = logging.getLogger(__name__)

class YahooScraper(BaseScraper):
    """
    Scraper for Yahoo Finance Hourly K-line data.
    Implements Iterative Mode: Fetches data per symbol and buffers it for batch insertion.
    
    Design:
    - Range: 3 days (reduced from 60d for efficiency)
    - Interval: 1 hour
    - Filter: Only keeps records where timestamp is exactly on the hour (ts % 3600 == 0)
    - Storage: Pure-INSERT into ODS (VARCHAR2)
    """

    def __init__(self, db_op: Optional[Any] = None):
        actual_db = db_op if db_op is not None else db_operator
        super().__init__(actual_db)
        
        # ADR-008: Iterative Mode (One symbol -> Many records)
        self.is_bulk_task = False 
        self.needs_driver = False  # API based, no Selenium needed
        self.batch_size = 100      # Buffer records before flushing to DB
        self.target_table = "ODS_PRICE_OHLCV"

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """Not used in Iterative Mode."""
        raise NotImplementedError("YahooScraper operates in Iterative Mode only.")

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Fetches hourly data for a single symbol from Yahoo Finance.
        Returns a list of records (One-to-Many).
        """
        ticker = f"{symbol.upper()}.AX"
        # Reduced range to 3d as per requirement
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1h&range=3d"
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            json_data = resp.json()
            res = json_data.get('chart', {}).get('result', [None])[0]
            
            if not res or 'timestamp' not in res:
                logger.warning(f"No data found for symbol {ticker}")
                return None
            
            timestamps = res['timestamp']
            quotes = res['indicators']['quote'][0]
            
            extracted_records = []
            for i, ts in enumerate(timestamps):
                # --- Data Quality Filter ---
                # 1. Only keep records that fall exactly on the hour (solves the +1 offset problem)
                if ts % 3600 != 0:
                    continue
                
                # 2. Skip records with missing close price
                close_price = quotes['close'][i]
                if close_price is None:
                    continue
                
                # Map to ODS structure. 
                # Note: All values are passed as-is; DbOperator will coerce them to VARCHAR2.
                extracted_records.append({
                    "CODE": symbol.upper(),
                    "RAW_TIMESTAMP": ts,
                    "OPEN_PRICE": quotes['open'][i],
                    "HIGH_PRICE": quotes['high'][i],
                    "LOW_PRICE": quotes['low'][i],
                    "CLOSE_PRICE": close_price,
                    "VOLUME": quotes['volume'][i],
                    "RECORD_DTS": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))
                })
            
            if extracted_records:
                logger.info(f"Extracted {len(extracted_records)} hourly bars for {ticker}")
                
            return extracted_records

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching Yahoo data for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing Yahoo data for {symbol}: {e}")
            return None