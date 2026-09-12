import unittest
import sys
import os

# --- Path Fix: Ensure project root is in sys.path ---
# This allows the test to find the 'src' module regardless of where it's called from
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.factory import ScraperFactory
from src.base_scraper import BaseScraper
from src.scrapers.afr_scraper import AfrScraper
from src.scrapers.annc_scraper import AnncScraper
from src.scrapers.consensus_scraper import ConsensusTrendsScraper, ConsensusTargetsScraper
from src.scrapers.list_scraper import ListScraper
from src.scrapers.short_scraper import ShortPositionScraper
from src.scrapers.yahoo_scraper import YahooPreScraper, YahooPostScraper

class TestScraperFactory(unittest.TestCase):
    """
    Test suite for ScraperFactory.
    Ensures correct class mapping, error handling, and inheritance consistency.
    """

    def test_get_valid_scraper(self):
        """
        Positive Test: Verify that valid task names return the correct Class.
        """
        # Test a few key mappings
        test_cases = [
            ("afr", AfrScraper),
            ("annc", AnncScraper),
            ("company_master", ListScraper),
            ("price_ohlcv_pre", YahooPreScraper),
        ]

        for task_name, expected_class in test_cases:
            with self.subTest(task=task_name):
                result = ScraperFactory.get_scraper(task_name)
                # CRITICAL: Verify it returns the CLASS, not an instance
                self.assertEqual(result, expected_class, f"Task {task_name} should map to {expected_class}")
                self.assertTrue(isinstance(result, type), f"Result for {task_name} should be a type (class)")

    def test_get_invalid_scraper(self):
        """
        Negative Test: Verify that unknown tasks raise ValueError with a helpful message.
        """
        invalid_task = "unknown_task_123"
        
        with self.assertRaises(ValueError) as cm:
            ScraperFactory.get_scraper(invalid_task)
        
        exception_msg = str(cm.exception)
        
        # Verify the error message contains the invalid task name
        self.assertIn(invalid_task, exception_msg)
        
        # Verify the error message contains the list of available tasks
        self.assertIn("afr", exception_msg)
        self.assertIn("annc", exception_msg)
        self.assertIn("short", exception_msg)

    def test_all_scrapers_inherit_base(self):
        """
        Consistency Test: Ensure every class in the factory map inherits from BaseScraper.
        """
        # Access the private map for validation
        scraper_map = ScraperFactory._SCRAPER_MAP
        
        for task_name, scraper_class in scraper_map.items():
            with self.subTest(task=task_name):
                self.assertTrue(
                    issubclass(scraper_class, BaseScraper), 
                    f"Scraper class for '{task_name}' ({scraper_class.__name__}) must inherit from BaseScraper"
                )

if __name__ == "__main__":
    unittest.main()