"""
Kakadu Configuration Loader
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv


# ============================================
# Path Configuration
# ============================================
# 1. Path(__file__).parent 是 src/
# 2. .parent.parent 是 project_root/
# 3. / "config" 进入 config/ 文件夹
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

DEFAULT_ENV_FILE = CONFIG_DIR / ".env"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.yaml"


# ============================================
# Dataclasses - Sensitive / Environment Config
# ============================================

@dataclass
class DatabaseConfig:
    wallet_path: str = ""
    wallet_password: str = ""
    tns_alias: str = ""
    user: str = ""
    password: str = ""

    @property
    def connection_string(self) -> dict:
        """Build Oracle connection dict for python-oracledb Thin Mode + Wallet."""
        return {
            "user": self.user,
            "password": self.password,
            "dsn": self.tns_alias,
            "config_dir": self.wallet_path,
        }


@dataclass
class PushoverConfig:
    user_key: str = ""
    api_token: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.user_key and self.api_token)


@dataclass
class OCIConfig:
    config_path: str = ""
    bucket_namespace: str = ""
    bucket_name: str = ""


@dataclass
class EnvConfig:
    """Holds all sensitive and environment-specific configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    pushover: PushoverConfig = field(default_factory=PushoverConfig)
    oci: OCIConfig = field(default_factory=OCIConfig)
    log_level: str = "INFO"

    @classmethod
    def load(cls, env_path: Path | str | None = DEFAULT_ENV_FILE, override: bool = True) -> "EnvConfig":
        """Load env variables from specified file or system environment."""
        # 确保路径是 Path 对象
        target_path = Path(env_path) if env_path else None
        
        if target_path and target_path.exists():
            load_dotenv(dotenv_path=target_path, override=override)
        else:
            # 如果没找到 .env 文件，尝试直接加载系统环境变量 (Production/Docker 模式)
            load_dotenv(override=override)

        return cls(
            database=DatabaseConfig(
                wallet_path=os.getenv("ORACLE_WALLET_PATH", ""),
                wallet_password=os.getenv("ORACLE_WALLET_PASSWORD", ""),
                tns_alias=os.getenv("ORACLE_TNS_ALIAS", ""),
                user=os.getenv("ORACLE_USER", ""),
                password=os.getenv("ORACLE_PASSWORD", ""),
            ),
            pushover=PushoverConfig(
                user_key=os.getenv("PUSHOVER_USER_KEY", ""),
                api_token=os.getenv("PUSHOVER_API_TOKEN", ""),
            ),
            oci=OCIConfig(
                config_path=os.getenv("OCI_CONFIG_PATH", ""),
                bucket_namespace=os.getenv("OCI_BUCKET_NAMESPACE", ""),
                bucket_name=os.getenv("OCI_BUCKET_NAME", ""),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )