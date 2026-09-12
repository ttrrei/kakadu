# src/alert_manager.py
"""
Kakadu Alert Manager
Implements ADR-018 and BRD Section 3: High-Tolerance Anti-False-Alarm Strategy.
"""

import logging
import requests
from typing import Optional
from .config import config

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Handles system notifications and data integrity alerts.
    Implements a two-tier alerting system to suppress transient noise 
    while ensuring critical failures are reported via Pushover.
    """

    def __init__(self):
        # Access Pushover credentials from the singleton config object
        self.pushover_cfg = config.env.pushover
        self.api_url = "https://api.pushover.net/1/messages.json"

    def check_tier1_mismatch(self, local_count: int, db_count: int, task_name: str, backup_path: str) -> bool:
        """
        Tier 1 (Warning Log): Detects row-count mismatch between local JSONL and DB.
        
        Principle: Zero-tolerance alerts are suppressed. Single batch hiccups are 
        logged as warnings and backups are retained, but no human is notified.
        
        Returns:
            True if a mismatch occurred (indicating backup should be retained).
            False if counts match.
        """
        if local_count != db_count:
            logger.warning(
                f"[TIER-1 ALERT] Data mismatch detected in task '{task_name}'. "
                f"Local: {local_count} rows, DB: {db_count} rows. "
                f"Backup retained at: {backup_path}"
            )
            return True
        
        return False

    def send_tier2_alert(self, message: str, priority: int = 1) -> bool:
        """
        Tier 2 (Pushover Alert): Triggers immediate notification for systemic risks.
        
        Args:
            message: The alert content to send.
            priority: Pushover priority (1 = High, 0 = Normal, -1 = Low).
            
        Returns:
            True if the alert was sent successfully, False otherwise.
        """
        if not self.pushover_cfg.enabled:
            logger.error(f"[TIER-2 FAILURE] Pushover is not configured. Cannot send critical alert: {message}")
            return False

        payload = {
            "token": self.pushover_cfg.api_token,
            "user": self.pushover_cfg.user_key,
            "message": message,
            "priority": priority,
            "title": "Kakadu System Critical"
        }

        try:
            # Use a short timeout to prevent the main pipeline from hanging on network jitter
            response = requests.post(self.api_url, data=payload, timeout=10)
            response.raise_for_status()
            logger.info("Tier 2 Pushover alert sent successfully.")
            return True
        except requests.exceptions.RequestException as e:
            # Critical: Alert failure must NOT crash the main ingestion pipeline
            logger.error(f"[ALERT-SYSTEM ERROR] Failed to send Pushover notification: {e}")
            return False

# Instantiate as a singleton for use in main.py
alert_manager = AlertManager()