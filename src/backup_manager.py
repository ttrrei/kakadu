# src/backup_manager.py

import os
import json
import logging
import zipfile
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

class BackupManager:
    """
    Handles local JSONL persistence and OCI Object Storage synchronization.
    Ensures zero data loss by saving raw extracted data before DB ingestion.
    Implements Atomic Writes, ZIP compression, and PAR-based cloud upload with path prefixing.
    """

    def __init__(self, backup_root: str, par_url: Optional[str] = None):
        self.backup_root = backup_root
        self.par_url = par_url # Injected from .env via BaseScraper
        self.logger = logging.getLogger(__name__)
        self._ensure_root_exists()

    def _ensure_root_exists(self):
        try:
            if not os.path.exists(self.backup_root):
                os.makedirs(self.backup_root, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Critical failure creating backup root {self.backup_root}: {e}")

    def save_local(self, table_name: str, data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Saves data using Atomic Write pattern: 
        Temp JSONL -> Final JSONL -> Temp ZIP -> Final ZIP -> Remove JSONL.
        """
        if not data:
            self.logger.info(f"No data to backup for {table_name}. Skipping.")
            return None

        try:
            # 1. Setup directory structure
            date_str = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%H%M%S_%f")
            dir_path = os.path.join(self.backup_root, table_name, date_str)
            os.makedirs(dir_path, exist_ok=True)

            # Define paths
            final_jsonl_path = os.path.join(dir_path, f"{timestamp}.jsonl")
            temp_jsonl_path = final_jsonl_path + ".tmp"
            final_zip_path = os.path.join(dir_path, f"{timestamp}.zip")
            temp_zip_path = final_zip_path + ".tmp"

            # 2. ATOMIC STEP 1: Write to temporary JSONL
            with open(temp_jsonl_path, 'w', encoding='utf-8') as f:
                for record in data:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            # Atomically rename temp to final JSONL
            os.replace(temp_jsonl_path, final_jsonl_path)

            # 3. ATOMIC STEP 2: Compress to temporary ZIP
            try:
                with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # arcname ensures the zip contains only the file, not the whole folder path
                    zipf.write(final_jsonl_path, arcname=os.path.basename(final_jsonl_path))
                
                # Atomically rename temp ZIP to final ZIP
                os.replace(temp_zip_path, final_zip_path)
                
                # 4. Cleanup: Remove the final JSONL now that ZIP is safe
                os.remove(final_jsonl_path)
                
                self.logger.info(f"Successfully backed up {len(data)} records (Atomic) to: {final_zip_path}")
                return final_zip_path

            except Exception as zip_e:
                self.logger.error(f"Compression failed: {zip_e}. Keeping {final_jsonl_path}")
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
                return final_jsonl_path

        except Exception as e:
            self.logger.error(f"Failed to save local backup for {table_name}: {e}")
            # Cleanup any leftover temp files
            for p in [temp_jsonl_path if 'temp_jsonl_path' in locals() else None, 
                      temp_zip_path if 'temp_zip_path' in locals() else None]:
                if p and os.path.exists(p):
                    os.remove(p)
            return None

    def sync_to_cloud(self, local_file_path: str, cloud_path: str) -> bool:
        """
        Uploads the ZIP file to OCI using a Pre-Authenticated Request (PAR) URL.
        Implements ADR-013: Appends cloud_path to the PAR URL to create a folder-like structure.
        """
        if not self.par_url:
            self.logger.warning("OCI PAR URL not provided in .env. Skipping cloud sync.")
            return False

        if not local_file_path or not os.path.exists(local_file_path):
            return False

        try:
            # OCI PAR URLs for object upload usually end with '/o/'
            # We append the cloud_path (e.g., 'TABLE/DATE/FILE.zip') to specify the target object name
            full_upload_url = f"{self.par_url.rstrip('/')}/{cloud_path}"
            
            self.logger.info(f"Syncing to OCI: {cloud_path}")
            with open(local_file_path, 'rb') as f:
                # Use PUT request to upload the binary file
                response = requests.put(full_upload_url, data=f, timeout=60)
                response.raise_for_status()
            
            self.logger.info(f"Successfully synced to OCI: {cloud_path}")
            return True
        except Exception as e:
            self.logger.error(f"Cloud sync failed for {cloud_path}: {e}")
            return False

    def purge_local(self, file_path: str):
        """Deletes local file after successful cloud sync to save disk space."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Purged local backup: {file_path}")
        except Exception as e:
            self.logger.warning(f"Failed to purge {file_path}: {e}")