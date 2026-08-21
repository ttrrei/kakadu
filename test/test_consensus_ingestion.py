import logging
import sys
import os

# Ensure src is in path for standalone execution
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.db_operator import DbOperator
from src.config import EnvConfig
from src.scrapers.consensus_scraper import ConsensusScraper

# Setup basic logging to see the "Logical Isolation" in action
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_cba_ingestion():
    # 1. Setup
    config = EnvConfig()
    
    # FIX: Initialize DbOperator without config to match your Singleton/Production implementation
    try:
        db = DbOperator() 
    except TypeError:
        # Fallback in case your version actually needs config (unlikely given the error)
        db = DbOperator(config)
    
    scraper = ConsensusScraper(db, config)
    
    test_symbols = ["CBA.AX"] # Change CBA.AX to AAPL
    
    print("\n" + "="*50)
    print("TEST 1: Full Ingestion (Trends + Targets)")
    print("="*50)
    # This should trigger both _handle_recommendations and _handle_targets
    scraper.run(test_symbols)
    
    print("\n" + "="*50)
    print("TEST 2: Filtered Ingestion (Only Recommendations)")
    print("="*50)
    # This verifies the --fields filter logic
    scraper.run(test_symbols, requested_fields=["recommendations"])

    # 2. Verification: Query the DB to see real data
    print("\n" + "="*50)
    print("VERIFICATION: Database Content Check")
    print("="*50)
    
    try:
        # Use the existing connection from DbOperator
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Check Trends
        cursor.execute("SELECT COUNT(*) FROM EQUITY.ODS_ANALYST_TRENDS WHERE CODE = 'CBA.AX'")
        count_trends = cursor.fetchone()[0]
        
        # Check Targets
        cursor.execute("SELECT COUNT(*) FROM EQUITY.ODS_ANALYST_TARGETS WHERE CODE = 'CBA.AX'")
        count_targets = cursor.fetchone()[0]
        
        print(f"CBA.AX Trends records in DB: {count_trends}")
        print(f"CBA.AX Targets records in DB: {count_targets}")
        
        if count_trends > 0 and count_targets > 0:
            print("\n✅ SUCCESS: Real data ingested into both tables.")
        else:
            print("\n❌ FAILURE: Data missing from one or more tables.")
            
        cursor.close()
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    test_cba_ingestion()