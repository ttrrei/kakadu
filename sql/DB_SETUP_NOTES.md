# Database Setup Notes

> Initial setup decisions for Kakadu Oracle ADB — recorded for future reference.

---

## 1. Access Control (Do First)

OCI Console → ADB → **Access Control**

- Add your VM public IP, **OR** simply set to **Allow public access** (fine for personal project)
- Web UI (Database Actions) uses HTTPS public endpoint — must be allowed here

---

## 2. ADMIN User

- No additional role/privilege setup needed
- Only two steps required:
  1. **Set ADMIN password**: OCI Console → ADB → Administration → Modify ADMIN Password
  2. **Access control**: ensure source IP is allowed (same as above)
- Directly usable in Database Actions Web UI for ad-hoc SQL queries
- No Profile modification needed

---

## 3. Wallet Configuration

- Downloaded from OCI Console → ADB → **Client Credentials**
- Requires a **Wallet password** (Keystore Password) at download time — **this is mandatory, no skip option**
- Wallet password **does NOT expire** — set it once and forget
- Wallet password ≠ database user password (completely independent)
- Only needed for Python scripts (python-oracledb Thin Mode); Web UI uses HTTPS auth instead

### VM setup

```bash
# Extract wallet to a fixed location
mkdir -p ~/wallet
unzip Wallet_*.zip -d ~/wallet

# Set env var (add to ~/.bashrc for persistence)
export TNS_ADMIN=/home/ubuntu/wallet
```

---

## 4. Schema Script (Run After Above)

**File**: `install_equity_schema.sql`

Executed as ADMIN in OCI Database Actions / SQL Worksheet.

### What it does

- Creates `EQUITY_PROFILE` (UNLIMITED password life, idle time, etc.)
- Creates `EQUITY` user
- Grants: DBA, CONNECT, RESOURCE, DWROLE, CREATE TRIGGER, CREATE JOB, CREATE TABLE/VIEW/PROCEDURE/SEQUENCE/TYPE
- Sets default tablespace DATA, quota unlimited

### Execution order

1. Deploy Wallet to VM (`TNS_ADMIN` env var pointing to wallet dir)
2. Run `install_equity_schema.sql` as ADMIN
3. Proceed with table DDL scripts (future phase)

---

## 5. Quick-Start Checklist

- [ ] OCI access control — add VM IP or allow public
- [ ] Set ADMIN password (OCI Console → ADB → Administration → Modify ADMIN password)
- [ ] Download and deploy Wallet to VM, set `TNS_ADMIN`
- [ ] Run `install_equity_schema.sql` as ADMIN in Database Actions / SQL Worksheet
- [ ] Test: Python thin-mode connection → `SELECT 1 FROM DUAL`
- [ ] Test: Database Actions Web UI → ADMIN login → ad-hoc query

---

*Last Updated: 2026-07-26*
