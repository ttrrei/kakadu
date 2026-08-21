from __future__ import annotations
import logging
import json
import requests
from typing import Any, List, Dict, Optional, Union
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper
from ..db_operator import db as db_operator

logger = logging.getLogger(__name__)

class AfrScraper(BaseScraper):
    """
    AFR (Australian Financial Review) 股票历史数据采集器。
    
    特点：
    1. 采用 GraphQL 接口，摒弃 Selenium，资源占用极低。
    2. 自动匹配 ODS_PRICE_TICK 表字段（大写）。
    3. 遵循 BaseScraper 的迭代模式 (Iterative Mode)。
    """

    def __init__(self, db_op: Optional[Any] = None):
        # 显式传递 db_operator 给基类
        super().__init__(db_op if db_op is not None else db_operator)
        
        # --- 配置 ---
        self.is_bulk_task = False   # 迭代模式：逐个 symbol 处理，方便错误隔离
        self.needs_driver = False  # 关键：设置为 False，不会启动浏览器，节省内存
        self.batch_size = 50       # 内存中积攒 50 条数据后执行一次数据库写入
        
        self.api_url = "https://api.afr.com/graphql"

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取单个股票的历史 5 分钟线数据。
        
        Args:
            driver: 始终为 None (因为 needs_driver=False)
            symbol: 股票代码 (例如 'ASX_CBA')
        """
        query = """
        query financialStockHistoricalQuotes($symbol: String!) {
          FIVE_MINUTES_1_DAY: financialStockHistoricalQuotes(
            interval: FIVE_MINUTES_1_DAY
            symbol: $symbol
          ) {
            quotes { open high low close time }
          }
        }
        """

        # 构造 GraphQL 请求参数
        # 使用 json.dumps 确保 variables 内部的 JSON 字符串格式正确
        params = {
            "query": query,
            "operationName": "financialStockHistoricalQuotes",
            "variables": json.dumps({"symbol": symbol}),
        }

        try:
            logger.debug(f"Fetching AFR data for {symbol}...")
            # 设置 20 秒超时，防止网络卡死挂起任务
            r = requests.get(self.api_url, params=params, timeout=20)
            r.raise_for_status()

            data = r.json()
            
            # 安全解析 JSON 路径
            quotes_data = (
                data.get("data", {})
                .get("FIVE_MINUTES_1_DAY", {})
                .get("quotes", [])
            )

            if not quotes_data:
                logger.warning(f"No quotes returned for symbol: {symbol}")
                return None

            # 转换为数据库 ODS 表结构（全大写字段名）
            # DbOperator 内部会自动将所有值转为字符串并注入 BATCH_ID/LOAD_TIME
            records = []
            for q in quotes_data:
                records.append({
                    "CODE": symbol,
                    "OPEN": str(q.get("open")),
                    "HIGH": str(q.get("high")),
                    "LOW": str(q.get("low")),
                    "CLOSE": str(q.get("close")),
                    "TICK_TIME": str(q.get("time"))
                })

            logger.info(f"Successfully extracted {len(records)} records for {symbol}")
            return records

        except Exception as e:
            # Shield Pattern: 捕获单个 symbol 的错误并记录，不中断整个任务
            logger.error(f"Failed to fetch AFR data for {symbol}: {str(e)}")
            return None

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """实现基类抽象方法，但在迭代模式下不会被调用"""
        raise NotImplementedError("AfrScraper uses iterative mode. Use scrape_one instead.")