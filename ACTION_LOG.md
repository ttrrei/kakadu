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
3. **DbOperator Thread Safety**: `db_operator.py` is currently not thread-safe.
4. **Hardcoded Batch Size**: `BATCH_SIZE` is currently hardcoded and needs to be moved to `EnvConfig`.

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

### ADR-006: Configuration Separation — config.yaml + .env
**Status**: Proposed
**Date**: 2026-07-30

#### 1. Context
Sensitive credentials (database passwords, API keys, Pushover tokens, Wallet paths) must be isolated from code to prevent accidental exposure via version control.

#### 2. Decision

**ADR-006.1: Dual-File Configuration**
- **`config.yaml`**: Non-sensitive configuration (data source URLs, ODS table names, log levels, batch sizes, etc.)
- **`.env`**: Sensitive credentials (database password, API keys, Pushover tokens, etc.)
- **`.env.example`**: Template file with placeholder values for reference

**ADR-006.2: Directory Structure**
```
kakadu/
├── config.yaml
├── .env           # gitignored
└── .env.example   # committed, no real secrets
```

**ADR-006.3: Secrets Never in Version Control**
- `.env` is explicitly excluded from Git via `.gitignore`
- Only `.env.example` (with placeholders) is committed

**ADR-006.4: config.py Loader**
- Single `config.py` module reads both files
- Uses `python-dotenv` for `.env` and `PyYAML` for `config.yaml`
- Provides a unified config object to the rest of the application

#### 3. Consequences
- Sensitive credentials are fully isolated from codebase
- Development team can share `.env.example` as a setup guide without security risk
- Adds `python-dotenv` and `PyYAML` dependencies

---

### ADR-007: Multi-Tiered Data Architecture
**Status**: Approved
**Date**: 2026-08-02

#### 1. Background
As the system evolves from simple data collection to complex signal generation, a flat database structure will lead to data quality issues, lack of traceability, and performance bottlenecks. A structured approach to the data lifecycle is required to decouple raw ingestion, business logic, and analytical consumption.

#### 2. Decisions

**ADR-007.1: Five-Layer Data Model**

Implement a tiered architecture to ensure separation of concerns and data integrity across the following layers:

1. **SYS (System)**:
    - **Responsibility**: Core system management, including metadata, application configuration, execution logs, and scheduling states.
    - **Examples**: `SYS_BATCH_LOG`, `SYS_CONFIG`.

2. **ODS (Operational Data Store)**:
    - **Responsibility**: Raw data landing zone. Acts as a "Pure" mirror of external systems, preserving original formats to ensure full data lineage and allow for reprocessing.
    - **Examples**: `ODS_YAHOO_HISTORY`.

3. **REF (Reference)**:
    - **Responsibility**: Static lookup layer containing master data, dictionaries, mapping tables, and system parameters.
    - **Examples**: `REF_TICKER_MASTER`, `REF_SECTOR_MAP`.

4. **BDI (Business Digital Image)**:
    - **Responsibility**: The intermediate processing layer (similar to DWD). Cleans, standardizes, and deduplicates ODS data to create a consistent and "clean" digital representation of business entities.
    - **Examples**: `BDI_EQUITY_PRICE_CLEANED`.

5. **DMT (Data Mart)**:
    - **Responsibility**: The application/presentation layer. Performs aggregations and technical indicator computations based on BDI data, optimized for direct consumption by APIs, signals, and reports.
    - **Examples**: `DMT_SENSITIVE_INDICATORS`, `DMT_MONTHLY_SUMMARY`.

#### 3. Consequences
- **Pros**: High data traceability (from DMT back to ODS); improved data quality through the BDI layer; optimized performance by separating raw storage from analytical workloads.
- **Cons**: Increased complexity in ETL/ELT orchestration and a higher number of managed database objects.

---

### ADR-008: Task-Based Scraper Orchestration Architecture
**Status**: Approved
**Date**: 2026-08-06
**Context**: The system requires multiple data ingestion tasks with varying execution patterns: some are "Bulk" (fetching all symbols in one page) and some are "Iterative" (fetching each symbol individually). Hardcoding these patterns in `main.py` leads to repetitive boilerplate, fragile error handling, and high maintenance overhead.

**Decision**: Implement a "Template Method" pattern via a `BaseScraper` abstract class to decouple the *execution orchestration* from the *extraction logic*.

**ADR-008.1: Unified Task Interface**
- All scrapers must inherit from `BaseScraper`.
- The `main.py` dispatcher interacts only with the `.run()` method, remaining agnostic to the internal scraping strategy.

**ADR-008.2: Dual-Mode Execution Strategy**
- **Bulk Mode (`is_bulk_task = True`)**: Executes `scrape_all()`. Optimized for high-density pages. Data is collected in one pass and submitted to `DbOperator` in a single batch.
- **Iterative Mode (`is_bulk_task = False`)**: Executes `scrape_one()` within a loop. Optimized for detail pages. Implements a "Fetch -> Buffer -> Flush" cycle to minimize DB round-trips while keeping memory footprint low.

**ADR-008.3: Isolation & Robustness (The "Shield" Pattern)**
- In Iterative Mode, each `scrape_one()` call is wrapped in an independent `try-except` block.
- Failure of a single symbol must not terminate the entire job. Errors are logged, and the system immediately proceeds to the next symbol to ensure maximum data yield.

**ADR-008.4: Resource-Conscious Buffering**
- To prevent OOM (Out of Memory) on the 1GB VM, Iterative Mode must use a configurable `BATCH_SIZE` (e.g., 50 records). The buffer is flushed to the database periodically, ensuring memory usage remains flat regardless of the total symbol count.

**Consequences**:
- **Pros**: Extreme reduction in `main.py` complexity; standardized error handling across all sources; easy extensibility for new data sources; optimized DB performance via balanced batching.
- **Cons**: Slight increase in initial abstraction complexity (introduction of base classes).

---

### ADR-009: ListScraper Implementation Pivot (Selenium → API CSV)
**Status**: Approved
**Date**: 2026-08-15
**Context**: The original plan was to use Selenium to scrape the Ticker list, but it was discovered that ASX provides a direct API CSV export endpoint.

**Decision**: Abandon the Selenium approach and use `requests` to directly fetch the CSV file.

**Rationale**:
- **Minimal memory footprint**: No Chrome process required, fully compliant with 1GB RAM constraint.
- **High stability**: API responses are more robust than DOM parsing, with no concern for page structure changes.
- **Extreme speed**: Single request retrieves the full dataset.

**Consequence**: Reduced VM CPU/RAM peaks and simplified code maintenance.

---

## Implementation Progress (Current State)

### Foundation Layer (Completed)
- **Configuration**: Implemented `src/config.py` with dual-file loading (`.env` + `config.yaml`) per ADR-006.
- **Database Operator**: Implemented `src/db_operator.py` as a Pure-INSERT engine with automatic audit injection (`BATCH_ID`, `LOAD_TIME`) and row-level fallback per ADR-005.
- **Schema Initialization**: Created `sql/install_equity_schema.sql` establishing the `EQUITY` user, `SYS_BATCH_LOG`, and core ADB privileges.
- **Scraper Framework**: Implemented `src/base_scraper.py` using the Template Method pattern, supporting both `Bulk` and `Iterative` modes with built-in Selenium lifecycle management per ADR-008.

### Current Focus
- **Phase 3: The First Win (List Scraper)**: Implementing `src/scrapers/list_scraper.py` to validate the end-to-end pipeline (Source -> DbOperator -> ODS).

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
8. **Dual-Config Implementation**: Create `config.yaml` + `.env` + `.env.example` per ADR-006, implement `config.py` loader, add `.gitignore` entry
9. **Multi-Tier ETL Pipeline**: Implement ETL/ELT orchestration for SYS, ODS, REF, BDI, DMT layers per ADR-007

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

*Last Updated: 2026-08-06*
*Maintained by: Kakadu Development Team*
