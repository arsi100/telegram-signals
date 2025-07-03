"""
Test script for macro-micro engine integration.
This script simulates:
1. Macro engine publishing bias updates
2. Micro engine receiving and processing these updates
3. Trade decision making based on bias and position conflicts
"""

import os
import sys
import time
import logging
import unittest
import pytz
from datetime import datetime, timedelta
import json
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from micro_scalp_engine.macro_integration import MacroIntegration
from macro_engine_modifications.publish_bias import publish_macro_bias

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestMacroIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Ensure we have GCP project ID
        if not os.getenv("GCP_PROJECT_ID"):
            raise EnvironmentError("GCP_PROJECT_ID environment variable not set")
            
        cls.test_symbol = "BTCUSDT"
        cls.macro_integration = MacroIntegration()
        
    def setUp(self):
        """Reset state before each test."""
        self.macro_integration._cached_bias = {}

    def test_bias_expiration(self):
        """Test that expired bias is properly handled."""
        # Add an expired bias with timezone awareness
        expired_time = datetime.now(pytz.UTC) - timedelta(hours=5)
        self.macro_integration._cached_bias[self.test_symbol] = (
            "LONG", 85.0, expired_time
        )
        
        # Check that expired bias is not returned
        direction, confidence = self.macro_integration.get_macro_bias(self.test_symbol)
        self.assertIsNone(direction)
        self.assertEqual(confidence, 0.0)

    def test_hysteresis_buffer(self):
        """Test the hysteresis buffer behavior."""
        # Test high confidence LONG bias with timezone awareness
        valid_time = datetime.now(pytz.UTC) + timedelta(hours=3)
        self.macro_integration._cached_bias[self.test_symbol] = (
            "LONG", 85.0, valid_time
        )
        
        # Should allow LONG trades
        self.assertTrue(
            self.macro_integration.should_allow_trade(self.test_symbol, "LONG")
        )
        # Should block SHORT trades
        self.assertFalse(
            self.macro_integration.should_allow_trade(self.test_symbol, "SHORT")
        )
        
        # Test hysteresis zone (75% confidence)
        self.macro_integration._cached_bias[self.test_symbol] = (
            "LONG", 75.0, valid_time
        )
        
        # Should allow both directions in hysteresis zone
        self.assertTrue(
            self.macro_integration.should_allow_trade(self.test_symbol, "LONG")
        )
        self.assertTrue(
            self.macro_integration.should_allow_trade(self.test_symbol, "SHORT")
        )

    @patch('google.cloud.bigtable.Client')
    def test_position_conflict(self, mock_bigtable):
        """Test position conflict detection."""
        # Mock a SWING position in Bigtable
        mock_row = MagicMock()
        mock_row.cells = {
            b'position': {
                b'type': [MagicMock(value=b'SWING')],
                b'symbol': [MagicMock(value=self.test_symbol.encode())]
            }
        }
        mock_table = MagicMock()
        mock_table.read_row.return_value = mock_row
        self.macro_integration.table = mock_table
        
        # Check position conflict
        has_conflict, size_mult = self.macro_integration.check_position_conflict(self.test_symbol)
        self.assertTrue(has_conflict)
        self.assertEqual(size_mult, 0.5)

    def test_end_to_end(self):
        """Test end-to-end flow from bias publication to trade decision."""
        logger.info("Starting end-to-end test...")
        
        # 1. Simulate bias publication by directly setting cache
        valid_time = datetime.now(pytz.UTC) + timedelta(hours=3)
        self.macro_integration._cached_bias[self.test_symbol] = (
            "LONG", 85.0, valid_time
        )
        
        # 2. Verify bias is received and cached
        direction, confidence = self.macro_integration.get_macro_bias(self.test_symbol)
        self.assertEqual(direction, "LONG")
        self.assertEqual(confidence, 85.0)
        
        # 3. Check trade permissions
        self.assertTrue(
            self.macro_integration.should_allow_trade(self.test_symbol, "LONG"),
            "Should allow LONG trades with LONG bias"
        )
        self.assertFalse(
            self.macro_integration.should_allow_trade(self.test_symbol, "SHORT"),
            "Should block SHORT trades with LONG bias"
        )
        
        logger.info("End-to-end test completed successfully")

def run_tests():
    """Run the test suite."""
    unittest.main(argv=[''], verbosity=2) 