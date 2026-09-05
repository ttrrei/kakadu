# src/symbol_provider.py
"""
Symbol Provider for Kakadu System
Implements centralized symbol sourcing for iterative scrapers.
Per ADR-016, all business filtering is pushed down to the database layer (Views).
"""

import logging
from typing import Iterator, Optional
from src.db_operator import DbOperator

logger = logging.getLogger(__name__)

class SymbolProvider:
    """
    Centralized Symbol Provider that fetches symbols as a generator from a specified 
    database object (Table or View).
    
    Ensures O(1) memory usage by yielding symbols one at a time.
    """
    
    def __init__(self, db_operator: Optional[DbOperator] = None, source_table: str = None):
        """
        Initialize SymbolProvider.
        
        Args:
            db_operator: Optional DbOperator dependency.
            source_table: The DB object (Table/View) to fetch symbols from. MUST be provided.
        """
        self.db_operator = db_operator or DbOperator()
        
        # --- 强制校验：必须提供 source_table (现在通常是视图名) ---
        if not source_table:
            raise KeyError("SymbolProvider requires 'source_table' (or View name) to be explicitly provided.")
            
        self._source_table = source_table
        self._required_suffix = ".AX" # 保持作为 API 适配的硬编码标准
    
    def get_target_symbols(self) -> Iterator[str]:
        """
        Fetch symbols as a generator from the configured source.
        The source is expected to be a View that already handles all business filtering.
        """
        conn = None
        cursor = None
        try:
            # 极简查询：假设视图只返回 CODE 列
            query = f"SELECT CODE FROM {self._source_table} WHERE CODE IS NOT NULL"
            logger.info(f"SymbolProvider: Fetching symbols from {self._source_table}")
            
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
                raw_symbol = str(row[0]).strip().upper() if row[0] is not None else None
                
                if not raw_symbol:
                    continue
                
                # --- 鲁棒性格式化逻辑 ---
                # 目标：统一将 "CBA", "CBA.AX", "CBA .AX" 全部转换为 "CBA.AX"
                
                # 1. 提取主体 (Base Symbol)
                if raw_symbol.endswith(self._required_suffix):
                    # 如果已有后缀，去掉后缀并再次 strip() 掉主体末尾的空格
                    base_symbol = raw_symbol[:-len(self._required_suffix)].strip()
                else:
                    # 如果没有后缀，直接 strip()
                    base_symbol = raw_symbol.strip()
                
                # 2. 统一拼接后缀
                formatted_symbol = f"{base_symbol}{self._required_suffix}"
                # -----------------------
                
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