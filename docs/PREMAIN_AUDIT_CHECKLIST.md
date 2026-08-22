# Kakadu Audit Checklist

## 1. Memory & Resource (1GB RAM Limit)
- Selenium: Headless mode, no-sandbox, and driver.quit() in finally block.
- Buffer: Iterative scrapers must clear buffer (.clear()) after DB flush.
- Batch Size: BATCH_SIZE must be sourced from config.yaml.
- Driver: python-oracledb must be in Thin Mode.
- Isolation: Only one Selenium instance at a time; cleanup_vm.sh hook available.

## 2. Data & Robustness
- Types: All data passed to DbOperator must be basic types (str, int, float). No datetime/Decimal.
- Error Handling: scrape_one() must be wrapped in try-except to prevent single-symbol crashes.
- Sequence: Fetch -> Local .jsonl Backup -> DB Insert.
- Audit Columns: BATCH_ID and LOAD_TIME must be injected by DbOperator, not by Scrapers.

## 3. Architecture & Config
- BaseScraper: All scrapers inherit from BaseScraper and use .run() as entry point.
- Modes: is_bulk_task correctly set for Bulk vs Iterative logic.
- Config: No hardcoded URLs/Keys. Use config.yaml for settings and .env for secrets.
- Stateless: Scrapers must not hold state between tasks.

## Audit Status
- base_scraper.py: [ ]
- db_operator.py: [ ]
- price_ohlcv: [ ]
- afr: [ ]
- short: [ ]
- annc: [ ]
- company_master: [ ]
- analyst_consensus: [ ]