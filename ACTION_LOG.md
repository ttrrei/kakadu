# Action Log - Architecture Decision Records & Test Benchmarks

---

## 1GB RAM Performance Benchmark Results

### Baseline Configuration
- **VM**: OCI Micro VM (1GB RAM)
- **Database**: Oracle Autonomous Database Always Free Tier
- **Python**: Thin Mode with python-oracledb
- **Authentication**: Wallet mTLS

### Key Findings
- [TODO] Memory profiling results for data ingestion pipeline
- [TODO] PL/SQL indicator computation performance metrics
- [TODO] Selenium browser task memory footprint analysis
- [TODO] Scheduled reboot effectiveness measurement

---

## Known Issues & Scope Changes

### Current Issues
1. **Network Glitch Tolerance**: Transient network failures during web scraping require retry logic and backup retention strategy
2. **Selenium Process Management**: Chrome processes need cleanup after scheduled runs to prevent memory accumulation

### Resolved Issues
- [TODO] Document previously resolved issues if any

---

## Architecture Decision Records (ADRs)

### ADR-001: Thin-Edge Thick-Core Paradigm
**Status**: Approved
**Date**: [To be filled]
**Context**: System must operate within 1GB RAM constraints while maintaining full market data processing capabilities.
**Decision**: Python serves as stateless, memory-conscious data collector (Thin-Edge). All complex transformations, indicator computations, and signal triggers are pushed down to Oracle PL/SQL (Thick-Core). This eliminates native client library overhead and maintains a flat memory profile.

---

### ADR-002: Zero Instant Client
**Status**: Approved
**Date**: [To be filled]
**Context**: Need lightweight Oracle connectivity without installing native client libraries.
**Decision**: Use python-oracledb in Thin Mode with Wallet mTLS authentication, eliminating native client library overhead and maintaining a flat memory profile.

---

### ADR-003: Process Shielding & Sanitization
**Status**: Approved
**Date**: [To be filled]
**Context**: Heavy headless browser (Selenium) tasks need to be decoupled from lightweight API tasks in scheduling.
**Decision**: Execute cleanup_vm.sh after runs to purge residual Chrome processes and prevent memory accumulation between scheduled jobs.

---

### ADR-004: Scheduled VM Reboot
**Status**: Approved
**Date**: [To be filled]
**Context**: System memory and OS caches may accumulate over time during continuous operation.
**Decision**: Implement weekend bash + crontab physical VM reboot to completely flush system memory and OS caches, ensuring clean state for the next operational period.

---

### ADR-005: DbOperator Minimalist Architecture Refactoring — Removing contracts.py & ODS Audit Specifications
**Status**: Approved
**Date**: 2026-07-30

#### 1. Background
The earlier refactored `db_operator.py` was overly complex, mixing dynamic `MERGE INTO` SQL generation, OCI Object Storage backup uploads, and intricate Mock compatibility logic. Additionally, introducing a separate `contracts.py` for data validation and audit column injection increased inter-module coupling and repetitive boilerplate code, violating the project's "Thin-Edge, Thick-Core" and Minimalism principles.

#### 2. Decisions

**ADR-005.1: No Independent contracts.py Module**
- Do not create a standalone `contracts.py` file.
- Audit column injection (`BATCH_ID` + `LOAD_TIME`) and `VARCHAR2` text-safe conversion logic are encapsulated directly in the private `_prepare_records()` method within `db_operator.py`.
- Scraper layer doesn't need to handle metadata enrichment — just submit raw `List[Dict]` to `DbOperator`, achieving "zero boilerplate" and single-point defense control.

**ADR-005.2: Audit Column Simplification**
- All ODS tables consistently retain only two audit columns: **`BATCH_ID`** (UUID v4 string) and **`LOAD_TIME`** (ISO-8601 string).
- Completely remove `SOURCE_SYSTEM` / `datasource` fields. Since Kakadu ODS uses "one source, one table" design (e.g., `ODS_PRICE_OHLCV` belongs to Yahoo, `ODS_SHORT_POSITION` belongs to Shortman), table names inherently encode source information.

**ADR-005.3: OCI Backup Logic Decoupling**
- Completely strip OCI Object Storage backup and file operation logic from `DbOperator`.
- `DbOperator` focuses solely on Oracle connection pool management and pure-INSERT; cloud and local backups are handled by a standalone `backup_manager.py` module.

**ADR-005.4: ODS Zero-Loss Storage Principle (Strict VARCHAR2)**
- All business columns and audit columns across 7 ODS tables use `VARCHAR2` storage, avoiding type conversion errors during Python-to-DB writes; all data cleaning and type coercion is pushed down to PL/SQL.

**ADR-005.5: Unified Batch-First Interface Design**
- Expose a unified `insert_batch(table_name, records, batch_id=None)` interface externally.
- Whether it's single Symbol multi-row OHLCV data or Shortman's large multi-row multi-column dataset, both accept `List[Dict[str, Any]]` directly.
- Internally uses `cursor.executemany()` to batch-append writes by `BATCH_SIZE` (5~10); if batch fails, automatically degrades to single `cursor.execute()` writes, logs exceptions, and skips dirty data.

#### 3. Consequences
- Avoids over-engineering, eliminates standalone contract layer files, and keeps Python side extremely lightweight (Thin-Edge).
- Next step: Write minimalist `db_operator.py` and DDL scripts `install_ods_tables.sql` for 7 ODS tables based on this ADR.

---

## Future Actions & Planned Improvements

### Priority Items
1. **Memory Optimization**: Profile and optimize data ingestion pipeline to reduce peak memory usage
2. **PL/SQL Performance Tuning**: Optimize indicator computation queries for faster signal generation
3. **Selenium Process Management**: Implement automated process cleanup between scheduled runs
4. **Alert Threshold Calibration**: Fine-tune noise-suppressed alerting thresholds based on historical failure patterns
5. **Simplified db_operator.py**: Rewrite `db_operator.py` per ADR-005 — remove MERGE INTO logic, strip OCI backup code, consolidate audit injection into `_prepare_records()`, expose single `insert_batch()` interface
6. **ODS DDL Scripts**: Rewrite `install_ods_tables.sql` per ADR-005 — 7 tables with only `BATCH_ID` + `LOAD_TIME` audit columns, all columns as `VARCHAR2`
7. **backup_manager.py Design**: Design and implement standalone `backup_manager.py` module for OCI Object Storage and local backup per ADR-005.3

---

## Scope Changes & Evolution

### Original Scope
- Full ASX market data ingestion across multiple domains
- Native database technical indicator computation
- Automated signal generation and alerting
- Zero infrastructure cost operation on 1GB RAM VM

### Current Scope (Aligned with Original)
All original scope items remain active. No significant scope changes have been made.

---

## Test Benchmarks & Performance Metrics

### Data Ingestion Performance
- [TODO] Record baseline throughput for each data domain
- [TODO] Track memory usage during ingestion cycles
- [TODO] Measure time-to-first-signal after data arrival

### Signal Generation Performance
- [TODO] Benchmark EMA, PSAR, Supertrend computation times in PL/SQL
- [TODO] Compare signal generation latency across different market conditions
- [TODO] Validate signal accuracy against known trading patterns

---

## Monitoring & Observability

### Current Monitoring Setup
- [TODO] Define key performance indicators (KPIs) for system health
- [TODO] Establish alerting thresholds based on historical data
- [TODO] Create dashboards for operational visibility

---

*Last Updated: 2026-07-30*
*Maintained by: Kakadu Development Team*
