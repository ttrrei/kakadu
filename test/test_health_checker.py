# test/test_health_checker.py
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import logging
import sys
import os

# =========================================================================
# Path Fix: Ensure the project root is in sys.path so 'src' can be imported
# =========================================================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import config
from src.health_checker import StartupHealthChecker
from src.symbol_provider import SymbolProvider

# Disable logging during tests to keep output clean, 
# but you can set it to INFO to see the "✓" marks.
logging.getLogger("src.health_checker").setLevel(logging.CRITICAL)

class TestStartupHealthChecker(unittest.TestCase):

    def setUp(self):
        # Use the actual project config singleton
        self.checker = StartupHealthChecker(config)

    # =========================================================================
    # 1. REAL-WORLD INTEGRATION TEST (The "Truth" Test)
    # =========================================================================
    def test_health_check_real_environment(self):
        """
        Scenario: Full Green.
        Verifies that the current environment is actually configured correctly.
        This is a 'Truth-Based' test.
        """
        try:
            self.checker.run()
        except RuntimeError as e:
            self.fail(f"Real-world health check failed! Your environment is not ready: {e}")

    # =========================================================================
    # 2. SIMULATED FAILURE TESTS (Using Mocks to force edge cases)
    # =========================================================================

    @patch("src.health_checker.Path.exists")
    def test_wallet_missing(self, mock_exists):
        """Scenario: Wallet directory does not exist on disk."""
        mock_exists.return_value = False
        
        with self.assertRaises(RuntimeError) as cm:
            self.checker.run()
        
        self.assertIn("Wallet directory not found", str(cm.exception))

    def test_credentials_missing(self):
        """Scenario: Required DB credentials are empty strings in config."""
        # We create a mock config to avoid mutating the real singleton
        mock_config = MagicMock()
        mock_config.env.database.wallet_path = "/tmp/fake_wallet"
        mock_config.env.database.user = "" # Missing user
        mock_config.env.database.password = "some_pass"
        mock_config.env.database.tns_alias = "some_tns"
        
        # Mock Path.exists to pass the first check
        with patch("src.health_checker.Path.exists", return_value=True):
            checker = StartupHealthChecker(mock_config)
            with self.assertRaises(RuntimeError) as cm:
                checker.run()
            self.assertIn("Missing required DB credentials", str(cm.exception))

    @patch("src.symbol_provider.SymbolProvider.get_target_symbols")
    def test_db_connection_crash(self, mock_get_symbols):
        """Scenario: Database connection throws an exception during probe."""
        # Simulate a database driver crash (e.g., oracledb.Error)
        mock_get_symbols.side_effect = Exception("ORA-12170: TNS:Connect timeout occurred")
        
        # Ensure wallet and creds pass
        with patch("src.health_checker.Path.exists", return_value=True):
            with self.assertRaises(RuntimeError) as cm:
                self.checker.run()
            self.assertIn("Database probe failed", str(cm.exception))

    @patch("src.symbol_provider.SymbolProvider.get_target_symbols")
    def test_db_table_empty(self, mock_get_symbols):
        """Scenario: DB connected, but the symbol source table is empty (StopIteration)."""
        # Create a generator that immediately raises StopIteration
        def empty_gen():
            yield from []
        
        mock_get_symbols.return_value = empty_gen()
        
        with patch("src.health_checker.Path.exists", return_value=True):
            # This should NOT raise an exception, it should just log a warning
            try:
                self.checker.run()
            except RuntimeError as e:
                self.fail(f"run() raised RuntimeError on empty table, but it should have passed: {e}")

if __name__ == "__main__":
    unittest.main()