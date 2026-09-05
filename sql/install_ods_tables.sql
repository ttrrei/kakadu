-- =============================================================================
-- Table: ODS_COMPANY_MASTER (Idempotent Version with Reset)
-- =============================================================================

BEGIN
  -- 1. 尝试删除旧表以确保结构更新 (Reset)
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_COMPANY_MASTER';
  DBMS_OUTPUT.PUT_LINE('Table ODS_COMPANY_MASTER dropped successfully.');
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-00942: table or view does not exist
    IF SQLCODE = -942 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_COMPANY_MASTER did not exist, proceeding to creation.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  -- 2. 创建表 (包含新加入的 COMPANY_NAME 和 LISTING_DATE)
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_COMPANY_MASTER (
        "CODE"         VARCHAR2(4000 BYTE), 
        "COMPANY_NAME"  VARCHAR2(4000 BYTE),
        "SECTOR"       VARCHAR2(4000 BYTE), 
        "LISTING_DATE"  VARCHAR2(50),
        "MARKET_CAP"    VARCHAR2(4000 BYTE), 
        "BATCH_ID"     VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"    VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"   TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_COMPANY_MASTER created successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_COMPANY_MASTER already exists, skipping creation.');
    ELSE
      RAISE; 
    END IF;
END;
/

-- 索引创建
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_CMP_BATCH ON EQUITY.ODS_COMPANY_MASTER("BATCH_ID")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_CMP_BATCH already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_CMP_CODE ON EQUITY.ODS_COMPANY_MASTER("CODE")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_CMP_CODE already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

-- =============================================================================
-- Table: ODS_SHORT_POSITIONS (Idempotent Version with Reset)
-- =============================================================================

BEGIN
  -- 1. 尝试删除旧表以确保结构更新 (Reset)
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_SHORT_POSITIONS';
  DBMS_OUTPUT.PUT_LINE('Table ODS_SHORT_POSITIONS dropped successfully.');
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-00942: table or view does not exist
    IF SQLCODE = -942 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_SHORT_POSITIONS did not exist, proceeding to creation.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  -- 2. 创建表 (All fields as VARCHAR2 to align with ODS design principles)
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_SHORT_POSITIONS (
        "PRODUCT_NAME"    VARCHAR2(4000 BYTE),
        "CODE"            VARCHAR2(4000 BYTE),
        "SHORT_POSITIONS"  VARCHAR2(4000 BYTE),
        "TOTAL_SHARES"     VARCHAR2(4000 BYTE),
        "SHORT_PERCENT"     VARCHAR2(4000 BYTE),
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"      TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_SHORT_POSITIONS created successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_SHORT_POSITIONS already exists, skipping creation.');
    ELSE
      RAISE; 
    END IF;
END;
/

-- 索引创建
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_SHORT_BATCH ON EQUITY.ODS_SHORT_POSITIONS("BATCH_ID")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_SHORT_BATCH already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_SHORT_CODE ON EQUITY.ODS_SHORT_POSITIONS("CODE")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_SHORT_CODE already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

-- =============================================================================
-- Table: ODS_PRICE_TICK (AFR Tick Data - Idempotent Version with Reset)
-- =============================================================================

BEGIN
  -- 1. 尝试删除旧表以确保结构更新 (Reset)
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_PRICE_TICK';
  DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_TICK dropped successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -942 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_TICK did not exist, proceeding to creation.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  -- 2. 创建表 (Aligning with ODS design: business columns as VARCHAR2)
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_PRICE_TICK (
        "CODE"            VARCHAR2(4000 BYTE),
        "OPEN"            VARCHAR2(4000 BYTE),
        "HIGH"            VARCHAR2(4000 BYTE),
        "LOW"             VARCHAR2(4000 BYTE),
        "CLOSE"           VARCHAR2(4000 BYTE),
        "TICK_TIME"       VARCHAR2(4000 BYTE),
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"      TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_TICK created successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_TICK already exists, skipping creation.');
    ELSE
      RAISE; 
    END IF;
END;
/

-- 索引创建
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_TICK_BATCH ON EQUITY.ODS_PRICE_TICK("BATCH_ID")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_TICK_BATCH already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_TICK_CODE ON EQUITY.ODS_PRICE_TICK("CODE")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_TICK_CODE already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_TICK_TIME ON EQUITY.ODS_PRICE_TICK("TICK_TIME")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Index IDX_ODS_TICK_TIME already exists, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/



-- =============================================================================
-- Table: ODS_MARKET_ANNC (ASX Company Announcements)
-- =============================================================================

BEGIN
  -- 1. 尝试删除旧表 (Reset)
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_MARKET_ANNC';
  DBMS_OUTPUT.PUT_LINE('Table ODS_MARKET_ANNC dropped.');
EXCEPTION WHEN OTHERS THEN 
  IF SQLCODE != -942 THEN RAISE; END IF;
END;
/

BEGIN
  -- 2. 创建表 (使用 RELEASE_DATE 避开 DATE 关键字)
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_MARKET_ANNC (
        "CODE"           VARCHAR2(4000 BYTE), 
        "RELEASE_DATE"   VARCHAR2(4000 BYTE), 
        "PSENSITIVE"     VARCHAR2(4000 BYTE), 
        "TITLE"          VARCHAR2(4000 BYTE),
        "BATCH_ID"       VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"      VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"     TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_MARKET_ANNC created successfully.');
EXCEPTION WHEN OTHERS THEN RAISE;
END;
/

-- 索引创建
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANNC_BATCH ON EQUITY.ODS_MARKET_ANNC("BATCH_ID")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANNC_CODE ON EQUITY.ODS_MARKET_ANNC("CODE")';
EXCEPTION WHEN OTHERS THEN 
  IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- =============================================================================
-- Table: ODS_ANALYST_TRENDS (Analyst Recommendation Distribution - Idempotent)
-- =============================================================================

BEGIN
  -- 1. Reset: Drop table if exists to ensure schema alignment
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_ANALYST_TRENDS';
  DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TRENDS dropped successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -942 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TRENDS did not exist, proceeding to creation.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  -- 2. Create Table: Time-series distribution of ratings
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_ANALYST_TRENDS (
        "CODE"            VARCHAR2(4000 BYTE), 
        "MONTH_DATE"      VARCHAR2(4000 BYTE), 
        "STRONG_BUY"      VARCHAR2(4000 BYTE), 
        "BUY"             VARCHAR2(4000 BYTE), 
        "HOLD"            VARCHAR2(4000 BYTE), 
        "SELL"            VARCHAR2(4000 BYTE), 
        "STRONG_SELL"     VARCHAR2(4000 BYTE), 
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"      TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TRENDS created successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TRENDS already exists, skipping creation.');
    ELSE
      RAISE; 
    END IF;
END;
/

-- Indexing for performance and audit
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANLYST_TRND_BATCH ON EQUITY.ODS_ANALYST_TRENDS("BATCH_ID")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANLYST_TRND_CODE ON EQUITY.ODS_ANALYST_TRENDS("CODE")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Indexes for ODS_ANALYST_TRENDS already exist, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/

-- =============================================================================
-- Table: ODS_ANALYST_TARGETS (Analyst Price Targets - Idempotent)
-- =============================================================================

BEGIN
  -- 1. Reset: Drop table if exists to ensure schema alignment
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_ANALYST_TARGETS';
  DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TARGETS dropped successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -942 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TARGETS did not exist, proceeding to creation.');
    ELSE
      RAISE;
    END IF;
END;
/

BEGIN
  -- 2. Create Table: Point-in-time price target consensus
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_ANALYST_TARGETS (
        "CODE"            VARCHAR2(4000 BYTE), 
        "TARGET_LOW"      VARCHAR2(4000 BYTE), 
        "TARGET_HIGH"     VARCHAR2(4000 BYTE), 
        "TARGET_MEAN"     VARCHAR2(4000 BYTE), 
        "TARGET_MEDIAN"    VARCHAR2(4000 BYTE), 
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"      TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TARGETS created successfully.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_ANALYST_TARGETS already exists, skipping creation.');
    ELSE
      RAISE; 
    END IF;
END;
/

-- Indexing for performance and audit
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANLYST_TGT_BATCH ON EQUITY.ODS_ANALYST_TARGETS("BATCH_ID")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_ANLYST_TGT_CODE ON EQUITY.ODS_ANALYST_TARGETS("CODE")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -955 THEN 
      DBMS_OUTPUT.PUT_LINE('Indexes for ODS_ANALYST_TARGETS already exist, skipping.');
    ELSE
      RAISE;
    END IF;
END;
/


-- =============================================================================
-- Table: ODS_PRICE_OHLCV_PRE (Yahoo Pre-Close Snapshot)
-- =============================================================================
BEGIN
  -- 1. Reset: Drop table if exists to ensure schema alignment
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_PRICE_OHLCV_PRE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF;
END;
/
BEGIN
  -- 2. Create Table: All business columns as VARCHAR2 per ADR-005
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_PRICE_OHLCV_PRE (
        "CODE"            VARCHAR2(4000 BYTE),
        "RAW_TIMESTAMP"   VARCHAR2(4000 BYTE),
        "OPEN_PRICE"      VARCHAR2(4000 BYTE),
        "HIGH_PRICE"      VARCHAR2(4000 BYTE),
        "LOW_PRICE"       VARCHAR2(4000 BYTE),
        "CLOSE_PRICE"     VARCHAR2(4000 BYTE),
        "VOLUME"          VARCHAR2(4000 BYTE),
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"    TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_OHLCV_PRE created successfully.');
EXCEPTION WHEN OTHERS THEN RAISE;
END;
/
BEGIN
  -- 3. Indexing for performance and audit
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_PRE_BATCH ON EQUITY.ODS_PRICE_OHLCV_PRE("BATCH_ID")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_PRE_CODE ON EQUITY.ODS_PRICE_OHLCV_PRE("CODE")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_PRE_TS ON EQUITY.ODS_PRICE_OHLCV_PRE("RAW_TIMESTAMP")';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- =============================================================================
-- Table: ODS_PRICE_OHLCV_POST (Yahoo Post-Close Snapshot)
-- =============================================================================
BEGIN
  -- 1. Reset: Drop table if exists to ensure schema alignment
  EXECUTE IMMEDIATE 'DROP TABLE EQUITY.ODS_PRICE_OHLCV_POST';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF;
END;
/
BEGIN
  -- 2. Create Table: All business columns as VARCHAR2 per ADR-005
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_PRICE_OHLCV_POST (
        "CODE"            VARCHAR2(4000 BYTE),
        "RAW_TIMESTAMP"   VARCHAR2(4000 BYTE),
        "OPEN_PRICE"      VARCHAR2(4000 BYTE),
        "HIGH_PRICE"      VARCHAR2(4000 BYTE),
        "LOW_PRICE"       VARCHAR2(4000 BYTE),
        "CLOSE_PRICE"     VARCHAR2(4000 BYTE),
        "VOLUME"          VARCHAR2(4000 BYTE),
        "BATCH_ID"        VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"       VARCHAR2(50)   NOT NULL,
        "RECORD_DTS"    TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
  DBMS_OUTPUT.PUT_LINE('Table ODS_PRICE_OHLCV_POST created successfully.');
EXCEPTION WHEN OTHERS THEN RAISE;
END;
/
BEGIN
  -- 3. Indexing for performance and audit
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_POST_BATCH ON EQUITY.ODS_PRICE_OHLCV_POST("BATCH_ID")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_POST_CODE ON EQUITY.ODS_PRICE_OHLCV_POST("CODE")';
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_PRICE_POST_TS ON EQUITY.ODS_PRICE_OHLCV_POST("RAW_TIMESTAMP")';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF;
END;
/