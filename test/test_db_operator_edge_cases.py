import sys
from pathlib import Path
import logging
import uuid
from datetime import datetime
from decimal import Decimal

# -------------------------------------------------------------------------
# Path Handling
# -------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.db_operator import DbOperator, InsertResult

# Configure logging to see the internal coercion and error handling
logging.basicConfig(
    level=logging.INFO, 
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def test_db_operator_edge_cases():
    print("\n====================================================")
    print("🛡️ STARTING DB_OPERATOR EDGE CASE & ROBUSTNESS TEST")
    print("====================================================")
    
    db_op = DbOperator()
    test_table = "ODS_PRICE_OHLCV_PRE" # Ensure this table exists in your schema
    
    try:
        # -----------------------------------------------------------------
        # Scenario 1: Audit Lifecycle (SYS_BATCH_LOG)
        # Goal: Verify that batch status can be created and updated without crashing.
        # -----------------------------------------------------------------
        print("\n--- Scenario 1: Audit Lifecycle (SYS_BATCH_LOG) ---")
        test_batch_id = str(uuid.uuid4())
        test_task = "TEST_EDGE_CASE_TASK"
        
        try:
            db_op.create_batch_record(test_batch_id, test_task)
            print(f"✅ Batch record created: {test_batch_id}")
            
            db_op.update_batch_status(test_batch_id, "SUCCESS", "Test completed successfully")
            print(f"✅ Batch status updated to SUCCESS: {test_batch_id}")
        except Exception as e:
            print(f"❌ Audit Lifecycle Failed: {e}")
            # This is a P0 failure because main.py relies on this for every run

        # -----------------------------------------------------------------
        # Scenario 2: Extreme Data Type Coercion
        # Goal: Verify that non-string types (Decimal, datetime, None, float) 
        #       are coerced to strings without triggering TypeErrors.
        # -----------------------------------------------------------------
        print("\n--- Scenario 2: Extreme Data Type Coercion ---")
        complex_records = [
            {
                "CODE": "TYPE1.AX", 
                "CLOSE_PRICE": Decimal("123.456"), # Decimal
                "VOLUME": 10000,                   # Int
                "EXTRA_COL": datetime.now()        # Datetime object
            },
            {
                "CODE": "TYPE2.AX", 
                "CLOSE_PRICE": None,              # NoneType
                "VOLUME": float('nan'),            # NaN float
                "EXTRA_COL": "Standard String"
            }
        ]
        
        try:
            # We use a specific batch_id to track this
            res = db_op.insert_batch(test_table, complex_records, batch_id=str(uuid.uuid4()))
            if res.is_fully_successful:
                print("✅ Complex types coerced and inserted successfully.")
            else:
                print(f"⚠️ Some records dropped: {res.dropped_count}. Check logs.")
        except Exception as e:
            print(f"❌ Coercion Failed: {e}")

        # -----------------------------------------------------------------
        # Scenario 3: Empty Dataset Handling
        # Goal: Ensure passing an empty list doesn't cause IndexError in _prepare_records.
        # -----------------------------------------------------------------
        print("\n--- Scenario 3: Empty Dataset Handling ---")
        try:
            empty_records = []
            res = db_op.insert_batch(test_table, empty_records)
            if res.attempted_count == 0 and res.inserted_count == 0:
                print("✅ Empty list handled gracefully. Result: Attempted=0, Inserted=0")
            else:
                print(f"❌ Unexpected result for empty list: {res}")
        except Exception as e:
            print(f"❌ Empty dataset caused crash: {e}")

        # -----------------------------------------------------------------
        # Scenario 4: Column Mismatch / Extra Columns
        # Goal: Verify that if a record has columns not in the table, 
        #       it is dropped during fallback without crashing the whole batch.
        # -----------------------------------------------------------------
        print("\n--- Scenario 4: Column Mismatch (Invalid Column) ---")
        mismatch_records = [
            {"CODE": "GOOD.AX", "CLOSE_PRICE": "10.0"},
            {"CODE": "BAD.AX", "NON_EXISTENT_COLUMN": "Oops"}, # This should trigger ORA error
        ]
        
        try:
            res = db_op.insert_batch(test_table, mismatch_records)
            if res.dropped_count > 0 and res.inserted_count > 0:
                print(f"✅ Correctly handled mismatch: Inserted={res.inserted_count}, Dropped={res.dropped_count}")
            else:
                print(f"⚠️ Unexpected result: Inserted={res.inserted_count}, Dropped={res.dropped_count}")
        except Exception as e:
            print(f"❌ Column mismatch caused crash: {e}")

    except Exception as e:
        print(f"💥 UNEXPECTED CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_op.close()
        logger.info("Connection pool shut down.")

    print("\n====================================================")
    print("✅ EDGE CASE TEST COMPLETE")
    print("====================================================")

if __name__ == "__main__":
    test_db_operator_edge_cases()