# Kakadu Project Implementation Roadmap

## 1. Executive Summary & Design Constraints

Kakadu is an ultra-lightweight quantitative data collection and indicator calculation engine designed for the Australian Securities Exchange (ASX). This project operates under extreme hardware constraints:

- **Compute**: OCI Micro VM (1GB RAM, Ubuntu 24.04 LTS)
- **Database**: Oracle Autonomous Database (ADB Always Free Tier, EQUITY Schema)

**Core Philosophy**: Thin-Edge, Thick-Core — Python is responsible only for stateless scraping and append-only writing; PL/SQL handles data cleaning, deduplication, and indicator calculations.

## 2. Phased Implementation Strategy

```
[Phase 1: Infra & DB] ──> [Phase 2: Scraper Iteration] ──> [Phase 3: Automation] ──> [Phase 4: Thick-Core]
```

### Phase 1: Infrastructure & DB Operator

**Goal**: Establish stable database connectivity, pure-INSERT persistence mechanisms, and local/cloud backup pathways.

- [ ] 1.1 Environment Setup: Configure .env environment variables, deploy Oracle mTLS Wallet, and verify python-oracledb Thin Mode connectivity (execute SELECT 1 FROM DUAL).

- [ ] 1.2 ODS Schema Creation: Execute install_goldenwattle.sql to establish the EQUITY Schema and ODS_* raw staging tables with full VARCHAR2 structure.

- [ ] 1.3 DbOperator (Append-Only): Implement db_operator.py using small-batch pure-INSERT commit logic (Batch Size = 5~10), without DB-side deduplication locks, to ensure maximum write throughput.

- [ ] 1.4 Backup & Consistency Layer: Implement local JSON Lines (.jsonl) data persistence (stored in /home/ubuntu/backup/). Implement OCI Object Storage batch upload module and line_count record count comparison verification logic.

### Phase 2: Iterative Scraper Development & Regression Test

**Goal**: Develop each data source individually, with full end-to-end regression testing and 1GB RAM stress verification upon completion of each.

- [ ] 2.1 Extractor #1: price_ohlcv (Yahoo/ASX API) Implement unified OHLCV data collection (Real-time/EOD/History) with pre-close and post-close independent scraping parameter handling (--session-type). Regression test: API fetch → JSONL backup → ODS_PRICE_OHLCV pure-INSERT write → OCI comparison.

- [ ] 2.2 Extractor #2: afr (AFR Quote & Tick API) Implement AFR Quote & Tick multi-target table simultaneous writing: ODS_PRICE_TICK (tick-level granularity) and ODS_PRICE_QUOTE_EAV (bid-ask order book depth).

- [x] 2.3 Extractor #3: short (Shortman API) Implement full-market short position history data collection, writing to ODS_SHORT_POSITION.

- [ ] 2.4 Extractor #4: annc (ASX Market Announcements - Selenium) Implement headless browser scraping, integrate cleanup_vm.sh to forcefully terminate residual Chrome/Chromedriver processes to prevent RAM leaks.

- [x] 2.5 Extractor #5: company_master (Ticker Universe - API CSV Export) Implement weekly full-market Master data collection, writing to ODS_COMPANY_MASTER.

- [ ] 2.6 Extractor #6: analyst_consensus (Yahoo API) Implement weekly institutional ratings and targets collection via Yahoo API, writing to both ODS_ANALYST_TRENDS and ODS_ANALYST_TARGETS within a single job.

### Phase 3: Scheduling, Isolation & Anti-Crash

**Goal**: Achieve unattended automated scheduling, ensuring long-term stable operation without crashes.

- [ ] 3.1 Crontab Event-Driven Schedules: Configure AEST pre-market (15:25) and post-market (16:45) separate scheduling commands. Configure weekly (Sat/Sun) static data updates and Cron pipelines.

- [ ] 3.2 Memory Protection & Physical Reboot: Configure 512MB OS Swap space as a last-resort fallback buffer. Configure weekend scheduled physical VM bash reboot to fully release OS memory fragments and cache.

- [ ] 3.3 Two-Tier Anti-Noise Alerting: Integrate Pushover alerting using a two-tier strategy aligned with BRD's "High-Tolerance Anti-False-Alarm" principle:

  - **Tier 1 (Warning Log)**: Single batch row-count mismatch between local JSONL backup and database write → log to file, retain backup. No Pushover notification.

  - **Tier 2 (Pushover Alert)**: Cumulative retry failures OR bulk data missingness across multiple batches/sources → triggers Pushover to on-call.

  **Rationale**: Prevents alert fatigue from transient single-batch hiccups while ensuring serious systemic issues escalate immediately.

### Phase 4: Thick-Core PL/SQL Analytics Engine

**Goal**: Push data cleaning, deduplication, and quantitative indicator calculations entirely to the Oracle database.

- [ ] 4.1 ODS Cleaning & Deduplication Procedures: Write PL/SQL stored procedures to clean append-only ODS_* text data, perform type conversion (VARCHAR2 → NUMBER/DATE), and deduplicate by primary key with latest timestamp into CORE_* tables.

- [ ] 4.2 Technical Indicator Calculation Engine: Write PL/SQL incremental calculation stored procedures to implement technical indicator algorithms such as EMA, PSAR, and Supertrend.

- [ ] 4.3 Analytics Views: Create final signal output views (e.g., VW_TRADING_SIGNALS) for upper-layer calls.

## 3. Definition of Done (DoD) & Acceptance Criteria

A single data source or phase is marked as "Done" only when all of the following criteria are met:

**Idempotency & Auditability**: Repeating the same batch does not compromise ODS traceability; all data carries LOAD_TIME and BATCH_ID audit markers.

**Consistency**: Local .jsonl backup row count, OCI Object Storage backup row count, and database write row count must be 100% matched.

**Memory Safety**: Throughout the full workflow, VM memory usage remains stable; no OOM crashes are triggered; no residual headless processes remain after Selenium runs.

**Data Isolation**: Pre-market and post-market data can be clearly distinguished by SESSION_TYPE, supporting point-in-time historical backtracking.

## 4. Known Risks & Safeguards

| Risk | Trigger Scenario | Safeguard & Response |
|---|---|---|
| OOM Crisis | Chrome browser multi-instance or memory not released (primarily during annc task) | Strict single-process operation; automatic cleanup_vm.sh (SIGKILL) call at task end |
| Data Mismatch | Network timeout causing partial data not persisted | Two-tier response: (1) Single batch mismatch → Warning log + backup retained. (2) Cumulative failures or bulk missingness → Pushover alert triggered. |
| Lock Contention | High-frequency concurrent writes lock ODS tables | No DB-side MERGE; adopt pure append-only INSERT; deduplication handled by async SP |
