# src/scrapers/yahoo_scraper.py
from __future__ import annotations
import logging
import requests
from typing import Any, List, Dict, Optional, Union

from ..base_scraper import BaseScraper
from ..db_operator import db as db_operator

logger = logging.getLogger(__name__)

class YahooScraper(BaseScraper):
    """
    Scraper for Yahoo Finance OHLCV data.
    Implements Iterative Mode: Fetches data per symbol and buffers it for batch insertion.
    
    Design:
    - Dynamic Table Routing: Routes data to ODS_PRICE_OHLCV_PRE or ODS_PRICE_OHLCV_POST based on session.
    - Memory-Efficient: Uses requests and returns List[Dict], maintaining O(1) memory footprint.
    - Zero-Loss: Integrated with BaseScraper's Fetch -> Backup -> Insert pipeline.
    """

    def __init__(self, db_op: Optional[Any] = None, session_type: str = "post_close"):
        # Use the provided db_op or fall back to the singleton
        actual_db = db_op if db_op is not None else db_operator
        super().__init__(actual_db)
        
        # --- ADR-008 & Configuration Mapping ---
        # Load scraper-specific config from config.yaml
        self.scraper_cfg = self.config.get('scrapers', {}).get('price_ohlcv', {})
        
        # 1. Mode Settings
        self.is_bulk_task = self.scraper_cfg.get('is_bulk', False)
        self.needs_driver = self.scraper_cfg.get('needs_driver', False)
        self.batch_size = self.scraper_cfg.get('batch_size', 50)
        
        # 2. Session-Based Dynamic Configuration
        # Retrieve the specific settings for the current session (pre_close / post_close)
        session_cfg = self.scraper_cfg.get('sessions', {}).get(session_type)
        
        if not session_cfg:
            raise ValueError(f"Invalid session_type '{session_type}' provided for YahooScraper. "
                             f"Available sessions: {list(self.scraper_cfg.get('sessions', {}).keys())}")
        
        # Dynamically set target table and API parameters based on session
        self.target_table = session_cfg.get('target_table')
        self.interval = session_cfg.get('interval')
        self.range = session_cfg.get('range')
        
        # Base URL for API requests
        self.base_url = self.scraper_cfg.get('base_url')
        
        if not self.target_table or not self.base_url:
            raise KeyError("Missing critical configuration (target_table or base_url) for YahooScraper.")

    def scrape_all(self, driver: Optional[Any], symbols: List[str]) -> List[Dict[str, Any]]:
        """Not used in Iterative Mode."""
        raise NotImplementedError("YahooScraper operates in Iterative Mode only.")

    def scrape_one(self, driver: Optional[Any], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Fetches OHLCV data for a single symbol from Yahoo Finance.
        Returns a list of records (One-to-Many).
        """
        ticker = symbol.upper()
        # Construct the dynamic URL based on session parameters
        url = f"{self.base_url}{ticker}?interval={self.interval}&range={self.range}"
        
        try:
            # Use a browser-like User-Agent to prevent 403/429 errors
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            json_data = response.json()
            # Navigate the Yahoo JSON structure: chart -> result[0]
            result = json_data.get('chart', {}).get('result', [None])[0]
            
            if not result or 'timestamp' not in result:
                logger.warning(f"No data returned from Yahoo for symbol {ticker}")
                return None
            
            timestamps = result['timestamp']
            quotes = result['indicators']['quote'][0]
            
            extracted_records = []
            for i, ts in enumerate(timestamps):
                # --- Data Quality Filter ---
                # 1. Only keep records that fall exactly on the hour (solves the +1 offset problem)
                # Note: This filter is applied for hourly intervals.
                if self.interval == "1h" and ts % 3600 != 0:
                    continue
                
                # 2. Skip records with missing close price to ensure data integrity
                close_price = quotes['close'][i]
                if close_price is None:
                    continue
                
                # Map to ODS structure. 
                # All values are passed as-is; DbOperator will coerce them to VARCHAR2.
                extracted_records.append({
                    "CODE": symbol.upper(),
                    "RAW_TIMESTAMP": str(ts),
                    "OPEN_PRICE": str(quotes['open'][i]) if quotes['open'][i] is not None else None,
                    "HIGH_PRICE": str(quotes['high'][i]) if quotes['high'][i] is not None else None,
                    "LOW_PRICE": str(quotes['low'][i]) if quotes['low'][i] is not None else None,
                    "CLOSE_PRICE": str(close_price),
                    "VOLUME": str(quotes['volume'][i]) if quotes['volume'][i] is not None else None
                })
            
            if extracted_records:
                logger.info(f"Extracted {len(extracted_records)} bars for {ticker} ({self.interval}/{self.range})")
                
            return extracted_records

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Symbol {ticker} not found on Yahoo Finance.")
            else:
                logger.error(f"HTTP error fetching Yahoo data for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing Yahoo data for {symbol}: {e}")
            return None