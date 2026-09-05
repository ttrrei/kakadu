# src/upload_manager.py

import os
import logging
import zipfile
import requests
from datetime import datetime
from typing import Optional
from src.backup_manager import BackupManager

logger = logging.getLogger(__name__)

class UploadManager:
    """
    UploadManager handles the Cloud Synchronization lifecycle.
    
    Design Principles:
    1. Batch-Compress-Upload: Reduces network overhead by uploading one ZIP per task.
    2. OCI PAR Integration: Uses Pre-Authenticated Requests for stateless, secure uploads.
    3. Post-Verification Cleanup: Only purges local data after successful HTTP 200 response.
    """

    def __init__(self, backup_manager: BackupManager, oci_par_url: str):
        """
        :param backup_manager: Instance of BackupManager to coordinate paths and cleanup.
        :param oci_par_url: The base OCI PAR URL for the bucket.
        """
        self.backup_manager = backup_manager
        self.oci_par_url = oci_par_url.rstrip('/')

    def _create_zip_archive(self, table_name: str, date_str: str) -> str:
        """
        Compresses the entire task directory into a single ZIP file.
        """
        task_dir = self.backup_manager.get_task_dir(table_name, date_str)
        timestamp = datetime.now().strftime("%H%M%S")
        zip_filename = f"{table_name}_{date_str}_{timestamp}.zip"
        zip_path = os.path.join(os.path.dirname(task_dir), zip_filename)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(task_dir):
                    for file in files:
                        if not file.startswith('.'): 
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, task_dir)
                            zipf.write(full_path, arcname)
            
            logger.info(f"Created compressed archive: {zip_path}")
            return zip_path
        except Exception as e:
            logger.error(f"Failed to create ZIP archive for {table_name}: {e}")
            raise

    def sync_to_cloud(self, table_name: str, date_str: Optional[str] = None):
        """
        Executes the full sync lifecycle: Compress -> Upload -> Purge.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        zip_path = None
        try:
            # 1. Compress
            zip_path = self._create_zip_archive(table_name, date_str)
            
            # 2. Construct OCI Path (Per ADR-013: {TABLE}/{DATE}/{FILE})
            # Example: /home/ubuntu/backup/ODS_PRICE_OHLCV/2026-08-29/120000.zip
            filename = os.path.basename(zip_path)
            cloud_path = f"{table_name}/{date_str}/{filename}"
            full_upload_url = f"{self.oci_par_url}/{cloud_path}"

            # 3. Upload via PUT request (OCI PAR standard)
            logger.info(f"Uploading {filename} to OCI Object Storage...")
            with open(zip_path, 'rb') as f:
                response = requests.put(full_upload_url, data=f, timeout=300)
                response.raise_for_status()

            logger.info(f"Successfully uploaded to OCI: {cloud_path}")

            # 4. Purge local data ONLY after successful upload
            self.backup_manager.clear_task_dir(table_name, date_str)

        except Exception as e:
            logger.error(f"Cloud sync failed for {table_name}: {e}")
            # We do NOT purge local data here, allowing for retry in the next run
            raise
        finally:
            # Always remove the temporary ZIP file
            if zip_path and os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception as e:
                    logger.warning(f"Could not remove temporary ZIP {zip_path}: {e}")
