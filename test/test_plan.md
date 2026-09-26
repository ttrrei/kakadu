# Kakadu Certification Plan (Condensed)

## 1. Objective
Validate the "Thin-Edge, Thick-Core" architecture under 1GB RAM constraints. Transition from local development to VM deployment via Truth-Based Verification.

## 2. Validation Matrix (The "Certification" Path)

### Phase I: Foundation Layer (Infrastructure)
**Goal**: Ensure the "Safety Net" is operational.
- [x] **DbOperator**: Bulk Insert $\rightarrow$ Fallback to Individual $\rightarrow$ Audit Injection $\rightarrow$ SP Trigger.
- [x] **Backup/Upload**: Local JSONL $\rightarrow$ Zip $\rightarrow$ OCI Cloud Sync $\rightarrow$ Local Purge.
- [x] **Health/Alert**: Startup Probe $\rightarrow$ Tier 2 Pushover Notification $\rightarrow$ Network Shielding.
- [x] **Config**: Dual-file (.env/yaml) loading $\rightarrow$ Hierarchical resolution.

### Phase II: Scraper Layer (Truth-Based)
**Goal**: Verify real-world data extraction and memory stability.

| Task | Mode | Key Verification | Status |
| :--- | :--- | :--- | :--- |
| `company_master` | Bulk | CSV API $\rightarrow$ Full Market Ingestion | ✅ |
| `price_ohlcv (Pre/Post)` | Iterative | Concurrent Fetching $\rightarrow$ Buffer Flushing | ✅ |
| `short` | Bulk | Shortman CSV $\rightarrow$ Pure-INSERT | ✅ |
| `analyst_consensus` | Iterative | Dual-Table Write $\rightarrow$ No-Data Handling | ✅ |
| `annc` | Bulk | **Selenium** $\rightarrow$ Error Recovery $\rightarrow$ Process Cleanup | ✅ |
| `afr` | Iterative | **High-Volume Tick** $\rightarrow$ Memory Stability | ✅ |

### Phase III: Orchestration & ETL (The Final Mile)
**Goal**: End-to-End pipeline from raw data to quantitative signal.
- [ ] **CLI Dispatch**: `main.py` $\rightarrow$ `scrape` $\rightarrow$ `transform` $\rightarrow$ `maintain`.
- [ ] **ETL Flow**: `ODS` (Raw) $\rightarrow$ `BDI` (Cleaned) $\rightarrow$ `DMT` (Indicators).
- [ ] **Audit Trail**: `SYS_BATCH_LOG` status transition (`RUNNING` $\rightarrow$ `SUCCESS`).

---

## 3. VM Deployment & Stress Test (Pre-Prod)
**Goal**: Final sign-off on OCI Micro VM (1GB RAM).

1. **Process Shielding**: Deploy `run_task.sh` $\rightarrow$ `cleanup_vm.sh` $\rightarrow$ Python.
2. **Memory Profiling**: Monitor `htop` during `annc` and `afr` runs (Peak $\le$ 800MB).
3. **Chaos Test**: Simulate Network/DB failure $\rightarrow$ Verify Tier 2 Alert.
4. **Hard Reset**: Verify daily `crontab` reboot and scheduled task execution.

## 4. Acceptance Criteria (DoD)
- [ ] **Zero OOM**: No crashes during full-market ingestion.
- [ ] **Zero Data Loss**: Local Backup = DB Count = Cloud Backup.
- [ ] **Zero Silence**: Every fatal error triggers a Pushover alert.
- [ ] **Zero Leakage**: No orphaned Chrome processes post-execution.