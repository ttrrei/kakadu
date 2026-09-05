"""Database operator for Oracle-backed ingestion workflows (Pure-INSERT Engine).

Adheres to ADR-005:
- Pure-INSERT (no MERGE INTO)
- Automatic Audit Injection (BATCH_ID, LOAD_TIME)
- Zero-Loss VARCHAR2 Coercion
- Best-effort fallback on batch execution failure
- Optimized for OCI Micro VM (1GB RAM)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import oracledb

# 导入配置加载类
from .config import EnvConfig

logger = logging.getLogger(__name__)


class DbOperator:
    """Singleton Oracle database operator with chunked Pure-INSERT execution."""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DbOperator, cls).__new__(cls)
            # 在单例初始化时加载配置
            cls._instance.config = EnvConfig.load()
        return cls._instance

    def _get_pool(self):
        """Lazily initialize and return the Oracle connection pool."""
        if self._pool is None:
            try:
                logger.info("Initializing Oracle connection pool...")
                # 使用 self.config.database 访问配置项
                pool_kwargs = dict(
                    user=self.config.database.user,
                    password=self.config.database.password,
                    dsn=self.config.database.tns_alias,
                    min=1,
                    max=40,
                    increment=1,
                    wallet_location=self.config.database.wallet_path,
                    config_dir=self.config.database.wallet_path,
                )
                if self.config.database.wallet_password:
                    pool_kwargs["wallet_password"] = self.config.database.wallet_password

                self._pool = oracledb.create_pool(**pool_kwargs)
                logger.info("Oracle connection pool established.")
            except oracledb.Error as exc:
                logger.error(f"Failed to create Oracle connection pool: {exc}")
                raise ConnectionError(f"Database connection failed: {exc}") from exc
        return self._pool

    def get_connection(self):
        """Acquire one connection from the pool."""
        return self._get_pool().acquire()

    def _prepare_records(
        self, records: list[dict[str, Any]], batch_id: str | None = None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Inject audit metadata (BATCH_ID, LOAD_TIME) & coerce all values to string/None."""
        if not records:
            return [], []

        effective_batch_id = batch_id or uuid.uuid4().hex
        load_time_str = datetime.now(timezone.utc).isoformat()

        # Collect union of all keys present in the data
        all_keys = set()
        for r in records:
            all_keys.update(r.keys())

        # Discard caller-supplied audit keys to enforce uniform management
        all_keys.discard("BATCH_ID")
        all_keys.discard("LOAD_TIME")

        # Stable column list: business columns (sorted) + audit columns
        columns = sorted(list(all_keys)) + ["BATCH_ID", "LOAD_TIME"]

        prepared = []
        for r in records:
            row = {}
            for col in columns:
                if col == "BATCH_ID":
                    row[col] = effective_batch_id
                elif col == "LOAD_TIME":
                    row[col] = load_time_str
                else:
                    val = r.get(col)
                    row[col] = None if val is None else str(val)
            prepared.append(row)

        return prepared, columns

    def insert_batch(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        batch_id: str | None = None,
    ) -> str | None:
        """Execute Pure-INSERT operations in small chunks.
        
        Args:
            table_name: Target ODS table.
            records: Raw list of dicts.
            batch_id: Optional custom batch UUID.
        """
        if not records:
            return None

        prepared_records, columns = self._prepare_records(records, batch_id)
        effective_batch_id = prepared_records[0]["BATCH_ID"]

        # Build parameterized INSERT query with double-quoted column names
        cols_sql = ", ".join([f'"{col}"' for col in columns])
        binds_sql = ", ".join([f":{col}" for col in columns])
        sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({binds_sql})"

        # Execute in small chunks
        batch_size = getattr(self.config, "BATCH_SIZE", 10)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for start in range(0, len(prepared_records), batch_size):
                chunk = prepared_records[start : start + batch_size]
                self._execute_chunk(cursor, conn, sql, chunk)
            
            # All chunks processed successfully, commit once
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"Batch insert completely failed for {table_name}: {exc}")
        finally:
            cursor.close()
            self._pool.release(conn)

        return effective_batch_id

    def _execute_chunk(self, cursor, conn, sql: str, chunk: list[dict[str, Any]]) -> None:
        """Execute a chunk and fallback to individual rows on failure."""
        try:
            cursor.executemany(sql, chunk)
        except oracledb.Error as exc:
            logger.warning(f"Chunk failed ({len(chunk)} rows): {exc}. Retrying individually...")
            self._execute_individually(cursor, conn, sql, chunk)

    def _execute_individually(self, cursor, conn, sql: str, chunk: list[dict[str, Any]]) -> None:
        """Best-effort fallback: commit good rows, log and drop bad ones."""
        for row in chunk:
            try:
                cursor.execute(sql, row)
            except oracledb.Error as exc:
                logger.error(f"Dropped record due to DB error: {exc} | Row: {row}")

    def close(self) -> None:
        """Shutdown the connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None
            logger.info("Connection pool closed.")

# Expose singleton instance
db = DbOperator()