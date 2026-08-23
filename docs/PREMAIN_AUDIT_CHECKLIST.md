# Kakadu Pre-Main Integration Audit Checklist

## 1. Memory & Resource (1GB RAM Limit)
- Selenium: Headless mode, no-sandbox, and driver.quit() MUST be in a finally block.
- Buffer: Iterative scrapers must explicitly clear buffer (.clear()) immediately after DB flush.
- Batch Size: BATCH_SIZE must be sourced from config.yaml, not hardcoded.
- Driver: python-oracledb must be configured in Thin Mode (no Instant Client).
- Isolation: Only one Selenium instance active at a time; cleanup_vm.sh hook integrated in main.

## 2. Data & Robustness
- Types: All data passed to DbOperator must be basic types (str, int, float). No datetime/Decimal objects.
- Error Handling: scrape_one() must be wrapped in try-except to ensure single-symbol failures don't crash the job.
- Sequence: Strict execution order: Fetch -> Local .jsonl Backup -> DB Insert.
- Audit Columns: BATCH_ID and LOAD_TIME must be injected by DbOperator._prepare_records(), NOT by Scrapers.

## 3. Architecture & Config
- BaseScraper: All scrapers must implement a self-contained .run() method.
  - .run() must handle: Config Loading -> Driver Lifecycle -> Fetching -> Backup -> DB Insert.
  - .run() must NOT require external driver or URL arguments.
- Modes: is_bulk_task correctly set to trigger either scrape_all() or the scrape_one() loop.
- Config: Zero hardcoded URLs/Keys. Use config.yaml for settings and .env for secrets.
- Stateless: Scrapers must not hold state/data in memory between different tasks or symbols.

## Known Anti-Patterns to Resolve
- [ ] **Orchestration Bypass**: Ensure no scraper (e.g., ConsensusScraper) implements its own `.run()` or calls `db.insert_batch` directly.
- [ ] **Driver Leaks**: Ensure no scraper requires `driver` as an argument in its public methods; all driver management must be internal to `.run()`.
- [ ] **Hardcoded URLs**: Move all API endpoints and URLs from Python code to `config.yaml`.
- [ ] **Backup Gap**: Verify that every single DB write is preceded by a `backup_manager.save_local()` call.

## Audit Status
- base_scraper.py: [ ]
- db_operator.py: [ ]
- price_ohlcv: [ ]
- afr: [ ]
- short: [ ]
- annc: [ ]
- company_master: [ ]
- analyst_consensus: [ ]