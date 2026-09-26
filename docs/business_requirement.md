# Kakadu Project Business Requirements Document (BRD)

## 1. Project Definition & Philosophy

- **Project Codename**: Kakadu (An ultra-lightweight data ingestion and analysis pipeline tailored for the ASX market).

- **Runtime Environment Constraints**:
  - Compute Node: OCI Micro VM (Ubuntu 24.04 LTS, 1GB RAM).
  - Database Node: Oracle Autonomous Database (ADB, Always Free Tier) EQUITY Schema.

- **Core Philosophy — "Thin-Edge, Thick-Core"**:
  - **Thin-Edge (Python 3.10+)**: Responsible solely for stateless data collection and transmission, strictly controlling memory overhead.
  - **Thick-Core (Oracle PL/SQL)**: Data validation, cleansing, transformation, and technical indicator generation (such as EMA, PSAR, Supertrend) are fully pushed down to the Oracle database for computation.

---

## 2. Ultra-Lightweight & Anti-Crash Requirements

- **Zero Instant Client Driver**: Mandates the use of `python-oracledb Thin Mode` + Wallet mTLS authentication, eliminating the memory overhead of client dynamic libraries.

- **Task Decoupling and Process Isolation**: API/HTTP collection tasks and headless browser tasks (Selenium) are isolated via Master Shell execution (`run_task.sh`), which automatically invokes `cleanup_vm.sh` to forcefully terminate residual Chrome processes before and after runs.

- **Streamed Chunked PURE-INSERT**: Data submission uses small batches (Batch Size = 5-10) to execute pure-INSERT statements, maintaining a flat memory curve. All deduplication is handled asynchronously by Oracle PL/SQL stored procedures.

- **Scheduled Daily VM Bash Reboot**: During the system's inactivity window, a bash and crontab schedule triggers a physical VM daily reboot to thoroughly clean up system cache and physical memory residuals.

- **Swap Memory Safeguard**: The system is configured with 512MB of swap space as a last-resort fallback for unexpected memory spikes.

---

## 3. Notification & Alerting Strategy

- **High-Tolerance Anti-False-Alarm Strategy (Pushover Integration)**:
  - **Background**: Fully accounts for the inherent instability of Web Scraping, target website structure tweaks, and short-term network jitter.
  - **Two-Tier Alerting Rule**:
    - **Tier 1 (Warning Log)**: Single batch row-count mismatch between local JSONL backup and database write -> logged to file for later inspection, backup retained. No immediate human notification.
    - **Tier 2 (Pushover Alert)**: Cumulative retry failures OR bulk data missingness detected across multiple batches/sources -> triggers Pushover notification to on-call.
  - **Principle**: Zero-tolerance alerts are suppressed; Pushover is reserved strictly for scenarios that indicate systemic data loss risk, not transient single-batch hiccups.

---

## 4. ODS Domain Data Model

Adopts standardized naming driven by data domains and business entities. Business columns consistently use `VARCHAR2` (zero-loss principle), with audit columns `LOAD_TIME`, and `BATCH_ID` uniformly injected:

| ODS Table Name | Business Domain & Purpose | Primary Key |
|---|---|---|
| **`ODS_PRICE_OHLCV`** | Yahoo 60d/1h K-line price data | `(CODE, RAW_TIMESTAMP)` |
| **`ODS_PRICE_TICK`** | AFR real-time tick-level granular price | `(CODE, TICK_TIME)` |
| **`ODS_PRICE_QUOTE_EAV`** | AFR real-string quote EAV key-value pairs (bid/ask, valuation, etc.) | `(CODE, TAG, UPDATE_TIME)` |
| **`ODS_SHORT_POSITION`** | Market-wide daily short positions | `(CODE, UPDATE_DATE)` |
| **`ODS_MARKET_ANNC`** | ASX official company announcements and news | `(CODE, "DATE", TITLE)` |
| **`ODS_COMPANY_MASTER`** | Market-wide company master data (code, sector, market cap) via API CSV export | `(CODE, UPDATE_DATE)` |
| **`ODS_ANALYST_TRENDS`** | Analyst rating trends & consensus (Yahoo API) | `(CODE, UPDATE_DATE)` |
| **`ODS_ANALYST_TARGETS`** | Analyst price targets & valuation (Yahoo API) | `(CODE, UPDATE_DATE)` |

---

## 5. Execution Schedule Windows (AEST)

- **Pre-close (~15:25 Mon-Fri)**: Collects afr and quote near-closing prices for intra-day signal calculation via specific tasks (e.g., `price_ohlcv_pre`).

- **Post-close (~16:45 onwards Mon-Fri)**: Sequentially collects afr, quote settlement prices, shortman shorting data (`ODS_SHORT_POSITION`), and annc company announcements via specific tasks (e.g., `price_ohlcv_post`, `short`, `annc`).

- **Weekly (Weekend Sat 06:00 / Sun 07:00)**:
  - Fetches `ODS_COMPANY_MASTER` master data via **API CSV Export**.
  - Collects Analyst Trends and Targets via **Yahoo API** (writing to `ODS_ANALYST_TRENDS` and `ODS_ANALYST_TARGETS` in a single job).
  - Executes VM daily reboot task via crontab.
