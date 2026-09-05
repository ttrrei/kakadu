# test_db_direct.py
from src.symbol_provider import SymbolProvider
from src.db_operator import DbOperator
import logging

logging.basicConfig(level=logging.INFO)

def test_direct_fetch():
    print("--- Starting Direct DB Fetch Test ---")
    try:
        db_op = DbOperator()
        provider = SymbolProvider(db_operator=db_op)
        
        symbols = list(provider.get_target_symbols())
        print(f"Symbols found: {symbols}")
        print(f"Total count: {len(symbols)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_direct_fetch()