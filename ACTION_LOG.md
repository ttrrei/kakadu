# Action Log - Architecture Decision Records & Test Benchmarks

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

## Known Issues & Scope Changes

### Current Issues
1. **Network Glitch Tolerance**: Transient network failures during web scraping require retry logic and backup retention strategy
2. **Selenium Process Management**: Chrome processes need cleanup after scheduled runs to prevent memory accumulation

### Resolved Issues
- [TODO] Document previously resolved issues if any

## Architecture Decision Records (ADRs)

### ADR-001: Thin-Edge Thick-Core Paradigm
**Status**: Approved  
**Date**: [To be filled]  
**Context**: System must operate within 1GB RAM constraints while maintaining full market data processing capabilities.  
**Decision**: Python serves as stateless, memory-conscious data collector (Thin-Edge). All complex transformations, indicator computations, and signal triggers are pushed down to Oracle PL/SQL (Thick-Core). This eliminates native client library overhead and maintains a flat memory profile.

### ADR-002: Zero Instant Client
**Status**: Approved  
**Date**: [To be filled]  
**Context**: Need lightweight Oracle connectivity without installing native client libraries.  
**Decision**: Use python-oracledb in Thin Mode with Wallet mTLS authentication, eliminating native client library overhead and maintaining a flat memory profile.

### ADR-003: Process Shielding & Sanitization
**Status**: Approved  
**Date**: [To be filled]  
**Context**: Heavy headless browser (Selenium) tasks need to be decoupled from lightweight API tasks in scheduling.  
**Decision**: Execute cleanup_vm.sh after runs to purge residual Chrome processes and prevent memory accumulation between scheduled jobs.

### ADR-004: Scheduled VM Reboot
**Status**: Approved  
**Date**: [To be filled]  
**Context**: System memory and OS caches may accumulate over time during continuous operation.  
**Decision**: Implement weekend bash + crontab physical VM reboot to completely flush system memory and OS caches, ensuring clean state for the next operational period.

## Future Actions & Planned Improvements

### Priority Items
1. **Memory Optimization**: Profile and optimize data ingestion pipeline to reduce peak memory usage
2. **PL/SQL Performance Tuning**: Optimize indicator computation queries for faster signal generation
3. **Selenium Process Management**: Implement automated process cleanup between scheduled runs
4. **Alert Threshold Calibration**: Fine-tune noise-suppressed alerting thresholds based on historical failure patterns

## Scope Changes & Evolution

### Original Scope
- Full ASX market data ingestion across multiple domains
- Native database technical indicator computation
- Automated signal generation and alerting
- Zero infrastructure cost operation on 1GB RAM VM

### Current Scope (Aligned with Original)
All original scope items remain active. No significant scope changes have been made.

## Test Benchmarks & Performance Metrics

### Data Ingestion Performance
- [TODO] Record baseline throughput for each data domain
- [TODO] Track memory usage during ingestion cycles
- [TODO] Measure time-to-first-signal after data arrival

### Signal Generation Performance  
- [TODO] Benchmark EMA, PSAR, Supertrend computation times in PL/SQL
- [TODO] Compare signal generation latency across different market conditions
- [TODO] Validate signal accuracy against known trading patterns

## Monitoring & Observability

### Current Monitoring Setup
- [TODO] Define key performance indicators (KPIs) for system health
- [TODO] Establish alerting thresholds based on historical data
- [TODO] Create dashboards for operational visibility

---

*Last Updated: [Current Date]*  
*Maintained by: Kakadu Development Team*
