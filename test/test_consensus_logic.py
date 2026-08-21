import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.scrapers.consensus_scraper import ConsensusScraper

class TestConsensusLogic(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_config = MagicMock()
        self.scraper = ConsensusScraper(self.mock_db, self.mock_config)

    def test_field_isolation_on_failure(self):
        mock_ticker = MagicMock()
        # Mock recommendations to return data
        mock_ticker.recommendations = MagicMock()
        mock_ticker.recommendations.empty = False
        mock_ticker.recommendations.iterrows.return_value = [("2023-01-01", {"strongBuy": 10})]
        
        with patch('yfinance.Ticker', return_value=mock_ticker):
            with patch.object(ConsensusScraper, '_handle_targets', side_effect=Exception("Yahoo API Crash")):
                self.scraper.run(["CBA.AX"])
                
                # Use ANY for the second argument to avoid strict list/dict comparison
                self.mock_db.insert_batch.assert_any_call("ODS_ANALYST_TRENDS", ANY)

    def test_field_filtering(self):
        mock_ticker = MagicMock()
        with patch('yfinance.Ticker', return_value=mock_ticker):
            with patch.object(ConsensusScraper, '_handle_targets') as mock_target_handler:
                self.scraper.run(["CBA.AX"], requested_fields=["recommendations"])
                mock_target_handler.assert_not_called()

if __name__ == '__main__':
    unittest.main()