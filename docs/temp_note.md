# Kakadu Development Progress Note - Yahoo Scraper

## 📅 Current Status: 2026-08-29
**Overall Status**: Core Pipeline Verified ✅ (End-to-End Integration Passed)

### 1. Achievements (What works)
- **Full Chain Integration**: `ODS_COMPANY_MASTER` $\rightarrow$ `SymbolProvider` $\rightarrow$ `YahooScraper` $\rightarrow$ `DbOperator` $\rightarrow$ `OCI Object Storage`.
- **Dynamic Routing**: Successfully implemented session-based routing (`pre_close` $\rightarrow$ `ODS_PRICE_OHLCV_PRE`).
- **Memory Safety**: Confirmed stable operation under 1GB RAM constraints (No Pandas, O(1) memory usage).
- **Zero-Loss Pipeline**: Verified the sequence: `Local Backup` $\rightarrow$ `DB Insert` $\rightarrow$ `Cloud Sync` $\rightarrow$ `Purge`.
- **Data Normalization**: Resolved Oracle `NULL` vs `''` issue and implemented dynamic `.AX` suffix completion.

### 2. Current Pain Point: Execution Speed 🐢
- **Observation**: Integration test for ~1,800 symbols took ~15.5 minutes.
- **Bottleneck**: 
    - **Synchronous I/O**: Each symbol is requested and processed sequentially.
    - **Blocking Sync**: The system waits for OCI Cloud upload to finish before processing the next batch.
- **Business Impact**: "Pre-close" data must be fetched rapidly to provide actionable intelligence before the market closes. Current speed may be too slow for real-time decision support.

### 3. Optimization Options (The Roadmap)

| Option | Method | Expected Speedup | Memory Risk | Complexity |
| :--- | :--- | :---: | :---: | :---: |
| **A. AsyncIO** | Replace `requests` with `httpx` + `asyncio` | 5x - 10x | Low | Medium |
| **B. Multi-Threading** | Use `ThreadPoolExecutor` for `scrape_one` | 3x - 5x | Medium | Low |
| **C. Background Sync** | Move OCI upload to a background queue | 2x - 3x | Low | Medium |

### 4. Strategic Pivot: `yahooquery` Consideration
- **Context**: Earlier evaluated `yahooquery` as a potential alternative to raw `requests`.
- **Pros**: 
    - Better internal handling of Yahoo's API.
    - Potential for faster multi-ticker fetching.
    - Lower maintenance burden (community-maintained).
- **Cons**: Potential memory overhead if Pandas is not strictly disabled.
- **Decision**: Keep as a **High-Priority Alternative**. If AsyncIO implementation proves too complex or unstable, pivot to `yahooquery` (with strict "No-Pandas" rule) to achieve the required speed for pre-close decision making.

---
**Next Action**: 
1. Implement `main.py` to enable scheduled execution.
2. Evaluate if current speed is acceptable in OCI VM environment.
3. If not, implement Option A (AsyncIO) or pivot to `yahooquery`.
4. Clean up code with temp print.