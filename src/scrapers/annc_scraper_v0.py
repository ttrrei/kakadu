# src/scrapers/annc_scraper.py
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class AnncScraper(BaseScraper):
    """
    ASX Company Announcements Scraper.
    Implements Bulk Mode: Fetches all announcements from summary pages.
    
    Adheres to ADR-015 (Identity-based Config) and production parsing logic.
    """

    # Identity for configuration mapping in config.yaml
    scraper_name = "annc"
    
    # Default task attributes
    is_bulk_task = True
    needs_driver = True

    def scrape_all(self, driver: Optional[WebDriver], symbols: List[str] = None) -> List[Dict[str, Any]]:
        """
        Iterates through configured summary URLs and extracts announcement data.
        """
        if not driver:
            logger.error("WebDriver is required for AnncScraper but was not provided.")
            return []

        cfg = self.config.get(self.scraper_name, {})
        urls = cfg.get('urls', [])
        
        if not urls:
            logger.error(f"Configuration Error: 'urls' list missing for {self.scraper_name} in config.yaml")
            return []

        all_extracted_data = []

        for url in urls:
            try:
                logger.info(f"Fetching announcements from: {url}")
                driver.get(url)
                
                # --- 生产环境真实解析逻辑开始 ---
                # 1. 定位表格主体
                # 路径: announcement_data -> tbody -> tr
                table_body = driver.find_element(By.TAG_NAME, "announcement_data") \
                                   .find_element(By.TAG_NAME, "tbody")
                rows = table_body.find_elements(By.TAG_NAME, 'tr')
                
                page_records = []
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, 'td')
                    
                    if len(cols) == 0:
                        continue
                    
                    # 敏感度判定逻辑 (完全还原生产代码)
                    # info[2] 是敏感度列
                    sensitive_text = cols[2].text
                    if sensitive_text == '':
                        psensitive = 'True'
                    elif sensitive_text == ' ':
                        psensitive = 'False'
                    else:
                        psensitive = 'Other'
                    
                    # 构建记录 (注意：UUID 由 DbOperator 自动注入，这里无需手动添加)
                    record = {
                        "CODE": cols[0].text.strip(),
                        "RELEASE_DATE": cols[1].text.replace("\n", " ").strip(),
                        "PSENSITIVE": psensitive,
                        "TITLE": cols[3].text.replace("\n", " ").strip()
                    }
                    page_records.append(record)
                
                logger.info(f"Successfully extracted {len(page_records)} records from {url}")
                all_extracted_data.extend(page_records)
                # --- 生产环境真实解析逻辑结束 ---

            except Exception as e:
                logger.error(f"Failed to scrape announcement page {url}: {e}")
                # 继续处理下一个 URL，确保最大数据产出

        return all_extracted_data

    def scrape_one(self, driver: Optional[WebDriver], symbol: str) -> Optional[Dict[str, Any]]:
        """Not implemented for Bulk mode."""
        raise NotImplementedError("AnncScraper operates in Bulk Mode only.")