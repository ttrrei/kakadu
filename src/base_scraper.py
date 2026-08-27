# src/base_scraper.py
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional, Union, Iterable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 导入单例 DbOperator、备份管理器以及新实现的 SymbolProvider
from .db_operator import db as db_operator
from .backup_manager import BackupManager
from .symbol_provider import get_target_symbols_generator

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    所有爬虫的抽象基类。
    实现了 '编排者' 模式，负责管理资源生命周期、执行策略（批量 vs 迭代）
    以及带有强制备份的数据库缓冲写入。
    """

    def __init__(self, db_op=db_operator):
        # 组合：持有 DbOperator 的引用
        self.db = db_op
        # 初始化备份管理器
        self.backup_manager = BackupManager()
        
        # --- 配置标志（由子类覆盖） ---
        self.is_bulk_task: bool = False   # True: 执行 scrape_all, False: 执行 scrape_one
        self.needs_driver: bool = True    # True: 使用 Selenium, False: 使用 API/CSV/Requests
        self.batch_size: int = 50        # 迭代模式下的缓冲区大小
        
        # 内部状态
        self._driver: Optional[webdriver.Chrome] = None

    def _create_driver(self) -> webdriver.Chrome:
        """创建针对 1GB RAM VM 优化的标准化无头 Chrome 驱动。"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
        )
        
        try:
            logger.info("Initializing Headless Chrome Driver...")
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_driver(self) -> Optional[webdriver.Chrome]:
        """懒加载 WebDriver。"""
        if not self.needs_driver:
            return None
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def run(self, symbols: Optional[List[str]] = None, table_name: str = "", job_name: str = ""):
        """
        主入口点。管理资源生命周期并选择执行策略。
        
        注意：对于迭代任务，'symbols' 参数将被忽略，改为通过 SymbolProvider 动态获取。
        """
        try:
            logger.info(f"Starting job {job_name} on table {table_name}...")
            
            if self.is_bulk_task:
                # 批量任务仍需要符号列表（通常是全量宇宙）
                if symbols is None:
                    # 兜底方案：如果没有提供列表，则从 Generator 中加载所有符号
                    symbols = list(get_target_symbols_generator())
                self._run_bulk(symbols, table_name, job_name)
            else:
                # 迭代任务直接使用生成器，以维持 O(1) 内存占用
                self._run_iterative(table_name, job_name)
                
            logger.info(f"Job {job_name} completed successfully.")
            
        except Exception as e:
            logger.error(f"Critical failure in job {job_name}: {e}")
            raise
        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None
                logger.info("WebDriver closed.")

    def _run_bulk(self, symbols: List[str], table_name: str, job_name: str):
        """批量模式策略：抓取 -> 备份 -> 写入。"""
        logger.info("Executing in BULK mode...")
        driver = self.get_driver()
        data = self.scrape_all(driver, symbols)
        
        if data:
            # 1. 先备份
            backup_path = self.backup_manager.save_local(table_name, data)
            if backup_path:
                # 2. 仅在备份成功后写入数据库
                self.db.insert_batch(table_name, data, batch_id=job_name)
                logger.info(f"Bulk insert completed: {len(data)} records.")
            else:
                logger.error(f"Backup failed for {table_name}. Aborting DB insert to prevent data loss.")
        else:
            logger.warning("No data extracted in bulk mode.")

    def _run_iterative(self, table_name: str, job_name: str):
        """迭代模式策略：抓取 -> 缓冲 -> 备份 -> 刷新。"""
        logger.info("Executing in ITERATIVE mode using SymbolProvider...")
        buffer = []
        success_count = 0
        fail_count = 0

        driver = self.get_driver()

        # 使用中心化的生成器，确保内存占用不随股票数量增加而增加
        for symbol in get_target_symbols_generator():
            try:
                result = self.scrape_one(driver, symbol)
                if result:
                    if isinstance(result, list):
                        buffer.extend(result)
                    elif isinstance(result, dict):
                        buffer.append(result)
                    else:
                        logger.warning(f"Unexpected return type from scrape_one for {symbol}: {type(result)}")
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to scrape symbol {symbol}: {e}")
                fail_count += 1
                continue

            # 当缓冲区达到设定阈值时，执行一次“备份 -> 写入”循环
            if len(buffer) >= self.batch_size:
                backup_path = self.backup_manager.save_local(table_name, list(buffer))
                if backup_path:
                    self.db.insert_batch(table_name, list(buffer), batch_id=job_name)
                    buffer.clear()
                else:
                    logger.error(f"Backup failed for batch. Retaining buffer for retry or logging.")

        # 处理最后剩余的缓冲数据
        if buffer:
            backup_path = self.backup_manager.save_local(table_name, list(buffer))
            if backup_path:
                self.db.insert_batch(table_name, list(buffer), batch_id=job_name)
            buffer.clear()

        logger.info(f"Iterative run finished. Success: {success_count}, Failed: {fail_count}")

    @abstractmethod
    def scrape_all(self, driver: Optional[webdriver.Chrome], symbols: List[str]) -> List[Dict[str, Any]]:
        """子类必须实现：批量抓取逻辑"""
        pass

    @abstractmethod
    def scrape_one(self, driver: Optional[webdriver.Chrome], symbol: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """子类必须实现：单股票抓取逻辑"""
        pass