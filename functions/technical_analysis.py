import logging
import numpy as np
import pandas as pd
import pandas_ta as ta
import os # Keep for config if it uses it, but remove local log dir creation
import sys # Added for sys.stdout

# Use relative import for config
from . import config # Import config to access parameters

# Configure logging for Cloud Functions (stdout)
logger = logging.getLogger(__name__)
# Assume configured_to_stdout is False initially
configured_to_stdout = False
if logger.hasHandlers():
    # Ensure handlers list is not empty before accessing its first element
    if logger.handlers: # Check if the list is not empty
        if isinstance(logger.handlers[0], logging.StreamHandler) and logger.handlers[0].stream == sys.stdout:
            configured_to_stdout = True

if not configured_to_stdout:
    # Remove any existing handlers to avoid duplicate logs if re-run or if other handlers exist
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    # Set level from config, default to INFO
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Create a stream handler to log to stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    formatter = logging.Formatter(log_format)
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(stream_handler)
    logger.setLevel(log_level)
    # Propagate to root logger to ensure output if other loggers are used by libraries
    # but set our logger to not propagate if we want to control its output exclusively.
    # For now, let's allow propagation.
    # logger.propagate = False 

def _ensure_dataframe(kline_data_list): # Renamed arg for clarity, expects list of dicts
    """Converts kline_data (list of dicts) to a Pandas DataFrame and ensures numeric types."""
    if not isinstance(kline_data_list, list):
        # If it's already a DataFrame, this function was called incorrectly after initial conversion.
        # However, to be robust for now, let's handle it, but log a warning.
        if isinstance(kline_data_list, pd.DataFrame):
            logger.warning("_ensure_dataframe received an already processed DataFrame. This is unexpected.")
            df = kline_data_list.copy()
        else:
            logger.error(f"_ensure_dataframe expects a list of dicts, got {type(kline_data_list)}")
            raise ValueError(f"Invalid input type for _ensure_dataframe: {type(kline_data_list)}")
    else:
        df = pd.DataFrame(kline_data_list)

    if df.empty:
        logger.warning("_ensure_dataframe: Input kline_data resulted in an empty DataFrame.")
        # Return empty df, subsequent checks for len(df) will handle it.
        return df 

    expected_columns = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
    # Check based on the raw kline_data structure from kraken_api.py
    if not expected_columns.issubset(df.columns):
        logger.error(f"DataFrame is missing one or more required OHLCV columns. Columns: {df.columns.tolist()}")
        raise ValueError(f"DataFrame columns do not match expected OHLCV format from Kraken API: {df.columns.tolist()}")

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
            
    if 'timestamp' in df.columns:
        try:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            # Set index AFTER potential NaNs in OHLCV are dropped, to keep consistent length
            # df = df.set_index(pd.DatetimeIndex(df['timestamp']), drop=False) 
        except Exception as e:
            logger.warning(f"Could not convert 'timestamp' to datetime objects: {e}")
            
    df.dropna(subset=['open', 'high', 'low', 'close', 'volume'], inplace=True)
    
    # Set index after dropna to ensure index matches the final data length
    if 'timestamp' in df.columns and pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        try:
            df = df.set_index(pd.DatetimeIndex(df['timestamp']), drop=False)
        except Exception as e:
             logger.warning(f"Could not set DatetimeIndex post-dropna: {e}")

    return df

def calculate_rsi(df: pd.DataFrame, return_all=False):
    """Calculate Relative Strength Index (RSI) using pandas-ta."""
    try:
        if df.empty or len(df) <= config.RSI_PERIOD:
            logger.warning(f"Not enough data points ({len(df)}) to calculate RSI with period {config.RSI_PERIOD}")
            return np.array([]) if return_all else 50.0

        rsi_series = df.ta.rsi(length=config.RSI_PERIOD)
        
        if rsi_series is None or rsi_series.empty:
            logger.warning("RSI calculation returned None or empty series.")
            return np.array([]) if return_all else 50.0

        if return_all:
            return rsi_series.to_numpy()
        else:
            latest_rsi = rsi_series.iloc[-1] if not pd.isna(rsi_series.iloc[-1]) else 50.0
            return latest_rsi
        
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}", exc_info=True)
        return np.array([]) if return_all else 50.0

def calculate_ema(df: pd.DataFrame, return_all=False):
    """Calculate Exponential Moving Average (EMA) using pandas-ta."""
    try:
        if df.empty or len(df) < config.EMA_PERIOD:
            logger.warning(f"Not enough data points ({len(df)}) to calculate EMA with period {config.EMA_PERIOD}")
            return np.array([]) if return_all else (df['close'].iloc[-1] if not df.empty else None)
            
        ema_series = df.ta.ema(length=config.EMA_PERIOD)

        if ema_series is None or ema_series.empty:
            logger.warning("EMA calculation returned None or empty series.")
            return np.array([]) if return_all else (df['close'].iloc[-1] if not df.empty else None)

        if return_all:
            return ema_series.to_numpy()
        else:
            latest_ema = ema_series.iloc[-1] if not pd.isna(ema_series.iloc[-1]) else (df['close'].iloc[-1] if not df.empty else None)
            return latest_ema
        
    except Exception as e:
        logger.error(f"Error calculating EMA: {e}", exc_info=True)
        last_close = df['close'].iloc[-1] if not df.empty and 'close' in df.columns else None
        return np.array([]) if return_all else last_close

def calculate_sma(df: pd.DataFrame, return_all=False):
    """Calculate Simple Moving Average (SMA) using pandas-ta."""
    try:
        if df.empty or len(df) < config.SMA_PERIOD:
            logger.warning(f"Not enough data points ({len(df)}) to calculate SMA with period {config.SMA_PERIOD}")
            return np.array([]) if return_all else (df['close'].iloc[-1] if not df.empty else None)
            
        sma_series = df.ta.sma(length=config.SMA_PERIOD)

        if sma_series is None or sma_series.empty:
            logger.warning("SMA calculation returned None or empty series.")
            return np.array([]) if return_all else (df['close'].iloc[-1] if not df.empty else None)

        if return_all:
            return sma_series.to_numpy()
        else:
            latest_sma = sma_series.iloc[-1] if not pd.isna(sma_series.iloc[-1]) else (df['close'].iloc[-1] if not df.empty else None)
            return latest_sma
        
    except Exception as e:
        logger.error(f"Error calculating SMA: {e}", exc_info=True)
        last_close = df['close'].iloc[-1] if not df.empty and 'close' in df.columns else None
        return np.array([]) if return_all else last_close

def analyze_volume_advanced(df: pd.DataFrame, return_all=False):
    """
    Advanced volume analysis based on institutional trading research.
    Implements multi-tier volume classification and order flow detection.
    Adds EWMA of volume, EWMA of price range (volatility), and their correlation.
    """
    try:
        default_result_latest = {
                'current_volume': 0.0,
                'avg_volume': 0.0, # Typically 20-period SMA of volume
                'volume_ratio': 0.0, # current_volume / avg_volume
                'volume_tier': 'UNKNOWN',
                'volume_momentum': 0.0,
                'volume_profile_strength': 0.0, # Original price-volume correlation
                'early_trend_signal': False,
                'late_entry_warning': False,
                'institutional_activity': False,
                'volume_ewma': 0.0,
                'price_range_ewma': 0.0,
                'vol_volatility_correlation': 0.0
            }
            
        if df.empty or 'volume' not in df.columns or 'high' not in df.columns or 'low' not in df.columns:
            logger.warning("analyze_volume_advanced: Missing volume, high, or low data.")
            return default_result_latest

        # Calculate various volume metrics
        current_volume = float(df['volume'].iloc[-1])
        
        # Multi-period volume averages (institutional approach)
        volume_10_sma = df['volume'].rolling(window=10, min_periods=1).mean().iloc[-1] # For tier reference
        volume_5 = df['volume'].tail(5).mean()
        volume_20 = df['volume'].tail(20).mean() 
        volume_50 = df['volume'].tail(50).mean() if len(df) >= 50 else df['volume'].mean()
        volume_200 = df['volume'].tail(200).mean() if len(df) >= 200 else df['volume'].mean()
        
        avg_volume_for_ratio = volume_10_sma if volume_10_sma > 0 else (volume_20 if volume_20 > 0 else 1) # Use 10-period SMA for ratio

        # Volume ratios for different timeframes
        ratio_current = current_volume / avg_volume_for_ratio if avg_volume_for_ratio > 0 else 0
        ratio_short = volume_5 / volume_20 if volume_20 > 0 else 0
        ratio_medium = volume_20 / volume_50 if volume_50 > 0 else 0
        ratio_long = volume_50 / volume_200 if volume_200 > 0 else 0
        
        # Volume momentum (trend in volume)
        if len(df) >= 10:
            recent_vol_trend = np.polyfit(range(10), df['volume'].tail(10), 1)[0]
            volume_momentum = recent_vol_trend / volume_20 if volume_20 > 0 else 0
        else:
            volume_momentum = 0
            
        # Volume Profile Strength (original price-volume relationship)
        if len(df) >= 20:
            price_returns = df['close'].pct_change().tail(20)
            volume_changes = df['volume'].pct_change().tail(20)
            correlation = price_returns.corr(volume_changes)
            volume_profile_strength = abs(correlation) if not pd.isna(correlation) else 0
        else:
            volume_profile_strength = 0
            
        # EWMA calculations
        # alpha_ewma = 0.1 # Old hardcoded alpha
        # Use alpha derived from config periods for EWMAs
        alpha_vol_short = 2 / (config.VOLUME_EWMA_SHORT_PERIOD + 1) if config.VOLUME_EWMA_SHORT_PERIOD > 0 else 0.1 # Default to 0.1 if period is 0
        volume_ewma_series = df['volume'].ewm(alpha=alpha_vol_short, adjust=False).mean()
        latest_volume_ewma = volume_ewma_series.iloc[-1]

        df['price_range'] = df['high'] - df['low']
        alpha_price_range = 2 / (config.PRICE_RANGE_EWMA_PERIOD + 1) if config.PRICE_RANGE_EWMA_PERIOD > 0 else 0.1 # Default to 0.1 if period is 0
        price_range_ewma_series = df['price_range'].ewm(alpha=alpha_price_range, adjust=False).mean()
        latest_price_range_ewma = price_range_ewma_series.iloc[-1]

        vol_volatility_correlation = 0.0
        if len(df) >= 20: # Need enough data for correlation
            # Ensure series have the same index for correlation
            corr_df = pd.DataFrame({
                'vol_ewma': volume_ewma_series.tail(20),
                'pr_ewma': price_range_ewma_series.tail(20)
            })
            # Only calculate correlation if both series have non-zero variance
            if corr_df['vol_ewma'].var() > 1e-6 and corr_df['pr_ewma'].var() > 1e-6:
                 vol_volatility_correlation = corr_df['vol_ewma'].corr(corr_df['pr_ewma'])
                 if pd.isna(vol_volatility_correlation): vol_volatility_correlation = 0.0
            else:
                vol_volatility_correlation = 0.0 # or some other default if variance is zero


        # Tier Classification (Refined based on current_volume / 10-period SMA of volume)
        # Uses config.VOLUME_TIER_THRESHOLDS
        volume_tier = 'UNKNOWN' # Default if no tier matches
        # Sort tiers by threshold value in descending order to find the highest matching tier
        sorted_tiers = sorted(config.VOLUME_TIER_THRESHOLDS.items(), key=lambda item: item[1], reverse=True)
        
        for tier_name, threshold in sorted_tiers:
            if ratio_current >= threshold: # ratio_current is current_volume / avg_volume_for_ratio (10-period SMA)
                volume_tier = tier_name
                break # Found the highest applicable tier
        
        # If ratio_current is below the lowest defined threshold (e.g. VERY_LOW at 0.0), it might remain UNKNOWN
        # or fall into the lowest category depending on threshold values.
        # Ensuring VERY_LOW is explicitly handled if ratio_current is very small.
        if volume_tier == 'UNKNOWN' and ratio_current < config.VOLUME_TIER_THRESHOLDS.get('LOW', 0.5): # Example fallback
             if ratio_current <= config.VOLUME_TIER_THRESHOLDS.get('VERY_LOW', 0.0) and 'VERY_LOW' in config.VOLUME_TIER_THRESHOLDS:
                 volume_tier = 'VERY_LOW'
             # else it remains UNKNOWN or could be assigned to LOW if thresholds are structured that way

        # Early trend and late entry warnings (Example logic, can be refined)
        early_trend_signal = False
        late_entry_warning = False
        
        # Institutional Activity Detection - adjust criteria if needed
        institutional_activity = (
            ratio_current > 1.2 and 
            volume_profile_strength > 0.4 and
            current_volume > volume_200 * 1.5  # Significant vs long-term average
        )
        
        # Late Entry Warning - adjust criteria if needed
        late_entry_warning = (
            ratio_current > 1.8 or # Corresponds to HIGH/EXTREME
            (ratio_current > 1.5 and volume_momentum < 0)  # High volume but declining
        )
        
        result = {
            'current_volume': current_volume,
            'avg_volume': avg_volume_for_ratio, # Changed to reflect the base for ratio_current
            'volume_ratio': ratio_current,
            'volume_tier': volume_tier,
            'volume_momentum': volume_momentum,
            'volume_profile_strength': volume_profile_strength,
            'early_trend_signal': early_trend_signal,
            'late_entry_warning': late_entry_warning,
            'institutional_activity': institutional_activity,
            'ratio_short': ratio_short,
            'ratio_medium': ratio_medium,
            'ratio_long': ratio_long,
            'volume_ewma': latest_volume_ewma,
            'price_range_ewma': latest_price_range_ewma,
            'vol_volatility_correlation': vol_volatility_correlation
        }

        if return_all:
            # For backtesting - return series data, including new EWMAs
            # Note: This part might need more fleshing out if full series are needed for all new metrics
            return {
                'volume_ratio_series': (df['volume'] / df['volume'].rolling(10, min_periods=1).mean()).fillna(0), # Based on 10-period SMA
                'volume_momentum_series': df['volume'].rolling(10).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == 10 else 0),
                'volume_ewma_series': volume_ewma_series,
                'price_range_ewma_series': price_range_ewma_series,
                # Placeholder for correlation series if needed for backtesting
                # 'vol_volatility_correlation_series': df['volume_ewma_series'].rolling(20).corr(df['price_range_ewma_series']),
                'latest_result': result
            }
        else:
            return result
        
    except Exception as e:
        logger.error(f"Error in advanced volume analysis: {e}", exc_info=True)
        return default_result_latest

# Update the existing analyze_volume function to use the new advanced version
def analyze_volume(df: pd.DataFrame, return_all=False):
    """Enhanced volume analysis with institutional-grade metrics"""
    return analyze_volume_advanced(df, return_all)

def detect_candlestick_patterns(df: pd.DataFrame, ema_series: pd.Series = None, volume_analysis: dict = None) -> dict:
    """
    Detects various candlestick patterns using pandas_ta and custom logic.
    Prioritizes the latest confirmed pattern.
    Adds fallback for raw patterns if no confirmed pattern is found on the latest candle.
    """
    # Initialize results
    pattern_summary = {"pattern_name": "N/A", "pattern_type": "neutral", "pattern_detected_raw": False, "latest_confirmed_signal": {}}

    if df.empty or len(df) < 3: # Need at least a few candles for pattern context
        logger.warning("DataFrame too short for candlestick pattern detection.")
        return pattern_summary

    # Use a copy to avoid SettingWithCopyWarning
    df_patterns = df.copy()

    # Define patterns to check - focus on a few key ones for clarity
    # We expect columns like 'CDL_HAMMER_Bull', 'CDL_DOJI_Neutral', etc.
    # The simple name 'hammer' gives raw signals (100 for bullish, -100 for bearish)
    # The specific TA-Lib names (e.g., CDLHAMMER) might also create boolean columns.
    
    # pandas-ta recommends running all patterns if specific ones are not needed.
    # Or, specify a list of names. Let's try specific common ones for clarity.
    patterns_to_check_talib = [
        "hammer", "hangingman", "invertedhammer", "shootingstar",
        "doji", "dojistar",
        "morningstar", "eveningstar",
        "morningdojistar", "eveningdojistar",
        "engulfing", "dragonflydoji", "gravestonedoji",
        # "abandonedbaby", # Often too rare or requires very specific conditions
        # "harami", "haramicross" # Also can be less distinct
    ]
    
    try:
        # Calculate all specified TA-Lib patterns recognized by pandas-ta
        # This will add columns like CDLHAMMER, CDLDOJI, CDLENGULFING etc.
        # It also adds raw signal columns like 'hammer_signal' (100/-100) if using simplified names.
        # Let's use simplified names to get raw signals easily for our fallback.
        # And also try to get the standard TA-Lib boolean columns.
        
        # Get raw signals (e.g., 'hammer' column with 100/-100)
        df_patterns.ta.cdl_pattern(name="all", append=True) # This adds many columns

        # Standard TA-Lib boolean columns might be named like 'CDLHAMMER', 'CDLENGULFING'
        # We need to check how pandas-ta names these when 'name=\"all\"' is used.
        # It often uses names like 'CDL_DOJI_NEUTRAL', 'CDL_HAMMER_BULL', 'CDL_ENGULFING_BULL'

    except Exception as e:
        logger.error(f"Error calculating candlestick patterns with pandas_ta: {e}")
        return pattern_summary

    latest_confirmed_signal = {"pattern_name": "N/A", "pattern_type": "neutral", "pattern_detected": False, "candle_index": -1}
    
    # --- Prioritize Confirmed Patterns on the LATEST candle ---
    # Check for specific pandas-ta generated boolean columns for the latest candle
    # These columns often have _Bull, _Bear, _Neutral suffixes
    # Example: df_patterns['CDL_HAMMER_BULL'].iloc[-1]
    
    # List of pattern types and their corresponding pandas-ta column suffixes
    # This mapping might need adjustment based on exact pandas-ta output for cdl_pattern(name="all")
    confirmed_pattern_map = {
        "Hammer": {"col_suffix": "_HAMMER_BULL", "type": "bullish"},
        "Inverted Hammer": {"col_suffix": "_INVERTEDHAMMER_BULL", "type": "bullish"},
        "Morning Star": {"col_suffix": "_MORNINGSTAR_BULL", "type": "bullish"},
        "Morning Doji Star": {"col_suffix": "_MORNINGDOJISTAR_BULL", "type": "bullish"},
        "Bullish Engulfing": {"col_suffix": "_ENGULFING_BULL", "type": "bullish"},
        "Dragonfly Doji": {"col_suffix": "_DRAGONFLYDOJI_BULL", "type": "bullish"}, # Usually bullish

        "Hanging Man": {"col_suffix": "_HANGINGMAN_BEAR", "type": "bearish"},
        "Shooting Star": {"col_suffix": "_SHOOTINGSTAR_BEAR", "type": "bearish"},
        "Evening Star": {"col_suffix": "_EVENINGSTAR_BEAR", "type": "bearish"},
        "Evening Doji Star": {"col_suffix": "_EVENINGDOJISTAR_BEAR", "type": "bearish"},
        "Bearish Engulfing": {"col_suffix": "_ENGULFING_BEAR", "type": "bearish"},
        "Gravestone Doji": {"col_suffix": "_GRAVESTONEDOJI_BEAR", "type": "bearish"}, # Usually bearish

        "Doji": {"col_suffix": "_DOJI_NEUTRAL", "type": "neutral"},
        # Add more confirmed patterns if needed
    }

    for p_name, p_info in confirmed_pattern_map.items():
        col_name_prefix = "CDL" # Default prefix
        # Check if the full column name exists, e.g., CDL_HAMMER_BULL
        full_col_name = f"{col_name_prefix}{p_info['col_suffix']}"
        if full_col_name in df_patterns.columns:
            if df_patterns[full_col_name].iloc[-1]: # Check if True (or > 0)
                latest_confirmed_signal["pattern_name"] = p_name
                latest_confirmed_signal["pattern_type"] = p_info["type"]
                latest_confirmed_signal["pattern_detected"] = True
                latest_confirmed_signal["candle_index"] = -1
                logger.debug(f"Latest candle CONFIRMED pattern: {p_name} ({p_info['type']})")
                break # Found a confirmed pattern on the latest candle

    pattern_summary["latest_confirmed_signal"] = latest_confirmed_signal
    pattern_summary["pattern_name"] = latest_confirmed_signal["pattern_name"]
    pattern_summary["pattern_type"] = latest_confirmed_signal["pattern_type"]
    # pattern_detected_raw will be set by the raw check if no confirmed pattern

    # --- Fallback: Check for RAW patterns in the last 3 candles if NO confirmed pattern on LATEST candle ---
    if not latest_confirmed_signal["pattern_detected"]:
        logger.debug("No CONFIRMED pattern on latest candle. Checking for RAW patterns in last 3 candles.")
        # Check for raw 'hammer' signal (100 for bullish, -100 for bearish)
        # The column name from df.ta.cdl_pattern(name='all') for raw hammer is 'CDL_HAMMER'
        # Or if we did df.ta.cdl_pattern(name='hammer'), it would be 'CDLHAMMER'.
        # Let's assume 'CDL_HAMMER' exists from 'all'
        
        raw_hammer_col = 'CDL_HAMMER' # This is what pandas-ta creates with name="all" for the raw hammer signal
        if raw_hammer_col in df_patterns.columns:
            for i in range(-1, -4, -1): # Check last 3 candles (index -1, -2, -3)
                if len(df_patterns) < abs(i): # Ensure we don't go out of bounds on short DFs
                    continue
                
                raw_signal_value = df_patterns[raw_hammer_col].iloc[i]
                if raw_signal_value == 100: # Bullish Hammer
                    pattern_summary["pattern_name"] = f"Raw Hammer ({abs(i)})"
                    pattern_summary["pattern_type"] = "bullish"
                    pattern_summary["pattern_detected_raw"] = True
                    logger.info(f"Found RAW Bullish Hammer on candle index {i} (from latest).")
                    break 
                elif raw_signal_value == -100: # Bearish Hammer (though Hanging Man is more common for this signal)
                    # We could map this to Hanging Man if contextually appropriate, or just "Raw Bearish Hammer"
                    pattern_summary["pattern_name"] = f"Raw Bearish Hammer ({abs(i)})" 
                    pattern_summary["pattern_type"] = "bearish" # Or map to Hanging Man
                    pattern_summary["pattern_detected_raw"] = True
                    logger.info(f"Found RAW Bearish Hammer signal on candle index {i} (from latest).")
                    break
            if pattern_summary["pattern_detected_raw"]:
                 logger.debug(f"Using RAW pattern after Hammer check: {pattern_summary['pattern_name']}")
        else:
            logger.warning(f"Raw hammer column '{raw_hammer_col}' not found after cdl_pattern(name='all').")
        
        # Add similar raw checks for Engulfing patterns if no Hammer was found yet
        if not pattern_summary["pattern_detected_raw"]:
            raw_engulfing_bull_col = 'CDL_ENGULFING_BULL' # pandas-ta name for confirmed Bullish Engulfing
            raw_engulfing_bear_col = 'CDL_ENGULFING_BEAR' # pandas-ta name for confirmed Bearish Engulfing
            # Note: pandas-ta might not have 'raw' unconfirmed engulfing signals directly in 'all'.
            # The 'CDLENGULFING' gives a general signal (-100 for bear, 100 for bull, 0 for none).
            # We'll use the general 'CDLENGULFING' as it's more likely to be present from cdl_pattern(name='all')
            # and represents the pattern occurrence.
            
            general_engulfing_col = 'CDLENGULFING' 
            if general_engulfing_col in df_patterns.columns:
                for i in range(-1, -4, -1): # Check last 3 candles
                    if len(df_patterns) < abs(i):
                        continue
                    raw_signal_value = df_patterns[general_engulfing_col].iloc[i]
                    if raw_signal_value == 100: # Bullish Engulfing
                        pattern_summary["pattern_name"] = f"Raw Bullish Engulfing ({abs(i)})"
                        pattern_summary["pattern_type"] = "bullish"
                        pattern_summary["pattern_detected_raw"] = True
                        logger.info(f"Found RAW Bullish Engulfing on candle index {i} (from latest).")
                        break
                    elif raw_signal_value == -100: # Bearish Engulfing
                        pattern_summary["pattern_name"] = f"Raw Bearish Engulfing ({abs(i)})"
                        pattern_summary["pattern_type"] = "bearish"
                        pattern_summary["pattern_detected_raw"] = True
                        logger.info(f"Found RAW Bearish Engulfing on candle index {i} (from latest).")
                        break
                if pattern_summary["pattern_detected_raw"]:
                    logger.debug(f"Using RAW pattern after Engulfing check: {pattern_summary['pattern_name']}")
            else:
                logger.warning(f"Raw engulfing column '{general_engulfing_col}' not found after cdl_pattern(name='all').")

        # TODO: Add similar raw checks for other key patterns (e.g., Doji) if needed,
        # by inspecting the columns created by cdl_pattern(name='all').
        # For Engulfing, it creates CDL_ENGULFING_BULL / CDL_ENGULFING_BEAR etc.
        # For Doji, it creates CDL_DOJI_NEUTRAL. These are already handled by confirmed check.
        # Raw signals are useful when the TA-Lib confirmed columns are too strict.


    # Log final pattern decision for this function call
    if pattern_summary["pattern_name"] != "N/A":
        log_msg = f"detect_candlestick_patterns result: Name='{pattern_summary['pattern_name']}', Type='{pattern_summary['pattern_type']}'"
        if pattern_summary.get("pattern_detected_raw"):
            log_msg += " (Raw Detection)"
        elif latest_confirmed_signal.get("pattern_detected"):
            log_msg += " (Confirmed Latest)"
        logger.info(log_msg)
    else:
        logger.debug("detect_candlestick_patterns: No significant pattern detected.")

    return pattern_summary

def calculate_atr(df: pd.DataFrame, return_all=False):
    """Calculate Average True Range (ATR) using pandas-ta for volatility filtering."""
    try:
        if df.empty or len(df) < config.ATR_PERIOD:
            logger.warning(f"Not enough data points ({len(df)}) to calculate ATR with period {config.ATR_PERIOD}")
            return np.array([]) if return_all else 0.0
            
        atr_series = df.ta.atr(length=config.ATR_PERIOD)

        if atr_series is None or atr_series.empty:
            logger.warning("ATR calculation returned None or empty series.")
            return np.array([]) if return_all else 0.0

        if return_all:
            return atr_series.to_numpy()
        else:
            latest_atr = atr_series.iloc[-1] if not pd.isna(atr_series.iloc[-1]) else 0.0
            return latest_atr
        
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}", exc_info=True)
        return np.array([]) if return_all else 0.0

def check_atr_filter(df: pd.DataFrame):
    """Check if current ATR is above 1.5x 20-period average for volatility filtering."""
    try:
        if df.empty or len(df) < config.ATR_PERIOD + 20:
            return False
            
        atr_series = df.ta.atr(length=config.ATR_PERIOD)
        if atr_series is None or atr_series.empty:
            return False
            
        # Calculate 20-period average of ATR
        atr_avg_series = atr_series.rolling(window=20).mean()
        
        current_atr = atr_series.iloc[-1]
        avg_atr = atr_avg_series.iloc[-1]
        
        if pd.isna(current_atr) or pd.isna(avg_atr) or avg_atr == 0:
            return False
            
        atr_ratio = current_atr / avg_atr
        return atr_ratio > config.ATR_MULTIPLIER
        
    except Exception as e:
        logger.error(f"Error checking ATR filter: {e}", exc_info=True)
        return False

def analyze_technicals(kline_data_list, symbol=None, interval_str=None):
    """
    Analyzes kline data to extract technical indicators and patterns.
    Args:
        kline_data_list: List of lists/tuples or pandas DataFrame with kline data (timestamp, open, high, low, close, volume).
        symbol: The symbol being analyzed (optional, for logging/context).
        interval_str: The interval string (optional, for logging/context).

    Returns:
        A dictionary containing technical indicators and analysis results, or None if analysis fails.
    """
    if interval_str is None:
        interval_str = "N/A"
    if symbol is None:
        current_symbol_log = "N/A"
    else:
        current_symbol_log = symbol

    # Convert to DataFrame if it's not already (e.g. from Kraken API)
    if not isinstance(kline_data_list, pd.DataFrame):
        df = pd.DataFrame(kline_data_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    else:
        df = kline_data_list # It's already a DataFrame

    # Ensure DataFrame is not empty
    if df.empty:
        logger.warning(f"[{current_symbol_log}] Empty kline data received for technical analysis.")
        return None
    
    # Convert timestamp to datetime objects if they are not already (e.g. numeric timestamps)
    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    try:
        min_len_for_analysis = max(config.RSI_PERIOD, config.EMA_PERIOD, config.ATR_PERIOD, 20) + 5 # Updated to use EMA_PERIOD and include ATR_PERIOD
        if df.empty or len(df) < min_len_for_analysis:
            logger.warning(f"Insufficient data after processing in DataFrame ({len(df)} points) for full analysis. Need at least {min_len_for_analysis}.")
            return None
        logger.info(f"DataFrame for technical analysis has {len(df)} rows after initial processing.")

        rsi_latest = calculate_rsi(df) 
        ema_latest = calculate_ema(df)
        ema_series_all = calculate_ema(df, return_all=True)  # Changed from sma_series_all to ema_series_all
        atr_latest = calculate_atr(df)
        atr_filter_passed = check_atr_filter(df)
        volume_analysis_latest = analyze_volume_advanced(df)  # Use new advanced volume analysis
        volume_analysis_all = analyze_volume_advanced(df, return_all=True)

        # Log DataFrame summary instead of full rows
        if not df.empty:
            symbol_name = df['symbol'].iloc[-1] if 'symbol' in df.columns else 'N/A'
            latest_timestamp = df['timestamp'].iloc[-1] if 'timestamp' in df.columns else 'N/A'
            latest_close = df['close'].iloc[-1] if 'close' in df.columns else 'N/A'
            logger.info(f"DataFrame for pattern detection: {len(df)} rows, symbol: {symbol_name}, latest: {latest_timestamp} @ {latest_close}")
        else:
            logger.info("DataFrame for pattern detection is empty.")

        pattern_result = detect_candlestick_patterns(df, ema_series_all, volume_analysis_all)

        # Apply ATR filter to the raw pattern_result if FILTER_PATTERNS_BY_ATR is True
        if config.FILTER_PATTERNS_BY_ATR and pattern_result.get("pattern_detected_raw"):
            if atr_latest > 0: # Avoid division by zero
                # Ensure df is not empty and has high/low columns for the last candle
                if not df.empty and 'high' in df.columns and 'low' in df.columns and len(df) > 0:
                    candle_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                    if (candle_range / atr_latest) < config.ATR_FILTER_THRESHOLD:
                        logger.info(f"[{current_symbol_log}] Raw pattern '{pattern_result.get('pattern_name')}' filtered out by ATR. Range/ATR: {candle_range/atr_latest:.2f} < threshold {config.ATR_FILTER_THRESHOLD:.2f}")
                        pattern_result = {"pattern_name": "N/A (ATR Filtered)", "pattern_type": "neutral", "pattern_detected_raw": False}
                    else:
                        logger.info(f"[{current_symbol_log}] Raw pattern '{pattern_result.get('pattern_name')}' PASSED ATR filter. Range/ATR: {candle_range/atr_latest:.2f} >= threshold {config.ATR_FILTER_THRESHOLD:.2f}")
                else:
                    logger.warning(f"[{current_symbol_log}] Cannot apply ATR filter due to empty DataFrame or missing columns.")
            else:
                logger.warning(f"[{current_symbol_log}] ATR is 0 or invalid, cannot apply ATR filter to pattern '{pattern_result.get('pattern_name')}'.")
        elif not config.FILTER_PATTERNS_BY_ATR and pattern_result.get("pattern_detected_raw"):
            logger.info(f"[{current_symbol_log}] ATR filter for patterns is DISABLED. Using raw pattern: '{pattern_result.get('pattern_name')}'")


        latest_close_price = df['close'].iloc[-1] if not df.empty and 'close' in df.columns else 0.0
        
        technicals = {
            'latest_close': latest_close_price,
            'rsi': rsi_latest,
            'ema': ema_latest,
            'atr': atr_latest,
            'atr_filter': atr_filter_passed,
            'volume_analysis': volume_analysis_latest,
            'pattern': pattern_result
        }
        
        # Enhanced logging with new volume metrics
        vol_tier = volume_analysis_latest.get('volume_tier', 'UNKNOWN')
        vol_ratio = volume_analysis_latest.get('volume_ratio', 0)
        early_signal = volume_analysis_latest.get('early_trend_signal', False)
        late_warning = volume_analysis_latest.get('late_entry_warning', False)
        
        logger.info(f"Enhanced technicals for {latest_timestamp}: RSI={rsi_latest:.1f}, EMA={ema_latest:.2f}, ATR={atr_latest:.4f}")
        logger.info(f"Volume analysis: {vol_tier} ({vol_ratio:.2f}x), Early={early_signal}, Late_Warning={late_warning}")
        logger.info(f"Pattern: {pattern_result.get('pattern_name', 'N/A')}, ATR_filter={atr_filter_passed}")
        
        return technicals

    except ValueError as ve: 
        logger.error(f"ValueError in analyze_technicals (likely bad DataFrame setup): {ve}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"General error in analyze_technicals: {e}", exc_info=True)
        return None 
