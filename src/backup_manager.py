# src/backup_manager.py

import os
import json
import logging
import shutil
import hashlib
from datetime import datetime, timezone
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)

class BatchBackupContext:
    """
    Manages a single batch's backup lifecycle:
    - Writes records to records.jsonl (JSON Lines format) with fsync support
    - Automatically generates manifest.json on explicit finalize() (containing count, size, sha256)
    - Strict exception handling: does not swallow exceptions on exit, ensuring data integrity awareness.
    """
    def __init__(self, batch_dir: str, table_name: str, batch_id: str):
        self.batch_dir = batch_dir
        self.table_name = table_name
        self.batch_id = batch_id
        self.records_path = os.path.join(batch_dir, "records.jsonl")
        self.manifest_path = os.path.join(batch_dir, "manifest.json")
        
        os.makedirs(batch_dir, exist_ok=True)
        self._file = open(self.records_path, 'w', encoding='utf-8')
        self.record_count = 0
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._finalized = False

    def append_records(self, records: List[Dict[str, Any]]) -> int:
        """
        Appends a list of records to records.jsonl.
        Returns the number of successfully written rows.
        """
        if not records:
            return 0
            
        written = 0
        try:
            for r in records:
                line = json.dumps(r, ensure_ascii=False)
                self._file.write(line + "\n")
                written += 1
            self._file.flush()
            os.fsync(self._file.fileno())  # Force disk flush to survive sudden power-loss
            self.record_count += written
        except Exception as e:
            logger.error(f"Error appending records to backup batch {self.batch_id}: {e}")
            raise
        return written

    def finalize(self) -> Dict[str, Any]:
        """
        Explicitly closes the records file, computes SHA-256 checksum, and writes manifest.json.
        Can be safely called multiple times (idempotent after first call).
        """
        if self._finalized:
            return self._read_manifest()

        if self._file and not self._file.closed:
            self._file.close()

        # Compute SHA-256 checksum of records.jsonl
        sha256_hash = hashlib.sha256()
        file_size = 0
        if os.path.exists(self.records_path):
            file_size = os.path.getsize(self.records_path)
            with open(self.records_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

        manifest = {
            "batch_id": self.batch_id,
            "table_name": self.table_name,
            "record_count": self.record_count,
            "file_size_bytes": file_size,
            "checksum_sha256": sha256_hash.hexdigest(),
            "created_at": self.created_at,
            "finalized_at": datetime.now(timezone.utc).isoformat()
        }

        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        self._finalized = True
        logger.info(f"Finalized backup batch {self.batch_id} | Rows: {self.record_count} | Size: {file_size} bytes | SHA256: {manifest['checksum_sha256'][:16]}...")
        return manifest

    def _read_manifest(self) -> Dict[str, Any]:
        """Helper to read an existing manifest file (Idempotent support)."""
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only ensure file handle cleanup; do NOT swallow exceptions or auto-generate incomplete manifests.
        if self._file and not self._file.closed:
            try:
                self._file.close()
            except Exception as e:
                logger.error(f"Error closing backup file for batch {self.batch_id}: {e}")
        # If an exception occurred inside the block, manifest won't be finalized, 
        # allowing upstream to recognize failure and retain local directory for inspection.


class BackupManager:
    """
    BackupManager handles the 'Thin-Edge' local persistence layer with Batch-level isolation.
    
    Design Principles:
    1. Single Responsibility: Only handles high-speed local disk writes.
    2. Batch Isolation: Organizes backups by {table}/{date}/{batch_id}/.
    3. Clean Separation: Core data in records.jsonl, metadata in manifest.json.
    """

    def __init__(self, base_backup_dir: str = "/home/ubuntu/backup"):
        self.base_backup_dir = base_backup_dir
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Ensure the root backup directory exists on the 30GB partition."""
        try:
            if not os.path.exists(self.base_backup_dir):
                os.makedirs(self.base_backup_dir, exist_ok=True)
                logger.info(f"Initialized base backup directory: {self.base_backup_dir}")
        except Exception as e:
            logger.critical(f"Critical Failure: Cannot create backup directory {self.base_backup_dir}: {e}")
            raise

    def get_batch_dir(self, table_name: str, batch_id: str, date_str: Optional[str] = None) -> str:
        """
        Returns a structured batch directory path.
        Pattern: /home/ubuntu/backup/{table_name}/{YYYY-MM-DD}/{batch_id}/
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        batch_dir = os.path.join(self.base_backup_dir, table_name, date_str, batch_id)
        return batch_dir

    def start_batch(self, table_name: str, batch_id: str, date_str: Optional[str] = None) -> BatchBackupContext:
        """
        Context manager initiator for a specific ingestion batch.
        """
        batch_dir = self.get_batch_dir(table_name, batch_id, date_str)
        return BatchBackupContext(batch_dir, table_name, batch_id)

    def clear_batch_dir(self, table_name: str, batch_id: str, date_str: Optional[str] = None):
        """
        Purges a specific batch backup directory. 
        Called by UploadManager ONLY after successful OCI sync, verification, and DB row count matching.
        """
        try:
            batch_dir = self.get_batch_dir(table_name, batch_id, date_str)
            if os.path.exists(batch_dir):
                shutil.rmtree(batch_dir)
                logger.info(f"Successfully purged local backup batch: {batch_dir}")
        except Exception as e:
            logger.error(f"Failed to purge backup batch {batch_id} for {table_name}: {e}")

    def clear_task_date_dir(self, table_name: str, date_str: Optional[str] = None):
        """
        Purges the entire date directory for a table (maintenance fallback).
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
                
            task_dir = os.path.join(self.base_backup_dir, table_name, date_str)
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
                logger.info(f"Successfully purged local date directory: {task_dir}")
        except Exception as e:
            logger.error(f"Failed to purge date directory {table_name} for {date_str}: {e}")