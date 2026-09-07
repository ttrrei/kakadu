# test/test_annc_scraper.py
import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

# --- 路径初始化：确保能找到 src 模块 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.annc_scraper import AnncScraper
from src.db_operator import db as db_operator

# 配置日志，确保采样数据能打印在控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestAnncScraper(unittest.TestCase):

    def setUp(self):
        # 初始化 Scraper
        self.scraper = AnncScraper()

    def test_annc_truth_verification(self):
        """
        事实性验证测试 (Truth-Based Verification):
        1. 不使用 mock_data 欺骗。
        2. 真实启动浏览器访问 ASX 汇总页。
        3. 拦截并打印列表首尾的数据，分别验证 Today 和 Previous Day。
        4. 验证数据是否成功落地数据库。
        """
        # --- 1. 定义拦截器：在真实抓取后打印首尾采样数据 ---
        original_scrape_all = self.scraper.scrape_all

        def sampling_interceptor(driver, symbols=None):
            logger.info("Interceptor: Initiating REAL scrape_all execution...")
            # 调用真实的抓取逻辑
            real_results = original_scrape_all(driver, symbols)
            
            if real_results:
                logger.info("==== [REAL DATA SAMPLE START] ====")
                
                # A. 打印前三条 (验证 Today 页面数据)
                logger.info("--- First 3 Records (Likely Today's Data) ---")
                for i, rec in enumerate(real_results[:5]):
                    logger.info(f"Row {i+1}: {rec}")
                
                # B. 打印最后三条 (验证 Previous Day 页面数据)
                logger.info("--- Last 3 Records (Likely Previous Day's Data) ---")
                # 使用切片 [-3:] 获取最后三条
                last_three = real_results[-5:]
                total = len(real_results)
                for i, rec in enumerate(last_three):
                    logger.info(f"Row {total - 2 + i}: {rec}")
                
                logger.info(f"Total records captured in this run: {total}")
                logger.info("==== [REAL DATA SAMPLE END] ====")
            else:
                logger.warning("Interceptor: REAL scrape_all returned NO data! Check URLs or Selectors.")
            
            return real_results

        # --- 2. 执行测试链路 ---
        target_table = "ODS_MARKET_ANNC"
        job_name = "REAL_VERIFY_ANNC_002"
        
        try:
            # 使用 side_effect 拦截，但不屏蔽真实调用
            with patch.object(AnncScraper, 'scrape_all', side_effect=sampling_interceptor):
                logger.info(f"Starting E2E Truth Test for {target_table}...")
                # 调用 run() -> 内部会触发 sampling_interceptor -> original_scrape_all
                self.scraper.run(job_name=job_name)

            # --- 3. 数据库事实验证 ---
            conn = db_operator.get_connection()
            cursor = conn.cursor()
            
            # 查询该 BATCH_ID 下的真实记录数
            # 使用双引号包裹 BATCH_ID 避免 Oracle 关键字冲突
            sql = f'SELECT COUNT(*) FROM {target_table} WHERE "BATCH_ID" = :bid'
            cursor.execute(sql, bid=job_name)
            count = cursor.fetchone()[0]
            cursor.close()
            
            self.assertGreater(count, 0, f"Database should contain real records for {job_name}")
            logger.info(f"✅ Truth Test PASSED: {count} real records landed in {target_table}")
            
        except Exception as e:
            self.fail(f"Truth Test FAILED with error: {e}")
        finally:
            if 'conn' in locals() and conn:
                db_operator._pool.release(conn)

    def test_config_integrity(self):
        """验证配置是否正确加载"""
        name = getattr(self.scraper, 'scraper_name', 'annc')
        cfg = self.scraper.config.get(name, {})
        self.assertIn('urls', cfg, "config.yaml must contain 'urls' list for annc")
        self.assertTrue(len(cfg['urls']) >= 2, "annc should have at least 2 summary URLs")
        self.assertEqual(cfg.get('is_bulk'), True, "annc must be in bulk mode")

if __name__ == "__main__":
    unittest.main()