import sys
from pathlib import Path

# -------------------------------------------------------------------------
# 路径处理：确保 src 文件夹在 Python 的搜索路径中
# -------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.config import config, EnvConfig

def test_env_secrets():
    print("\n--- 1. Testing .env Secrets (Sensitive Data) ---")
    env = config.env
    
    # 验证数据库配置
    db_results = {
        "ORACLE_USER": env.database.user,
        "ORACLE_TNS_ALIAS": env.database.tns_alias,
        "ORACLE_WALLET_PATH": env.database.wallet_path,
    }
    
    all_found = True
    for key, value in db_results.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value if value else 'NOT FOUND'}")
        if not value: all_found = False
        
    if all_found:
        print("🚀 SUCCESS: All critical .env secrets loaded.")
    else:
        print("⚠️  WARNING: Some .env secrets are missing. Check config/.env")

def test_yaml_structure():
    print("\n--- 2. Testing config.yaml Structure (Non-Sensitive) ---")
    
    # 验证全局配置 (假设 YAML 中有 'global' 节点)
    global_cfg = config.get('system')
    if global_cfg:
        print(f"✅ Global config found: {list(global_cfg.keys())}")
    else:
        print("❌ Global config node NOT FOUND in config.yaml")

    # 验证 Scraper 特定配置 (假设 YAML 中有 'scrapers' 节点)
    scrapers_cfg = config.get('scrapers')
    if scrapers_cfg:
        print(f"✅ Scrapers config found. Available scrapers: {list(scrapers_cfg.keys())}")
        
        # 尝试读取一个具体 scraper 的配置 (例如 price_ohlcv)
        # 这里的逻辑模拟 BaseScraper 的调用方式
        test_scraper = 'price_ohlcv'
        specific_cfg = scrapers_cfg.get(test_scraper)
        if specific_cfg:
            print(f"✅ Found specific config for {test_scraper}: {specific_cfg}")
        else:
            print(f"⚠️  No specific config found for {test_scraper}")
    else:
        print("❌ Scrapers config node NOT FOUND in config.yaml")

def test_edge_cases():
    print("\n--- 3. Testing Edge Cases & Defaults ---")
    
    # 验证不存在的 key 是否返回 None 而不崩溃
    non_existent = config.get('non_existent_key')
    if non_existent is None:
        print("✅ Correctly returned None for non-existent key")
    else:
        print("❌ Unexpected value returned for non-existent key")

    # 验证带默认值的 get
    default_val = config.get('missing_with_default', default="DEFAULT_VALUE")
    if default_val == "DEFAULT_VALUE":
        print("✅ Correctly returned default value")
    else:
        print(f"❌ Failed to return default value, got: {default_val}")

if __name__ == "__main__":
    print("====================================================")
    print("🚀 STARTING FULL CONFIGURATION INTEGRATION TEST")
    print("====================================================")
    
    try:
        test_env_secrets()
        test_yaml_structure()
        test_edge_cases()
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n====================================================")
    print("✅ CONFIGURATION TEST COMPLETE")
    print("====================================================")