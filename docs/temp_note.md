# Kakadu Integration Roadmap

## Current System State

**Foundation Layer (Certified):** config, db_operator, symbol_provider, base_scraper, backup_manager, and upload_manager have all passed rigorous audits.

**Scraper Layer (Verified):** price_ohlcv, afr, annc, short, company_master, and consensus have been standardized and passed End-to-End (E2E) Truth Tests.

**Configuration Layer (Aligned):** 
- `config.yaml` implements identity-based configuration
- `is_bulk` flags are perfectly synchronized with Scraper implementations

---

## Remaining Critical Path

### Phase 1: Main Orchestration (main.py)

**Goal:** Transform independent components into an automated pipeline, achieving "one-click execution with zero manual intervention."

- [ ] **CLI Dispatcher Implementation**
  - Implement argparse to support `--task` (e.g., `--task annc`)
  - Implement `--session-type` (e.g., pre-close vs post-close) to route tasks correctly

- [ ] **Startup Health Check**
  - Validate existence of Oracle Wallet directory
  - Verify all critical environment variables in `.env` are present
  - SymbolProvider Probe: Attempt to fetch a single symbol from the DB; if it fails, terminate the job immediately with a critical error to prevent "silent failure"

- [ ] **Lifecycle Orchestration**
  - Implement the strict execution flow: Config Loading → Scraper.run() → UploadManager.sync_to_cloud() → Local Backup Purge

- [ ] **Process Shielding (The Final Defense)**
  - In the outermost `finally` block of `main.py`, explicitly invoke `cleanup_vm.sh` for any task where `needs_driver=True` to ensure zero Chrome process leakage

- [ ] **Two-Tier Alerting Integration**
  - **Tier 1 (Warning):** Compare local `.jsonl` row counts vs DB write counts; log a warning and retain backup if they mismatch
  - **Tier 2 (Pushover):** Trigger external Pushover notifications for cumulative failures or bulk data missingness

---

### Phase 2: Production Deployment & Stress Testing

**Goal:** Prove "Zero-Crash" and "Zero-Loss" claims on the 1GB RAM OCI Micro VM.

- [ ] **Environment Mirroring**
  - Deploy the full stack on an Ubuntu 24.04 LTS VM
  - Configure a 512MB Swap file as a last-resort safety net

- [ ] **Full-Market Truth Test**
  - Execute full ingestion cycles (~2,000 symbols) and monitor memory peaks via `htop`
  - Verify that `cleanup_vm.sh` completely flushes RAM after Selenium tasks

- [ ] **Failure Simulation**
  - Simulate network outages → Verify local backup integrity
  - Simulate DB connection timeouts → Verify DbOperator fallback mechanisms

---

### Phase 3: Thick-Core (PL/SQL) Enhancement

**Goal:** Push all business logic and transformations entirely into the Oracle Database.

- [ ] **ODS Data Cleansing Procedures**
  - Develop PL/SQL stored procedures to clean VARCHAR2 raw data and cast it to strong types
  - Implement deduplication logic based on BATCH_ID

- [ ] **Technical Indicator Engine**
  - Implement incremental calculation procedures for EMA, PSAR, and Supertrend within the DB

- [ ] **Signal Output Views**
  - Create final analytical views (e.g., VW_TRADING_SIGNALS) for direct consumption by APIs/Reports

---

## Quick Reference

- **Memory Red-Line:** Never use `list(generator)` or load large Pandas DataFrames in the Python layer.
- **Persistence Principle:** Every DB write must be preceded by a BackupManager local save.
- **Cleanup Principle:** Every Selenium-based task must terminate with a call to `cleanup_vm.sh`.