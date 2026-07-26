-- =============================================================================
-- Kakadu Project - Pure Database Infrastructure & Schema Initialization
-- Target Database: Oracle Autonomous Database (ADB, Always Free)
-- Target Schema:   EQUITY
-- Execution Mode:  Run as ADMIN user in OCI Database Actions / SQL Worksheet
-- =============================================================================
SET DEFINE OFF;

-- -----------------------------------------------------------------------------
-- 1. Create Custom Profile (Anti-Lockout, Anti-Expiration, Anti-Timeout)
-- -----------------------------------------------------------------------------
BEGIN
  EXECUTE IMMEDIATE '
    CREATE PROFILE EQUITY_PROFILE LIMIT 
      PASSWORD_LIFE_TIME      UNLIMITED 
      FAILED_LOGIN_ATTEMPTS   UNLIMITED 
      PASSWORD_GRACE_TIME     UNLIMITED
      PASSWORD_REUSE_TIME     UNLIMITED
      PASSWORD_REUSE_MAX      UNLIMITED
      IDLE_TIME               UNLIMITED
      CONNECT_TIME            UNLIMITED';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -2377 AND SQLCODE != -2378 THEN RAISE; END IF; -- Profile already exists
END;
/

-- -----------------------------------------------------------------------------
-- 2. Create EQUITY User Schema (Idempotent)
--    >>> EDIT "ChangeMe_Strong#2026" before executing <<<
-- -----------------------------------------------------------------------------
BEGIN
  EXECUTE IMMEDIATE 'CREATE USER EQUITY IDENTIFIED BY "ChangeMe_Strong#2026"';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -1920 THEN RAISE; END IF; -- ORA-01920: User already exists
END;
/

-- -----------------------------------------------------------------------------
-- 3. Apply Profile, Tablespace & Storage Quota
-- -----------------------------------------------------------------------------
-- Assign the custom no-expiry profile
ALTER USER EQUITY PROFILE EQUITY_PROFILE;

-- Set standard ADB default tablespace and grant unlimited storage quota
ALTER USER EQUITY DEFAULT TABLESPACE DATA;
ALTER USER EQUITY QUOTA UNLIMITED ON DATA;

-- -----------------------------------------------------------------------------
-- 4. Grant ADB Application Roles & Explicit Privileges
-- -----------------------------------------------------------------------------
-- Full DBA for personal single-user schema
GRANT DBA TO EQUITY;

-- Traditional roles (redundant but harmless for personal use)
GRANT CONNECT TO EQUITY;
GRANT RESOURCE TO EQUITY;

-- DWROLE is the standard Autonomous Data Warehouse / ADB application role.
BEGIN
  EXECUTE IMMEDIATE 'GRANT DWROLE TO EQUITY';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -1919 THEN RAISE; END IF; -- ORA-01919: Role DWROLE does not exist
END;
/

-- Core connection and object creation privileges
GRANT CREATE SESSION TO EQUITY;
GRANT CREATE TABLE TO EQUITY;
GRANT CREATE VIEW TO EQUITY;
GRANT CREATE PROCEDURE TO EQUITY;
GRANT CREATE SEQUENCE TO EQUITY;
GRANT CREATE TYPE TO EQUITY;
GRANT CREATE TRIGGER TO EQUITY;

-- Essential for Thick-Core PL/SQL asynchronous tasks (e.g., deduplication & indicator jobs)
GRANT CREATE JOB TO EQUITY;

-- -----------------------------------------------------------------------------
-- 5. Verification Check (Optional)
-- -----------------------------------------------------------------------------
PROMPT =====================================================================
PROMPT EQUITY Schema Initialization Complete.
PROMPT Profile: EQUITY_PROFILE assigned.
PROMPT Quota:   UNLIMITED ON DATA.
PROMPT Roles:   DWROLE, CREATE SESSION, CREATE JOB granted.
PROMPT =====================================================================

COMMIT;
