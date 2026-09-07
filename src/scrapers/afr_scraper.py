# src/scrapers/afr_scraper.py
from __future__ import annotations
import logging
import json
import requests
from typing import Any, List, Dict, Optional, Union
from selenium.webdriver.chrome.webdriver import WebDriver

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class AfrScraper(BaseScraper):
    """
    AFR (Australian Financial Review) 股票历史数据采集器。
    
    特点：
    1. 采用 GraphQL 接口，完全摒弃 Selenium，资源占用极低。
    2. 遵循 ADR-015：通过 scraper_name 从 config.yaml 动态加载所有配置。
    3. 遵循 BaseScraper 的迭代模式 (Iterative Mode)。
    4. 包含 Symbol 适配逻辑，将标准 ".AX" 格式转换为 AFR 专用的 "ASX_" 格式。
    """

    # 身份标识：用于在 config.yaml 中映射配置
    scraper_name = "afr"
    
    # 默认属性（可被 config.yaml 覆盖）
    is_bulk_task = False
    needs_driver = False

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取单个股票的历史 5 分钟线数据。
        
        Args:
            driver: 始终为 None (因为 needs_driver=False)
            symbol: 股票代码 (例如 'CBA.AX')
        """
        # 1. 格式适配：将 "CBA.AX" 转换为 "ASX_CBA"
        # AFR API 无法识别 ".AX" 后缀，必须使用 "ASX_TICKER" 格式
        afr_symbol = symbol.replace(".AX", "").strip().upper()
        if not afr_symbol.startswith("ASX_"):
            afr_symbol = f"ASX_{afr_symbol}"

        # 2. 从配置中动态获取 URL
        cfg = self.config.get(self.scraper_name, {})
        api_url = cfg.get("url")
        
        if not api_url:
            logger.error(f"Configuration Error: 'url' for {self.scraper_name} not found in config.yaml")
            return None

        # 3. 构造 GraphQL 查询
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
        params = {
            "query": query,
            "operationName": "financialStockHistoricalQuotes",
            "variables": json.dumps({"symbol": afr_symbol}),
        }

        try:
            logger.debug(f"Fetching AFR data for {afr_symbol} (original: {symbol})...")
            # 设置 20 秒超时，防止网络卡死挂起任务
            r = requests.get(api_url, params=params, timeout=20)
            r.raise_for_status()

            data = r.json()
            
            # 安全解析 JSON 路径
            quotes_data = (
                data.get("data", {})
                .get("FIVE_MINUTES_1_DAY", {})
                .get("quotes", [])
            )

            if not quotes_data:
                logger.warning(f"No quotes returned from AFR for symbol: {afr_symbol}")
                return None

            # 4. 转换为数据库 ODS 表结构（全大写字段名）
            # DbOperator 内部会自动将所有值转为字符串并注入 BATCH_ID/LOAD_TIME
            records = []
            for q in quotes_data:
                records.append({
                    "CODE": symbol, # 数据库中依然存储标准格式 "CBA.AX"
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
            logger.error(f"Failed to fetch AFR data for {afr_symbol}: {str(e)}")
            return None

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str]) -> List[Dict[str, Any]]:
        """实现基类抽象方法，但在迭代模式下不会被调用"""
        raise NotImplementedError("AfrScraper uses iterative mode. Use scrape_one instead.")