# Kakadu System Integration & Quality Assurance Protocol

This document serves as the master verification standard for the Kakadu engine. It ensures that all components—from the lowest-level data fetcher to the top-level dispatcher—adhere to the "Thin-Edge, Thick-Core" philosophy and the strict 1GB RAM resource constraints.

---

## Usage Guide: The Three-Phase Verification

To ensure system stability, this protocol must be executed in three distinct phases. Do not proceed to the next phase until all items in the current phase are checked.

### Phase 1: Component Audit (The "Foundation" Phase)

**Goal:** Verify that every single scraper and the DB operator are "standardized."

- **Action:** Audit every file listed in the `Audit Status` section.

- **Criteria:** Each file must strictly satisfy the requirements in **Section 1 (Memory)**, **Section 2 (Data)**, and **Section 3 (Architecture)**.

- **Outcome:** A set of "Clean" scrapers ready for integration.

### Phase 2: Main Integration (The "Orchestration" Phase)

**Goal:** Ensure the dispatcher (`main.py`) correctly manages the lifecycle.

- **Action:** Develop `main.py` and verify the items in **Section 4 (Main-Integration)**.

- **Criteria:** The system must handle CLI arguments, session types, and resource cleanup without manual intervention.

- **Outcome:** A functional, automated pipeline.

### Phase 3: End-to-End Validation (The "Stress" Phase)

**Goal:** Prove the "Zero-Loss" and "Anti-Crash" claims.

- **Action:** Run full-market ingestion cycles and simulate failures.

- **Criteria:** Verify the `Backup -> OCI -> DB` row-count consistency and the Two-Tier alerting triggers.

- **Outcome:** Production-ready deployment on OCI Micro VM.

---

## Verification Standards

### 1. Memory & Resource (1GB RAM Limit)

- [ ] **Selenium**: Headless mode, no-sandbox, and `driver.quit()` MUST be in a `finally` block.

- [ ] **Buffer**: Iterative scrapers must explicitly clear buffer (`.clear()`) immediately after DB flush.

- [ ] **Batch Size**: `BATCH_SIZE` must be sourced from `config.yaml`, not hardcoded.

- [ ] **Driver**: `python-oracledb` must be configured in **Thin Mode** (no Instant Client).

- [ ] **Isolation**: Only one Selenium instance active at a time; `cleanup_vm.sh` hook integrated in `main.py`.

### 2. Data & Robustness (Zero-Loss Principle)

- [ ] **Types**: All data passed to `DbOperator` must be basic types (`str`, `int`, `float`). No `datetime`/`Decimal` objects.

- [ ] **Error Handling**: `scrape_one()` must be wrapped in `try-except` to ensure single-symbol failures don't crash the job.

- [ ] **Sequence**: Strict execution order: **Fetch -> Local .jsonl Backup -> DB Insert**.

- [ ] **Audit Columns**: `BATCH_ID` and `LOAD_TIME` must be injected by `DbOperator._prepare_records()`, NOT by Scrapers.

- [ ] **Session Logic**: Scrapers supporting multiple sessions (e.g., pre-close/post-close) must handle these parameters via config/args without hardcoding.

### 3. Architecture & Config

- [ ] **BaseScraper**: All scrapers must implement a self-contained `.run()` method.
  - `.run()` must handle: Config Loading -> Driver Lifecycle -> Fetching -> Backup -> DB Insert.
  - `.run()` must NOT require external driver or URL arguments.

- [ ] **Modes**: `is_bulk_task` correctly set to trigger either `scrape_all()` or the `scrape_one()` loop.

- [ ] **Config**: Zero hardcoded URLs/Keys. Use `config.yaml` for settings and `.env` for secrets.

- [ ] **Stateless**: Scrapers must not hold state/data in memory between different tasks or symbols.

- [ ] **Dependencies**: All required libs (`python-oracledb`, `selenium`, etc.) are documented in `requirements.txt`.

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

---

## Known Anti-Patterns to Resolve

- [ ] **Orchestration Bypass**: No scraper implements its own `.run()` or calls `db.insert_batch` directly.

- [ ] **Driver Leaks**: No scraper requires `driver` as an argument in its public methods.

- [ ] **Hardcoded URLs**: All API endpoints moved to `config.yaml`.

- [ ] **Backup Gap**: Every single DB write is preceded by a `backup_manager.save_local()` call.

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
