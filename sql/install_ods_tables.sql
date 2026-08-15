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
  -- 2. 创建表
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_SHORT_POSITIONS (
        "PRODUCT_NAME"    VARCHAR2(4000 BYTE),
        "CODE"            VARCHAR2(4000 BYTE),
        "SHORT_POSITIONS" NUMBER(20, 0),
        "TOTAL_SHARES"    NUMBER(20, 0),
        "SHORT_PERCENT"   NUMBER(10, 4),
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