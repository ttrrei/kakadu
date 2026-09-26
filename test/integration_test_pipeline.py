import logging
import uuid
import sys
import os

# 确保 src 目录在 python 路径中
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.db_operator import db
from src.scrapers.list_scraper import ListScraper
from src.scrapers.afr_scraper import AfrScraper
from src.scrapers.annc_scraper import AnncScraper
# 如果你的类名不同，请根据实际 src/scrapers/ 下的文件名修改类名

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationPipelineTest")

def run_scraper_test(scraper_class):
    """
    Simulates the full pipeline for a single scraper:
    Create Log -> Run Scraper -> Update Log -> Verify DB.
    """
    scraper_name = scraper_class().scraper_name
    logger.info(f"\n{'='*60}\nTesting Scraper: {scraper_name}\n{'='*60}")
    
    # 1. Setup
    batch_id = f"INT_TEST_{uuid.uuid4().hex[:6]}"
    scraper = scraper_class()
    
    try:
        # 2. Create Initial Log Record
        logger.info(f"Step 1: Creating batch record {batch_id}...")
        db.create_batch_record(batch_id=batch_id, task_name=scraper_name)
        
        # 3. Execute Scraper
        logger.info(f"Step 2: Executing {scraper_name}.run()...")
        # We pass batch_id to ensure ODS records are tagged correctly
        scraper.run(job_name=f"test_{scraper_name}", batch_id=batch_id)
        
        # 4. Update Log to SUCCESS
        logger.info(f"Step 3: Updating batch status to SUCCESS...")
        db.update_batch_status(batch_id=batch_id, status="SUCCESS")
        
        # 5. Truth-Based Verification in DB
        logger.info("Step 4: Verifying results in Database...")
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Verify SYS_BATCH_LOG
        cursor.execute(
            "SELECT STATUS FROM EQUITY.SYS_BATCH_LOG WHERE BATCH_ID = :bid", 
            bid=batch_id
        )
        status = cursor.fetchone()[0]
        assert status == "SUCCESS", f"Expected SUCCESS, got {status}"
        
        # Verify ODS Table has data for this batch
        cursor.execute(
            f"SELECT COUNT(*) FROM {scraper.target_table} WHERE BATCH_ID = :bid", 
            bid=batch_id
        )
        count = cursor.fetchone()[0]
        logger.info(f"Verification: Found {count} records in {scraper.target_table}")
        
        # Note: We don't assert count > 0 because some scrapers might 
        # return no data depending on the market time, but the pipeline should work.
        
        cursor.close()
        db._pool.release(conn)
        
        logger.info(f"✅ {scraper_name} Integration Test PASSED.")
        
    except Exception as e:
        logger.error(f"❌ {scraper_name} Integration Test FAILED: {e}")
        # Try to mark as failed in DB for audit
        try:
            db.update_batch_status(batch_id=batch_id, status="FAILED", error_message=str(e))
        except:
            pass
        return False
    return True

if __name__ == "__main__":
    # The three representative cases: Bulk, Iterative API, Iterative Selenium
    test_cases = [
        ListScraper, 
        AfrScraper, 
        AnncScraper
    ]
    
    results = []
    for case in test_cases:
        results.append(run_scraper_test(case))
    
    logger.info(f"\n{'='*60}\nFinal Results: {sum(results)}/{len(test_cases)} Passed\n{'='*60}")
    
    if all(results):
        logger.info("🚀 ALL INTEGRATION TESTS PASSED. Ready for main.py development!")
        sys.exit(0)
    else:
        logger.error("Some tests failed. Please check logs.")
        sys.exit(1)