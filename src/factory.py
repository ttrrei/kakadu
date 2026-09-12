from typing import Type, Dict
import logging

from .scrapers.afr_scraper import AfrScraper
from .scrapers.annc_scraper import AnncScraper
from .scrapers.consensus_scraper import ConsensusTrendsScraper, ConsensusTargetsScraper
from .scrapers.list_scraper import ListScraper
from .scrapers.short_scraper import ShortPositionScraper
from .scrapers.yahoo_scraper import YahooPreScraper, YahooPostScraper
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ScraperFactory:
    """
    ScraperFactory implements the Factory Pattern to decouple the orchestration 
    layer (main.py) from specific scraper implementations.
    
    Adheres to the Open-Closed Principle: new scrapers can be added by 
    updating the _SCRAPER_MAP without changing the get_scraper logic.
    """

    # Private mapping of task names (scraper_name) to Scraper Classes
    # Note: We map to the CLASS, not an instance, to allow main.py 
    # to control instantiation (e.g., passing different db_operators).
    _SCRAPER_MAP: Dict[str, Type[BaseScraper]] = {
        "afr": AfrScraper,
        "annc": AnncScraper,
        "analyst_trends": ConsensusTrendsScraper,
        "analyst_targets": ConsensusTargetsScraper,
        "company_master": ListScraper,
        "short": ShortPositionScraper,
        "price_ohlcv_pre": YahooPreScraper,
        "price_ohlcv_post": YahooPostScraper,
    }

    @classmethod
    def get_scraper(cls, task_name: str) -> Type[BaseScraper]:
        """
        Returns the Scraper class associated with the given task name.
        
        Args:
            task_name: The identifier used in config.yaml (e.g., 'annc', 'afr')
            
        Returns:
            The Scraper class (uninstantiated).
            
        Raises:
            ValueError: If the task_name is not recognized.
        """
        scraper_class = cls._SCRAPER_MAP.get(task_name)
        
        if not scraper_class:
            available_tasks = ", ".join(cls._SCRAPER_MAP.keys())
            error_msg = f"Unknown task '{task_name}'. Available tasks are: [{available_tasks}]"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return scraper_class

# For convenience, we can expose the method directly or use the class
get_scraper = ScraperFactory.get_scraper