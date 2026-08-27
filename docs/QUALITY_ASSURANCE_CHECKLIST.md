# Kakadu System Integration & Quality Assurance Protocol

This document serves as the master verification standard for the Kakadu engine—ensuring all components adhere to the "Thin-Edge, Thick-Core" philosophy and the strict 1GB RAM resource constraints.

---

## Usage Guide: The Three-Phase Verification

Execute in three distinct phases. Do not proceed to the next phase until all items in the current phase are checked.

### Phase 1: Component Audit (The "Foundation" Phase)
**Goal:** Verify every scraper and DB operator are "standardized."

- **Action:** Audit every file listed in the `Audit Status` section.
- **Criteria:** Each file must strictly satisfy requirements in **Section 1**, **Section 2**, and **Section 3**.
- **Outcome:** A set of "Clean" scrapers ready for integration.

### Phase 2: Main Integration (The "Orchestration" Phase)
**Goal:** Ensure `main.py` correctly manages the lifecycle.

- **Action:** Develop `main.py` and verify items in **Section 4**.
- **Criteria:** System must handle CLI arguments, session types, and resource cleanup without manual intervention.
- **Outcome:** A functional, automated pipeline.

### Phase 3: End-to-End Validation (The "Stress" Phase)
**Goal:** Prove the "Zero-Loss" and "Anti-Crash" claims.

- **Action:** Run full-market ingestion cycles and simulate failures.
- **Criteria:** Verify `Backup -> OCI -> DB` row-count consistency and Two-Tier alerting triggers.
- **Outcome:** Production-ready deployment on OCI Micro VM.

---

## Verification Standards

### 1. Memory & Resource (1GB RAM Limit)

- [ ] **Selenium**: Headless mode, no-sandbox, and `driver.quit()` MUST be in a `finally` block.
- [ ] **Buffer**: Iterative scrapers must explicitly clear buffer (`.clear()`) immediately after DB flush.
- [ ] **Batch Size**: `BATCH_SIZE` must be sourced from `config.yaml`, not hardcoded.
- [ ] **Driver**: `python-oracledb` must be configured in **Thin Mode** (no Instant Client).
- [ ] **Isolation**: Only one Selenium instance active at a time; `cleanup_vm.sh` hook integrated in `main.py`.
- [ ] **Symbol Provider**: `SymbolProvider` interface (or equivalent in `BaseScraper`/`main.py`) must fetch symbols as a generator/iterator from `ODS_COMPANY_MASTER` via `DbOperator`, never loading the full symbol list into memory at once. Memory usage for symbol iteration must remain O(1) regardless of total symbol count.

### 2. Data & Robustness (Zero-Loss Principle)

- [ ] **Types**: All data passed to `DbOperator` must be basic types (`str`, `int`, `float`). No `datetime`/`Decimal` objects.
- [ ] **Error Handling**: `scrape_one()` must be wrapped in `try-except` to ensure single-symbol failures don't crash the job.
- [ ] **Sequence**: Strict execution order: **Fetch -> Local .jsonl Backup -> DB Insert**.
- [ ] **Audit Columns**: `BATCH_ID` and `LOAD_TIME` must be injected by `DbOperator._prepare_records()`, NOT by Scrapers.
- [ ] **Session Logic**: Scrapers supporting multiple sessions (e.g., pre-close/post-close) must handle these parameters via config/args without hardcoding.
- [ ] **Symbol Validation**: Symbols retrieved from `SymbolProvider` must be validated (non-empty string, alphanumeric with allowed exchange suffixes like `.AX`) before being passed to `scrape_one()`. Invalid symbols must be logged and skipped without terminating the job.
- [ ] **Fallback Mechanism**: If `SymbolProvider` fails to retrieve symbols (e.g., DB connection issue), iterative scrapers must log a Tier 2 alert-worthy error and terminate gracefully—no hardcoded symbol fallbacks are permitted.

### 3. Architecture & Config

- [ ] **BaseScraper**: All scrapers must implement a self-contained `.run()` method.
  - `.run()` must handle: Config Loading -> Driver Lifecycle -> Fetching -> Backup -> DB Insert.
  - `.run()` must NOT require external driver or URL arguments.
- [ ] **Modes**: `is_bulk_task` correctly set to trigger either `scrape_all()` or the `scrape_one()` loop.
- [ ] **Config**: Zero hardcoded URLs/Keys. Use `config.yaml` for settings and `.env` for secrets.
- [ ] **Stateless**: Scrapers must not hold state/data in memory between different tasks or symbols.
- [ ] **Dependencies**: All required libs (`python-oracledb`, `selenium`, etc.) are documented in `requirements.txt`.
- [ ] **SymbolProvider Abstraction**: The mechanism for providing symbols to iterative scrapers (whether via a dedicated `SymbolProvider` class or integrated into `BaseScraper`) must be abstracted such that scrapers depend only on an iterable of symbol strings, not on database specifics or query logic.
- [ ] **Centralized Symbol Source**: All iterative scrapers must source their symbol list exclusively from the centralized `SymbolProvider` (backed by `ODS_COMPANY_MASTER`). No scraper may contain hardcoded symbols, scattered SQL queries, or alternative symbol sources (e.g., local files, APIs) for its primary symbol iteration.
- [ ] **Configurable Symbol Filtering**: Optional symbol filtering (e.g., by sector, market cap, or inclusion/exclusion lists) must be configurable via `config.yaml` and applied by the `SymbolProvider`, not within individual scrapers.

### 4. Main-Integration & Verification (The "Final Mile")

- [ ] **CLI Dispatcher**: `main.py` supports `--task` and `--session-type` arguments per BRD schedule.
- [ ] **Process Shielding**: `cleanup_vm.sh` is explicitly invoked in a `finally` block for all browser-based tasks.
- [ ] **Two-Tier Alerting**:
  - **Tier 1**: (Local Count != DB Count) -> Log Warning + Retain Backup.
  - **Tier 2**: (Cumulative Failures / Bulk Missingness) -> Pushover Alert.
- [ ] **Backup Lifecycle**:
  - Local `.jsonl` -> OCI Object Storage Sync.
  - Row count verification between Local File and DB Table.
  - Local purge ONLY after successful OCI sync & verification.
- [ ] **Database Connection Resilience**: `DbOperator` must handle stale connections, implement proper cleanup, and validate connection health before use.
- [ ] **Atomic Backup Writes**: Backup files must be written to a temporary file first and atomically renamed upon completion.
- [ ] **Explicit Error Classification**: Scrapers must distinguish between HTTP 429 (Rate Limit), Empty API Response (200 OK + []), and Network/HTTP 5xx errors.
- [ ] **Startup Validation**: On launch, the system must validate Oracle Wallet directory, required environment variables, and `python-oracledb` version.
- [ ] **SymbolProvider Health Check**: `main.py` must validate the `SymbolProvider` can establish a database connection and retrieve at least one symbol from `ODS_COMPANY_MASTER` during startup validation—failure must block execution and log a critical error.
- [ ] **Symbol Count Metrics**: The number of symbols processed by each iterative scraper must be logged at INFO level for monitoring and anomaly detection.

---

## Known Anti-Patterns to Resolve

- [ ] **Orchestration Bypass**: No scraper implements its own `.run()` or calls `db.insert_batch` directly.
- [ ] **Driver Leaks**: No scraper requires `driver` as an argument in its public methods.
- [ ] **Hardcoded URLs**: All API endpoints moved to `config.yaml`.
- [ ] **Backup Gap**: Every single DB write is preceded by a `backup_manager.save_local()` call.
- [ ] **Symbol Source Pollution**: No iterative scraper may bypass the centralized `SymbolProvider` to fetch symbols via direct API calls, hardcoded lists, or alternative database tables (except `ODS_COMPANY_MASTER` as the source of truth).

---

## Audit Status

- [ ] `base_scraper.py`
- [ ] `db_operator.py`
- [ ] `price_ohlcv`
- [ ] `afr`
- [ ] `short`
- [ ] `annc`
- [ ] `company_master`
- [ ] `analyst_consensus`
