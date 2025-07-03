"""
Macro Integration Module

This module handles the integration between the MICRO-SCALP engine and the MACRO engine's bias signals.
It implements:
1. Subscription to macro bias updates
2. Hysteresis buffer for bias filtering
3. Position conflict checking
"""

import os
import json
import logging
import pytz
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from google.cloud import pubsub_v1, bigtable
from google.cloud.bigtable import row_filters

# --- Configuration ---
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MACRO_BIAS_TOPIC = "macro-bias-updates"
MACRO_BIAS_SUB = "micro-macro-bias-sub"

# Confidence thresholds with hysteresis
CONFIDENCE_THRESHOLD_ACTIVATE = 80.0  # Threshold to activate directional bias
CONFIDENCE_THRESHOLD_DEACTIVATE = 70.0  # Threshold to deactivate directional bias

class MacroIntegration:
    def __init__(self):
        """Initialize the macro integration module."""
        self._cached_bias: Dict[str, Tuple[str, float, datetime]] = {}
        self._setup_pubsub()
        self._setup_bigtable()
        
    def _setup_pubsub(self):
        """Set up Pub/Sub subscriber for macro bias updates."""
        if not PROJECT_ID:
            logging.warning("GCP_PROJECT_ID not set, running in test mode")
            return
            
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(PROJECT_ID, MACRO_BIAS_SUB)
        
        def callback(message):
            try:
                data = json.loads(message.data.decode())
                symbol = data["symbol"]
                direction = data["direction"]
                confidence = float(data["confidence"])
                expires_at = datetime.fromisoformat(data["expires_at"])
                
                self._cached_bias[symbol] = (direction, confidence, expires_at)
                logging.info(f"Received macro bias for {symbol}: {direction} ({confidence}%)")
                
                message.ack()
            except Exception as e:
                logging.error(f"Error processing macro bias message: {e}")
                message.nack()
        
        streaming_pull_future = subscriber.subscribe(
            subscription_path, callback=callback
        )
        logging.info("Initialized Pub/Sub subscriber for macro bias updates")
        
    def _setup_bigtable(self):
        """Set up Bigtable client for position tracking."""
        if not PROJECT_ID:
            logging.warning("GCP_PROJECT_ID not set, running in test mode")
            return
            
        self.bigtable_client = bigtable.Client(project=PROJECT_ID)
        self.instance = self.bigtable_client.instance("cryptotracker-bigtable")
        self.table = self.instance.table("live-positions")
        logging.info("Initialized Bigtable client for position tracking")
        
    def get_macro_bias(self, symbol: str) -> Tuple[Optional[str], float]:
        """
        Get the current macro bias for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Tuple of (direction, confidence) where direction is None if no valid bias
        """
        if symbol not in self._cached_bias:
            return None, 0.0
            
        direction, confidence, expires_at = self._cached_bias[symbol]
        
        # Convert naive datetime to UTC if needed
        if expires_at.tzinfo is None:
            expires_at = pytz.UTC.localize(expires_at)
            
        if datetime.now(pytz.UTC) > expires_at:
            del self._cached_bias[symbol]
            return None, 0.0
            
        return direction, confidence
        
    def should_allow_trade(self, symbol: str, proposed_direction: str) -> bool:
        """
        Check if a trade should be allowed based on macro bias.
        
        Args:
            symbol: Trading pair
            proposed_direction: The direction of the proposed trade ("LONG" or "SHORT")
            
        Returns:
            True if trade should be allowed, False otherwise
        """
        direction, confidence = self.get_macro_bias(symbol)
        
        # No bias or low confidence - allow all trades
        if direction is None or confidence < CONFIDENCE_THRESHOLD_DEACTIVATE:
            return True
            
        # High confidence - only allow trades in same direction
        if confidence >= CONFIDENCE_THRESHOLD_ACTIVATE:
            return direction == proposed_direction
            
        # In hysteresis zone - allow all trades
        return True
        
    def check_position_conflict(self, symbol: str) -> Tuple[bool, float]:
        """
        Check for position conflicts with SWING trades.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Tuple of (has_conflict, size_multiplier)
        """
        if not hasattr(self, 'table'):
            return False, 1.0
            
        row_key = f"position:{symbol}"
        row = self.table.read_row(row_key)
        
        if not row:
            return False, 1.0
            
        position_type = row.cells[b'position'][b'type'][0].value.decode()
        
        # If SWING position exists, reduce size
        if position_type == 'SWING':
            return True, 0.5
            
        return False, 1.0 