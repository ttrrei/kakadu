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

### ADR-005: DbOperator 架构重构与 ODS 审计规范简化
**Status**: Approved
**Date**: 2026-07-30

#### 1. 背景 (Context)
早期重构的 `db_operator.py` 过于复杂，混入了动态 `MERGE INTO` SQL 生成、OCI Object Storage 备份上传以及复杂的 Mock 兼容逻辑，偏离了项目 "Thin-Edge, Thick-Core" 和 "Pure-INSERT" 的核心设计原则。

#### 2. 决策内容 (Decisions)

**ADR-005.1: 审计列简化 (Audit Columns)**
- 所有 ODS 表仅统一保留 **`BATCH_ID`** (UUID v4) 和 **`LOAD_TIME`** (ISO-8601 字符串) 两个审计列。
- 废弃 `SOURCE_SYSTEM` / `datasource` 字段，因为 ODS 采用一源一表设计，表名本身已明确数据源。

**ADR-005.2: OCI 备份解耦 (Backup Decoupling)**
- 从 `DbOperator` 中彻底移除 OCI Object Storage 备份逻辑。
- `DbOperator` 仅负责数据库连接池管理与 Pure-INSERT，备份与云同步由独立的备份模块处理。

**ADR-005.3: ODS Zero-Loss 存储原则 (Strict VARCHAR2)**
- 7 个 ODS 表的所有业务列与审计列统一采用 `VARCHAR2` 存储，杜绝 Python 侧类型转换导致的落库异常。

**ADR-005.4: 统一批次接口设计 (Batch-First Standard Interface)**
- 统一 DB 写入接口，接收扁平化的 `List[Dict[str, Any]]` 数据集。
- 不论是单 Symbol 序列数据还是全市场大表矩阵，均直接利用 `cursor.executemany()` 进行 Batch Size (5~10) 小批量纯追加写入，严禁将批量数据集拆解为逐行复杂操作。

#### 3. 影响与后续 (Consequences)
- 极大简化 `db_operator.py` 的代码复杂度，降低 VM 内存开销。
- 下一步将根据此规范重新编写 `install_ods_tables.sql` DDL 脚本与极简版 `db_operator.py`。

---

## Future Actions & Planned Improvements

### Priority Items
1. **Memory Optimization**: Profile and optimize data ingestion pipeline to reduce peak memory usage
2. **PL/SQL Performance Tuning**: Optimize indicator computation queries for faster signal generation
3. **Selenium Process Management**: Implement automated process cleanup between scheduled runs
4. **Alert Threshold Calibration**: Fine-tune noise-suppressed alerting thresholds based on historical failure patterns
5. **OCI Backup Module Design**: Design and implement standalone backup module for OCI Object Storage cloud sync (per ADR-005.2)
6. **ODS DDL & DbOperator Rewrite**: Rewrite `install_ods_tables.sql` and simplify `db_operator.py` per ADR-005 specifications

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
- [TODO] Define key performance indicators (KPPs) for system health
- [TODO] Establish alerting thresholds based on historical data
- [TODO] Create dashboards for operational visibility

---

*Last Updated: 2026-07-30*
*Maintained by: Kakadu Development Team*
