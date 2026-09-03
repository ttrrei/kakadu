# run_yahoo_speed_test.py
import os
import sys

# 将项目根目录添加到 Python 搜索路径
# __file__ 是当前脚本路径，dirname 两次回到根目录
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import time
from src.scrapers.yahoo_scraper import YahooScraper

# 配置日志，只看 INFO，减少 IO 开销
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # 1. 实例化 (确保 session_type 正确)
    scraper = YahooScraper(session_type="post_close")
    
    # 2. 记录开始时间
    start_time = time.time()
    logger.info("🚀 Starting REAL Yahoo Scraper Speed Test...")

    try:
        # 3. 执行真实抓取
        # 注意：这里不传 symbols，它会通过 SymbolProvider 抓取所有真实符号
        scraper.run(table_name="ODS_PRICE_OHLCV", job_name="SPEED_TEST_REAL")
        
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"✅ Test Completed in {duration:.2f} seconds ({duration/60:.2f} minutes)")
        
    except Exception as e:
        logger.error(f"❌ Test crashed: {e}")