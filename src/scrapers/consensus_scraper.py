import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import yfinance as yf
import pandas as pd

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ConsensusScraper(BaseScraper):
    """
    Scraper for Analyst Consensus data using Yahoo Finance API.
    
    Implements 'Logical Isolation' where Trends and Targets are treated as 
    independent tasks within a single job to prevent fragile fields from 
    blocking stable ones.
    """

    # Map field names to their specific handler methods and target ODS tables
    FIELD_CONFIG = {
        "recommendations": {
            "handler": "_handle_recommendations",
            "table": "ODS_ANALYST_TRENDS"
        },
        "analyst_price_targets": {
            "handler": "_handle_targets",
            "table": "ODS_ANALYST_TARGETS"
        }
    }

    def __init__(self, db_operator, config):
        # BaseScraper.__init__ typically assigns the db_operator to self.db
        super().__init__(db_operator) 
        self.config = config
        self.is_bulk_task = False  # Iterative mode: fetch per symbol

    # =========================================================================
    # BaseScraper Contract Implementations
    # =========================================================================
    def scrape_all(self, symbols: List[str]):
        """Implementation of BaseScraper abstract method."""
        self.run(symbols)

    def scrape_one(self, symbol: str):
        """Implementation of BaseScraper abstract method."""
        self.run([symbol])

    # =========================================================================
    # Core Logic
    # =========================================================================
    def run(self, symbols: List[str], requested_fields: Optional[List[str]] = None):
        """
        Main orchestration logic.
        :param symbols: List of tickers to fetch.
        :param requested_fields: Optional list to filter which fields to scrape.
        """
        # Temporal Alignment: Single timestamp for the entire job run
        job_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Determine which fields to execute
        fields_to_run = requested_fields if requested_fields else list(self.FIELD_CONFIG.keys())
        
        logger.info(f"Starting Consensus job. Fields: {fields_to_run}. Symbols: {len(symbols)}")

        for symbol in symbols:
            try:
                # Initialize Ticker object once per symbol to minimize network overhead
                ticker = yf.Ticker(symbol)
                
                # Logical Isolation: Iterate through requested fields independently
                for field_name in fields_to_run:
                    if field_name not in self.FIELD_CONFIG:
                        logger.warning(f"Unknown field requested: {field_name}. Skipping.")
                        continue
                    
                    config_item = self.FIELD_CONFIG[field_name]
                    handler_name = config_item["handler"]
                    table_name = config_item["table"]
                    handler = getattr(self, handler_name)
                    
                    try:
                        # Execute field-specific extraction
                        records = handler(ticker, symbol, job_timestamp)
                        
                        if records:
                            # Pure-INSERT into the specific ODS table using self.db from BaseScraper
                            self.db.insert_batch(table_name, records)
                            logger.info(f"Successfully ingested {len(records)} records for {symbol} -> {table_name}")
                        else:
                            logger.info(f"No data found for {symbol} field {field_name}")
                            
                    except Exception as e:
                        # Field-level failure: Log and continue to next field
                        logger.error(f"Field-level failure [{field_name}] for {symbol}: {str(e)}")
                        
            except Exception as e:
                # Ticker-level failure: Log and continue to next symbol
                logger.error(f"Ticker-level failure for {symbol}: {str(e)}")

    def _handle_recommendations(self, ticker: yf.Ticker, symbol: str, timestamp: str) -> List[Dict[str, Any]]:
        """
        Handles 'recommendations' (recommendationTrend).
        Input: pandas.DataFrame
        Output: List of records for ODS_ANALYST_TRENDS
        """
        try:
            df = ticker.recommendations
            if df is None or df.empty:
                return []

            records = []
            # The index is usually the date
            for date, row in df.iterrows():
                records.append({
                    "CODE": symbol,
                    "MONTH_DATE": str(date),
                    "STRONG_BUY": str(row.get("strongBuy", "")),
                    "BUY": str(row.get("buy", "")),
                    "HOLD": str(row.get("hold", "")),
                    "SELL": str(row.get("sell", "")),
                    "STRONG_SELL": str(row.get("strongSell", "")),
                })
            return records
        except Exception as e:
            # Re-raise to be caught by the field-level try-except in run()
            raise RuntimeError(f"Error processing recommendations: {e}")

    def _handle_targets(self, ticker: yf.Ticker, symbol: str, timestamp: str) -> List[Dict[str, Any]]:
        """
        Handles Analyst Price Targets.
        Updated to use the latest yfinance key naming convention found via diagnostics.
        """
        try:
            info = ticker.info
            
            # Yahoo Finance now provides these as top-level keys in the info dict
            target_low = info.get("targetLowPrice")
            target_high = info.get("targetHighPrice")
            target_mean = info.get("targetMeanPrice")
            target_median = info.get("targetMedianPrice")

            # If all are missing, then there is truly no data for this ticker
            if target_low is None and target_high is None and target_mean is None and target_median is None:
                return []

            # Return as a list containing a single record (snapshot)
            return [{
                "CODE": symbol,
                "TARGET_LOW": str(target_low) if target_low is not None else "",
                "TARGET_HIGH": str(target_high) if target_high is not None else "",
                "TARGET_MEAN": str(target_mean) if target_mean is not None else "",
                "TARGET_MEDIAN": str(target_median) if target_median is not None else "",
            }]
        except Exception as e:
            # Re-raise to be caught by the field-level try-except in run()
            raise RuntimeError(f"Error processing price targets: {e}")