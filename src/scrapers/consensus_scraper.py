# src/scrapers/consensus_scraper.py
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Union
import yfinance as yf

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ConsensusBase(BaseScraper):
    """
    Internal base class for Analyst Consensus logic.
    Implements common settings for all consensus-related scrapers.
    """
    # Define as class attributes to avoid overriding BaseScraper.__init__
    # This ensures self.db is correctly initialized to the db_operator singleton
    is_bulk_task = False
    needs_driver = False

    def scrape_all(self, driver: Optional[Any], symbols: List[str]) -> List[Dict[str, Any]]:
        """Consensus scrapers are strictly iterative."""
        raise NotImplementedError("Consensus scrapers operate in Iterative Mode only.")

# ==============================================================================
# Concrete Implementations
# ==============================================================================

class ConsensusTrendsScraper(ConsensusBase):
    """
    Identity: Analyst Recommendation Trends.
    Maps to 'analyst_trends' in config.yaml.
    Target Table: ODS_ANALYST_TRENDS
    """
    scraper_name = "analyst_trends"

    def scrape_one(self, driver: Optional[Any], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Fetches recommendation trends for a single symbol.
        Returns a list of records (One-to-Many).
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.recommendations
            
            if df is None or df.empty:
                logger.info(f"No recommendation trends found for {symbol}")
                return None

            records = []
            # The index of ticker.recommendations is usually the date
            for date, row in df.iterrows():
                records.append({
                    "CODE": symbol.upper(),
                    "MONTH_DATE": str(date),
                    "STRONG_BUY": str(row.get("strongBuy", "")),
                    "BUY": str(row.get("buy", "")),
                    "HOLD": str(row.get("hold", "")),
                    "SELL": str(row.get("sell", "")),
                    "STRONG_SELL": str(row.get("strongSell", "")),
                })
            
            if records:
                logger.info(f"Extracted {len(records)} trend records for {symbol}")
            return records

        except Exception as e:
            logger.error(f"Error processing trends for {symbol}: {e}")
            return None

class ConsensusTargetsScraper(ConsensusBase):
    """
    Identity: Analyst Price Targets.
    Maps to 'analyst_targets' in config.yaml.
    Target Table: ODS_ANALYST_TARGETS
    """
    scraper_name = "analyst_targets"

    def scrape_one(self, driver: Optional[Any], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Fetches analyst price targets for a single symbol.
        Returns a single record snapshot.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            target_low = info.get("targetLowPrice")
            target_high = info.get("targetHighPrice")
            target_mean = info.get("targetMeanPrice")
            target_median = info.get("targetMedianPrice")

            if all(v is None for v in [target_low, target_high, target_mean, target_median]):
                logger.info(f"No price targets found for {symbol}")
                return None

            # Return as a single record snapshot
            return {
                "CODE": symbol.upper(),
                "TARGET_LOW": str(target_low) if target_low is not None else None,
                "TARGET_HIGH": str(target_high) if target_high is not None else None,
                "TARGET_MEAN": str(target_mean) if target_mean is not None else None,
                "TARGET_MEDIAN": str(target_median) if target_median is not None else None,
            }

        except Exception as e:
            logger.error(f"Error processing targets for {symbol}: {e}")
            return None