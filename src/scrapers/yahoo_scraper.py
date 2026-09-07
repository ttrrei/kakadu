# src/scrapers/yahoo_scraper.py
from __future__ import annotations
import logging
import requests
from typing import Any, List, Dict, Optional, Union

from ..base_scraper import BaseScraper
from ..db_operator import db as db_operator

logger = logging.getLogger(__name__)

class YahooBase(BaseScraper):
    """
    Internal base class for Yahoo Finance OHLCV logic.
    Implements the core extraction and filtering logic.
    Not intended to be instantiated directly.
    """
    def __init__(self, db_op=None):
        # Ensure we use the singleton db_operator if none provided
        actual_db = db_op if db_op is not None else db_operator
        super().__init__(db_op=actual_db)
        
        # Lift configuration parameters to attributes for observability and testing
        # These are loaded based on the 'scraper_name' defined in subclasses
        cfg = self.config.get(self.scraper_name, {})
        self.base_url = cfg.get('base_url')
        self.interval = cfg.get('interval')
        self.range = cfg.get('range')

    def scrape_all(self, driver: Optional[Any], symbols: List[str]) -> List[Dict[str, Any]]:
        """Yahoo OHLCV is strictly iterative."""
        raise NotImplementedError("Yahoo scrapers operate in Iterative Mode only.")

    def scrape_one(self, driver: Optional[Any], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Fetches OHLCV data for a single symbol from Yahoo Finance.
        Returns a list of records (One-to-Many).
        """
        ticker = symbol.upper()
        
        if not self.base_url or not self.interval or not self.range:
            logger.error(f"Configuration Error: Missing parameters for {self.scraper_name}")
            return None

        url = f"{self.base_url}{ticker}?interval={self.interval}&range={self.range}"
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            json_data = response.json()
            result = json_data.get('chart', {}).get('result', [None])[0]
            
            if not result or 'timestamp' not in result:
                logger.warning(f"No data returned from Yahoo for symbol {ticker}")
                return None
            
            timestamps = result['timestamp']
            quotes = result['indicators']['quote'][0]
            
            extracted_records = []
            for i, ts in enumerate(timestamps):
                # Data Quality Filter: Only keep records exactly on the hour for 1h interval
                # This solves the common Yahoo API offset problem
                if self.interval == "1h" and ts % 3600 != 0:
                    continue
                
                close_price = quotes['close'][i]
                if close_price is None:
                    continue
                
                # Map to ODS structure. All values coerced to string for VARCHAR2 storage.
                extracted_records.append({
                    "CODE": ticker,
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

        except Exception as e:
            logger.error(f"Error processing Yahoo data for {symbol}: {e}")
            return None

# ==============================================================================
# Concrete Implementations (The "Plugins")
# ==============================================================================

class YahooPreScraper(YahooBase):
    """
    Identity: Pre-Close OHLCV.
    Maps to 'price_ohlcv_pre' in config.yaml.
    """
    scraper_name = "price_ohlcv_pre"

class YahooPostScraper(YahooBase):
    """
    Identity: Post-Close OHLCV.
    Maps to 'price_ohlcv_post' in config.yaml.
    """
    scraper_name = "price_ohlcv_post"