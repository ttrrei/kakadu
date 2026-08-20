# Kakadu System Architecture Design (SAD)

## 1. High-Level Architecture

Kakadu is a lightweight data acquisition and quantitative intelligence engine designed for ASX market data. Running on an OCI Micro VM (1GB RAM) with an Oracle Autonomous Database (Always Free Tier) backend, Kakadu achieves stable execution under extreme hardware constraints via a **"Thin-Edge, Thick-Core"** architecture.

```
+-----------------------------------------------------------------------+
| Thin-Edge (Python 3.10+)                                              |
| - Stateless HTTP/API Fetchers                                         |
| - Standalone Headless Browser Scrapers (Selenium, on-demand/ephemeral)|
| - Small-Batch Chunked PURE-INSERT (5-10 records per execution)         |
| - Local Text Persistence (saved to /home/ubuntu/backup/, OCI sync)    |
+-----------------------------------------------------------------------+
                                  |
            Thin Mode Driver (Wallet mTLS Connection)
                                  v
+-----------------------------------------------------------------------+
| Thick-Core (Oracle PL/SQL)                                            |
| - ODS Tables (Raw VARCHAR2 landing, zero data loss)                   |
| - Data Cleansing & Type Cast Stored Procedures                         |
| - Technical Indicator Computation Engine (EMA, PSAR, Supertrend)       |
+-----------------------------------------------------------------------+
```

**Core Design Principle:** Thin-Edge, Thick-Core

- **Thin-Edge (Python):** Responsible solely for Data Fetching → Transport → DB Ingestion. Processes are strictly stateless and exit immediately upon completion without memory persistence.
- **Thick-Core (Oracle PL/SQL):** All data transformations, validations, and technical indicator computations are pushed down to the database layer. The Python layer maintains no heavy state.

## 2. Core Functional Components

### A. Unified Dispatcher (main.py)

**Responsibility:** Single CLI entry point using argparse to route extraction tasks, parse CLI flags, configure logging, and enforce clean process termination.

### B. Database Operator Layer (db_operator.py)

**Responsibility:** Manages connection pooling (Wallet mTLS) via python-oracledb Thin Mode. Executes pure-INSERT statements for small-batch commits (5–10 records). All deduplication is deferred to asynchronous Oracle PL/SQL stored procedures. If a batch insertion fails, it automatically falls back to row-by-row execution; individual bad records are logged and skipped to prevent silent data loss while allowing the rest of the batch to complete successfully.

### C. Data Extractors (src/scrapers/)

**Responsibility:** Decoupled, independent scraping modules per data source.

| Component | Data Source | Method | Schedule Frequency |
|-----------|-------------|--------|-------------------|
| price_ohlcv | Yahoo / ASX Quotes | API / HTTP JSON | Multiple times per trading day / Daily Post-close |
| afr | AFR Real-time quotes & EAV depth | API / HTTP JSON | Pre-close / Post-close |
| annc | ASX Company Announcements | Headless Browser (Selenium) | Daily Morning |
| company_master | Ticker universe & metadata | API / HTTP CSV | Weekly (Sat 06:00 AEST) |
| analyst_consensus | Broker analyst ratings & consensus | Headless Browser (Selenium) | Weekly (Sun 07:00 AEST) |
| short | Shortman daily short interest | API / HTTP JSON | Daily Post-close |

**Browser Isolation Strategy:** Selenium/Chrome instances launch on-demand and execute strictly serially (at most one Chrome instance active on the VM at any time). Immediately after a task finishes, cleanup_vm.sh executes SIGKILL on residual Chrome/Chromedriver processes to guarantee zero process or memory leakage.

### D. Oracle Storage & Analytics Layer (sql/)

- **ODS Layer (Operational Data Store):** All columns land as VARCHAR2 to strictly prevent data truncation, enabling flexible PL/SQL cleansing downstream.
- **Core & Analytics Layer:** PL/SQL stored procedures transform raw ODS records into typed datasets and compute technical indicators (EMA, PSAR, Supertrend).

### E. Text Backup & Validation Layer (src/backup/)

**Responsibility:** Prior to database ingestion, raw extracted data is persisted locally in JSON Lines format under `/home/ubuntu/backup/` (utilizing the primary 30GB disk partition) and batch-uploaded to OCI Object Storage. Post-ingestion, record counts between OCI backup files and DB tables are verified; discrepancies exceeding threshold trigger alerts.

## 3. ODS Domain Model & Legacy Mapping

| Kakadu ODS Table | Data Domain | Description | Frequency / Window (AEST) | Business Primary Key | Legacy Ref |
|------------------|-------------|-------------|---------------------------|----------------------|------------|
| ODS_PRICE_OHLCV | Yahoo / ASX Quotes | OHLCV prices (Real-time/EOD/History) | Daily Post-close / Intraday | (CODE, RAW_TIMESTAMP) | ods_yahoo_history |
| ODS_PRICE_TICK | AFR Real-Time Tick | AFR real-time tick data | Pre-close & Post-close | (CODE, TICK_TIME) | ODS_TICKER |
| ODS_PRICE_QUOTE_EAV | AFR Quote EAV | AFR market depth / valuation pairs | Pre-close 15:25 / Post-close 16:45 | (CODE, TAG, UPDATE_TIME) | ODS_QUOTE |
| ODS_SHORT_POSITION | Shortman Daily | Daily short interest data | Daily Post-close | (CODE, UPDATE_DATE) | ODS_SHORTMAN_HISTORY |
| ODS_MARKET_ANNC | ASX Announcements | Official ASX company news | Daily Morning | (CODE, "DATE", TITLE) | ODS_ANNC |
| ODS_COMPANY_MASTER | Ticker Master | Market-wide ticker list & metadata | Weekly (Sat 06:00) | (CODE, UPDATE_DATE) | MTD_CODE_LIST |
| ODS_ANALYST_CONSENSUS | Broker Consensus | Analyst ratings & consensus | Weekly (Sun 07:00) | (CODE, UPDATE_DATE) | ODS_CONSENSUS |

## 4. Resource Management & Anti-Crash Strategies

| Strategy | Implementation | Effect |
|----------|----------------|--------|
| Zero Instant Client | Uses python-oracledb Thin Mode without C libraries | Saves ~400MB RAM overhead |
| Small-Batch PURE-INSERT | Commits 5–10 records per execution batch | Maintains flat Python RAM footprint; deduplication deferred to async PL/SQL |
| Browser Isolation & Purge | Sequential Selenium execution followed by cleanup_vm.sh (only for annc & analyst_consensus); company_master migrated to API/CSV | Prevents orphan Chrome processes from leaking RAM; reduced cleanup frequency lowers VM pressure |
| Physical VM Reboot | Scheduled weekly crontab reboot | Completely flushes OS cache and memory fragmentation |
| Swap Safety Net | Allocates a 512MB swap file on the OS layer | Emergency buffer for unexpected OOM spikes |

**Swap Usage Principle:** The 512MB swap serves strictly as a last-resort fallback and is not intended for regular execution. Routine memory safety relies entirely on batch size capping and strict process termination.

## 5. Data Backup & Consistency Verification

- **Local Disk Persistence:** Raw extracted records (JSON Lines) are saved to `/home/ubuntu/backup/<source>/<timestamp>.jsonl` on the 30GB main partition.
- **OCI Sync:** Upon task completion, the local backup directory is batch-uploaded to OCI Object Storage via OCI CLI or SDK.
- **Consistency Verification:** Compares ingested ODS record counts against raw text line counts using a **two-tier alerting strategy**:
  - **Tier 1 (Warning Log):** Single batch row-count mismatch → logged locally, backup retained, no Pushover notification.
  - **Tier 2 (Pushover Alert):** Cumulative retry failures OR bulk missingness across multiple batches → triggers Pushover notification.
- **Auto-Purge:** Once uploaded and verified, processed local files under `/home/ubuntu/backup/` are automatically purged to prevent local disk exhaustion.

## 6. Logging & Alerting

- **Logging:** Process-level logs are written to local files (daily rotation) and Stdout.
- **Alerting:** Pushover notifications use a **two-tier strategy** aligned with BRD's "High-Tolerance Anti-False-Alarm" principle:
  - **Tier 1 (Warning Log):** When a single batch's local JSONL backup row count does not match the database write row count → log to file, retain backup. No human notification.
  - **Tier 2 (Pushover Alert):** When cumulative retry failures occur OR bulk data missingness is detected across the network/system → triggers Pushover to on-call.
  - **Rationale:** Prevents alert fatigue from transient single-batch hiccups while ensuring serious systemic issues escalate immediately.
