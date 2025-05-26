import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os
from datetime import datetime, timezone
import logging # Add logging import

# Configure basic logging for tests to see output from modules
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Adjust sys.path to correctly locate the 'functions' package
# Get the absolute path of the project root directory (parent of 'tests')
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root) # Add project root to sys.path

# Now import the modules using absolute paths from the project root
from functions.signal_generator import process_crypto_data
from functions import config # Import the entire config module
from google.cloud import firestore

class TestLocalSignalGeneration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Config is loaded when 'from functions import config' is executed.
        # We can print values here to confirm they are as expected for a test environment.
        # Ensure your .env file or environment sets MODE=TEST for testing if defaults aren't sufficient.
        print(f"setUpClass: MODE from config: {config.MODE}")
        print(f"setUpClass: MIN_CONFIDENCE_ENTRY loaded as: {config.MIN_CONFIDENCE_ENTRY}")
        print(f"setUpClass: PROFIT_TARGET_PERCENTAGE loaded as: {config.PROFIT_TARGET_PERCENT}")
        print(f"setUpClass: LOSS_TARGET_PERCENTAGE loaded as: {config.LOSS_TARGET_PERCENT}")
        print(f"setUpClass: ENABLE_GEMINI_ANALYSIS set to: {config.ENABLE_GEMINI_ANALYSIS}")

    def create_mock_market_data(self, current_price=100):
        """Creates a mock DataFrame similar to what Kraken API would return."""
        data = {
            'timestamp': pd.to_datetime(['2023-01-01 10:00:00+00:00', '2023-01-01 10:05:00+00:00']),
            'open': [current_price * 0.99, current_price],
            'high': [current_price * 1.01, current_price * 1.02],
            'low': [current_price * 0.98, current_price * 0.99],
            'close': [current_price, current_price * 1.01],
            'volume': [1000, 1200]
        }
        df = pd.DataFrame(data)
        df['time'] = df['timestamp'] 
        return df

    @patch('functions.signal_generator.get_sentiment_score')
    @patch('functions.signal_generator.get_gemini_analysis')
    @patch('functions.signal_generator.get_open_position')
    @patch('functions.signal_generator.is_in_cooldown_period')
    @patch('functions.signal_generator.analyze_technicals')
    def test_long_signal_very_low_volume_high_rsi_raw_hammer(
        self,
        mock_analyze_technicals,
        mock_is_in_cooldown_period,
        mock_get_open_position,
        mock_get_gemini_analysis,
        mock_get_sentiment_score
    ):
        print(f"Running: test_long_signal_very_low_volume_high_rsi_raw_hammer")
        with patch('functions.config.ENABLE_GEMINI_ANALYSIS', False), \
             patch('functions.config.MIN_CONFIDENCE_ENTRY', 20), \
             patch('functions.config.PROFIT_TARGET_PERCENT', 3.0), \
             patch('functions.config.LOSS_TARGET_PERCENT', 1.0):

            print(f"Inside test: MIN_CONFIDENCE_ENTRY: {config.MIN_CONFIDENCE_ENTRY}")
            print(f"Inside test: PROFIT_TARGET_PERCENTAGE: {config.PROFIT_TARGET_PERCENT}")
            print(f"Inside test: LOSS_TARGET_PERCENTAGE: {config.LOSS_TARGET_PERCENT}")
            print(f"Inside test: ENABLE_GEMINI_ANALYSIS: {config.ENABLE_GEMINI_ANALYSIS}")

            symbol = 'PF_TESTUSD' 
            current_price = 100.00 

            mock_analyze_technicals.return_value = {
                'rsi': 76.0,
                'ema_short': current_price * 0.99, 'ema_long': current_price * 0.98,
                'ema': current_price * 0.98, 
                'atr': 0.5, 'volume_ratio_to_mean': 0.15, 
                'pattern_name': 'Raw Hammer (L)',
                'pattern': { 
                    'pattern_name': 'Raw Hammer (L)', 'pattern_type': 'bullish', 'pattern_detected_raw': True,
                    'score': 5 
                },
                'primary_trend': 'UP', 'price_vs_ema_short': 'above', 'price_vs_ema_long': 'above',
                'latest_price': current_price, 'latest_timestamp': pd.Timestamp.now(tz='UTC'),
                'df_length': 200,
                'volume_analysis': {'volume_tier': 'VERY_LOW', 'volume_ratio': 0.15, 'late_entry_warning': False}
            }
            mock_is_in_cooldown_period.return_value = False 
            mock_get_open_position.return_value = None
            mock_get_sentiment_score.return_value = {
                'sentiment_score_raw': 0.6, 'source': 'mock', 'error': None,
                'sentiment_confidence_final_RULE_WEIGHTED': 0.1 
            }
            mock_get_gemini_analysis.return_value = {'signal_type': 'NEUTRAL', 'confidence': 0.3} 

            mock_db_client = MagicMock(spec=firestore.Client) 
            mock_kline_data = self.create_mock_market_data(current_price=current_price)

            result_signal = process_crypto_data(symbol, mock_kline_data, mock_db_client)

            self.assertIsNotNone(result_signal, "A signal should have been generated.")
            self.assertEqual(result_signal['symbol'], symbol)
            self.assertEqual(result_signal['signal_type'], 'LONG')
            self.assertGreaterEqual(result_signal['confidence_score'], config.MIN_CONFIDENCE_ENTRY, 
                                  f"Confidence score {result_signal['confidence_score']} should be >= {config.MIN_CONFIDENCE_ENTRY}")

            # Use the latest close from the mock_kline_data for expected TP/SL, same as signal_generator.py
            actual_latest_close = mock_kline_data['close'].iloc[-1]
            expected_tp = actual_latest_close * (1 + config.PROFIT_TARGET_PERCENT / 100)
            expected_sl = actual_latest_close * (1 - config.LOSS_TARGET_PERCENT / 100)

            self.assertIn('take_profit', result_signal)
            self.assertAlmostEqual(result_signal['take_profit'], expected_tp, places=2)
            self.assertIn('stop_loss', result_signal)
            self.assertAlmostEqual(result_signal['stop_loss'], expected_sl, places=2)

            print(f"Test {self.id()} PASSED. Signal: {result_signal['signal_type']} for {symbol} with TP: {result_signal['take_profit']}, SL: {result_signal['stop_loss']}, Confidence: {result_signal['confidence_score']}")

    @patch('functions.signal_generator.get_sentiment_score')
    @patch('functions.signal_generator.get_gemini_analysis')
    @patch('functions.signal_generator.get_open_position')
    @patch('functions.signal_generator.is_in_cooldown_period')
    @patch('functions.signal_generator.analyze_technicals')
    def test_no_signal_if_cooldown(
        self,
        mock_analyze_technicals,
        mock_is_in_cooldown_period,
        mock_get_open_position,
        mock_get_gemini_analysis,
        mock_get_sentiment_score
    ):
        with patch('functions.config.ENABLE_GEMINI_ANALYSIS', False):
            print(f"Running: test_no_signal_if_cooldown")
            symbol = 'PF_COOLUSD'
            current_price = 200.00

            mock_analyze_technicals.return_value = {
                'rsi': 76.0, 'ema_short': 198, 'ema_long': 197, 'atr': 1.0,
                'ema': 197, 
                'volume_ratio_to_mean': 1.2, 
                'pattern_name': 'Confirmed Bullish Engulfing (L)',
                'pattern': { 'pattern_name': 'Confirmed Bullish Engulfing (L)', 'pattern_type': 'bullish', 'score': 10},
                'primary_trend': 'UP', 'price_vs_ema_short': 'above', 'price_vs_ema_long': 'above',
                'latest_price': current_price,
                'latest_timestamp': pd.Timestamp.now(tz='UTC'), 'df_length': 200,
                'volume_analysis': {'volume_tier': 'NORMAL'}
            }
            mock_is_in_cooldown_period.return_value = True 
            mock_get_open_position.return_value = None
            mock_get_sentiment_score.return_value = {'sentiment_score_raw': 0.7, 'source': 'mock', 'error': None}
            mock_get_gemini_analysis.return_value = {'signal_type': 'NEUTRAL', 'confidence': 0.1}

            mock_db_client = MagicMock(spec=firestore.Client)
            mock_kline_data = self.create_mock_market_data(current_price=current_price)
            result_signal = process_crypto_data(symbol, mock_kline_data, mock_db_client)

            self.assertIsNone(result_signal, "No signal should be generated during cooldown.")
            print(f"Test {self.id()} PASSED. No signal as expected due to cooldown.")

    @patch('functions.signal_generator.get_sentiment_score')
    @patch('functions.signal_generator.get_gemini_analysis')
    @patch('functions.signal_generator.get_open_position')
    @patch('functions.signal_generator.is_in_cooldown_period')
    @patch('functions.signal_generator.analyze_technicals')
    def test_exit_signal_generation(
        self,
        mock_analyze_technicals,
        mock_is_in_cooldown_period,
        mock_get_open_position,
        mock_get_gemini_analysis,
        mock_get_sentiment_score
    ):
        with patch('functions.config.ENABLE_GEMINI_ANALYSIS', False), patch('functions.config.MIN_CONFIDENCE_EXIT', 15):
            print(f"Running: test_exit_signal_generation. MIN_CONFIDENCE_EXIT: {config.MIN_CONFIDENCE_EXIT}")
            symbol = 'PF_EXITLONG_USD'
            current_price = 250.00
            entry_price = 240.00

            mock_get_open_position.return_value = {
                'id': 'test_pos_id', 'symbol': symbol, 'type': 'LONG', 
                'entry_price': entry_price, 'timestamp': datetime.now(timezone.utc).isoformat()
            }
            mock_analyze_technicals.return_value = {
                'rsi': 30.0, 'ema_short': current_price * 1.01, 'ema_long': current_price * 1.02,
                'ema': current_price * 1.02, 
                'atr': 1.0, 'volume_ratio_to_mean': 0.9, 
                'pattern_name': 'Raw Bearish Engulfing (S)',
                'pattern': { 
                    'pattern_name': 'Raw Bearish Engulfing (S)', 'pattern_type': 'bearish', 'pattern_detected_raw': True,
                    'score': 6
                },
                'primary_trend': 'DOWN', 'price_vs_ema_short': 'below', 'price_vs_ema_long': 'below',
                'latest_price': current_price, 'latest_timestamp': pd.Timestamp.now(tz='UTC'),
                'df_length': 200,
                'volume_analysis': {'volume_tier': 'NORMAL'}
            }
            mock_is_in_cooldown_period.return_value = False
            mock_get_sentiment_score.return_value = {
                'sentiment_score_raw': 0.0,
                'source': 'mock', 
                'error': None,
                'sentiment_confidence_final_RULE_WEIGHTED': 0.05
            }
            mock_get_gemini_analysis.return_value = {'signal_type': 'NEUTRAL', 'confidence': 0.1}

            mock_db_client = MagicMock(spec=firestore.Client)
            mock_kline_data = self.create_mock_market_data(current_price=current_price)

            result_signal = process_crypto_data(symbol, mock_kline_data, mock_db_client)

            self.assertIsNotNone(result_signal, "An EXIT_LONG signal should have been generated.")
            self.assertEqual(result_signal['symbol'], symbol)
            self.assertEqual(result_signal['signal_type'], 'EXIT_LONG')
            self.assertGreaterEqual(result_signal['confidence_score'], config.MIN_CONFIDENCE_EXIT)
            self.assertIn('reason_for_exit', result_signal) 
            self.assertEqual(result_signal['reason_for_exit'], 'Rule-based exit criteria met.')

            print(f"Test {self.id()} PASSED. Signal: {result_signal['signal_type']} for {symbol} with Confidence: {result_signal['confidence_score']}")

if __name__ == '__main__':
    # Ensure logging is also configured if run directly
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_dir = os.path.dirname(__file__)
    log_dir = os.path.join(test_dir, 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
            print(f"Created logs directory: {log_dir}")
        except OSError as e:
            print(f"Error creating logs directory {log_dir}: {e}")

    unittest.main(verbosity=2) 