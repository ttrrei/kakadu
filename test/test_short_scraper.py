# tests/test_short_scraper.py
import pytest
import logging
from unittest.mock import patch, MagicMock
from src.scrapers.short_scraper import ShortPositionScraper
from src.db_operator import db as db_operator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def scraper(mock_db):
    return ShortPositionScraper(db_op=mock_db)

# =============================================================================
# UNIT TESTS (Mocked)
# =============================================================================

def test_scrape_all_success(scraper):
    """
    Unit Test: Verify basic parsing logic with standard CSV content.
    """
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
        assert isinstance(results[0]["CODE"], str)
        assert results[0]["CODE"] == "TDO"
        assert results[1]["SHORT_POSITIONS"] == "70928934"
        assert results[1]["SHORT_PERCENT"] == "11.82860866"

def test_scrape_all_with_commas_and_empty_values(scraper):
    """
    Unit Test: Verify that commas are removed and empty values are handled as empty strings.
    """
    # Note: Fields with commas must be quoted in CSV to be parsed as a single column
    mock_csv = """Product,Product Code,Reported Short Positions,Total Product in Issue,% of Total Product in Issue Reported as Short Positions
COMMA CORP,COM,"1,234,567","10,000,000",1.23
EMPTY CORP,EMP,,,0.0"""

    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_csv
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        results = scraper.scrape_all(driver=None, symbols=[])

        # Test comma removal
        assert results[0]["SHORT_POSITIONS"] == "1234567"
        assert results[0]["TOTAL_SHARES"] == "10000000"
        
        # Test empty value handling
        assert results[1]["SHORT_POSITIONS"] == ""
        assert results[1]["TOTAL_SHARES"] == ""
        assert results[1]["SHORT_PERCENT"] == "0.0"

def test_scrape_all_failure(scraper):
    """
    Unit Test: Verify that the scraper returns an empty list on request failure.
    """
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection error")
        results = scraper.scrape_all(driver=None, symbols=[])
        assert results == []

# =============================================================================
# INTEGRATION TEST (Real Network & Database)
# =============================================================================

def test_end_to_end_integration():
    """
    Integration Test: Real API -> Parse -> DbOperator -> Oracle.
    Running this test will actually import data into ODS_SHORT_POSITIONS.
    """
    # Initialize scraper with the real db_operator singleton
    scraper = ShortPositionScraper(db_op=db_operator)
    
    conn = None
    try:
        logger.info("Starting End-to-End Integration Test for ShortPositionScraper...")
        
        # 1. Trigger the full pipeline using BaseScraper's _run_bulk method
        # This will call scrape_all() and then insert the results into the DB
        scraper._run_bulk([], "ODS_SHORT_POSITIONS")
        
        # 2. Verify the database contains records
        conn = db_operator.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM EQUITY.ODS_SHORT_POSITIONS")
        count = cursor.fetchone()[0]
        cursor.close()
        
        assert count > 0, "Database should contain records after bulk import"
        logger.info(f"✅ Integration test PASSED: {count} records found in ODS_SHORT_POSITIONS")
        
    except Exception as e:
        pytest.fail(f"Integration test FAILED: {e}")
    finally:
        if conn:
            db_operator._pool.release(conn)