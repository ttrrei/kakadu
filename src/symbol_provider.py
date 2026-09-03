# src/symbol_provider.py
"""
Symbol Provider for Kakadu System
Implements centralized symbol sourcing for iterative scrapers per ADR-012
"""

import re
import logging
from typing import Iterator, Optional
from src.db_operator import DbOperator
from src.config import config

logger = logging.getLogger(__name__)

class SymbolProvider:
    """
    Centralized Symbol Provider that fetches symbols as a generator from a specified table.
    
    Ensures O(1) memory usage by yielding symbols one at a time.
    """
    
    def __init__(self, db_operator: Optional[DbOperator] = None, source_table: str = None):
        """
        Initialize SymbolProvider.
        
        Args:
            db_operator: Optional DbOperator dependency.
            source_table: The table to fetch symbols from. MUST be provided.
        """
        self.config = config 
        self.db_operator = db_operator or DbOperator()
        
        # --- 强制校验：必须提供 source_table ---
        if not source_table:
            raise KeyError("SymbolProvider requires 'source_table' to be explicitly provided.")
            
        self._source_table = source_table
        self._symbol_pattern = None
        
        # Load filtering configuration (Global filters are still used for validation)
        self._load_filter_config()
    
    def _load_filter_config(self):
        """Load symbol filtering configuration from global symbol_filter in config.yaml."""
        filter_cfg = self.config.get('symbol_filter', {})
        
        if not isinstance(filter_cfg, dict):
            filter_cfg = {}

        # 1. Inclusion/Exclusion lists
        self._excluded_symbols = set(filter_cfg.get('excluded_symbols', []))
        self._included_symbols = set(filter_cfg.get('included_symbols', []))
        self._use_included_only = bool(self._included_symbols)
        
        # 2. Suffix Configuration (e.g., '.AX')
        self._required_suffix = filter_cfg.get('require_suffix', '.AX')
        
        # 3. Dynamic Regex
        escaped_suffix = re.escape(self._required_suffix)
        self._symbol_pattern = re.compile(rf'^[A-Z0-9.\-]+{escaped_suffix}$')
    
    def get_target_symbols(self) -> Iterator[str]:
        """
        Fetch symbols as a generator from the configured source table.
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
                
                # 1. Apply filters
                if not self._passes_filters(symbol):
                    continue
                
                # 2. Dynamic Suffix Completion
                formatted_symbol = symbol
                if not symbol.endswith(self._required_suffix):
                    formatted_symbol = f"{symbol}{self._required_suffix}"
                
                # 3. Final Validation
                if not self._is_valid_symbol(formatted_symbol):
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
        if self._use_included_only and symbol not in self._included_symbols:
            return False
        if symbol in self._excluded_symbols:
            return False
        return True
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        if not self._symbol_pattern.match(symbol):
            return False
        if len(symbol) < 4: 
            return False
        return True