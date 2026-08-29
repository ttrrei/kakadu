# src/symbol_provider.py
"""
Symbol Provider for Kakadu System
Implements centralized symbol sourcing for iterative scrapers per ADR-012
"""

import re
import logging
from typing import Iterator, Optional
from src.db_operator import DbOperator
from src.config import config  # Unified config object (yaml + env)

logger = logging.getLogger(__name__)

class SymbolProvider:
    """
    Centralized Symbol Provider that fetches symbols as a generator from ODS_COMPANY_MASTER
    via DbOperator, applying config-driven filtering and validation.
    
    Ensures O(1) memory usage by yielding symbols one at a time.
    """
    
    def __init__(self, db_operator: Optional[DbOperator] = None):
        """
        Initialize SymbolProvider with optional DbOperator dependency injection.
        """
        self.config = config 
        self.db_operator = db_operator or DbOperator()
        
        # The regex pattern is defined dynamically in _load_filter_config
        self._symbol_pattern = None
        
        # Load filtering configuration from config.yaml
        self._load_filter_config()
    
    def _load_filter_config(self):
        """Load symbol filtering configuration from config.yaml."""
        filter_cfg = self.config.get('symbol_filter', {})
        
        if not isinstance(filter_cfg, dict):
            filter_cfg = {}

        # 1. Inclusion/Exclusion lists
        self._excluded_symbols = set(filter_cfg.get('excluded_symbols', []))
        self._included_symbols = set(filter_cfg.get('included_symbols', []))
        self._use_included_only = bool(self._included_symbols)
        
        # 2. Suffix Configuration (e.g., '.AX')
        self._required_suffix = filter_cfg.get('require_suffix', '.AX')
        
        # 3. Dynamic Regex: Ensure the symbol ends with the configured suffix
        escaped_suffix = re.escape(self._required_suffix)
        self._symbol_pattern = re.compile(rf'^[A-Z0-9.\-]+{escaped_suffix}$')
        
        # 4. Source Table
        self._source_table = filter_cfg.get('source_table', "ODS_COMPANY_MASTER")
    
    def get_target_symbols(self) -> Iterator[str]:
        """
        Fetch symbols as a generator from the configured source table via DbOperator.
        
        Handles the conversion from DB-clean symbols (e.g., 'CBA') 
        to API-ready symbols (e.g., 'CBA.AX').
        
        Yields:
            str: Validated and formatted symbol strings (O(1) memory usage)
        """
        conn = None
        cursor = None
        try:
            query = f"SELECT CODE FROM {self._source_table} WHERE CODE IS NOT NULL "
            logger.info(f"SymbolProvider: Fetching symbols from {self._source_table} using query: {query}")
            
            conn = self.db_operator.get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            processed_count = 0
            yielded_count = 0
            
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                
                processed_count += 1
                symbol = str(row[0]).strip().upper() if row[0] is not None else None
                
                if not symbol:
                    continue
                
                # 1. Apply inclusion/exclusion filters (on the raw DB symbol)
                if not self._passes_filters(symbol):
                    logger.debug(f"SymbolProvider: Symbol {symbol} filtered out by config.")
                    continue
                
                # 2. Dynamic Suffix Completion
                # If the DB symbol doesn't already have the suffix (e.g., 'CBA' -> 'CBA.AX')
                formatted_symbol = symbol
                if not symbol.endswith(self._required_suffix):
                    formatted_symbol = f"{symbol}{self._required_suffix}"
                
                # 3. Final Validation
                if not self._is_valid_symbol(formatted_symbol):
                    logger.warning(f"SymbolProvider: Skipping invalid symbol format: {formatted_symbol}")
                    continue
                
                yielded_count += 1
                yield formatted_symbol
            
            logger.info(f"SymbolProvider: Finished. DB Rows: {processed_count}, Symbols Yielded: {yielded_count}")
                
        except Exception as e:
            logger.error(f"SymbolProvider: Failed to retrieve symbols from {self._source_table}: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.db_operator._pool.release(conn)
    
    def _passes_filters(self, symbol: str) -> bool:
        """Check if symbol passes configured filters."""
        if self._use_included_only and symbol not in self._included_symbols:
            return False
            
        if symbol in self._excluded_symbols:
            return False
            
        return True
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """Validate symbol format (must match regex and minimum length)."""
        if not self._symbol_pattern.match(symbol):
            return False
            
        if len(symbol) < 4: 
            return False
            
        return True

def get_symbol_provider() -> SymbolProvider:
    """Factory function to get a SymbolProvider instance."""
    return SymbolProvider()

def get_target_symbols_generator() -> Iterator[str]:
    """Simple generator function that yields symbols from the configured source table."""
    provider = SymbolProvider()
    yield from provider.get_target_symbols()