# test/test_alert_manager.py
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys
import os
import requests

# ==============================================================================
# PATH FIX: Prevent ModuleNotFoundError: No module named 'src'
# ==============================================================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.alert_manager import AlertManager, alert_manager
from src.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestAlertManagerUnit(unittest.TestCase):
    """
    Unit Tests: Focus on logic, state management, and crash-proofing.
    No real network calls are made here.
    """

    def setUp(self):
        self.am = AlertManager()

    def test_tier1_mismatch_logic(self):
        """Test Tier 1: Should return True on mismatch and False on match."""
        # Case 1: Mismatch
        self.assertTrue(
            self.am.check_tier1_mismatch(100, 90, "test_task", "/tmp/backup"),
            "Tier 1 should return True when counts differ"
        )
        # Case 2: Match
        self.assertFalse(
            self.am.check_tier1_mismatch(100, 100, "test_task", "/tmp/backup"),
            "Tier 1 should return False when counts match"
        )
        logger.info("✅ Unit Test: Tier 1 mismatch logic PASSED")

    @patch('src.alert_manager.requests.post')
    def test_tier2_disabled_state(self, mock_post):
        """Test that AlertManager handles missing config without crashing."""
        # Patch underlying variables to make 'enabled' property return False
        with patch.object(config.env.pushover, 'user_key', ""), \
             patch.object(config.env.pushover, 'api_token', ""):
            
            result = self.am.send_tier2_alert("Test Message")
            self.assertFalse(result)
            mock_post.assert_not_called()
            
        logger.info("✅ Unit Test: Tier 2 disabled state (no crash) PASSED")

    @patch('src.alert_manager.requests.post')
    def test_tier2_exception_handling(self, mock_post):
        """Test that network exceptions (e.g. DNS failure) do NOT crash the main program."""
        # Mock a catastrophic network failure (ConnectionError)
        mock_post.side_effect = requests.exceptions.ConnectionError("DNS Failure")
        
        try:
            result = self.am.send_tier2_alert("Crash Test Message")
            self.assertFalse(result, "Should return False when request fails")
        except Exception as e:
            self.fail(f"AlertManager crashed on network exception: {e}")
            
        logger.info("✅ Unit Test: Tier 2 network exception shielding PASSED")

    @patch('src.alert_manager.requests.post')
    def test_tier2_http_error_handling(self, mock_post):
        """Test that HTTP errors (4xx, 5xx) from the server do NOT crash the program."""
        # Mock a response that raises an HTTPError when raise_for_status() is called
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error: Unauthorized")
        mock_post.return_value = mock_response
        
        try:
            result = self.am.send_tier2_alert("HTTP Error Test")
            self.assertFalse(result, "Should return False when server returns HTTP error")
        except Exception as e:
            self.fail(f"AlertManager crashed on HTTP error: {e}")
            
        logger.info("✅ Unit Test: Tier 2 HTTP error shielding PASSED")


class TestAlertManagerIntegration(unittest.TestCase):
    """
    Integration Tests: Real network calls using .env credentials.
    """

    def test_real_pushover_notification(self):
        """
        Truth-Based Test: Send a real notification to the phone.
        Requires valid PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN in .env
        """
        if not config.env.pushover.enabled:
            self.skipTest("Pushover credentials not found in .env. Skipping integration test.")

        logger.info("🚀 Sending real Pushover notification... Please check your phone.")
        
        # Use platform-agnostic node name
        node_name = os.uname().nodename if os.name != 'nt' else os.getenv('COMPUTERNAME', 'Windows')
        test_message = f"Kakadu Integration Test: System is Online. Node: {node_name}"
        
        # Use the singleton instance
        success = alert_manager.send_tier2_alert(
            message=test_message, 
            priority=1
        )
        
        self.assertTrue(success, "Real Pushover API call failed. Check .env tokens and network.")
        logger.info("✅ Integration Test: Real notification delivered PASSED")


if __name__ == "__main__":
    unittest.main()