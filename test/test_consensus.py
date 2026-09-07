# test/test_consensus.py
import unittest
import logging
import sys
import os
from pathlib import Path

# --- 路径补丁 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.consensus_scraper import ConsensusTrendsScraper, ConsensusTargetsScraper
from src.db_operator import db as db_operator
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestConsensusRealIntegration(unittest.TestCase):
    """
    真实环境集成测试：
    验证：Config -> SymbolProvider (DB View) -> Yahoo API -> Backup -> DB
    """

    def test_real_trends_pipeline(self):
        """验证 Trends 真实全链路"""
        logger.info("🚀 Starting REAL Integration Test: Analyst Trends...")
        
        # 1. 实例化 (此时会根据 scraper_name = 'analyst_trends' 从 config.yaml 读取配置)
        scraper = ConsensusTrendsScraper()
        job_name = "REAL_INTEGRATION_TRENDS"
        
        # 2. 执行 (内部会调用 SymbolProvider 查询真实的 DB View)
        # 注意：这里不再 mock _get_symbol_generator
        scraper.run(job_name=job_name)
        
        # 3. 数据库验证
        conn = db_operator.get_connection()
        cursor = conn.cursor()
        try:
            # 检查是否写入了数据
            sql = f'SELECT COUNT(*) FROM EQUITY.ODS_ANALYST_TRENDS WHERE BATCH_ID = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            
            logger.info(f"✅ DB Verification: Found {count} records in ODS_ANALYST_TRENDS")
            self.assertGreater(count, 0, "Should have ingested real data from the DB view symbols")
        finally:
            cursor.close()
            db_operator._pool.release(conn)

    def test_real_targets_pipeline(self):
        """验证 Targets 真实全链路"""
        logger.info("🚀 Starting REAL Integration Test: Analyst Targets...")
        
        # 1. 实例化 (根据 scraper_name = 'analyst_targets' 读取配置)
        scraper = ConsensusTargetsScraper()
        job_name = "REAL_INTEGRATION_TARGETS"
        
        # 2. 执行
        scraper.run(job_name=job_name)
        
        # 3. 数据库验证
        conn = db_operator.get_connection()
        cursor = conn.cursor()
        try:
            sql = f'SELECT COUNT(*) FROM EQUITY.ODS_ANALYST_TARGETS WHERE BATCH_ID = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            
            logger.info(f"✅ DB Verification: Found {count} records in ODS_ANALYST_TARGETS")
            self.assertGreater(count, 0, "Should have ingested real data from the DB view symbols")
        finally:
            cursor.close()
            db_operator._pool.release(conn)

if __name__ == "__main__":
    unittest.main()