# Kakadu System State Snapshot & Integration Roadmap

## 📌 System Context (The "North Star")
- **Philosophy**: "Thin-Edge, Thick-Core" (Python is a stateless collector; Oracle PL/SQL handles all logic).
- **Constraint**: Strict 1GB RAM limit (OCI Micro VM).
- **Core Principle**: Zero-Loss Data Pipeline (`Fetch` $\rightarrow$ `Local Backup` $\rightarrow$ `DB Insert` $\rightarrow$ `Cloud Sync` $\rightarrow$ `Purge`).

---

## ✅ Verified Infrastructure (The Foundation)
The following components have passed rigorous integration and unit testing and are considered "Certified":

1. **Configuration (`src/config.py`)**: 
   - Implements Dual-File loading (`.env` + `config.yaml`).
   - **ADR-015**: Hierarchical priority implemented: `Scraper-specific` $\rightarrow$ `System-global` $\rightarrow$ `Code default`.
   - **Structure**: Flat top-level configuration for scrapers to ensure direct resolution by `BaseScraper`.
2. **Database Operator (`src/db_operator.py`)**:
   - **Thin Mode**: `python-oracledb` in Thin Mode (No Instant Client).
   - **Robustness**: Implements "Batch-to-Single" fallback for maximum data yield.
   - **Audit Injection**: Automatically injects `BATCH_ID` (UUID) and `LOAD_TIME` (ISO-8601) into all ODS writes.
3. **Symbol Provider (`src/symbol_provider.py`)**:
   - **ADR-016**: Business filtering pushed to DB Views. Python layer is now a pure O(1) memory generator.
   - **Robustness**: Handles dirty data (whitespace, case, missing suffixes) with standardized formatting.
4. **Base Scraper (`src/base_scraper.py`)**:
   - **Memory Safety**: Direct generator iteration (no `list()` conversion).
   - **Performance**: Implements local buffering $\rightarrow$ batch flush to DB.
   - **Resource Lifecycle**: Guaranteed WebDriver `quit()` in `finally` blocks.
5. **Backup & Upload (`src/backup_manager.py` & `src/upload_manager.py`)**:
   - **ADR-014**: Decoupled Local Persistence from Cloud Sync.
   - **Robustness**: Atomic writes via temp-file-and-rename; format-agnostic ZIP compression.

---

## 🛠 Current Architecture State
- **ODS Schema**: Aligned with `install_ods_tables.sql`. All business columns are `VARCHAR2`.
- **Price Routing**: Shifted from internal session matrices to **Class-based Routing** (e.g., `price_ohlcv_pre` vs `price_ohlcv_post` as distinct scraper identities).
- **Scraper Status**: Most scrapers have pivoted from Selenium to API-based ingestion to save RAM (except `annc`).

---

## 🚩 Remaining Critical Path (The "To-Do")

### Phase 1: Scraper-by-Scraper Audit (High Priority)
Since `BaseScraper` was refactored, all subclasses must be updated to remove redundant initialization and adhere to the new contract.

- [ ] **`list_scraper.py`**: 
    - Remove `__init__`.
    - Update URL fetching to use `self.config.get(self.scraper_name, ...)` instead of nested `scrapers` node.
    - Add `scraper_name = "company_master"`.
- [ ] **`short_scraper.py`**: 
    - Remove `__init__`.
    - Remove hardcoded `target_table` and `is_bulk_task`.
    - Add `scraper_name = "short"`.
- [ ] **`yahoo_scraper.py`**: 
    - Remove `__init__` and all `session_type` routing logic.
    - Move `interval` and `range` resolution to `config.yaml` $\rightarrow$ `BaseScraper`.
    - Add `scraper_name = "price_ohlcv_pre"` (and create `_post` variant).
- [ ] **`afr_scraper.py`**: 
    - Remove `__init__` and manual flag assignments.
    - Add `scraper_name = "afr"`.
- [ ] **`annc_scraper.py`**: 
    - Remove `__init__` and manual flag assignments.
    - Add `scraper_name = "annc"`.
- [ ] **`consensus_scraper.py` (Major Refactor)**: 
    - Remove custom `run()` method (bypass of `BaseScraper.run` causes buffer/backup failure).
    - Implement `scrape_one()` to handle `yf.Ticker` logic.
    - Implement `scrape_all()` as `NotImplementedError`.
    - Add `scraper_name = "analyst_consensus"`.

### Phase 2: Main Orchestration (`main.py`)
- [ ] **CLI Dispatcher**: Implement `--task` and `--session-type` arguments.
- [ ] **Startup Health Check**: Validate Wallet path, DB connectivity, and `SymbolProvider` health.
- [ ] **Process Shielding**: Integrate `cleanup_vm.sh` in a `finally` block for browser tasks.
- [ ] **Two-Tier Alerting**: Implement Tier 1 (Log) and Tier 2 (Pushover) notifications.

### Phase 3: Performance Optimization (The Speed Gap)
- **Problem**: Sequential processing of ~1,800 symbols is too slow for "Pre-close" decision support.
- **Evaluation Needed**:
    - **Option A**: `AsyncIO` (`httpx`) for concurrent API requests.
    - **Option B**: `ThreadPoolExecutor` (already implemented in `BaseScraper`, needs tuning).
    - **Option C**: Pivot to `yahooquery` (with strict "No-Pandas" rule).

---

## 📝 Quick Reference for New Session
- **Target Table for Price**: `ODS_PRICE_OHLCV_PRE` / `ODS_PRICE_OHLCV_POST`.
- **Config Node for Global**: `system`.
- **Config Node for Scrapers**: Top-level (e.g., `price_ohlcv_pre`).
- **Critical Constraint**: Never load full symbol lists or large dataframes into memory.