# Kakadu: Systematic Equity Intelligence & Decision Support Engine

**Kakadu** is an ultra-lean, high-resilience **systematic equity intelligence and quantitative decision support engine** built for the Australian Securities Exchange (ASX).

Designed to operate under extreme hardware and resource constraints (**OCI Micro VM with 1GB RAM** and **Oracle Autonomous Database Always Free Tier**), Kakadu automates the entire lifecycle from multi-domain market data ingestion to database-native technical signal generation and alerting—at zero infrastructure cost.

---

## Core Value Proposition

* **Automated Data Foundation**: Ingests full-market ASX data across multiple domains, including Tick, OHLCV, Short Positions, Market Announcements, and Analyst Consensus (Trends & Targets).
* **Quantitative Signal Generation**: Computes technical indicators (EMA, PSAR, Supertrend) natively within the database engine to yield high-confidence intra-day and post-close trading signals.
* **Ultra-Lean Self-Healing Architecture**: Embraces a "Thin-Edge, Thick-Core" philosophy to ensure 24/7 unattended reliability within a strict 1GB RAM footprint.

---

## Architectural Philosophy & Operational Resilience

* **Thin-Edge, Thick-Core Paradigm**: Python serves strictly as a stateless, memory-conscious data collector (Thin-Edge). All complex transformations, indicator computations, and signal triggers are pushed down to Oracle PL/SQL (Thick-Core).
* **Zero Instant Client**: Utilizes `python-oracledb` in **Thin Mode** with Wallet mTLS authentication, eliminating native client library overhead and maintaining a flat memory profile.
* **Process Shielding & Sanitization**: Decouples lightweight API tasks from heavy headless browser (Selenium) tasks in scheduling, executing `cleanup_vm.sh` after runs to purge residual Chrome processes.
* **Scheduled VM Reboot**: Implements a weekend `bash + crontab` physical VM reboot to completely flush system memory and OS caches.
* **Noise-Suppressed Alerting**: Tolerates transient network glitches and web scraping instabilities using a **two-tier strategy**: single-batch mismatches log to file (backup retained), while cumulative failures or bulk missingness trigger Pushover alerts to on-call.

---

## Core Documentation Map

The Kakadu project repository is structured around 4 core living documents:

| Document | Core Responsibility | Key Contents |
| :--- | :--- | :--- |
| [**BRD.md**](./BRD.md) | **Business Requirements & Acceptance** | Data domain definitions, business objectives, execution schedules, high-tolerance alert thresholds, and acceptance criteria. |
| [**SAD_AND_AUDIT.md**](./SAD_AND_AUDIT.md) | **System Architecture & Debt Audit** | System design, OCI/ADB constraints, anti-crash memory safeguards, and the Kosciuszko "Never Copy" anti-pattern list. |
| [**ROADMAP.md**](./ROADMAP.md) | **Implementation Roadmap** | Phase M1–M4 delivery plan, feature prioritization, and key milestones. |
| [**ACTION_LOG.md**](./ACTION_LOG.md) | **Decision Log & Test Benchmarks** | Architecture Decision Records (ADRs), 1GB RAM performance benchmark results, known issues, and scope changes. |

---

## ODS Domain Data Model

| ODS Table Name | Data Domain & Scope | Frequency / Window (AEST) | Primary Key |
| :--- | :--- | :--- | :--- |
| **`ODS_PRICE_OHLCV`** | Yahoo Finance 60d/1h K-line market data | Daily Post-close | `(CODE, RAW_TIMESTAMP)` |
| **`ODS_PRICE_TICK`** | AFR real-time tick-level granular pricing | Pre-close & Post-close | `(CODE, TICK_TIME)` |
| **`ODS_PRICE_QUOTE_EAV`** | AFR market quote EAV pairs (Depth/Valuation) | Pre-close 15:25 / Post-close 16:45 | `(CODE, TAG, UPDATE_TIME)` |
| **`ODS_SHORT_POSITION`** | Shortman daily market-wide short positions | Daily Post-close | `(CODE, UPDATE_DATE)` |
| **`ODS_MARKET_ANNC`** | ASX official company announcements & news | Daily Morning | `(CODE, "DATE", TITLE)` |
| **`ODS_COMPANY_MASTER`** | Market-wide company master data (Sector, Market Cap) | Weekly Batch (Sat 06:00) | `(CODE, UPDATE_DATE)` |
| **`ODS_ANALYST_TRENDS`** | Analyst rating trends & consensus (Yahoo API) | Weekly Batch (Sun 07:00) | `(CODE, UPDATE_DATE)` |
| **`ODS_ANALYST_TARGETS`** | Analyst price targets & valuation (Yahoo API) | Weekly Batch (Sun 07:00) | `(CODE, UPDATE_DATE)` |

---

## Quick Start