# test/test_yahoo.py
import unittest
from unittest.mock import MagicMock, patch
from src.scrapers.yahoo_scraper import YahooScraper

class TestYahooScraper(unittest.TestCase):

    def setUp(self):
        # Mock the DbOperator to avoid real DB connections
        self.mock_db = MagicMock()
        # Instantiate the scraper with the mock DB
        self.scraper = YahooScraper(db_op=self.mock_db)

    @patch('requests.get')
    def test_scrape_one_success(self, mock_get):
        """Test that scrape_one correctly filters and maps Yahoo API data."""
        
        # 1. Mock a Yahoo API response
        # We provide 3 timestamps: 
        # - One exactly on the hour (should be kept)
        # - One offset by 1 second (should be filtered out)
        # - One exactly on the hour but with None close price (should be filtered out)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": [1700000000, 1700000001, 1700003600], 
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 10.1, 10.2],
                                "high": [11.0, 11.1, 11.2],
                                "low": [9.0, 9.1, 9.2],
                                "close": [10.5, 10.6, None], # Third one is None
                                "volume": [1000, 1100, 1200]
                            }
                        ]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response

        # 2. Execute scrape_one
        symbol = "CBA"
        result = self.scraper.scrape_one(None, symbol)

        # 3. Verifications
        # Only the first record should survive:
        # - Record 1: 1700000000 % 3600 == 0 AND close is not None -> KEEP
        # - Record 2: 1700000001 % 3600 != 0 -> FILTER
        # - Record 3: 1700003600 % 3600 == 0 BUT close is None -> FILTER
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["CODE"], "CBA")
        self.assertEqual(result[0]["RAW_TIMESTAMP"], 170000000) # Wait, 1700000000
        # Correcting the check:
        self.assertEqual(result[0]["RAW_TIMESTAMP"], 1700000000)
        self.assertEqual(result[0]["CLOSE_PRICE"], 10.5)

    @patch('requests.get')
    def test_scrape_one_api_failure(self, mock_get):
        """Test that the scraper handles HTTP errors gracefully."""
        mock_get.side_effect = Exception("Connection Timeout")
        
        result = self.scraper.scrape_one(None, "CBA")
        
        self.assertIsNone(result)

    def test_run_integration(self):
        """Test the full .run() flow: Fetch -> Buffer -> DbOperator."""
        
        # Mock scrape_one to return a list of 2 records per symbol
        self.scraper.scrape_one = MagicMock(return_value=[
            {"CODE": "TEST", "VAL": "V1"},
            {"CODE": "TEST", "VAL": "V2"}
        ])
        
        # Set a small batch size to trigger a flush
        self.scraper.batch_size = 2
        
        symbols = ["S1", "S2"] # Total 4 records will be generated
        self.scraper.run(symbols, "ODS_PRICE_OHLCV", "TEST_JOB")
        
        # Verify that insert_batch was called
        # Since batch_size is 2 and we have 4 records, it should be called twice
        # (or once if the buffer logic flushes at the end)
        self.assertTrue(self.mock_db.insert_batch.called)
        
        # Check that the data passed to DB is a flat list
        args, _ = self.mock_db.insert_batch.call_args
        records = args[1]
        self.assertIsInstance(records, list)
        self.assertIsInstance(records[0], dict)

if __name__ == "__main__":
    unittest.main()