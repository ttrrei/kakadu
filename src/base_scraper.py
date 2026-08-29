# src/base_scraper.py
from __future__ import annotations
import logging
import os
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Union

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .db_operator import db as db_operator
from .backup_manager import BackupManager
from .config import config
from .symbol_provider import get_target_symbols_generator

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    所有爬虫的抽象基类。
    实现了 '编排者' 模式，负责管理资源生命周期、执行策略（批量 vs 迭代）
    以及带有强制备份和云同步的数据库写入。
    """

    def __init__(self, db_op=db_operator):
        self.db = db_op
        self.config = config
        
        # 1. 从 config.yaml 注入备份根路径
        backup_path = self.config.get('system', {}).get('backup_dir', '/home/ubuntu/backup')
        
        # 2. 从 .env (通过 config.env 或 os.getenv) 注入 PAR URL
        par_url = None
        if hasattr(self.config, 'env') and self.config.env:
            par_url = getattr(self.config.env, 'oci_par_url', None)
        if not par_url:
            par_url = os.getenv("OCI_PAR_URL")
        
        self.backup_manager = BackupManager(backup_root=backup_path, par_url=par_url)
        
        self.is_bulk_task: bool = False
        self.needs_driver: bool = True
        self.batch_size: int = 50
        self._driver: Optional[webdriver.Chrome] = None

    def _create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
        try:
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_driver(self) -> Optional[webdriver.Chrome]:
        if not self.needs_driver: return None
        if self._driver is None: self._driver = self._create_driver()
        return self._driver

    def run(self, symbols: Optional[List[str]] = None, table_name: str = "", job_name: str = ""):
        try:
            logger.info(f"Starting job {job_name} on table {table_name}...")
            if self.is_bulk_task:
                if symbols is None: symbols = list(get_target_symbols_generator())
                self._run_bulk(symbols, table_name, job_name)
            else:
                self._run_iterative(table_name, job_name)
            logger.info(f"Job {job_name} completed successfully.")
        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

    def _run_bulk(self, symbols: List[str], table_name: str, job_name: str):
        logger.info("Executing in BULK mode...")
        driver = self.get_driver()
        data = self.scrape_all(driver, symbols)
        if data:
            self._flush_buffer(data, table_name, job_name)
        else:
            logger.warning("No data extracted in bulk mode.")

    def _run_iterative(self, table_name: str, job_name: str):
        logger.info("Executing in ITERATIVE mode...")
        buffer = []
        success_count = 0
        fail_count = 0
        driver = self.get_driver()

        for symbol in get_target_symbols_generator():
            try:
                result = self.scrape_one(driver, symbol)
                if result:
                    if isinstance(result, list): buffer.extend(result)
                    elif isinstance(result, dict): buffer.append(result)
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to scrape symbol {symbol}: {e}")
                fail_count += 1
                continue

            if len(buffer) >= self.batch_size:
                self._flush_buffer(buffer, table_name, job_name)

        if buffer:
            self._flush_buffer(buffer, table_name, job_name)
        logger.info(f"Iterative run finished. Success: {success_count}, Failed: {fail_count}")

    def _flush_buffer(self, buffer: List[Any], table_name: str, job_name: str):
        """
        核心生命周期管理 (ADR-013):
        1. 原子备份 (Local ZIP) -> 2. 数据库写入 (Insert) -> 3. 云端同步 (OCI Sync with Prefix) -> 4. 本地清理 (Purge)
        """
        # 1. 本地原子备份 (Returns path to .zip)
        backup_path = self.backup_manager.save_local(table_name, list(buffer))
        if not backup_path:
            logger.error(f"Backup failed for {table_name}. Aborting DB insert to prevent data loss.")
            return

        try:
            # 2. 数据库写入
            self.db.insert_batch(table_name, list(buffer), batch_id=job_name)
            
            # 3. 构建云端路径 (Prefixing per ADR-013)
            # 格式: TABLE_NAME/YYYY-MM-DD/TIMESTAMP.zip
            file_name = os.path.basename(backup_path)
            date_str = datetime.now().strftime("%Y-%m-%d")
            cloud_path = f"{table_name}/{date_str}/{file_name}"
            
            # 4. 云端同步 (If enabled in config.yaml)
            if self.config.get('oci', {}).get('enabled', False):
                if self.backup_manager.sync_to_cloud(backup_path, cloud_path):
                    # 5. 同步成功后清理本地
                    self.backup_manager.purge_local(backup_path)
                else:
                    logger.warning(f"Cloud sync failed for {backup_path}. Local backup retained.")
            
        except Exception as e:
            logger.error(f"Database insert failed for {table_name}: {e}. Local backup retained at {backup_path}")
        finally:
            if isinstance(buffer, list):
                buffer.clear()

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]: pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]: pass