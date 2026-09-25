# src/upload_manager.py

import os
import logging
import zipfile
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from src.backup_manager import BackupManager

logger = logging.getLogger(__name__)

class UploadManager:
    """
    UploadManager handles the Cloud Synchronization lifecycle (Batch Level).
    
    Design Principles (P0 Fix & ADR-013/014):
    1. Batch-Level Sync: Compresses and uploads a single ZIP per batch_id.
    2. OCI PAR Integration: Uses Pre-Authenticated Requests for stateless, secure uploads.
    3. Verify-Then-Purge: Only deletes the local batch directory after ZIP upload succeeds.
    4. Zip Compression: Reduces storage cost and network transfer time (Critical for 1GB VM / Free Tier).
    """

    def __init__(self, backup_manager: BackupManager, oci_par_url: str):
        """
        :param backup_manager: Instance of BackupManager to coordinate local cleanup.
        :param oci_par_url: The base OCI PAR URL for the bucket.
        """
        self.backup_manager = backup_manager
        # Ensure trailing slash for URL joining
        self.oci_par_url = oci_par_url.rstrip('/') + '/'

    def _create_zip_archive(self, batch_dir: str, table_name: str, batch_id: str) -> str:
        """
        Compresses the entire batch directory into a single ZIP file in the parent directory.
        Returns the path to the created ZIP file.
        """
        # Zip stored in parent of batch_dir (e.g., /home/ubuntu/backup/ODS_TABLE/2026-09-15/)
        parent_dir = os.path.dirname(batch_dir)
        timestamp = datetime.now().strftime("%H%M%S")
        zip_filename = f"{table_name}_{batch_id}_{timestamp}.zip"
        zip_path = os.path.join(parent_dir, zip_filename)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(batch_dir):
                    for file in files:
                        if not file.startswith('.'): 
                            full_path = os.path.join(root, file)
                            # Archive name: batch_id/records.jsonl, batch_id/manifest.json
                            arcname = os.path.join(batch_id, os.path.relpath(full_path, batch_dir))
                            zipf.write(full_path, arcname)
            
            logger.info(f"Created compressed archive: {zip_path} ({os.path.getsize(zip_path)} bytes)")
            return zip_path
        except Exception as e:
            logger.error(f"Failed to create ZIP archive for {batch_id}: {e}")
            raise

    def sync_to_cloud(
        self, 
        table_name: str, 
        batch_id: str, 
        backup_path: str, 
        manifest: Dict[str, Any]
    ) -> bool:
        """
        Executes the full sync lifecycle for a single batch:
        1. Compress batch directory to ZIP
        2. Upload ZIP to OCI Object Storage via PAR (PUT)
        3. Verify upload success (HTTP 2xx)
        4. Purge local batch directory (clear_batch_dir)
        5. Cleanup temporary ZIP file
        
        Failure at any step raises Exception -> Caller (main.py) treats as Tier-1 Warning & Retains Local Data.
        
        :param table_name: ODS Table name (e.g., ODS_PRICE_OHLCV)
        :param batch_id: UUID batch identifier
        :param backup_path: Full local path to the batch directory 
                            (e.g., /home/ubuntu/backup/ODS_PRICE_OHLCV/2026-09-15/abc123/)
        :param manifest: The manifest dict returned by BatchBackupContext.finalize()
        :return: True if sync & purge successful.
        """
        if not os.path.isdir(backup_path):
            raise NotADirectoryError(f"Backup path does not exist: {backup_path}")

        # Extract Date Str from backup_path for object prefix
        # Path pattern: .../backup/{table_name}/{YYYY-MM-DD}/{batch_id}/
        try:
            date_str = os.path.basename(os.path.dirname(backup_path))
            # Validate date format roughly
            if len(date_str) != 10 or date_str.count('-') != 2:
                date_str = datetime.now().strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now().strftime("%Y-%m-%d")

        zip_path = None
        try:
            # 1. Compress
            zip_path = self._create_zip_archive(backup_path, table_name, batch_id)
            
            # 2. Construct OCI Object Path (ADR-013): {TABLE}/{YYYY-MM-DD}/{ZIP_FILENAME}
            # Example: ODS_PRICE_OHLCV/2026-09-15/ODS_PRICE_OHLCV_abc123_120000.zip
            zip_filename = os.path.basename(zip_path)
            cloud_object_path = f"{table_name}/{date_str}/{zip_filename}"
            full_upload_url = f"{self.oci_par_url}{cloud_object_path}"

            # 3. Upload ZIP via PUT (Streaming to save RAM)
            logger.info(f"Uploading {zip_filename} to OCI Object Storage: {cloud_object_path}")
            file_size = os.path.getsize(zip_path)
            with open(zip_path, 'rb') as f:
                response = requests.put(
                    full_upload_url, 
                    data=f, 
                    timeout=300,  # 5 min timeout
                    headers={'Content-Length': str(file_size)}
                )
                response.raise_for_status()

            logger.info(f"Successfully uploaded batch {batch_id} to OCI: {cloud_object_path}")

            # 4. Purge Local Batch Directory (ONLY after successful upload)
            # This calls BackupManager.clear_batch_dir(table_name, batch_id, date_str)
            self.backup_manager.clear_batch_dir(table_name, batch_id, date_str)
            
            return True

        except Exception as e:
            logger.error(f"Cloud sync failed for batch {batch_id}: {e}")
            # Re-raise to let main.py handle Tier-1 Warning & Retention
            raise
        finally:
            # 5. Always cleanup temporary ZIP file
            if zip_path and os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                    logger.debug(f"Removed temporary zip: {zip_path}")
                except Exception as e:
                    logger.warning(f"Could not remove temporary ZIP {zip_path}: {e}")