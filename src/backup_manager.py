# src/backup_manager.py

import os
import json
import logging
import shutil
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

class BackupManager:
    """
    BackupManager handles the 'Thin-Edge' local persistence layer.
    
    Design Principles:
    1. Single Responsibility: Only handles high-speed local disk writes.
    2. Atomic Writes: Uses temp-file-and-rename pattern to prevent corrupted backups.
    3. Shield Pattern: Failures in backup must not crash the main scraping pipeline.
    4. O(1) Memory: Writes data immediately to disk without internal buffering.
    """

    def __init__(self, base_backup_dir: str = "/home/ubuntu/backup"):
        # Path defined in SAD and BRD
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

    def get_task_dir(self, table_name: str, date_str: Optional[str] = None) -> str:
        """
        Returns a structured directory for the current task.
        Pattern: /home/ubuntu/backup/{table_name}/{YYYY-MM-DD}/
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        task_dir = os.path.join(self.base_backup_dir, table_name, date_str)
        os.makedirs(task_dir, exist_ok=True)
        return task_dir

    def save_record(self, table_name: str, symbol: str, data: Any):
        """
        Saves a symbol's data using an atomic write operation.
        Prevents corrupted files if the process crashes during write.
        """
        try:
            task_dir = self.get_task_dir(table_name)
            final_path = os.path.join(task_dir, f"{symbol}.json")
            temp_path = f"{final_path}.tmp"
            
            # 1. Write to temporary file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 2. Atomic rename (Standard Linux behavior)
            os.replace(temp_path, final_path)
                
        except (OSError, IOError) as e:
            logger.error(f"Disk I/O Error during backup for {symbol} in {table_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving backup for {symbol}: {e}")

    def clear_task_dir(self, table_name: str, date_str: Optional[str] = None):
        """
        Purges the local backup directory. Called by UploadManager after successful OCI sync.
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
                
            task_dir = os.path.join(self.base_backup_dir, table_name, date_str)
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
                logger.info(f"Successfully purged local backup: {task_dir}")
        except Exception as e:
            logger.error(f"Failed to purge backup directory {table_name} for {date_str}: {e}")