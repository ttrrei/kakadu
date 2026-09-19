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
|---|---|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context**: System must operate within 1GB RAM constraints while maintaining full market data processing capabilities.

**Decision**: Python serves as stateless, memory-conscious data collector (Thin-Edge). All complex transformations, indicator computations, and signal triggers are pushed down to Oracle PL/SQL (Thick-Core). This eliminates native client library overhead and maintains a flat memory profile.

---

### ADR-002: Zero Instant Client

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context**: Need lightweight Oracle connectivity without installing native client libraries.

**Decision**: Use python-oracledb in Thin Mode with Wallet mTLS authentication, eliminating native client library overhead and maintaining a flat memory profile.

---

### ADR-003: Process Shielding & Sanitization

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context**: Heavy headless browser (Selenium) tasks need to be decoupled from lightweight API tasks in scheduling.

**Decision**: Execute cleanup_vm.sh via an external Master Shell script (run_task.sh). The cleanup is performed both before and after the Python process execution. This ensures that even if the Python process crashes with a segmentation fault or is killed by the OS (OOM), the environment is sanitized for the next run.


---

### ADR-004: Scheduled VM Reboot

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | [To be filled] |

**Context**: System memory and OS caches may accumulate over time during continuous operation.

**Decision**: Implement a daily physical VM reboot via crontab during the longest period of system inactivity. This provides a "hard reset" of the OS kernel, flushes all memory fragments, and ensures a pristine state for the daily batch processing window.

---

### ADR-005: DbOperator Minimalist Architecture Refactoring

| Field | Value |
|---|---|
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
- All ODS tables consistently retain only two audit columns: `BATCH_ID` (UUID v4 string) and `LOAD_TIME` (ISO-8601 string)
- Completely remove `SOURCE_SYSTEM` / `datasource` fields. Since Kakadu ODS uses "one source, one table" design (e.g., `ODS_PRICE_OHLCV` belongs to Yahoo, `ODS_SHORT_POSITION` belongs to Shortman), table names inherently encode source information

**ADR-005.3: OCI Backup Logic Decoupling**
- Completely strip OCI Object Storage backup and file operation logic from `DbOperator`
- `DbOperator` focuses solely on Oracle connection pool management and pure-INSERT; cloud and local backups are handled by a standalone `backup_manager.py` module

**ADR-005.4: ODS Zero-Loss Storage Principle (Strict VARCHAR2)**
- All business columns and audit columns across 7 ODS tables use `VARCHAR2` storage, avoiding type conversion errors during Python-to-DB writes; all data cleaning and type coercion is pushed down to PL/SQL

**ADR-005.5: Unified Batch-First Interface Design**
- Expose a unified `insert_batch(table_name, records, batch_id=None)` interface externally
- Whether it's single Symbol multi-row OHLCV data or Shortman's large multi-row multi-column dataset, both accept `List[Dict[str, Any]]` directly
- Internally uses `cursor.executemany()` to batch-append writes by `BATCH_SIZE` (5-10); if batch fails, automatically degrades to single `cursor.execute()` writes, logs exceptions, and skips dirty data

#### 3. Consequences

- Avoids over-engineering, eliminates standalone contract layer files, and keeps Python side extremely lightweight (Thin-Edge)
- Next step: Write minimalist `db_operator.py` and DDL scripts `install_ods_tables.sql` for 7 ODS tables based on this ADR

---

### ADR-006: Configuration Separation

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-07-30 |

#### 1. Context

Sensitive credentials (database passwords, API keys, Pushover tokens, Wallet paths) must be isolated from code to prevent accidental exposure via version control.

#### 2. Decision

**ADR-006.1: Dual-File Configuration**
- `config.yaml`: Non-sensitive configuration (data source URLs, ODS table names, log levels, batch sizes, etc.)
- `.env`: Sensitive credentials (database password, API keys, Pushover tokens, etc.)
- `.env.example`: Template file with placeholder values for reference

**ADR-006.2: Directory Structure**

```
kakadu/
├── config.yaml
├── .env           # gitignored
└── .env.example   # committed, no real secrets
```

**ADR-006.3: Secrets Never in Version Control**
- .env is explicitly excluded from Git via .gitignore
- Only .env.example (with placeholders) is committed

**ADR-006.4: config.py Loader**
- Single config.py module reads both files
- Uses python-dotenv for .env and PyYAML for config.yaml
- Provides a unified config object to the rest of the application

#### 3. Consequences

- Sensitive credentials are fully isolated from codebase
- Development team can share .env.example as a setup guide without security risk
- Adds python-dotenv and PyYAML dependencies

---

### ADR-007: Multi-Tiered Data Architecture

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-02 |

#### 1. Background

As the system evolves from simple data collection to complex signal generation, a flat database structure will lead to data quality issues, lack of traceability, and performance bottlenecks. A structured approach to the data lifecycle is required to decouple raw ingestion, business logic, and analytical consumption.

#### 2. Decisions

**ADR-007.1: Five-Layer Data Model**

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
| **Pros** | High data traceability (from DMT back to ODS); improved data quality through the BDI layer; optimized performance by separating raw storage from analytical workloads |
| **Cons** | Increased complexity in ETL/ELT orchestration and a higher number of managed database objects |

---

### ADR-008: Task-Based Scraper Orchestration Architecture

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-06 |

**Context**: The system requires multiple data ingestion tasks with varying execution patterns: some are "Bulk" (fetching all symbols in one page) and some are "Iterative" (fetching each symbol individually). Hardcoding these patterns in main.py leads to repetitive boilerplate, fragile error handling, and high maintenance overhead.

**Decision**: Implement a "Template Method" pattern via a BaseScraper abstract class to decouple the execution orchestration from the extraction logic.

**ADR-008.1: Unified Task Interface**
- All scrapers must inherit from BaseScraper
- The main.py dispatcher interacts only with the `.run()` method, remaining agnostic to the internal scraping strategy

**ADR-008.2: Dual-Mode Execution Strategy**
- **Bulk Mode** (`is_bulk_task = True`): Executes `scrape_all()`. Optimized for high-density pages. Data is collected in one pass and submitted to DbOperator in a single batch.
- **Iterative Mode** (`is_bulk_task = False`): Executes `scrape_one()` within a loop. Optimized for detail pages. Implements a "Fetch to Buffer to Flush" cycle to minimize DB round-trips while keeping memory footprint low.

**ADR-008.3: Isolation & Robustness (The "Shield" Pattern)**
- In Iterative Mode, each `scrape_one()` call is wrapped in an independent try-except block.
- Failure of a single symbol must not terminate the entire job. Errors are logged, and the system immediately proceeds to the next symbol to ensure maximum data yield.

**ADR-008.4: Resource-Conscious Buffering**
- To prevent OOM (Out of Memory) on the 1GB VM, Iterative Mode must use a configurable `BATCH_SIZE` (e.g., 50 records). The buffer is flushed to the database periodically, ensuring memory usage remains flat regardless of the total symbol count.

**Consequences**:

| Description |
|---|
| **Pros** | Extreme reduction in main.py complexity; standardized error handling across all sources; easy extensibility for new data sources; optimized DB performance via balanced batching |
| **Cons** | Slight increase in initial abstraction complexity (introduction of base classes) |

---

### ADR-009: ListScraper Implementation Pivot

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-15 |

**Context**: The original plan was to use Selenium to scrape the Ticker list, but it was discovered that ASX provides a direct API CSV export endpoint.

**Decision**: Abandon the Selenium approach and use requests to directly fetch the CSV file.

**Rationale**:
- **Minimal memory footprint**: No Chrome process required, fully compliant with 1GB RAM constraint
- **High stability**: API responses are more robust than DOM parsing, with no concern for page structure changes
- **Extreme speed**: Single request retrieves the full dataset

**Consequence**: Reduced VM CPU/RAM peaks and simplified code maintenance.

---

### ADR-010: Consolidation of Quote and Yahoo Scrapers

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-20 |

**Context**: It was identified that the "Quote Scraper" (ASX API) and "Yahoo Scraper" (Yahoo Finance API) both serve the same business purpose: collecting OHLCV price data for the same target table (ODS_PRICE_OHLCV). Maintaining two separate scrapers for the same data domain creates redundant code and increases the risk of logic divergence.

**Decision**: Merge the Quote and Yahoo scraping logic into a single unified extractor: `price_ohlcv`.

**Rationale**:
- **Simplified Maintenance**: A single class handles all OHLCV API logic
- **Resource Efficiency**: Reduces the number of classes and potential memory overhead during orchestration
- **Data Consistency**: Ensures that regardless of the API source, the data is processed through a single pipeline before hitting the ODS

**Consequence**:
- Updated `project_roadmap.md` and `system_architecture_design.md` to reflect the removal of the redundant "Quote" extractor
- All OHLCV-related tasks are now routed through the `price_ohlcv` extractor

---

### ADR-011: Analyst Consensus Implementation Pivot

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-25 |

**Context**: The original plan used Selenium to scrape analyst consensus data into a single table. However, Yahoo API provides a more stable data source, and the data structure naturally splits into Rating Trends and Price Targets.

**Decision**:
- Abandon Selenium for analyst data; implement via Yahoo API.
- Split the target from one table (ODS_ANALYST_CONSENSUS) into two specialized tables: ODS_ANALYST_TRENDS and ODS_ANALYST_TARGETS.
- Maintain a single Python job to populate both tables to minimize orchestration overhead.

**Rationale**:
- **Memory Safety**: Eliminates another heavy Chrome process, reducing OOM risk.
- **Data Normalization**: Separating trends from targets allows for cleaner PL/SQL analytics.
- **Stability**: API-based ingestion is significantly more resilient than DOM parsing.

**Consequence**:
- Updated ODS schema and all project documentation.
- Reduced frequency of cleanup_vm.sh calls.

---

### ADR-012: Centralized Symbol Provider for Iterative Scrapers

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-27 |

#### 1. Background

Iterative scrapers (e.g., afr, short, annc, analyst_consensus) require a list of symbols to process individually. Early designs risked:

- Hardcoded symbol lists (violating config isolation)
- Per-scraper DB queries (creating tight coupling and duplication)
- In-memory symbol lists (risking OOM on 1GB VM with ~2000+ ASX symbols)

This violates the "Thin-Edge" principle and introduces memory, coupling, and maintenance risks.

#### 2. Decision

**ADR-012.1: Centralized SymbolProvider Interface**
- Introduce a SymbolProvider abstraction (or equivalent logic in BaseScraper) responsible for supplying symbols to iterative scrapers
- Must fetch symbols as a generator/iterator from `ODS_COMPANY_MASTER` via `DbOperator` — never load full list into memory
- Apply optional filtering (via `config.yaml`) and validation (e.g., `.AX` suffix, non-empty) at the provider level
- Scrapers depend only on an `Iterable[str]`, not on database or query specifics

**ADR-012.2: Integration with BaseScraper**
- `BaseScraper` (in iterative mode) retrieves symbols via `self.symbol_provider()` or config-injected provider
- Each `scrape_one(symbol)` call is wrapped in try-except to isolate failures
- Symbol-level errors are logged and skipped; job continues to next symbol

**ADR-012.3: Configuration & Validation**
- Symbol filtering (e.g., by sector, exclusion lists) configured in `config.yaml` under `[symbol_filter]`
- `main.py` validates SymbolProvider health at startup: must connect to DB and yield at least one symbol
- Invalid symbols logged at WARNING; provider failure triggers Tier 2 alert and graceful shutdown

#### 3. Consequences

| Description |
|---|
| **Memory Safety** | Symbol iteration uses O(1) memory; no risk of OOM from large symbol lists |
| **Loose Coupling** | Scrapers unaware of symbol source; easy to test/mock |
| **Single Source of Truth** | All iterative scrapers use the same, fresh ticker list from ODS_COMPANY_MASTER |
| **Config-Driven** | Filtering and validation centralized, not scattered in scraper logic |
| **Observability** | Symbol count per job logged at INFO level for anomaly detection |

**Next Step**: Implement SymbolProvider in `src/symbol_provider.py` or integrate into BaseScraper, update `base_scraper.py` to use it, and ensure all iterative scrapers inherit the behavior.

---

### ADR-013: Cloud Backup Path Prefixing

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-28 |

#### 1. Background
Initially, the `BackupManager` uploaded ZIP files to the root of the OCI Object Storage bucket using only the timestamp as the filename. As the system scales to multiple data sources (OHLCV, Short, Annc, etc.), storing all backups in a flat root directory would lead to thousands of indistinguishable files, making data recovery and lifecycle management impossible.

#### 2. Decision
Implement a hierarchical prefixing strategy for all cloud uploads to simulate a folder structure within the flat OCI Object Storage.

**Path Pattern**: `{ODS_TABLE_NAME}/{YYYY-MM-DD}/{TIMESTAMP}.zip`

**Implementation Details**:
- The `BaseScraper` now constructs a `cloud_path` by combining the target table name, current date, and the generated filename.
- This `cloud_path` is passed to `BackupManager.sync_to_cloud()`, which appends it to the PAR URL.

#### 3. Consequences
| Description |
|---|
| **Pros** | High observability in OCI Console; enables table-level and date-level data recovery; aligns with Data Lake storage standards. |
| **Cons** | Slight increase in logic complexity within `BaseScraper` to handle path construction. |

---

### ADR-014: Decoupling Backup and Upload

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-29 |

#### 1. Background

The current `BackupManager` implementation follows a "Fetch to Buffer to Flush" synchronous cycle. This creates a significant performance bottleneck: the scraper must wait for the OCI Cloud upload to complete before processing the next batch of symbols. Integration tests showed that for ~1,800 symbols, this synchronous I/O overhead accounts for a large portion of the 15.5-minute total execution time, which is unacceptable for "Pre-close" real-time decision support.

#### 2. Decision

Decouple the "Local Persistence" (Backup) from the "Cloud Synchronization" (Upload) by introducing a dedicated `UploadManager` and shifting to a **Batch-Compress-Upload** strategy.

**ADR-014.1: Single Responsibility Refactoring**
- `BackupManager`: Stripped of all cloud-related logic. Its sole responsibility is the high-speed persistence of raw data to the local disk.
- `UploadManager`: A new standalone module responsible for the end-of-job synchronization lifecycle: Local Folder to Compression (.zip) to Single Cloud Upload to Local Cleanup.

**ADR-014.2: Shift to Batch-Compress-Upload Pattern**
- Abandon the "periodic flush" mechanism during the scraping phase.
- All data for a specific task is written locally first.
- Once the `main.py` orchestrator confirms all symbols are processed, it triggers the `UploadManager` to compress the entire local directory into a single archive and upload it to OCI Object Storage in one request.

**ADR-014.3: Orchestration via `main.py`**
- The execution flow is now managed by `main.py` as follows:
  SymbolProvider to Scraper to BackupManager (Local Write) to UploadManager (Compress and Sync) to Purge.

#### 3. Consequences

| Description |
|---|
| **Pros** | **Extreme Speedup**: Scraping speed is now limited by API response and Disk I/O, not Network Latency. **Reduced API Overhead**: Minimizes the number of connections to OCI. **Improved Reliability**: Local files serve as a fail-safe buffer if the cloud upload fails. |
| **Cons** | **Latency**: Cloud data is only available after the entire job completes, not in real-time. **Disk Usage**: Temporary increase in local disk usage until the final purge. |

---

### ADR-015: Dynamic Configuration-Driven Identity and Decoupled Symbol Sourcing

| Field | Value |
|---|---|
| **Status** | Completed |
| **Date** | 2026-09-03 |

#### 1. Background
The original `BaseScraper` and `SymbolProvider` adopted a global single-configuration pattern. All scrapers shared the same `max_workers` setting and the same symbol source table (`ODS_COMPANY_MASTER`). This led to two critical issues:
1. **Resource Runaway**: No ability to set different concurrency levels for API scrapers (lightweight) vs. Selenium scrapers (heavyweight), easily causing OCI micro VM memory overflow.
2. **Data Coupling**: No ability to specify different symbol source tables for scrapers targeting different markets, limiting multi-market extensibility.

#### 2. Decision
Introduce the **"Identity-based Configuration"** pattern to completely decouple scraper runtime parameters from symbol sources.

**2.1 Dynamic Configuration Loading Mechanism**
- **Identity Definition**: Every scraper subclass must define a unique `scraper_name` attribute (e.g., `scraper_name = "price_ohlcv"`).
- **Hierarchical Priority**: Implement a strict three-tier configuration resolution chain:
  1. **Scraper-Specific**: `config.yaml` to `scrapers` to `{scraper_name}`
  2. **System-Global**: `config.yaml` to `system` (Fallback for common parameters like `batch_size`)
  3. **Code Default**: Hardcoded fallback values within the `BaseScraper` class.
- **Mandatory Validation**: The `symbol_source` parameter is designated as a **Critical Config**. If it is missing from both the scraper-specific and system-global levels in `config.yaml`, the system must throw a `KeyError` at startup to prevent silent failures.

**2.2 Decoupled SymbolProvider**
- **Instance-Based Model**: Refactor `SymbolProvider` from a static utility to a configurable class.
- **Dynamic Instantiation**: `BaseScraper` instantiates its own `SymbolProvider` instance at runtime, passing the `symbol_source` table name retrieved from the configuration.
- **Pipeline Parameterization**: Ensure the entire Fetch to Local Backup to DB Insert pipeline is driven by these dynamically loaded parameters.

#### 3. Consequences
| Description |
|---|
| **Pros**: **High Flexibility**: Each scraper can independently tune concurrency and symbol sources; **Strong Robustness**: Mandatory startup validation eliminates "missing config" runtime crashes; **Scalability**: New market scrapers can be added via YAML updates without modifying core orchestration code. |
| **Cons**: Every new scraper subclass must explicitly define the `scraper_name` attribute to enable configuration mapping. |

#### 4. Implementation Details
- `src/base_scraper.py`: Refactor `__init__` and `_run_iterative` to implement the hierarchical config lookup and dynamic `SymbolProvider` instantiation.
- `src/symbol_provider.py`: Upgrade `SymbolProvider` to a class that accepts `source_table` as an argument; remove global static generators.
- `src/scrapers/`: Update all scrapers (e.g., `price_ohlcv`, `afr`) to define their respective `scraper_name`.
- `test/`: Implement validation tests to ensure the priority chain (Specific to System to Default) is strictly honored.

---

### ADR-016: Symbol Filtering Logic Migration

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-05 |

#### 1. Background
Initially, the `SymbolProvider` handled symbol filtering (inclusion/exclusion lists, sector filtering) within the Python layer. This required loading configuration from `config.yaml` and performing iterative checks in Python, which introduced:
- **Logic Duplication**: Filtering logic existed in Python but the data lived in the DB.
- **Configuration Overhead**: Changes to the target symbol universe required updating YAML files and redeploying/restarting the VM.
- **Violation of "Thin-Edge"**: Python was performing business-level data selection instead of acting as a stateless transport.

#### 2. Decision
Shift all symbol filtering and universe definition from the Python `SymbolProvider` to the Oracle Database layer using **Database Views**.

**2.1 Implementation Strategy**
- **Database-Side**: Create specialized Views (e.g., `VW_TARGET_SYMBOLS`, `VW_PRICE_OHLCV_TARGETS`) that encapsulate all `WHERE` clauses (Sector, Market Cap, Exclusion lists).
- **Python-Side**: The `SymbolProvider` is stripped of all filtering logic. It now accepts a `source_table` parameter which can be either a raw table or a View. It simply executes `SELECT CODE FROM {source}`.
- **Transport Adaptation**: The only logic remaining in `SymbolProvider` is basic string cleaning and suffix completion (e.g., adding `.AX`), as this is required for external API compatibility.

#### 3. Consequences
| Description |
|---|
| **Pros**: **Zero-Latency Filtering**: DB handles selection via optimized indexes. **Dynamic Updates**: The target universe can be changed by updating a View definition in SQL without touching the Python codebase. **Extreme Thin-Edge**: Python becomes a pure data pipe. |
| **Cons**: Requires the creation and management of View objects within the Oracle schema. |

---

### ADR-017: Pre-Production Environment & Truth-Based Verification

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-07 |

#### 1. Background
During the development and audit of the `AnncScraper`, it was identified that traditional unit testing using `unittest.mock.patch` (returning static mock data) created a "false sense of security." While the database ingestion pipeline was verified, the actual connectivity to the ASX website and the accuracy of the DOM parsing remained unproven. Given the extreme 1GB RAM constraint of the OCI Micro VM, "it works on my machine" is an unacceptable benchmark for production readiness.

#### 2. Decisions

**ADR-017.1: Mandatory Pre-Production (Pre-Prod) Environment**
- Establish a separate Ubuntu Server instance that is a **1:1 mirror** of the production OCI Micro VM (1GB RAM, Ubuntu 24.04 LTS).
- All scrapers must be verified in this environment before being promoted to production.
- This environment will be used to profile actual memory peaks (via `htop`) and verify the effectiveness of `cleanup_vm.sh` and `BaseScraper` batching logic.

**ADR-017.2: Shift to Truth-Based Verification**
- Abandon "Mock-only" tests for final integration.
- Implement "Truth-Based" tests: The system must execute the full pipeline (Fetch to Backup to Insert) using real URLs and real database connections.
- **Sampling Requirement**: To ensure transparency, the system must log a sample of the first and last 3 records of the extracted dataset to the console during verification to allow immediate human validation of data integrity.

**ADR-017.3: Deployment Sequence**
- The deployment order is strictly defined as:
  Local Dev to Pre-Prod VM (Stress/Truth Test) to Production VM.

#### 3. Consequences

| Description |
|---|
| **Pros** | Eliminates "Mock-based deception"; guarantees that the system can operate within 1GB RAM; ensures that DOM changes on the source website are detected before production failure. |
| **Cons** | Increases infrastructure overhead (requires an additional VM); increases the time required for the QA cycle. |

---

### ADR-018: Orchestration Layer Design

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-10 |

#### 1. Background
With the Foundation Layer and Scraper Layer certified, the system requires a centralized orchestrator (`main.py`) to transform independent components into an automated production pipeline. The orchestrator must manage the full lifecycle—from environment validation to resource cleanup—while strictly adhering to the 1GB RAM constraint and "Zero-Loss" principle.

#### 2. Decisions

**ADR-018.1: Service-Oriented Component Architecture**
- Implement `StartupHealthChecker` and `AlertManager` as **Service Classes** (Composition) rather than Base Classes (Inheritance).
- **Rationale**: Prevents "Responsibility Pollution" in the `BaseScraper`. Scrapers should remain focused on data extraction, while system-level concerns (environment probes, Pushover notifications) are handled by the orchestrator.

**ADR-018.2: Startup Health Probe (Anti-Silent Failure)**
- Implement a mandatory `StartupHealthChecker` that validates:
  - Oracle Wallet directory existence.
  - Presence of critical `.env` variables.
  - Database connectivity via a `SymbolProvider` probe (fetching a single symbol).
- **Rationale**: In a headless cron environment, "silent failures" are the highest risk. The system must "fail fast" and terminate immediately if the environment is compromised.

**ADR-018.3: Two-Tier Alerting Integration**
- Integrate an `AlertManager` to execute the BRD-defined alerting strategy:
  - **Tier 1 (Warning)**: Local `.jsonl` vs DB row-count mismatch, then Log Warning and Retain Backup.
  - **Tier 2 (Critical)**: Systemic crashes or bulk data missingness, then Trigger Pushover API notification.
- **Rationale**: Suppresses transient noise while ensuring zero-tolerance for systemic data loss.

**ADR-018.4: Scraper Factory Pattern**
- Implement a `ScraperFactory` to map CLI task strings (e.g., `--task annc`) to their corresponding Scraper classes.
- **Rationale**: Decouples `main.py` from specific scraper implementations. Adding new data sources requires only a mapping update in the factory, not a modification of the orchestration logic (Open-Closed Principle).

**ADR-018.5: Global Process Shielding (The Final Defense)**
- Wrap the entire orchestration flow in a global `try...finally` block.
- The `finally` block must explicitly invoke `cleanup_vm.sh` for any task requiring a browser driver.
- **Rationale**: Ensures zero Chrome process leakage regardless of how the program terminates (success or crash), protecting the 1GB RAM limit.

#### 3. Consequences

| Description |
|---|
| **Pros** | Extreme robustness against environment issues; standardized alerting; high extensibility for new scrapers; guaranteed memory sanitization |
| **Cons** | Slight increase in initial boilerplate (creation of 3 new service modules) |

---

---

### ADR-019: Pipeline Orchestration & External Monitoring

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-12 |

#### 1. Background

As the system moves to production, two critical risks remain:
1. **Silent Failures**: If the VM freezes, the network drops, or the system crashes before an alert is sent, the system fails silently, and data gaps are only discovered days later.
2. **Residual Process Leakage**: While `main.py` has a `finally` block, a hard crash (e.g., Segmentation Fault or OOM Kill) can bypass Python's exception handling, leaving orphaned Chrome processes that compromise the 1GB RAM limit.
3. **ETL Gap**: Raw data in ODS needs to be transformed into BDI/DMT layers via Oracle Stored Procedures, requiring a coordinated trigger mechanism.

#### 2. Decisions

**ADR-019.1: Master Shell Orchestration (The "Wrapper" Pattern)**
- Transition from direct Python execution to a Master Shell script (`run_task.sh`).
- The shell script enforces a strict execution sequence: 
  `Pre-run Cleanup` $\rightarrow$ `Python Scraper` $\rightarrow$ `Python Transformer` $\rightarrow$ `Post-run Cleanup`.
- This ensures environment sanitization regardless of the Python process's exit state.

**ADR-019.2: External Heartbeat (The "Dead Man's Switch")**
- Implement an external monitoring loop using Supabase.
- The system sends a "Heartbeat" signal to a Supabase-backed monitor upon successful completion of the daily pipeline.
- **Failure Logic**: If the monitor does not receive a signal within a 25-hour window, it triggers a high-priority "System Down" alert via Pushover.
- **Rationale**: Shifts the monitoring paradigm from "Alert on Error" to "Alert on Silence."

**ADR-019.3: Integrated DB Transformation Trigger**
- Implement a `DbTransformer` service within the Python project.
- This service is responsible for calling Oracle Stored Procedures to move data from ODS to BDI/DMT layers.
- By keeping this in the Python project, it shares the existing `DbOperator` connection pool and `config.yaml` credentials.

**ADR-019.4: Physical VM Hard-Reset**
- Implement a daily physical VM reboot via `crontab` during the system's longest inactivity window.
- **Rationale**: Completely flushes OS caches and kernel-level memory fragments, ensuring a pristine state for the next operational cycle.

#### 3. Consequences

| Description |
|---|
| **Pros** | **Zero-Silence**: Total visibility into system health via external monitoring; **Absolute Sanitization**: Environment is cleaned regardless of Python process state; **Unified ETL**: Data movement from raw ingestion to final transformation is managed under a single orchestration logic. |
| **Cons** | Increased reliance on external infrastructure (Supabase) for monitoring; slightly more complex deployment (requires crontab and shell script management). |

---

### ADR-020: Config-Driven ETL Triggering Mechanism

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-15 |

#### 1. Background

As the system moves from raw data ingestion (ODS) to quantitative analysis (BDI/DMT), a mechanism is needed to trigger Oracle PL/SQL stored procedures. There was a risk of over-engineering this layer by creating a complex class hierarchy (similar to the Scraper Factory) or hardcoding procedure calls within the Python orchestration logic.

#### 2. Decision

**ADR-020.1: Service-Based Trigger (Non-Factory)**
- Implement a single `DbTransformer` service class. Unlike scrapers, transformation logic is uniform (calling a procedure by name); therefore, a Factory pattern is rejected in favor of a simple parameter-driven service.
- The `DbTransformer` acts as a "remote control," utilizing the existing `DbOperator` connection pool to execute `cursor.callproc()`.

**ADR-020.2: Mapping-Driven Orchestration**
- All transformation triggers are decoupled from code and moved to `config.yaml`.
- **Global Pipeline**: A defined sequence of procedures for full-system ETL.
- **Task-Post-Actions**: A mapping between specific scrapers and the procedures they should trigger upon completion.
- **Maintenance Mapping**: A mapping between system maintenance actions (e.g., `cleanup_old_data`) and their corresponding PL/SQL procedures.

**ADR-020.3: Multi-Entry CLI Routing**
- Expand `main.py` to support sub-commands (`scrape`, `transform`, `maintain`).
- This allows the system to run full pipelines, specific transformations, or isolated maintenance tasks (e.g., weekend cleanup) without triggering the entire scraping engine.

#### 3. Consequences

| Description |
|---|
| **Pros** | **Zero-Code Updates**: New ETL steps or maintenance tasks can be added via YAML updates. **Memory Efficiency**: Maintains a flat RAM profile by keeping all logic in PL/SQL. **Operational Flexibility**: Supports both automated pipelines and manual targeted triggers. |
| **Cons** | Requires strict naming conventions for PL/SQL procedures to ensure YAML mappings remain intuitive. |

---

### ADR-021: Decoupling BATCH_ID from PL/SQL Transformation Triggers

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-09-18 |

**Context**: During the design of the `DbTransformer` service, it was debated whether the `BATCH_ID` generated by `main.py` should be passed as a parameter to every Oracle stored procedure (SP).

**Decision**: PL/SQL stored procedures will NOT accept `BATCH_ID` as an input parameter. 

**Rationale**: 
- **Simplicity**: Passing `BATCH_ID` to every SP increases boilerplate in both Python and PL/SQL.
- **Data-Driven Logic**: The "Thick-Core" (PL/SQL) is designed to handle data based on its internal state (e.g., processing all records in ODS that have not yet been moved to BDI, or using the most recent `LOAD_TIME`).
- **Consistency**: Since ODS tables already contain the `BATCH_ID` and `LOAD_TIME` injected by `DbOperator`, the SPs can query these fields internally if specific batch filtering is required, without needing them passed explicitly from the Python layer.

**Consequence**: `DbTransformer` remains a simple "trigger" mechanism, and SP signatures remain clean and focused on business logic.

---

## 4. Implementation Progress (Current State)

### Foundation & Scraper Layer (Certified)
- **Configuration**: Implemented `src/config.py` with dual-file loading per ADR-006
- **Database Operator**: Implemented `src/db_operator.py` as a Pure-INSERT engine per ADR-005
- **Scraper Framework**: Implemented `src/base_scraper.py` and all 6 target scrapers, verified via Truth-Based Tests per ADR-017
- **Symbol Provider**: Implemented centralized `SymbolProvider` with SQL View support per ADR-012 and ADR-016
- **Backup & Upload**: Implemented `BackupManager` and `UploadManager` for decoupled cloud sync per ADR-014

### Orchestration Layer (In Progress)
- **Service Components**: Implemented and unit-tested `StartupHealthChecker`, `AlertManager`, and `ScraperFactory` per ADR-018
- **Pipeline Integration**: Developing `main.py` to integrate all certified components into a production-ready pipeline.

### Current Focus
**Integration & Shielding Phase**: Transitioning from pure Python orchestration to a Shell-wrapped pipeline for absolute resource sanitization.

| Component | Status | Reference |
|---|---|---|
| `main.py` core orchestration | Pending | ADR-018 |
| `run_task.sh` Master Shell | Pending | ADR-019 |
| `cleanup_vm.sh` Resource Shield | Pending | ADR-019 |
| CLI interface (argparse) | Pending | ADR-018 |

---

## 5. Future Actions & Planned Improvements

### Priority Items
| Item | Status | Reference |
|---|---|---|
| **Production Deployment**: Deploy to OCI Micro VM and verify 1GB RAM stability under full-market load | Planned | ADR-017 |
| **ETL Transformation**: Implement `DbTransformer` to trigger Oracle Stored Procedures | Planned | ADR-019 |
| **External Monitoring**: Deploy Supabase Heartbeat (Dead Man's Switch) | Planned | ADR-019 |
| **VM Automation**: Configure `crontab` for daily reboot and task scheduling | Planned | ADR-004 / ADR-019 |
| **PL/SQL Engine**: Implement the "Thick-Core" analytics (EMA, PSAR, Supertrend) | Planned | Roadmap Phase 4 |
| **Memory Stress Test**: Execute full ingestion cycles and monitor peak memory via htop | Planned | ADR-017 |

### Completed Items (Moved from Future)
- **Simplified db_operator.py**: Rewritten per ADR-005, removed MERGE INTO logic, stripped OCI backup code, consolidated audit injection
- **ODS DDL Scripts**: Created `install_equity_schema.sql` for all ODS tables per ADR-007 data model
- **Architectural Pivot**: Moved process shielding from `main.py` `finally` block to external Master Shell for higher reliability | ADR-019 |

### Long-Term Roadmap
- **Phase 4: Thick-Core PL/SQL Analytics Engine**
  - ODS Cleaning & Deduplication Procedures
  - Technical Indicator Calculation (EMA, PSAR, Supertrend)
  - Analytics Views (e.g., `VW_TRADING_SIGNALS`)