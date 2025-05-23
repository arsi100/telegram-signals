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
            
        # EWMA calculations (alpha=0.1)
        alpha_ewma = 0.1
        volume_ewma_series = df['volume'].ewm(alpha=alpha_ewma, adjust=False).mean()
        latest_volume_ewma = volume_ewma_series.iloc[-1]

        df['price_range'] = df['high'] - df['low']
        price_range_ewma_series = df['price_range'].ewm(alpha=alpha_ewma, adjust=False).mean()
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
        if ratio_current > 2.0: # EXTREME >2x
            volume_tier = 'EXTREME'
        elif ratio_current >= 1.5: # HIGH 1.5-2x
            volume_tier = 'HIGH'
        elif ratio_current >= 1.2: # ELEVATED 1.2-1.5x
            volume_tier = 'ELEVATED'
        elif ratio_current >= 0.8: # NORMAL 0.8-1.2x
            volume_tier = 'NORMAL'
        elif ratio_current >= 0.5: # LOW 0.5-0.8x
            volume_tier = 'LOW'
        else: # VERY_LOW <0.5x
            volume_tier = 'VERY_LOW'
            
        # Early Trend Detection (Quant Approach) - adjust criteria if needed
        early_trend_signal = (
            1.0 <= ratio_current <= 1.4 and  # Optimal volume range (consider adjusting based on new tiers)
            volume_momentum > 0 and           # Volume trending up
            ratio_short > 1.1 and            # Recent acceleration
            volume_profile_strength > 0.3    # Good price-volume correlation
        )
        
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

def detect_candlestick_patterns(df: pd.DataFrame, sma_series_all: np.ndarray, volume_analysis_all: dict, return_all=False):
    """Detects and confirms candlestick patterns using pandas-ta and custom logic."""
    pattern_details = {
        "hammer": {"name": "Hammer", "type": "bullish"},
        "shooting_star": {"name": "Shooting Star", "type": "bearish"},
        "bullish_engulfing": {"name": "Bullish Engulfing", "type": "bullish"},
        "bearish_engulfing": {"name": "Bearish Engulfing", "type": "bearish"},
        "morning_star": {"name": "Morning Star", "type": "bullish"},
        "evening_star": {"name": "Evening Star", "type": "bearish"}
    }
    default_result_latest = {
        "pattern_name": "N/A", "pattern_type": "neutral", "pattern_detected_raw": False
    }
    default_result_all_confirmed = {key: np.array([False] * len(df)) for key in pattern_details}

    min_data_len = max(config.SMA_PERIOD, config.VOLUME_PERIOD, 20) + 5 
    if df.empty or len(df) < min_data_len:
        logger.warning(f"Insufficient data ({len(df)} points) for pattern detection. Need at least {min_data_len}.")
        return default_result_all_confirmed if return_all else default_result_latest

    try:
        # Load only the specific candlestick patterns we need instead of all patterns
        # This avoids TA-Lib warnings for patterns we don't use
        try:
            # Use correct pandas-ta syntax for candlestick patterns
            # pandas-ta uses the cdl_pattern function with name parameter
            import pandas_ta as ta
            
            # Create the pattern columns using pandas-ta cdl_pattern function
            df['CDL_HAMMER'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="hammer")
            df['CDL_SHOOTINGSTAR'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="shootingstar") 
            df['CDL_ENGULFING'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="engulfing")
            df['CDL_MORNINGSTAR'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="morningstar")
            df['CDL_EVENINGSTAR'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="eveningstar")
        except Exception as e:
            logger.warning(f"Error loading specific candlestick patterns: {e}")
            # Fallback: create empty columns if pattern loading fails
            series_len = len(df)
            df["CDL_HAMMER"] = pd.Series([0]*series_len, index=df.index)
            df["CDL_SHOOTINGSTAR"] = pd.Series([0]*series_len, index=df.index)
            df["CDL_ENGULFING"] = pd.Series([0]*series_len, index=df.index)
            df["CDL_MORNINGSTAR"] = pd.Series([0]*series_len, index=df.index)
            df["CDL_EVENINGSTAR"] = pd.Series([0]*series_len, index=df.index)

        # Access the appended columns
        # pandas-ta cdl functions return 0 (no pattern), 100 (bullish), or -100 (bearish)
        # Check if columns exist before trying to access, default to a series of zeros if not
        series_len = len(df)
        raw_hammer = df["CDL_HAMMER"] if "CDL_HAMMER" in df.columns else pd.Series([0]*series_len, index=df.index)
        raw_shooting_star = df["CDL_SHOOTINGSTAR"] if "CDL_SHOOTINGSTAR" in df.columns else pd.Series([0]*series_len, index=df.index)
        engulfing = df["CDL_ENGULFING"] if "CDL_ENGULFING" in df.columns else pd.Series([0]*series_len, index=df.index)
        morning_star = df["CDL_MORNINGSTAR"] if "CDL_MORNINGSTAR" in df.columns else pd.Series([0]*series_len, index=df.index)
        evening_star = df["CDL_EVENINGSTAR"] if "CDL_EVENINGSTAR" in df.columns else pd.Series([0]*series_len, index=df.index)

        raw_detections = {
            "hammer": (raw_hammer == 100),
            "shooting_star": (raw_shooting_star == -100),
            "bullish_engulfing": (engulfing == 100),
            "bearish_engulfing": (engulfing == -100),
            "morning_star": (morning_star == 100),
            "evening_star": (evening_star == -100),
        }

        # Log raw_detections - MUCH REDUCED VERBOSITY
        total_patterns_detected = 0
        patterns_with_detections = []
        
        for pattern_key, series in raw_detections.items():
            if hasattr(series, 'empty') and not series.empty:
                try:
                    any_detected = series.any()
                    if any_detected:
                        recent_count = series.tail(15).sum() if hasattr(series, 'sum') else 0
                        total_patterns_detected += recent_count
                        patterns_with_detections.append(f"{pattern_key}({recent_count})")
                except Exception:
                    pass  # Skip problematic patterns silently
        
        # Single summary log instead of 6 individual pattern logs
        if patterns_with_detections:
            symbol_info = df['symbol'].iloc[-1] if 'symbol' in df.columns and not df.empty else "current_symbol"
            logger.info(f"Pattern summary for {symbol_info}: {', '.join(patterns_with_detections)} (total: {total_patterns_detected})")
        # No logging if no patterns detected to reduce noise

        confirmed_patterns_all = {key: np.array([False] * len(df)) for key in pattern_details}
        
        open_p = df['open'].to_numpy()
        high_p = df['high'].to_numpy()
        low_p = df['low'].to_numpy()
        close_p = df['close'].to_numpy()
        body_sizes_abs = np.abs(open_p - close_p)

        avg_volume_arr = volume_analysis_all.get('avg_volume', np.array([np.nan]*len(df)))
        high_volume_arr = volume_analysis_all.get('high_volume', np.array([False]*len(df)))
        
        avg_body_lookback = 5 
        loop_start_idx = avg_body_lookback + 3 
        
        for i in range(loop_start_idx, len(df) - 1):
            pattern_idx = i
            confirmation_idx = i + 1
            prev_candle_idx = i - 1
            engulf_context_idx = i - 3

            if pd.isna(sma_series_all[pattern_idx]) or pd.isna(avg_volume_arr[pattern_idx]) or pd.isna(avg_volume_arr[confirmation_idx]):
                continue

            open_patt, high_patt, low_patt, close_patt = open_p[pattern_idx], high_p[pattern_idx], low_p[pattern_idx], close_p[pattern_idx]
            body_patt_abs = body_sizes_abs[pattern_idx]
            
            open_conf, close_conf = open_p[confirmation_idx], close_p[confirmation_idx]
            is_high_volume_patt = high_volume_arr[pattern_idx]
            is_high_volume_conf = high_volume_arr[confirmation_idx]

            avg_body_prev_candles = np.mean(body_sizes_abs[pattern_idx - avg_body_lookback : pattern_idx]) if pattern_idx >= avg_body_lookback else 0.01
            avg_body_prev_candles = max(avg_body_prev_candles, 0.01) # Avoid division by zero

            # Iterate through specific patterns for confirmation
            for pattern_key, details in pattern_details.items():
                # CRITICAL CHANGE HERE: Use raw_detections
                if raw_detections[pattern_key].iloc[pattern_idx]:
                    confirmed = False
                    trend_check = False
                    strength_check = False
                    volume_check = False
                    confirmation_candle_check = False

                    # Generic Trend Confirmation (example for bullish, adapt for bearish)
                    if details["type"] == "bullish":
                        # Check for preceding downtrend (e.g., price < SMA or series of lower lows/highs)
                        # For simplicity: pattern candle low is below SMA and confirmation closes above SMA
                        if low_patt < sma_series_all[pattern_idx] and close_conf > sma_series_all[confirmation_idx]:
                            trend_check = True 
                        # A more robust trend: SMA is sloping down then up, or price action.
                        # Example: sma_series_all[pattern_idx-3] > sma_series_all[pattern_idx-1] and sma_series_all[confirmation_idx] > sma_series_all[pattern_idx]
                        if len(sma_series_all) > pattern_idx - 3 and \
                           sma_series_all[pattern_idx-3] > sma_series_all[pattern_idx-1] and \
                           sma_series_all[confirmation_idx] > sma_series_all[pattern_idx]:
                            trend_check = True
                    elif details["type"] == "bearish":
                        # Check for preceding uptrend
                        if high_patt > sma_series_all[pattern_idx] and close_conf < sma_series_all[confirmation_idx]:
                            trend_check = True
                        if len(sma_series_all) > pattern_idx - 3 and \
                           sma_series_all[pattern_idx-3] < sma_series_all[pattern_idx-1] and \
                           sma_series_all[confirmation_idx] < sma_series_all[pattern_idx]:
                            trend_check = True
                    
                    # Volume Confirmation (Pattern or Confirmation Candle)
                    if is_high_volume_patt or is_high_volume_conf:
                        volume_check = True

                    # Candle Strength (body size vs avg body size)
                    if body_patt_abs > avg_body_prev_candles * config.CANDLE_BODY_STRENGTH_FACTOR:
                        strength_check = True

                    # Confirmation Candle Logic
                    if details["type"] == "bullish" and close_conf > open_conf and close_conf > high_patt:
                        confirmation_candle_check = True
                    elif details["type"] == "bearish" and close_conf < open_conf and close_conf < low_patt:
                        confirmation_candle_check = True
                    
                    # Specific pattern characteristics (can refine further)
                    if pattern_key == "hammer": # Bullish
                        lower_wick = low_patt - min(open_patt, close_patt)
                        upper_wick = high_patt - max(open_patt, close_patt)
                        if lower_wick > body_patt_abs * config.HAMMER_WICK_RATIO and \
                           upper_wick < body_patt_abs * config.HAMMER_UPPER_WICK_MAX_RATIO and \
                           trend_check and strength_check and volume_check and confirmation_candle_check:
                            confirmed = True
                    
                    elif pattern_key == "shooting_star": # Bearish
                        upper_wick = high_patt - max(open_patt, close_patt)
                        lower_wick = min(open_patt, close_patt) - low_patt
                        if upper_wick > body_patt_abs * config.SHOOTING_STAR_WICK_RATIO and \
                           lower_wick < body_patt_abs * config.SHOOTING_STAR_LOWER_WICK_MAX_RATIO and \
                           trend_check and strength_check and volume_check and confirmation_candle_check:
                            confirmed = True

                    elif pattern_key == "bullish_engulfing":
                        # Engulfing specific checks
                        open_prev, high_prev, low_prev, close_prev = open_p[prev_candle_idx], high_p[prev_candle_idx], low_p[prev_candle_idx], close_p[prev_candle_idx]
                        # Pattern candle engulfs previous candle's body
                        if close_patt > open_prev and open_patt < close_prev and \
                           trend_check and strength_check and volume_check and confirmation_candle_check:
                             # Additional check: current body is larger than previous body
                            if body_patt_abs > abs(open_prev - close_prev) * config.ENGULFING_BODY_FACTOR:
                                confirmed = True
                                
                    elif pattern_key == "bearish_engulfing":
                        open_prev, high_prev, low_prev, close_prev = open_p[prev_candle_idx], high_p[prev_candle_idx], low_p[prev_candle_idx], close_p[prev_candle_idx]
                        # Pattern candle engulfs previous candle's body
                        if open_patt > close_prev and close_patt < open_prev and \
                           trend_check and strength_check and volume_check and confirmation_candle_check:
                            if body_patt_abs > abs(open_prev - close_prev) * config.ENGULFING_BODY_FACTOR:
                                confirmed = True

                    if confirmed:
                        confirmed_patterns_all[pattern_key][confirmation_idx] = True
                        # logger.debug(f"Confirmed {details['name']} at index {confirmation_idx} (pattern at {pattern_idx})")
                        # Only report one pattern per confirmation candle for simplicity of return_latest
                        break # Exit inner loop once a pattern is confirmed for this candle i
            
            # This break was inside the pattern_key loop, should be outside if we want one pattern per i
            # If a pattern was confirmed for candle i (its confirmation is at i+1), then we can potentially stop for this 'i'
            # However, the current structure with `confirmed_patterns_all` storing all allows multiple raw patterns
            # but `return_latest` will pick one.
            # if any(confirmed_patterns_all[key][confirmation_idx] for key in confirmed_patterns_all):
            #    pass # continue to next i

        if return_all:
            return confirmed_patterns_all # This returns a dict of boolean arrays
        else:
            # Find the latest confirmed pattern
            latest_confirmed_signal = default_result_latest.copy()
            latest_confirmed_signal["pattern_detected_raw"] = False # Explicitly reset

            # Iterate backwards from the last possible confirmation index
            # Last pattern_idx is len(df) - 2, so last confirmation_idx is len(df) - 1
            for i in range(len(df) - 1, loop_start_idx -1, -1): # i is confirmation_idx here
                # Check raw detections at pattern_idx = i-1
                raw_pattern_idx = i-1
                if raw_pattern_idx < 0: continue

                pattern_found_this_candle = False
                for pattern_key, details in pattern_details.items():
                    if confirmed_patterns_all[pattern_key][i]: # Check confirmed status at confirmation_idx
                        latest_confirmed_signal["pattern_name"] = details["name"]
                        latest_confirmed_signal["pattern_type"] = details["type"]
                        # Check raw detection at pattern_idx for "pattern_detected_raw"
                        # This raw_detections should use raw_pattern_idx
                        if raw_detections[pattern_key].iloc[raw_pattern_idx]:
                             latest_confirmed_signal["pattern_detected_raw"] = True
                        else:
                            # This case should ideally not happen if confirmed_patterns_all[pattern_key][i] is true
                            # as confirmation implies raw detection. Log if it does.
                            logger.warning(f"Confirmed pattern {details['name']} at {i} but no raw detection at {raw_pattern_idx}")
                            latest_confirmed_signal["pattern_detected_raw"] = False


                        pattern_found_this_candle = True
                        break # Found the latest confirmed pattern type for this candle
                
                if pattern_found_this_candle:
                    # If any pattern was confirmed and processed for this candle index i, break main loop
                    break 
            
            # Fallback for pattern_detected_raw if no confirmed pattern was found by iterating backwards
            # This ensures pattern_detected_raw reflects the very last candle's raw signals if no *confirmed* one exists
            if latest_confirmed_signal["pattern_name"] == "N/A" and len(df) > 0:
                last_pattern_idx = len(df) -2 # df.ta.strategy was on df up to last candle, raw detection is for pattern candle
                if last_pattern_idx >=0:
                    for pattern_key, details in pattern_details.items():
                        # Check raw detection on the candle that would be 'pattern_idx' if we were confirming the last possible candle.
                        # The columns from df.ta.strategy are for the whole df.
                        # The last candle that could BE a pattern is len(df)-2, because confirmation is len(df)-1
                        # However, raw_detections are on the actual candle. So use -1 for latest.
                        # The issue is df.ta.strategy columns like "CDL_HAMMER" are results for *that* candle.
                        # So, for the very last candle df.iloc[-1], we can check its raw pattern status.
                        
                        # If trying to get the raw signal for the *absolute latest* candle (df.iloc[-1]):
                        raw_check_idx = len(df) - 1 # Index for iloc for the last candle
                        if raw_check_idx >=0 : # Ensure df is not empty
                            if raw_detections[pattern_key].iloc[raw_check_idx]:
                                latest_confirmed_signal["pattern_name"] = f"Raw {details['name']}" # Indicate it's raw
                                latest_confirmed_signal["pattern_type"] = details["type"]
                                latest_confirmed_signal["pattern_detected_raw"] = True
                                # logger.debug(f"No confirmed pattern, returning latest raw: {details['name']} at index {raw_check_idx}")
                                break # Found a raw pattern for the latest candle

            return latest_confirmed_signal
        
    except Exception as e:
        logger.error(f"Error detecting candlestick patterns: {e}", exc_info=True)
        if return_all:
            return default_result_all_confirmed
        else:
            return default_result_latest

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

def analyze_technicals(kline_data_list): # Expects list of dicts from kraken_api
    """Main function to perform technical analysis using pandas-ta."""
    if not kline_data_list:
        logger.warning("analyze_technicals: Empty kline_data_list received.")
        return None
    
    try:
        df = _ensure_dataframe(kline_data_list) # Initial and only call to _ensure_dataframe
        
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
        
        technicals = {
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
