# src/config.py
"""
Kakadu Configuration Loader
Implements ADR-006: Dual-File Configuration (.env + config.yaml)
"""

import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ============================================
# Path Configuration
# ============================================
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
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    pushover: PushoverConfig = field(default_factory=PushoverConfig)
    oci: OCIConfig = field(default_factory=OCIConfig)
    log_level: str = "INFO"

    @classmethod
    def load(cls, env_path: Path | str | None = DEFAULT_ENV_FILE, override: bool = True) -> "EnvConfig":
        target_path = Path(env_path) if env_path else None
        if target_path and target_path.exists():
            load_dotenv(dotenv_path=target_path, override=override)
        else:
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

# ============================================
# The Unified Config Object (The "Magic" part)
# ============================================

class ConfigManager:
    """
    Combines YAML settings and ENV secrets into a single access point.
    Implements .get() to mimic dictionary access for the YAML part.
    """
    def __init__(self):
        # 1. Load Sensitive Env Data
        self.env = EnvConfig.load()
        
        # 2. Load Non-Sensitive YAML Data
        self._yaml_config: Dict[str, Any] = self._load_yaml()

    def _load_yaml(self) -> Dict[str, Any]:
        if not DEFAULT_CONFIG_FILE.exists():
            logger.warning(f"config.yaml not found at {DEFAULT_CONFIG_FILE}. Using empty config.")
            return {}
        
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config.yaml: {e}")
            return {}

    def get(self, key: str, default: Any = None, **kwargs) -> Any:
        """
        Allows access to YAML config using dot-notation or nested keys.
        Example: config.get('scrapers', {}).get('company_master', {})
        """
        # This implementation allows the .get().get() chain used in scrapers
        # by returning the sub-dictionary from the YAML config.
        return self._yaml_config.get(key, default)

# Instantiate the singleton object that the rest of the app imports
config = ConfigManager()