"""Database operator for Oracle-backed ingestion workflows (Pure-INSERT Engine).

Adheres to ADR-005:
- Pure-INSERT (no MERGE INTO)
- Automatic Audit Injection (BATCH_ID, LOAD_TIME)
- Zero-Loss VARCHAR2 Coercion
- Best-effort fallback on batch execution failure (with precise InsertResult tracking)
- Optimized for OCI Micro VM (1GB RAM)

Critical Fixes (per Review & P0 Fix):
- Audit methods now RAISE exceptions (Fail-Fast, Anti-Silent-Failure).
- Connection pool max=5 (Physical memory guardrail).
- insert_batch now returns structured InsertResult (attempted, inserted, dropped) to prevent silent data loss.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

import oracledb

from .config import EnvConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InsertResult:
    """Represents the actual database persistence metrics for a batch insertion."""
    batch_id: str
    attempted_count: int
    inserted_count: int
    dropped_count: int

    @property
    def is_fully_successful(self) -> bool:
        return self.attempted_count > 0 and self.inserted_count == self.attempted_count

    @property
    def has_dropped_records(self) -> bool:
        return self.dropped_count > 0


class DbOperator:
    """Singleton Oracle database operator with chunked Pure-INSERT execution."""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DbOperator, cls).__new__(cls)
            cls._instance.config = EnvConfig.load()
        return cls._instance

    def _get_pool(self):
        """Lazily initialize and return the Oracle connection pool."""
        if self._pool is None:
            try:
                logger.info("Initializing Oracle connection pool (max=5)...")
                pool_kwargs = dict(
                    user=self.config.database.user,
                    password=self.config.database.password,
                    dsn=self.config.database.tns_alias,
                    min=1,
                    max=5,          # 🔴 CRITICAL: Reduced for 1GB VM safety
                    increment=1,
                    wallet_location=self.config.database.wallet_path,
                    config_dir=self.config.database.wallet_path,
                )
                if self.config.database.wallet_password:
                    pool_kwargs["wallet_password"] = self.config.database.wallet_password

                self._pool = oracledb.create_pool(**pool_kwargs)
                logger.info("Oracle connection pool established (max=5).")
            except oracledb.Error as exc:
                logger.error(f"Failed to create Oracle connection pool: {exc}")
                raise ConnectionError(f"Database connection failed: {exc}") from exc
        return self._pool

    def get_connection(self):
        """Acquire one connection from the pool."""
        return self._get_pool().acquire()

    # =========================================================================
    # Transformation Trigger Methods (ADR-020 / ADR-021)
    # =========================================================================

    def call_procedure(self, proc_name: str, params: list = None) -> None:
        """
        Executes a PL/SQL stored procedure.
        
        Args:
            proc_name: The full name of the procedure (e.g., 'EQUITY.SP_CLEAN_ODS').
            params: A list of parameters to pass to the procedure. Defaults to None.
        
        Raises:
            oracledb.Error: If the procedure execution fails (propagated to caller for Tier 2 alerting).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            logger.info(f"Executing PL/SQL Procedure: {proc_name} | Params: {params}")
            cursor.callproc(proc_name, params or [])
            conn.commit()
            logger.info(f"Successfully executed procedure: {proc_name}")
        except oracledb.Error as exc:
            conn.rollback()
            logger.error(f"Database error occurred while executing {proc_name}: {exc}")
            raise
        except Exception as exc:
            conn.rollback()
            logger.error(f"Unexpected error occurred while executing {proc_name}: {exc}")
            raise
        finally:
            cursor.close()
            self._pool.release(conn)

    # =========================================================================
    # Batch Logging Methods (FAIL-FAST: Exceptions MUST propagate)
    # =========================================================================

    def create_batch_record(self, batch_id: str, task_name: str, source_system: str = "INTERNAL") -> None:
        """
        Insert an initial 'RUNNING' record into SYS_BATCH_LOG.
        
        RAISES:
            Exception: On any DB error. Caller (main.py) MUST treat as fatal startup failure.
        """
        sql = """
            INSERT INTO EQUITY.SYS_BATCH_LOG 
            (BATCH_ID, LAYER, PIPELINE_NAME, STATUS, SOURCE_SYSTEM) 
            VALUES (:batch_id, 'ODS', :pipeline, 'RUNNING', :source)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, batch_id=batch_id, pipeline=task_name, source=source_system)
            conn.commit()
            logger.info(f"Batch record created: {batch_id} for task {task_name}")
        except Exception as exc:
            conn.rollback()
            logger.error(f"Failed to create batch record in SYS_BATCH_LOG: {exc}")
            raise
        finally:
            cursor.close()
            self._pool.release(conn)

    def update_batch_status(self, batch_id: str, status: str, error_message: str = None) -> None:
        """
        Update the status of a batch in SYS_BATCH_LOG.
        
        RAISES:
            Exception: On any DB error. Caller must handle.
        """
        sql = """
            UPDATE EQUITY.SYS_BATCH_LOG 
            SET STATUS = :p_status, 
                END_TIME = SYSTIMESTAMP, 
                ERROR_MESSAGE = :p_err 
            WHERE BATCH_ID = :p_bid
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, p_status=status, p_err=error_message, p_bid=batch_id)
            conn.commit()
            logger.info(f"Batch record updated: {batch_id} -> {status}")
        except Exception as exc:
            conn.rollback()
            logger.error(f"Failed to update batch status in SYS_BATCH_LOG: {exc}")
            raise
        finally:
            cursor.close()
            self._pool.release(conn)

    # =========================================================================
    # Core Ingestion Methods (P0 Fix: Precise Counting & InsertResult)
    # =========================================================================

    def _prepare_records(
        self, records: list[dict[str, Any]], batch_id: str | None = None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Inject audit metadata (BATCH_ID, LOAD_TIME) & coerce all values to string/None."""
        if not records:
            return [], []

        effective_batch_id = batch_id or uuid.uuid4().hex
        load_time_str = datetime.now(timezone.utc).isoformat()

        all_keys = set()
        for r in records:
            all_keys.update(r.keys())

        all_keys.discard("BATCH_ID")
        all_keys.discard("LOAD_TIME")

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
    ) -> InsertResult:
        """
        Execute Pure-INSERT operations in small chunks (5-10 records).
        
        Returns:
            InsertResult containing exact attempted, inserted, and dropped counts.
        """
        if not records:
            eff_id = batch_id or uuid.uuid4().hex
            return InsertResult(batch_id=eff_id, attempted_count=0, inserted_count=0, dropped_count=0)

        prepared_records, columns = self._prepare_records(records, batch_id)
        effective_batch_id = prepared_records[0]["BATCH_ID"]
        attempted_count = len(prepared_records)

        cols_sql = ", ".join([f'"{col}"' for col in columns])
        binds_sql = ", ".join([f":{col}" for col in columns])
        sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({binds_sql})"

        batch_size = getattr(self.config, "insert_batch_size", 10)
        
        inserted_count = 0
        dropped_count = 0

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for start in range(0, attempted_count, batch_size):
                chunk = prepared_records[start : start + batch_size]
                chunk_inserted, chunk_dropped = self._execute_chunk(cursor, conn, sql, chunk)
                inserted_count += chunk_inserted
                dropped_count += chunk_dropped
            
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"Batch insert completely failed for {table_name}: {exc}")
            # If the entire batch transaction fails catastrophically
            dropped_count = attempted_count - inserted_count
        finally:
            cursor.close()
            self._pool.release(conn)

        result = InsertResult(
            batch_id=effective_batch_id,
            attempted_count=attempted_count,
            inserted_count=inserted_count,
            dropped_count=dropped_count
        )
        logger.info(f"InsertResult [{table_name}] -> Attempted: {attempted_count}, Inserted: {inserted_count}, Dropped: {dropped_count}")
        return result

    def _execute_chunk(self, cursor, conn, sql: str, chunk: list[dict[str, Any]]) -> tuple[int, int]:
        """Execute a chunk via executemany. Fallback to individual rows on failure."""
        try:
            cursor.executemany(sql, chunk)
            return len(chunk), 0
        except oracledb.Error as exc:
            logger.warning(f"Chunk failed ({len(chunk)} rows): {exc}. Retrying individually...")
            return self._execute_individually(cursor, conn, sql, chunk)

    def _execute_individually(self, cursor, conn, sql: str, chunk: list[dict[str, Any]]) -> tuple[int, int]:
        """Best-effort fallback: commit good rows, log and drop bad ones. Returns (inserted, dropped)."""
        inserted = 0
        dropped = 0
        for row in chunk:
            try:
                cursor.execute(sql, row)
                inserted += 1
            except oracledb.Error as exc:
                logger.error(f"Dropped record due to DB error: {exc} | Row: {row}")
                dropped += 1
        return inserted, dropped

    def close(self) -> None:
        """Shutdown the connection pool. Called ONLY in main() finally block."""
        if self._pool:
            self._pool.close()
            self._pool = None
            logger.info("Connection pool closed.")

# Expose singleton instance
db = DbOperator()