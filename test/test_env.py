# tests/test_config.py
import sys
from pathlib import Path

# -------------------------------------------------------------------------
# 路径处理：确保 src 文件夹在 Python 的搜索路径中
# -------------------------------------------------------------------------
# 1. Path(__file__).parent 是 tests/
# 2. .parent 是 project_root/
# 3. / "src" 是 src/
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.config import EnvConfig

def test_load_config():
    print("--- Testing Configuration Loading from /tests ---")
    
    # 1. 加载配置
    try:
        cfg = EnvConfig.load()
        print("✅ Successfully called EnvConfig.load()")
    except Exception as e:
        print(f"❌ Error during load: {e}")
        return

    # 2. 验证数据库配置
    db = cfg.database
    print(f"Database User: {db.user if db.user else 'NOT FOUND'}")
    print(f"TNS Alias: {db.tns_alias if db.tns_alias else 'NOT FOUND'}")
    print(f"Wallet Path: {db.wallet_path if db.wallet_path else 'NOT FOUND'}")
    
    # 3. 验证连接字符串字典
    conn_dict = db.connection_string
    print(f"Connection Dict Keys: {list(conn_dict.keys())}")

    # 检查结果
    if db.user == "":
        print("\n⚠️  WARNING: Database user is empty. Check if .env is in the 'config/' folder.")
    else:
        print("\n🚀 SUCCESS: Configuration loaded correctly from .env!")

if __name__ == "__main__":
    test_load_config()