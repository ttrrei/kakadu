# test/test_list_scraper.py
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.list_scraper import ListScraper
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestListScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = ListScraper()

    @patch('src.scrapers.list_scraper.requests.get')
    def test_scrape_all_logic_with_mock(self, mock_get):
        """Unit Test: Verify that the scraper correctly parses CSV content."""
        mock_response = MagicMock()
        mock_csv_content = (
            '"ASX code","Company name","GICs industry group","Listing date","Market Cap"\n'
            '"CBA","Commonwealth Bank","Financials","1991-09-12",289040418474\n'
            '"4DS","4DS Memory","Semiconductors","2010-12-09","--"'
        )
        mock_response.text = mock_csv_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = self.scraper.scrape_all(None, [])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["CODE"], "CBA")
        self.assertIsNone(results[1]["MARKET_CAP"])
        logger.info("✅ Mock API parsing test PASSED")

    def test_end_to_end_integration(self):
        """Integration Test: API -> Parse -> DbOperator -> Oracle with BATCH_ID verification."""
        conn = None
        try:
            logger.info("Starting End-to-End Integration Test for ListScraper...")
            
            # 1. 使用真实的 db_operator
            real_scraper = ListScraper(db_op=db_operator)
            
            # 2. 定义参数
            target_table = "EQUITY.ODS_COMPANY_MASTER"
            job_name = "TEST_LIST_E2E"
            
            # 3. 执行全链路 (注意这里现在传递 job_name)
            real_scraper.run([], target_table, job_name)
            
            # 4. 验证 BATCH_ID 匹配的数据是否存在
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            sql = f"SELECT COUNT(*) FROM {target_table} WHERE BATCH_ID = :bid"
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain records for {job_name}")
            logger.info(f"✅ Integration test PASSED: {count} records found in {target_table}")
        except Exception as e:
            self.fail(f"Integration test FAILED: {e}")
        finally:
            if conn:
                db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()