"""
Symbol Provider for Kakadu System
Implements centralized symbol sourcing for iterative scrapers per ADR-012
"""

import re
import logging
from typing import Iterator, Optional
from src.db_operator import DbOperator
from src.config import EnvConfig

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
        self.config = EnvConfig.load()
        self.db_operator = db_operator or DbOperator()
        
        # Compile regex pattern for symbol validation
        # Allows alphanumeric characters, dots, and hyphens, ending with .AX
        self._symbol_pattern = re.compile(r'^[A-Z0-9.\-]+\.AX$')
        
        # Load filtering configuration from the config object
        # Note: Assuming EnvConfig.load() returns an object where we can access 
        # symbol_filter if it's defined in config.yaml. 
        # If EnvConfig is strictly for .env, this part might need adjustment to read config.yaml.
        self._load_filter_config()
    
    def _load_filter_config(self):
        """Load symbol filtering configuration."""
        # Attempt to get filter config from the loaded configuration
        # Since EnvConfig might be a simple object, we use getattr or check for a dict
        filter_cfg = getattr(self.config, 'symbol_filter', {})
        if not isinstance(filter_cfg, dict):
            filter_cfg = {}

        self._excluded_symbols = set(filter_cfg.get('excluded_symbols', []))
        self._included_symbols = set(filter_cfg.get('included_symbols', []))
        self._use_included_only = bool(self._included_symbols)
    
    def get_target_symbols(self) -> Iterator[str]:
        """
        Fetch symbols as a generator from ODS_COMPANY_MASTER via DbOperator.
        
        Yields:
            str: Validated symbol strings one at a time (O(1) memory usage)
        """
        conn = None
        cursor = None
        try:
            # Query to get symbols from ODS_COMPANY_MASTER
            query = "SELECT CODE FROM ODS_COMPANY_MASTER WHERE CODE IS NOT NULL AND TRIM(CODE) != ''"
            
            conn = self.db_operator.get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            # Fetch one row at a time to maintain O(1) memory usage
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                
                symbol = str(row[0]).strip().upper() if row[0] is not None else None
                
                if not symbol:
                    continue
                
                # Apply inclusion/exclusion filters
                if not self._passes_filters(symbol):
                    continue
                
                # Validate symbol format
                if not self._is_valid_symbol(symbol):
                    logger.warning(f"Skipping invalid symbol format: {symbol}")
                    continue
                
                yield symbol
                
        except Exception as e:
            logger.error(f"Failed to retrieve symbols from ODS_COMPANY_MASTER: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                # Return connection to the pool via the pool's release method
                # DbOperator uses a pool, so we must release it.
                self.db_operator._pool.release(conn)
    
    def _passes_filters(self, symbol: str) -> bool:
        """Check if symbol passes configured filters."""
        if self._use_included_only and symbol not in self._included_symbols:
            return False
            
        if symbol in self._excluded_symbols:
            return False
            
        return True
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """Validate symbol format (must end with .AX and be alphanumeric)."""
        if not self._symbol_pattern.match(symbol):
            return False
            
        if len(symbol) <= 3:  # Minimum valid: "A.AX"
            return False
            
        return True

def get_symbol_provider() -> SymbolProvider:
    """Factory function to get a SymbolProvider instance."""
    return SymbolProvider()

def get_target_symbols_generator() -> Iterator[str]:
    """Simple generator function that yields symbols from ODS_COMPANY_MASTER."""
    provider = SymbolProvider()
    yield from provider.get_target_symbols()