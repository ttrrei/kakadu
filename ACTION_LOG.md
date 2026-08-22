# Action Log - Architecture Decision Records & Test Benchmarks

---

## 1. 1GB RAM Performance Benchmark Results

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

## 2. Known Issues & Scope Changes

### Current Issues

1. **Network Glitch Tolerance**: Transient network failures during web scraping require retry logic and backup retention strategy
2. **Selenium Process Management**: Chrome processes need cleanup after scheduled runs to prevent memory accumulation
3. **DbOperator Thread Safety**: `db_operator.py` is currently not thread-safe
4. **Hardcoded Batch Size**: `BATCH_SIZE` is currently hardcoded and needs to be moved to `EnvConfig`

### Resolved Issues

- [TODO] Document previously resolved issues if any

---

## 3. Architecture Decision Records (ADRs)

### ADR-001: Thin-Edge Thick-Core Paradigm

| Field | Value |
|-------|-------|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context:** System must operate within 1GB RAM constraints while maintaining full market data processing capabilities.

**Decision:** Python serves as stateless, memory-conscious data collector (Thin-Edge). All complex transformations, indicator computations, and signal triggers are pushed down to Oracle PL/SQL (Thick-Core). This eliminates native client library overhead and maintains a flat memory profile.

---

### ADR-002: Zero Instant Client

| Field | Value |
|-------|-------|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context:** Need lightweight Oracle connectivity without installing native client libraries.

**Decision:** Use python-oracledb in Thin Mode with Wallet mTLS authentication, eliminating native client library overhead and maintaining a flat memory profile.

---

### ADR-003: Process Shielding & Sanitization

| Field | Value |
|-------|-------|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context:** Heavy headless browser (Selenium) tasks need to be decoupled from lightweight API tasks in scheduling.

**Decision:** Execute `cleanup_vm.sh` after runs to purge residual Chrome processes and prevent memory accumulation between scheduled jobs.

---

### ADR-004: Scheduled VM Reboot

| Field | Value |
|-------|-------|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context:** System memory and OS caches may accumulate over time during continuous operation.

**Decision:** Implement weekend bash + crontab physical VM reboot to completely flush system memory and OS caches, ensuring clean state for the next operational period.

---

### ADR-005: DbOperator Minimalist Architecture Refactoring — Removing contracts.py & ODS Audit Specifications

| Field | Value |
|-------|-------|
| **Status** | Approved |
| **Date** | 2026-07-30 |

#### 1. Background

The earlier refactored `db_operator.py` was overly complex, mixing dynamic `MERGE INTO` SQL generation, OCI Object Storage backup uploads, and intricate Mock compatibility logic. Additionally, introducing a separate `contracts.py` for data validation and audit column injection increased inter-module coupling and repetitive boilerplate code, violating the project's "Thin-Edge, Thick-Core" and Minimalism principles.

#### 2. Decisions

**ADR-005.1: No Independent contracts.py Module**
- Do not create a standalone `contracts.py` file
- Audit column injection (`BATCH_ID` + `LOAD_TIME`) and `VARCHAR2` text-safe conversion logic are encapsulated directly in the private `_prepare_records()` method within `db_operator.py`
- Scraper layer doesn't need to handle metadata enrichment — just submit raw `List[Dict]` to `DbOperator`, achieving "zero boilerplate" and single-point defense control

**ADR-005.2: Audit Column Simplification**
- All ODS tables consistently retain only two audit columns: **`BATCH_ID`** (UUID v4 string) and **`LOAD_TIME`** (ISO-8601 string)
- Completely remove `SOURCE_SYSTEM` / `datasource` fields. Since Kakadu ODS uses "one source, one table" design (e.g., `ODS_PRICE_OHLCV` belongs to Yahoo, `ODS_SHORT_POSITION` belongs to Shortman), table names inherently encode source information

**ADR-005.3: OCI Backup Logic Decoupling**
- Completely strip OCI Object Storage backup and file operation logic from `DbOperator`
- `DbOperator` focuses solely on Oracle connection pool management and pure-INSERT; cloud and local backups are handled by a standalone `backup_manager.py` module

**ADR-005.4: ODS Zero-Loss Storage Principle (Strict VARCHAR2)**
- All business columns and audit columns across 7 ODS tables use `VARCHAR2` storage, avoiding type conversion errors during Python-to-DB writes; all data cleaning and type coercion is pushed down to PL/SQL

**ADR-005.5: Unified Batch-First Interface Design**
- Expose a unified `insert_batch(table_name, records, batch_id=None)` interface externally
- Whether it's single Symbol multi-row OHLCV data or Shortman's large multi-row multi-column dataset, both accept `List[Dict[str, Any]]` directly
- Internally uses `cursor.executemany()` to batch-append writes by `BATCH_SIZE` (5~10); if batch fails, automatically degrades to single `cursor.execute()` writes, logs exceptions, and skips dirty data

#### 3. Consequences

- Avoids over-engineering, eliminates standalone contract layer files, and keeps Python side extremely lightweight (Thin-Edge)
- Next step: Write minimalist `db_operator.py` and DDL scripts `install_ods_tables.sql` for 7 ODS tables based on this ADR

---

### ADR-006: Configuration Separation — config.yaml + .env

| Field | Value |
|-------|-------|
| **Status** | Proposed |
| **Date** | 2026-07-30 |

#### 1. Context

Sensitive credentials (database passwords, API keys, Pushover tokens, Wallet paths) must be isolated from code to prevent accidental exposure via version control.

#### 2. Decision

**ADR-006.1: Dual-File Configuration**
- **`config.yaml`**: Non-sensitive configuration (data source URLs, ODS table names, log levels, batch sizes, etc.)
- **`.env`**: Sensitive credentials (database password, API keys, Pushover tokens, etc.)
- **`.env.example`**: Template file with placeholder values for reference

**ADR-006.2: Directory Structure**

```
```text
kakadu/
├── config.yaml
├── .env           # gitignored
└── .env.example   # committed, no real secrets
```
**ADR-006.3: Secrets Never in Version Control**

.env is explicitly excluded from Git via .gitignore
Only .env.example (with placeholders) is committed
### ADR-006.4: config.py Loader

Single config.py module reads both files
Uses python-dotenv for .env and PyYAML for config.yaml
Provides a unified config object to the rest of the application
#### 3. Consequences
Sensitive credentials are fully isolated from codebase
Development team can share .env.example as a setup guide without security risk
Adds python-dotenv and PyYAML dependencies
### ADR-007: Multi-Tiered Data Architecture
| Field | Value |
|-------|-------|
| Status | Approved |
| Date | 2026-08-02 |
#### 1. Background
As the system evolves from simple data collection to complex signal generation, a flat database structure will lead to data quality issues, lack of traceability, and performance bottlenecks. A structured approach to the data lifecycle is required to decouple raw ingestion, business logic, and analytical consumption.

#### 2. Decisions
### ADR-007.1: Five-Layer Data Model

Implement a tiered architecture to ensure separation of concerns and data integrity across the following layers:

| Layer | Responsibility | Examples |
|---|---|---|
| SYS (System) | Core system management, including metadata, application configuration, execution logs, and scheduling states | SYS_BATCH_LOG, SYS_CONFIG |
| ODS (Operational Data Store) | Raw data landing zone. Acts as a "Pure" mirror of external systems, preserving original formats to ensure full data lineage and allow for reprocessing | ODS_YAHOO_HISTORY |
| REF (Reference) | Static lookup layer containing master data, dictionaries, mapping tables, and system parameters | REF_TICKER_MASTER, REF_SECTOR_MAP |
| BDI (Business Digital Image) | The intermediate processing layer. Cleans, standardizes, and deduplicates ODS data to create a consistent and "clean" digital representation of business entities | BDI_EQUITY_PRICE_CLEANED |
| DMT (Data Mart) | The application/presentation layer. Performs aggregations and technical indicator computations based on BDI data, optimized for direct consumption by APIs, signals, and reports | DMT_SENSITIVE_INDICATORS, DMT_MONTHLY_SUMMARY |
#### 3. Consequences
| Description |
|---|
| Pros | High data traceability (from DMT back to ODS); improved data quality through the BDI layer; optimized performance by separating raw storage from analytical workloads |
Cons	Increased complexity in ETL/ELT orchestration and a higher number of managed database objects
### ADR-008: Task-Based Scraper Orchestration Architecture
| Field | Value |
|-------|-------|
| Status | Approved |
| Date | 2026-08-06 |
**Context:** The system requires multiple data ingestion tasks with varying execution patterns: some are "Bulk" (fetching all symbols in one page) and some are "Iterative" (fetching each symbol individually). Hardcoding these patterns in main.py leads to repetitive boilerplate, fragile error handling, and high maintenance overhead.

**Decision:** Implement a "Template Method" pattern via a BaseScraper abstract class to decouple the execution orchestration from the extraction logic.

### ADR-008.1: Unified Task Interface

All scrapers must inherit from BaseScraper
The main.py dispatcher interacts only with the .run() method, remaining agnostic to the internal scraping strategy
### ADR-008.2: Dual-Mode Execution Strategy

Bulk Mode (is_bulk_task = True): Executes scrape_all(). Optimized for high-density pages. Data is collected in one pass and submitted to DbOperator in a single batch
Iterative Mode (is_bulk_task = False): Executes scrape_one() within a loop. Optimized for detail pages. Implements a "Fetch -> Buffer -> Flush" cycle to minimize DB round-trips while keeping memory footprint low
### ADR-008.3: Isolation & Robustness (The "Shield" Pattern)

In Iterative Mode, each scrape_one() call is wrapped in an independent try-except block
Failure of a single symbol must not terminate the entire job. Errors are logged, and the system immediately proceeds to the next symbol to ensure maximum data yield
### ADR-008.4: Resource-Conscious Buffering

To prevent OOM (Out of Memory) on the 1GB VM, Iterative Mode must use a configurable BATCH_SIZE (e.g., 50 records). The buffer is flushed to the database periodically, ensuring memory usage remains flat regardless of the total symbol count
Consequences:

| Description |
|---|
| Pros | Extreme reduction in main.py complexity; standardized error handling across all sources; easy extensibility for new data sources; optimized DB performance via balanced batching |
Cons	Slight increase in initial abstraction complexity (introduction of base classes)
### ADR-009: ListScraper Implementation Pivot (Selenium $\rightarrow$ API CSV)
| Field | Value |
|-------|-------|
| Status | Approved |
| Date | 2026-08-15 |
Context: The original plan was to use Selenium to scrape the Ticker list, but it was discovered that ASX provides a direct API CSV export endpoint.

**Decision:** Abandon the Selenium approach and use requests to directly fetch the CSV file.

#### Rationale:

Minimal memory footprint: No Chrome process required, fully compliant with 1GB RAM constraint
High stability: API responses are more robust than DOM parsing, with no concern for page structure changes
Extreme speed: Single request retrieves the full dataset
Consequence: Reduced VM CPU/RAM peaks and simplified code maintenance.

### ADR-010: Consolidation of Quote and Yahoo Scrapers
| Field | Value |
|-------|-------|
| Status | Approved |
| Date | 2026-08-20 |
Context: It was identified that the "Quote Scraper" (ASX API) and "Yahoo Scraper" (Yahoo Finance API) both serve the same business purpose: collecting OHLCV price data for the same target table (ODS_PRICE_OHLCV). Maintaining two separate scrapers for the same data domain creates redundant code and increases the risk of logic divergence.

**Decision:** Merge the Quote and Yahoo scraping logic into a single unified extractor: price_ohlcv.

#### Rationale:

Simplified Maintenance: A single class handles all OHLCV API logic
Resource Efficiency: Reduces the number of classes and potential memory overhead during orchestration
Data Consistency: Ensures that regardless of the API source, the data is processed through a single pipeline before hitting the ODS
#### Consequence:

Updated 
project_roadmap.md
 and 
system_architecture_design.md
 to reflect the removal of the redundant "Quote" extractor
All OHLCV-related tasks are now routed through the price_ohlcv extractor
### ADR-011: Analyst Consensus Implementation Pivot (Selenium $\rightarrow$ Yahoo API & Table Split)
| Field | Value |
|-------|-------|
| Status | Approved |
| Date | 2026-08-25 |
Context: The original plan used Selenium to scrape analyst consensus data into a single table. However, Yahoo API provides a more stable data source, and the data structure naturally splits into Rating Trends and Price Targets.

**Decision:**

Abandon Selenium for analyst data; implement via Yahoo API.
Split the target from one table (ODS_ANALYST_CONSENSUS) into two specialized tables: ODS_ANALYST_TRENDS and ODS_ANALYST_TARGETS.
Maintain a single Python job to populate both tables to minimize orchestration overhead.
#### Rationale:

Memory Safety: Eliminates another heavy Chrome process, reducing OOM risk.
Data Normalization: Separating trends from targets allows for cleaner PL/SQL analytics.
Stability: API-based ingestion is significantly more resilient than DOM parsing.
#### Consequence:

Updated ODS schema and all project documentation.
Reduced frequency of cleanup_vm.sh calls.
## 4. Implementation Progress (Current State)
### Foundation Layer (Completed)
Configuration: Implemented src/config.py with dual-file loading (.env + config.yaml) per ADR-006
Database Operator: Implemented src/db_operator.py as a Pure-INSERT engine with automatic audit injection (BATCH_ID, LOAD_TIME) and row-level fallback per ADR-005
Schema Initialization: Created sql/install_equity_schema.sql establishing the EQUITY user, SYS_BATCH_LOG, and core ADB privileges
Scraper Framework: Implemented src/base_scraper.py using the Template Method pattern, supporting both Bulk and Iterative modes with built-in Selenium lifecycle management per ADR-008
### Current Focus
Audit Phase: Conducting a comprehensive pre-integration audit on the audit/pre-main-integration branch to verify all scrapers against the 1GB RAM and "Thin-Edge" constraints before developing main.py.
## 5. Future Actions & Planned Improvements
### Priority Items
Memory Optimization: Profile and optimize data ingestion pipeline to reduce peak memory usage
PL/SQL Performance Tuning: Optimize indicator computation queries for faster signal generation
Selenium Process Management: Implement automated process cleanup between scheduled runs
Alert Threshold Calibration: Fine-tune noise-suppressed alerting thresholds based on historical failure patterns
Simplified db_operator.py: Rewrite db_operator.py per ADR-005 — remove MERGE INTO logic, strip OCI backup code, consolidate audit injection into _prepare_records(), expose single insert_batch() interface
ODS DDL Scripts: Rewrite `install_ods_tables.
