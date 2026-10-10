# src/scrapers/annc_scraper.py
from __future__ import annotations
import logging
import time
from typing import List, Dict, Any, Optional
import requests
import html
from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AnncScraper(BaseScraper):
    """ASX Company Announcements Scraper - Pure HTTP (no Selenium)."""

    scraper_name = "annc"
    is_bulk_task = True
    needs_driver = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        self.connect_timeout = 10
        self.read_timeout = 60
        self.max_retries = 3

    def scrape_all(self, driver: Optional[Any], symbols: List[str] = None) -> List[Dict[str, Any]]:
        cfg = self.config.get(self.scraper_name, {})
        urls = cfg.get('urls', [])

        if not urls:
            logger.error(f"Configuration Error: 'urls' list missing for {self.scraper_name} in config.yaml")
            return []

        all_extracted_data = []

        for url in urls:
            page_records = self._fetch_with_retry(url)
            if page_records:
                logger.info(f"Successfully extracted {len(page_records)} records from {url}")
                all_extracted_data.extend(page_records)
            else:
                logger.error(f"All retries exhausted for {url}")

        return all_extracted_data

    def _fetch_with_retry(self, url: str) -> List[Dict[str, Any]]:
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Fetching {url} (attempt {attempt}/{self.max_retries})")
                resp = self.session.get(
                    url,
                    timeout=(self.connect_timeout, self.read_timeout),
                    allow_redirects=True
                )
                resp.raise_for_status()

                if self._is_blocked(resp):
                    raise RuntimeError("Response appears to be a WAF challenge page")

                return self._parse_html(resp.text)

            except requests.exceptions.Timeout:
                last_error = f"Timeout (connect={self.connect_timeout}s, read={self.read_timeout}s)"
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {e}"
            except Exception as e:
                last_error = f"Parse error: {e}"

            logger.warning(f"Attempt {attempt} failed for {url}: {last_error}")
            if attempt < self.max_retries:
                time.sleep(5 * attempt)

        if "announcement_data tag not found" in str(last_error):
            logger.warning(f"No announcements available (empty page): {url}")
        else:
            logger.error(f"All {self.max_retries} attempts failed for {url}: {last_error}")
        return []

    def _is_blocked(self, resp: requests.Response) -> bool:
        text_lower = resp.text.lower()
        if 'announcement_data' in text_lower:
            return False
        blocked_indicators = [
            'incapsula incident id', 'imperva', 'access denied',
            'request blocked', 'please enable javascript',
            'checking your browser', 'ddos protection',
        ]
        return any(indicator in text_lower for indicator in blocked_indicators)

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'lxml')

        announcement_data = soup.find('announcement_data')
        if not announcement_data:
            logger.error("<announcement_data> tag not found in response")
            return []

        rows = announcement_data.find_all('tr')
        if len(rows) <= 1:
            logger.warning("No data rows found (only header or empty)")
            return []

        page_records = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue

            code = cols[0].get_text(separator=' ', strip=True)
            release_date = cols[1].get_text(separator=' ', strip=True)
            title = self._extract_title(cols[3])

            # PSENSITIVE is represented by an icon in the dedicated third column.
            # Do not infer sensitivity from cell text: an &nbsp; cell can look empty
            # after HTML/text normalization.
            #
            # <td>&nbsp;</td>                                      -> False
            # <td><img src=".../icon-price-sensitive.svg" ...></td> -> True
            sensitive_cell = cols[2]
            sensitive_icon = None

            for img in sensitive_cell.find_all("img"):
                src = str(img.get("src", "")).lower()
                alt = str(img.get("alt", "")).lower()
                title_attr = str(img.get("title", "")).lower()

                if (
                    "price-sensitive" in src
                    or "price sensitive" in alt
                    or "price sensitive" in title_attr
                ):
                    sensitive_icon = img
                    break

            # Keep the existing string format expected by the database layer.
            psensitive = "True" if sensitive_icon is not None else "False"

            record = {
                "CODE": code,
                "RELEASE_DATE": release_date,
                "PSENSITIVE": psensitive,
                "TITLE": title,
            }
            page_records.append(record)

        return page_records

    def scrape_one(self, driver: Optional[Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Bulk-only scraper: not used, but must exist for ABC contract."""
        return None


    def _extract_title(self, cell) -> str:
        """只取标题文字，忽略 <span>(页数/大小/PDF 标签) 和 <img>，
        同时处理被转义成文本的 <span ...>PDF</span>。"""
        anchor = cell.find("a")
        if anchor is None:
            anchor = cell

        parts = anchor.find_all(string=True, recursive=False)
        title = " ".join(parts)

        # 文本里如果带有被转义/字面的标签，再解析一次并删掉 span/img
        if "<" in title or "&lt;" in title or "&amp;" in title:
            frag = BeautifulSoup(html.unescape(title), "lxml")
            for tag in frag.find_all(["span", "img"]):
                tag.decompose()
            title = frag.get_text(" ", strip=True)

        title = title.replace("\xa0", " ")
        return " ".join(title.split())