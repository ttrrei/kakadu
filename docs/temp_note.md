# Kakadu Final Implementation Roadmap

## Phase 1: Core Orchestration (Current)
- [ ] Finalize `src/main.py` (Batch ID integration, Tier 1 check, Cloud Sync).
- [ ] Functional Test: Run all scrapers $\rightarrow$ Verify DB $\rightarrow$ Verify Cloud ZIP.

## Phase 2: Infrastructure & Shielding
- [ ] Create `scripts/cleanup_vm.sh`: Force kill Chrome/Chromedriver processes.
- [ ] Create `scripts/run_task.sh` (Master Shell):
    - Sequence: `cleanup` $\rightarrow$ `main.py (scrape)` $\rightarrow$ `main.py (transform)` $\rightarrow$ `cleanup`.
- [ ] Configure `crontab`:
    - Schedule `run_task.sh` for each task.
    - Schedule `sudo reboot` (Daily pre-run).

## Phase 3: Data Transformation (ETL)
- [ ] Implement `src/services/db_transformer.py`: Single service class for `callproc` execution.
- [ ] Update `config.yaml`: Define `etl_pipeline`, `task_post_actions`, and `maintenance_tasks` mappings.
- [ ] Expand `main.py` CLI: Implement sub-commands (`scrape`, `transform`, `maintain`) for flexible routing.
- [ ] Integration Test: Verify `scrape` $\rightarrow$ `post_action` trigger flow.

## Phase 4: External Monitoring (Dead Man's Switch)
- [ ] Create `scripts/heartbeat.sh`: Send status to Supabase.
- [ ] Configure Supabase Edge Function: Monitor heartbeat $\rightarrow$ Alert via Pushover if missing.

## Critical Constraints (The Red Line)
- RAM: < 1GB (OCI Micro VM).
- Cleanup: Mandatory before and after every run.
- Reliability: Zero-loss pipeline (Local $\rightarrow$ DB $\rightarrow$ Cloud $\rightarrow$ Purge).
```

```markdown Action_Log.md
# Action Log - Kakadu Project

## Completed
- [x] Architecture Design: Thin-Edge, Thick-Core philosophy.
- [x] Core Services: `DbOperator`, `BackupManager`, `UploadManager`, `SymbolProvider`.
- [x] Scraper Framework: `BaseScraper` and `ScraperFactory` implemented.
- [x] Configuration: Dual-file system (.env + config.yaml).
- [x] Health Check: `StartupHealthChecker` implemented.
- [x] Audit: `main.py` reviewed and certified for 1GB RAM (SRE Audit).
- [x] Logic Update: `batch_id` implementation completed for traceability.

## In Progress
- [ ] Final `main.py` implementation and integration testing.

## Next Steps
- [ ] Implement `cleanup_vm.sh` and `run_task.sh` (Master Shell).
- [ ] Implement `DbTransformer` for Oracle Stored Procedure execution.
- [ ] Set up VM-level automation (Crontab reboot & task scheduling).
- [ ] Deploy Supabase Heartbeat monitoring (Dead Man's Switch).