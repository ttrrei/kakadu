Apply
# Kakadu System State Snapshot & Integration Roadmap

## 📌 System Context (The "North Star")
- **Philosophy**: "Thin-Edge, Thick-Core" (Python is a stateless collector; Oracle PL/SQL handles all logic).
- **Constraint**: Strict 1GB RAM limit (OCI Micro VM).
- **Core Principle**: Zero-Loss Data Pipeline (`Fetch` $\rightarrow$ `Local Backup` $\rightarrow$ `DB Insert` $\rightarrow$ `Cloud Sync` $\rightarrow$ `Purge`).

---

## ✅ Verified Infrastructure (The Foundation)
The following components have passed integration testing and are considered "Certified":

1. **Configuration (`src/config.py`)**: 
   - Implements Dual-File loading (`.env` + `config.yaml`).
   - **ADR-015**: Hierarchical priority implemented: `Scraper-specific` $\rightarrow$ `System-global` $\rightarrow$ `Code default`.
2. **Database Operator (`src/db_operator.py`)**:
   - **Thin Mode**: `python-oracledb` in Thin Mode (No Instant Client).
   - **Robustness**: Implements "Batch-to-Single" fallback. If a batch insert fails (e.g., ORA-12899 value too large), it automatically retries records individually to ensure maximum data yield.
   - **Audit Injection**: Automatically injects `BATCH_ID` (UUID) and `LOAD_TIME` (ISO-8601) into all ODS writes.
3. **Symbol Provider (`src/symbol_provider.py`)**:
   - Implements O(1) memory usage via generators fetching from `ODS_COMPANY_MASTER`.
4. **Backup & Upload (`src/backup_manager.py` & `src/upload_manager.py`)**:
   - **ADR-014**: Decoupled Local Persistence from Cloud Sync.
   - Pattern: `Local Write` (during scrape) $\rightarrow$ `Compress & Sync` (end of job) $\rightarrow$ `Purge`.

---

## 🛠 Current Architecture State
- **ODS Schema**: Aligned with `install_ods_tables.sql`. All business columns are `VARCHAR2` to prevent type-conversion crashes.
- **Price Routing**: `price_ohlcv` scraper uses a `sessions` matrix in `config.yaml` to route data to `ODS_PRICE_OHLCV_PRE` or `ODS_PRICE_OHLCV_POST` based on the execution window.
- **Scraper Status**: Most scrapers have pivoted from Selenium to API-based ingestion to save RAM (except `annc`).

---

## 🚩 Remaining Critical Path (The "To-Do")

### Phase 1: Component Audit (Final Polish)
- [ ] **BaseScraper Integration**: Verify the "Glue" logic: `main.py` $\rightarrow$ `session_type` $\rightarrow$ `target_table` $\rightarrow$ `DbOperator`.
- [ ] **Scraper-by-Scraper Audit**: 
    - Ensure all scrapers use `CODE` instead of `SYMBOL`.
    - Remove all hardcoded URLs/Keys.
    - Verify `needs_driver` flag alignment in `config.yaml`.

### Phase 2: Main Orchestration (`main.py`)
- [ ] **CLI Dispatcher**: Implement `--task` and `--session-type` arguments.
- [ ] **Startup Health Check**: Validate Wallet path, DB connectivity, and `SymbolProvider` health.
- [ ] **Process Shielding**: Integrate `cleanup_vm.sh` in a `finally` block for browser tasks.
- [ ] **Two-Tier Alerting**: Implement Tier 1 (Log) and Tier 2 (Pushover) notifications.

### Phase 3: Performance Optimization (The Speed Gap)
- **Problem**: Current sequential processing of ~1,800 symbols is too slow for "Pre-close" decision support.
- **Evaluation Needed**:
    - **Option A**: `AsyncIO` (`httpx`) for concurrent API requests.
    - **Option B**: `ThreadPoolExecutor` for `scrape_one`.
    - **Option C**: Pivot to `yahooquery` (with strict "No-Pandas" rule).

---

## 📝 Quick Reference for New Session
- **Target Table for Price**: `ODS_PRICE_OHLCV_PRE` / `ODS_PRICE_OHLCV_POST`.
- **Config Node for Global**: `system`.
- **Config Node for Scrapers**: `scrapers`.
- **Critical Constraint**: Never load full symbol lists or large dataframes into memory.