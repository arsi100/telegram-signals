#!/usr/bin/env python3
"""
Local pipeline testing script for CryptoSignalTracker.
Mocks external dependencies like API calls and Firestore.
"""

import os
import sys
import logging
import time
import pandas as pd
from unittest import mock
from datetime import datetime, timezone

# Ensure the 'functions' directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
functions_dir = os.path.join(script_dir, 'functions')
if functions_dir not in sys.path:
    sys.path.insert(0, functions_dir)

# Now import from 'functions'
try:
    from functions.signal_generator import process_crypto_data
    from functions import config
    # Import for mocking
    from functions.sentiment_analysis import LunarCrushAPI
    from functions.position_manager import is_in_cooldown_period, get_open_position, record_signal_ts
except ImportError as e:
    print(f"Error importing modules: {e}. Make sure functions_dir is correct: {functions_dir}")
    sys.exit(1)

# --- Logging Setup ---
def setup_test_logging():
    """Sets up logging for the test script."""
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format, stream=sys.stdout)
    # Silence some overly verbose loggers if necessary
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Mock Data Generation ---
def generate_mock_ohlcv_data(symbol: str, num_points: int = 200) -> list:
    """Generates mock OHLCV data for a given symbol."""
    data = []
    base_price = 70000  # Starting price for BTC example
    current_time_sec = int(time.time())
    for i in range(num_points):
        timestamp = current_time_sec - (num_points - 1 - i) * 300  # 5-min intervals
        open_price = base_price + (i * 10) + ((-1)**i * 50) # Some variation
        close_price = open_price + ((-1)**(i+1) * 20) + (i*5)
        high_price = max(open_price, close_price) + 10
        low_price = min(open_price, close_price) - 10
        volume = 10 + (i % 10) + ((-1)**i * 3)
        
        data.append({
            "symbol": symbol, # Adding symbol to each kline dict
            "timestamp": timestamp,
            "open": str(open_price),
            "high": str(high_price),
            "low": str(low_price),
            "close": str(close_price),
            "volume": str(volume),
            "trades": str(100 + i) # Dummy trade count
        })
        base_price = close_price # Next candle opens near last close
    logger.debug(f"Generated {len(data)} mock OHLCV data points for {symbol}. Last point: {data[-1]}")
    return data

def mock_lunarcrush_get_coin_metrics(self, symbol: str):
    """Mocks the LunarCrushAPI.get_coin_metrics method."""
    logger.info(f"[MOCK] LunarCrushAPI.get_coin_metrics called for {symbol}")
    if symbol == "bitcoin": # LunarCrush uses lowercase coin names
        return {
            'average_sentiment_score': 4.5, # Bullish
            'social_impact_score': 4.0,
            'galaxy_score': 75.0,
            'social_volume': 1000.0,
            'social_volume_change_24h': 2.0, # > 1.5 threshold
            'timestamp': int(time.time())
        }
    elif symbol == "ethereum":
         return {
            'average_sentiment_score': 1.5, # Bearish
            'social_impact_score': 2.0,
            'galaxy_score': 40.0,
            'social_volume': 500.0,
            'social_volume_change_24h': 0.5,
            'timestamp': int(time.time())
        }
    else: # Default neutral
        return {
            'average_sentiment_score': 3.0,
            'social_impact_score': 3.0,
            'galaxy_score': 50.0,
            'social_volume': 100.0,
            'social_volume_change_24h': 1.0,
            'timestamp': int(time.time())
        }

# --- Mock Firestore Interactions ---
# Using a simple dictionary for a fake DB in this test
mock_db_store = {}

def mock_is_in_cooldown_period(symbol: str, db_mock, cooldown_minutes: int) -> bool:
    logger.info(f"[MOCK] is_in_cooldown_period called for {symbol}.")
    key = f"cooldown__{symbol}"
    if key in mock_db_store:
        last_signal_time = mock_db_store[key]
        if (datetime.now(timezone.utc) - last_signal_time).total_seconds() / 60 < cooldown_minutes:
            logger.info(f"[MOCK] {symbol} is in cooldown (mock).")
            return True
    return False

def mock_get_open_position(symbol: str, db_mock):
    logger.info(f"[MOCK] get_open_position called for {symbol}.")
    key = f"position__{symbol}"
    return mock_db_store.get(key)

def mock_record_signal_ts(symbol: str, db_mock):
    logger.info(f"[MOCK] record_signal_ts called for {symbol}.")
    mock_db_store[f"cooldown__{symbol}"] = datetime.now(timezone.utc)
    return True

def main():
    setup_test_logging()
    logger.info("🚀 Starting local pipeline test for CryptoSignalTracker 🚀")

    test_symbol_btc = "PF_XBTUSD" 
    test_symbol_eth = "PF_ETHUSD"
    
    mock_kline_data_btc = generate_mock_ohlcv_data(test_symbol_btc)
    mock_kline_data_eth = generate_mock_ohlcv_data(test_symbol_eth)

    db_mock = "firestore_mock_object" 

    # Corrected with mock.patch block - paths adjusted to where functions are looked up
    with mock.patch.object(LunarCrushAPI, 'get_coin_metrics', new=mock_lunarcrush_get_coin_metrics), \
         mock.patch('functions.signal_generator.is_in_cooldown_period', new=mock_is_in_cooldown_period), \
         mock.patch('functions.signal_generator.get_open_position', new=mock_get_open_position), \
         mock.patch('functions.signal_generator.record_signal_ts', new=mock_record_signal_ts):

        logger.info(f"--- Processing {test_symbol_btc} ---")
        # Set a specific known "open position" for BTC to test exit/avg logic if desired
        # mock_db_store[f"position__{test_symbol_btc}"] = {
        #     "type": "LONG", "entry_price": 68000, "ref_path": "mock/path", "avg_down_count": 0
        # }
        btc_signal = process_crypto_data(test_symbol_btc, mock_kline_data_btc, db_mock)
        if btc_signal:
            logger.info(f"🔥 Signal for {test_symbol_btc}: {btc_signal}")
        else:
            logger.info(f"💨 No signal for {test_symbol_btc}.")
        # Clear specific mock state if needed for next run
        # if f"position__{test_symbol_btc}" in mock_db_store: del mock_db_store[f"position__{test_symbol_btc}"]
        # if f"cooldown__{test_symbol_btc}" in mock_db_store: del mock_db_store[f"cooldown__{test_symbol_btc}"]

        logger.info(f"--- Processing {test_symbol_eth} ---")
        eth_signal = process_crypto_data(test_symbol_eth, mock_kline_data_eth, db_mock)
        if eth_signal:
            logger.info(f"🔥 Signal for {test_symbol_eth}: {eth_signal}")
        else:
            logger.info(f"💨 No signal for {test_symbol_eth}.")
            
    logger.info("Local pipeline test finished.")

if __name__ == "__main__":
    main() 