"""
DbTransformer Service
Implements ADR-020: Config-Driven ETL Triggering Mechanism.

Responsibility:
- Acts as a high-level orchestrator for Oracle PL/SQL stored procedures.
- Reads 'etl_groups' from config.yaml to execute sequences of transformations.
- Ensures strict sequential execution and immediate halt on failure (Error Propagation).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.db_operator import db as db_operator
from src.config import config

logger = logging.getLogger(__name__)

class DbTransformer:
    """
    Service class to trigger Oracle PL/SQL transformations.
    Decouples the 'what to run' (config.yaml) from the 'how to run' (DbOperator).
    """

    def __init__(self, db_op=db_operator):
        self.db = db_op
        self.config = config

    def trigger_group(self, group_name: str) -> bool:
        """
        Executes a group of stored procedures defined in config.yaml.
        
        Args:
            group_name: The key in the 'etl_groups' section of config.yaml 
                        (e.g., 'full_pipeline', 'post_price_ohlcv_pre').
        
        Returns:
            bool: True if all procedures in the group executed successfully, False otherwise.
        
        Raises:
            KeyError: If the group_name is not found in the configuration.
            Exception: Propagates database errors to the orchestrator for alerting.
        """
        # 1. Load the ETL group from config.yaml
        etl_groups = self.config.get('etl_groups', {})
        if group_name not in etl_groups:
            logger.error(f"Configuration Error: ETL group '{group_name}' not found in config.yaml")
            raise KeyError(f"ETL group '{group_name}' is not defined in configuration.")

        procedures = etl_groups[group_name]
        
        if not isinstance(procedures, list):
            logger.error(f"Configuration Error: ETL group '{group_name}' must be a list of procedure names.")
            raise TypeError(f"ETL group '{group_name}' must be a list.")

        if not procedures:
            logger.warning(f"ETL group '{group_name}' is empty. Nothing to execute.")
            return True

        logger.info(f"🚀 Starting ETL Group Execution: [{group_name}] ({len(procedures)} steps)")

        # 2. Sequential Execution (Strict Order)
        try:
            for index, proc_name in enumerate(procedures, start=1):
                logger.info(f"Step {index}/{len(procedures)}: Triggering {proc_name}...")
                
                # Call the procedure via DbOperator
                # Per ADR-021, we do not pass BATCH_ID; the SP handles its own data selection.
                self.db.call_procedure(proc_name)
                
            logger.info(f"✅ ETL Group [{group_name}] completed successfully.")
            return True

        except Exception as e:
            # ADR-020: Immediate halt on failure to prevent data corruption in downstream steps
            logger.error(f"❌ ETL Group [{group_name}] failed at step {index} ({proc_name}): {e}")
            # Re-raise the exception so main.py can trigger Tier 2 alerts via AlertManager
            raise e

# Expose singleton instance for use in main.py
db_transformer = DbTransformer()