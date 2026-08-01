-- =============================================================================
-- Project: Kakadu / Equity ODS
-- File:   cleanup_db.sql
-- Purpose: Complete Wipe of EQUITY Schema for Clean Re-installation
-- Execution: Run as ADMIN user in OCI Database Actions / SQL Worksheet
-- -----------------------------------------------------------------------------
-- WARNING: This will DELETE ALL DATA and OBJECTS in the EQUITY schema.
-- =============================================================================

SET DEFINE OFF;

PROMPT 🗑️ Starting Full Cleanup of EQUITY Schema...

-- 1. Drop the user and all its objects (including tables, indexes, and sequences)
-- CASCADE ensures that all dependent objects are also removed.
BEGIN
  EXECUTE IMMEDIATE 'DROP USER EQUITY CASCADE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -1918 THEN RAISE; END IF; -- ORA-01918: user does not exist
END;
/

-- 2. Drop the custom profile to ensure a clean slate for the next install
BEGIN
  EXECUTE IMMEDIATE 'DROP PROFILE EQUITY_PROFILE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -1350 THEN RAISE; END IF; -- ORA-01350: profile does not exist
END;
/

PROMPT ✅ Cleanup Complete. The EQUITY user and all associated ISEQ\$\$, tables, and indexes have been removed.
PROMPT 🚀 You can now run install_equity_schema.sql for a fresh installation.

COMMIT;