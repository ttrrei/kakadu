-- =============================================================================
-- Table: ODS_COMPANY_MASTER (Idempotent Version)
-- =============================================================================

BEGIN
  -- 尝试创建表
  EXECUTE IMMEDIATE '
    CREATE TABLE EQUITY.ODS_COMPANY_MASTER (
        "CODE"       VARCHAR2(4000 BYTE), 
        "SECTOR"     VARCHAR2(4000 BYTE), 
        "MARKET_CAP" VARCHAR2(4000 BYTE), 
        "BATCH_ID"   VARCHAR2(50)   NOT NULL, 
        "LOAD_TIME"  VARCHAR2(50)   NOT NULL,
        "RECORD_DTS" TIMESTAMP WITH LOCAL TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )';
EXCEPTION
  WHEN OTHERS THEN
    -- ORA-00955: name is already used by an existing object
    IF SQLCODE = -955 THEN
      DBMS_OUTPUT.PUT_LINE('Table ODS_COMPANY_MASTER already exists, skipping creation.');
    ELSE
      RAISE; -- 如果是其他错误，则抛出
    END IF;
END;
/

-- 索引的创建同样需要幂等处理
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX EQUITY.IDX_ODS_CMP_BATCH ON EQUITY.ODS_COMPANY_MASTER("BATCH_ID")';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -// ORA-00955: name is already used by an existing object
       -955 THEN 
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