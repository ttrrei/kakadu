import os
import logging
from pathlib import Path
from src.config import ConfigManager
from src.symbol_provider import SymbolProvider

logger = logging.getLogger(__name__)

class StartupHealthChecker:
    """
    Implements ADR-018.2: Startup Health Probe (Anti-Silent Failure).
    Validates environment and database connectivity before pipeline execution.
    """

    def __init__(self, config: ConfigManager):
        self.config = config

    def run(self):
        """
        Executes the health check sequence. 
        Raises RuntimeError if any critical check fails.
        """
        logger.info("Performing startup health checks...")

        # 1. Verify Wallet Directory
        wallet_path = self.config.env.database.wallet_path
        if not wallet_path or not Path(wallet_path).exists():
            raise RuntimeError(f"Critical Error: Oracle Wallet directory not found at: {wallet_path}")
        logger.info("Wallet directory verified.")

        # 2. Verify Essential DB Credentials
        db_cfg = self.config.env.database
        missing_creds = []
        if not db_cfg.user: missing_creds.append("ORACLE_USER")
        if not db_cfg.password: missing_creds.append("ORACLE_PASSWORD")
        if not db_cfg.tns_alias: missing_creds.append("ORACLE_TNS_ALIAS")

        if missing_creds:
            raise RuntimeError(f"Critical Error: Missing required DB credentials in .env: {', '.join(missing_creds)}")
        logger.info("DB credentials verified.")

        # 3. Real Database Probe (The "Truth" Test)
        # We use SymbolProvider to verify the entire connection chain (Thin Mode -> Wallet -> DB)
        try:
            # We attempt to probe using the first available symbol source from the config 
            # or a default ODS_COMPANY_MASTER if no scrapers are defined yet.
            # For the probe, we just need to see if we can execute a SELECT.
            
            # Try to find any symbol_source in the config to use for the probe
            symbol_source = "ODS_COMPANY_MASTER" # Default fallback
            for key, value in self.config._yaml_config.items():
                if isinstance(value, dict) and 'symbol_source' in value:
                    symbol_source = value['symbol_source']
                    break

            logger.info(f"Probing database connection via {symbol_source}...")
            provider = SymbolProvider(source_table=symbol_source)
            
            # Attempt to fetch exactly one symbol
            gen = provider.get_target_symbols()
            try:
                next(gen)
                logger.info("Database probe successful: Connection established and query executed.")
            except StopIteration:
                logger.warning("Database connected, but the symbol source table is empty.")
            
        except Exception as e:
            raise RuntimeError(f"Critical Error: Database probe failed. System cannot proceed. Details: {e}")

        logger.info("All startup health checks passed. System is ready.")