# tests/test_short_scraper.py
import pytest
from unittest.mock import patch, MagicMock
from src.scrapers.short_scraper import ShortPositionScraper

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def scraper(mock_db):
    return ShortPositionScraper(db_op=mock_db)

def test_scrape_all_success(scraper):
    # Mock CSV content
    mock_csv = """Product,Product Code,Reported Short Positions,Total Product in Issue,% of Total Product in Issue Reported as Short Positions
3D ENERGI LTD ORDINARY,TDO,181029,524226804,.03453257
4DMEDICAL LIMITED ORDINARY,4DX,70928934,599638859,11.82860866"""

    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_csv
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        results = scraper.scrape_all(driver=None, symbols=[])

        assert len(results) == 2
        assert results[0]["CODE"] == "TDO"
        assert results[0]["PRODUCT_NAME"] == "3D ENERGI LTD ORDINARY"
        assert results[1]["SHORT_POSITIONS"] == "70928934"
        assert float(results[1]["SHORT_PERCENT"]) > 10.0

def test_scrape_all_failure(scraper):
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection error")
        
        results = scraper.scrape_all(driver=None, symbols=[])
        
        assert results == []
