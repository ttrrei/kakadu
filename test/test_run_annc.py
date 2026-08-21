# test/test_run_annc.py
import logging
import sys
import os

# 确保 src 目录在路径中 (如果不用 python -m 运行，这行很重要)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.annc_scraper import AnncScraper
from src.db_operator import db as db_operator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_real_annc_import():
    """
    验证真实 URL 的抓取和导入链路
    """
    scraper = AnncScraper()
    urls = {
        "PREV_DAY": "https://www.asx.com.au/asx/v2/statistics/prevBusDayAnns.do",
        "TODAY": "https://www.asx.com.au/asx/v2/statistics/todayAnns.do"
    }
    target_table = "ODS_MARKET_ANNC"
    
    try:
        driver = scraper.get_driver()
        total_imported = 0
        
        for job_type, url in urls.items():
            logger.info(f"Testing {job_type} URL: {url}")
            driver.get(url)
            
            data = scraper.scrape_all(driver)
            if data:
                import datetime
                today_str = datetime.datetime.now().strftime("%Y%m%d")
                batch_id = f"TEST_REAL_{job_type}_{today_str}"
                
                db_operator.insert_batch(target_table, data, batch_id=batch_id)
                total_imported += len(data)
                logger.info(f"✅ Successfully imported {len(data)} records for {job_type}")
            else:
                logger.warning(f"⚠️ No data found for {job_type}")
        
        # 验证结果
        if total_imported > 0:
            logger.info(f"🚀 ALL TESTS PASSED: Total {total_imported} real records imported.")
        else:
            logger.error("❌ TEST FAILED: No data was imported from either URL.")
            
    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE: {e}")
        raise e
    finally:
        if scraper._driver:
            scraper._driver.quit()

if __name__ == "__main__":
    test_real_annc_import()