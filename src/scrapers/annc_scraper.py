# src/scrapers/annc_scraper.py

import logging
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from src.base_scraper import BaseScraper

class AnncScraper(BaseScraper):
    """
    ASX Company Announcements Scraper.
    Implements the 'Bulk' extraction pattern per ADR-008.
    """

    # 提取选择器为类属性，便于未来移入 config.yaml
    TABLE_SELECTOR = (By.TAG_NAME, "announcement_data")
    ROW_SELECTOR = (By.TAG_NAME, "tr")
    COL_SELECTOR = (By.TAG_NAME, "td")

    def __init__(self):
        super().__init__()
        self.is_bulk_task = True
        self.logger = logging.getLogger(__name__)

    def scrape_all(self, driver: WebDriver, symbols: List[str] = None) -> List[Dict[str, Any]]:
        """
        Extracts all announcement records from the current page.
        """
        self.logger.info("Starting announcement extraction...")
        results = []

        try:
            # 定位表格主体
            table_body = driver.find_element(*self.TABLE_SELECTOR).find_element(By.TAG_NAME, "tbody")
            rows = table_body.find_elements(*self.ROW_SELECTOR)
            
            self.logger.info(f"Found {len(rows)} potential announcement rows.")

            for row in rows:
                try:
                    cols = row.find_elements(*self.COL_SELECTOR)
                    if len(cols) < 4:
                        continue

                    # 业务逻辑：敏感度判断
                    raw_sensitive = cols[2].text
                    if raw_sensitive == '':
                        psensitive = 'True'
                    elif raw_sensitive.strip() == '':
                        psensitive = 'False'
                    else:
                        psensitive = 'Other'

                    # 构建记录 (仅包含业务列)
                    record = {
                        "CODE": cols[0].text.strip(),
                        "RELEASE_DATE": cols[1].text.replace("\n", " ").strip(),
                        "PSENSITIVE": psensitive,
                        "TITLE": cols[3].text.replace("\n", " ").strip()
                    }
                    results.append(record)

                except Exception as row_err:
                    self.logger.warning(f"Skipping a row due to error: {row_err}")
                    continue

        except (NoSuchElementException, TimeoutException) as e:
            self.logger.error(f"Failed to locate announcement table: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during scrape_all: {e}")

        self.logger.info(f"Successfully extracted {len(results)} records.")
        return results

    def scrape_one(self, driver: WebDriver, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """Not implemented for Bulk mode."""
        return None