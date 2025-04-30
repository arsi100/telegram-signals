import logging
import numpy as np
import talib
import os # Import os for directory creation

# Use absolute imports
from functions import config # Import config to access parameters

# Set up logging
log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)
log_file_path = os.path.join(log_directory, "technical_analysis.log")

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    filename=log_file_path,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def convert_klines_to_numpy(kline_data):
    """
    Convert kline data to numpy arrays for TA-Lib functions.
    
    Args:
        kline_data: List of candlestick data
        
    Returns:
        Tuple of (open, high, low, close, volume) numpy arrays
    """
    open_prices = np.array([float(k["open"]) for k in kline_data])
    high_prices = np.array([float(k["high"]) for k in kline_data])
    low_prices = np.array([float(k["low"]) for k in kline_data])
    close_prices = np.array([float(k["close"]) for k in kline_data])
    volume = np.array([float(k["volume"]) for k in kline_data])
    
    return open_prices, high_prices, low_prices, close_prices, volume

def calculate_rsi(kline_data, return_all=False):
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        kline_data: List of candlestick data dictionaries.
        return_all: If True, return the full array of RSI values. 
                    If False, return only the latest RSI value.
        
    Returns:
        Latest RSI value (float), the full RSI numpy array, or None on error.
        Returns neutral RSI (50.0) if only latest is requested and error occurs.
    """
    try:
        _, _, _, close_prices, _ = convert_klines_to_numpy(kline_data)
        
        # Ensure enough data points for the calculation
        if len(close_prices) <= config.RSI_PERIOD:
            logger.warning(f"Not enough data points ({len(close_prices)}) to calculate RSI with period {config.RSI_PERIOD}")
            return None if return_all else 50.0
            
        rsi = talib.RSI(close_prices, timeperiod=config.RSI_PERIOD)
        
        if return_all:
            return rsi # Return the full array (includes NaNs at the start)
        else:
            # Return the most recent non-NaN RSI value
            latest_rsi = rsi[~np.isnan(rsi)][-1] if len(rsi[~np.isnan(rsi)]) > 0 else 50.0
            return latest_rsi
        
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        return None if return_all else 50.0

def calculate_sma(kline_data, return_all=False):
    """
    Calculate Simple Moving Average (SMA).
    
    Args:
        kline_data: List of candlestick data dictionaries.
        return_all: If True, return the full array of SMA values. 
                    If False, return only the latest SMA value.
        
    Returns:
        Latest SMA value (float), the full SMA numpy array, or None on error.
        Returns last close price if only latest is requested and error occurs.
    """
    try:
        _, _, _, close_prices, _ = convert_klines_to_numpy(kline_data)

        # Ensure enough data points for the calculation
        if len(close_prices) < config.SMA_PERIOD:
            logger.warning(f"Not enough data points ({len(close_prices)}) to calculate SMA with period {config.SMA_PERIOD}")
            return None if return_all else (close_prices[-1] if len(close_prices) > 0 else None)
            
        sma = talib.SMA(close_prices, timeperiod=config.SMA_PERIOD)
        
        if return_all:
            return sma # Return the full array (includes NaNs at the start)
        else:
            # Return the most recent non-NaN SMA value
            latest_sma = sma[~np.isnan(sma)][-1] if len(sma[~np.isnan(sma)]) > 0 else close_prices[-1]
            return latest_sma
        
    except Exception as e:
        logger.error(f"Error calculating SMA: {e}")
        last_close = kline_data[-1]['close'] if kline_data else None
        return None if return_all else last_close

def analyze_volume(kline_data, return_all=False):
    """
    Analyze trading volume, calculating average volume and identifying high volume periods.
    
    Args:
        kline_data: List of candlestick data dictionaries.
        return_all: If True, return dictionary of arrays (current, avg, ratio, high_volume_bool).
                    If False, return dictionary of latest values.
        
    Returns:
        Dictionary containing volume analysis results, or None on error.
        Returns default values if only latest is requested and error occurs.
    """
    default_result_latest = {
        "current_volume": 0.0,
        "avg_volume": 0.0,
        "volume_ratio": 1.0,
        "high_volume": False
    }
    default_result_all = {
        "current_volume": np.array([]),
        "avg_volume": np.array([]),
        "volume_ratio": np.array([]),
        "high_volume": np.array([])
    }

    try:
        _, _, _, _, volume = convert_klines_to_numpy(kline_data)
        
        if len(volume) < config.VOLUME_PERIOD:
            logger.warning(f"Not enough data points ({len(volume)}) for volume analysis with period {config.VOLUME_PERIOD}")
            return default_result_all if return_all else default_result_latest
        
        # Calculate rolling average volume using a sliding window
        # Use pandas for easier rolling calculations if available, otherwise numpy
        try:
            import pandas as pd
            volume_series = pd.Series(volume)
            # Shift window by 1 so avg_volume[i] is avg of [i-period ... i-1]
            avg_volume_arr = volume_series.rolling(window=config.VOLUME_PERIOD).mean().shift(1).to_numpy()
        except ImportError:
            logger.warning("Pandas not found, using numpy for rolling volume average (potentially slower).")
            # Naive numpy implementation (less efficient for large datasets)
            avg_volume_arr = np.full_like(volume, np.nan, dtype=float)
            for i in range(config.VOLUME_PERIOD, len(volume)):
                avg_volume_arr[i] = np.mean(volume[i-config.VOLUME_PERIOD:i])
                
        # Calculate ratio: current_volume / avg_volume (handle division by zero or NaN avg)
        # We compare volume[i] with avg_volume[i] (average of previous N periods)
        volume_ratio_arr = np.full_like(volume, np.nan, dtype=float)
        valid_avg_mask = ~np.isnan(avg_volume_arr) & (avg_volume_arr > 0)
        volume_ratio_arr[valid_avg_mask] = volume[valid_avg_mask] / avg_volume_arr[valid_avg_mask]
        volume_ratio_arr[~valid_avg_mask] = 1.0 # Default ratio if avg is zero or NaN
        
        high_volume_arr = volume_ratio_arr > 1.0

        results_all = {
            "current_volume": volume,
            "avg_volume": avg_volume_arr,
            "volume_ratio": volume_ratio_arr,
            "high_volume": high_volume_arr
        }

        if return_all:
            return results_all
        else:
            # Get the latest values, handling potential NaNs at the start
            latest_results = {}
            for key, arr in results_all.items():
                valid_values = arr[~np.isnan(arr)] if key != 'high_volume' else arr # boolean array doesn't have NaNs
                latest_results[key] = valid_values[-1] if len(valid_values) > 0 else default_result_latest[key]
            return latest_results

    except Exception as e:
        logger.error(f"Error analyzing volume: {e}")
        return default_result_all if return_all else default_result_latest

def detect_candlestick_patterns(
    kline_data, 
    open_p, high_p, low_p, close_p, # Numpy arrays from convert_klines_to_numpy
    sma_arr, # Numpy array from calculate_sma(return_all=True)
    volume_analysis, # Dict of arrays from analyze_volume(return_all=True)
    return_all=False
):
    """
    Detects confirmed candlestick patterns considering trend, strength, and volume.

    Args:
        kline_data: Original list of candlestick data dictionaries.
        open_p, high_p, low_p, close_p: Numpy arrays of OHLC prices.
        sma_arr: Numpy array of SMA values.
        volume_analysis: Dictionary containing numpy arrays for volume analysis 
                         (e.g., 'high_volume').
        return_all: If True, return dict of boolean arrays for each confirmed pattern.
                    If False, return dict of booleans for latest confirmed pattern status.

    Returns:
        Dictionary containing pattern detection results (boolean arrays or latest booleans).
        Returns default False values if error occurs or insufficient data.
    """
    default_result_latest = {
        "confirmed_hammer": False,
        "confirmed_shooting_star": False,
        "confirmed_bullish_engulfing": False,
        "confirmed_bearish_engulfing": False
    }
    default_result_all = {
        "confirmed_hammer": np.array([False] * len(kline_data)),
        "confirmed_shooting_star": np.array([False] * len(kline_data)),
        "confirmed_bullish_engulfing": np.array([False] * len(kline_data)),
        "confirmed_bearish_engulfing": np.array([False] * len(kline_data))
    }
    
    # Increase minimum data length requirement to account for avg body calculation lookback
    avg_body_lookback = 5 # Lookback for average body (-8 to -4 relative to pattern candle i)
    min_data_len = max(config.SMA_PERIOD, config.VOLUME_PERIOD, avg_body_lookback + 3) + 2 
    
    if len(kline_data) < min_data_len:
        logger.warning(f"Insufficient data ({len(kline_data)} points) for pattern detection. Need at least {min_data_len}.")
        return default_result_all if return_all else default_result_latest

    try:
        # 1. Initial TA-Lib Pattern Detection
        hammer = talib.CDLHAMMER(open_p, high_p, low_p, close_p)
        shooting_star = talib.CDLSHOOTINGSTAR(open_p, high_p, low_p, close_p)
        # Note: TA-Lib engulfing requires previous candle, so result is for candle i based on i and i-1
        engulfing = talib.CDLENGULFING(open_p, high_p, low_p, close_p) 
        bullish_engulfing_raw = (engulfing > 0)
        bearish_engulfing_raw = (engulfing < 0)

        # Initialize result arrays
        confirmed_hammer_arr = np.array([False] * len(kline_data))
        confirmed_shooting_star_arr = np.array([False] * len(kline_data))
        confirmed_bullish_engulfing_arr = np.array([False] * len(kline_data))
        confirmed_bearish_engulfing_arr = np.array([False] * len(kline_data))

        # Iterate through candles to check confirmations 
        # Need data for candle i-7 to i+1 for all checks
        start_index = avg_body_lookback + 3 # Ensure index i-7 exists
        if start_index < min_data_len - 1: # Also respect SMA/Volume lookback
             start_index = min_data_len - 1
             
        # Calculate Body Sizes once
        body_sizes = np.abs(open_p - close_p)

        for i in range(start_index, len(kline_data) - 1): 
            pattern_idx = i 
            confirmation_idx = i + 1
            prev_candle_idx = i - 1 
            engulf_context_idx = i - 3 # Context candle for engulfing check

            # Check if necessary data is available (SMA, Volume Avg might have NaNs at start)
            if np.isnan(sma_arr[pattern_idx]) or np.isnan(volume_analysis['avg_volume'][pattern_idx]) or \
               np.isnan(volume_analysis['avg_volume'][confirmation_idx]): # Need avg volume for conf candle too
                continue
                
            # --- Get data for relevant candles ---
            open_patt = open_p[pattern_idx]
            high_patt = high_p[pattern_idx]
            low_patt = low_p[pattern_idx]
            close_patt = close_p[pattern_idx]
            body_patt = body_sizes[pattern_idx] #abs(open_patt - close_patt)
            
            open_conf = open_p[confirmation_idx]
            close_conf = close_p[confirmation_idx]
            
            is_high_volume_patt = volume_analysis['high_volume'][pattern_idx]
            # Add high volume check for confirmation candle
            is_high_volume_conf = volume_analysis['high_volume'][confirmation_idx]
            
            sma_patt = sma_arr[pattern_idx]

            # --- Define Confirmation Conditions (Enhanced) ---
            # Bullish confirmation candle also has close > open
            confirm_bullish = (close_conf > close_patt) and (close_conf > open_conf)
            # Bearish confirmation candle also has close < open
            confirm_bearish = (close_conf < close_patt) and (close_conf < open_conf)

            # --- Define Trend Conditions --- (Unchanged)
            trend_down = close_patt < sma_patt
            trend_up = close_patt > sma_patt
            
            # --- Define Strength Conditions (Enhanced) --- 
            body_gt_zero = body_patt > 1e-9 
            
            # Hammer Strength (Unchanged)
            is_strong_hammer = False
            if body_gt_zero:
                lower_shadow = min(open_patt, close_patt) - low_patt
                upper_shadow = high_patt - max(open_patt, close_patt)
                is_strong_hammer = lower_shadow >= 2 * body_patt and upper_shadow < 0.5 * body_patt
                
            # Shooting Star Strength (Unchanged)
            is_strong_shooting_star = False
            if body_gt_zero:
                upper_shadow = high_patt - max(open_patt, close_patt)
                lower_shadow = min(open_patt, close_patt) - low_patt
                is_strong_shooting_star = upper_shadow >= 2 * body_patt and lower_shadow < 0.5 * body_patt
            
            # Engulfing Strength (Unchanged)
            is_strong_engulfing = False
            if prev_candle_idx >= 0:
                body_prev = body_sizes[prev_candle_idx] #abs(open_p[prev_candle_idx] - close_p[prev_candle_idx])
                if body_prev > 1e-9: 
                    is_strong_engulfing = body_patt >= 1.5 * body_prev
                    
            # Engulfing Context (Small body check at index i-3)
            engulfing_has_small_prev_context = False
            if engulf_context_idx >= 0:
                 # Calculate avg body size from i-8 to i-4 (5 periods before context candle)
                 if i >= avg_body_lookback + 3: # Ensure indices are valid
                     avg_body_lookback_start = i - avg_body_lookback - 3
                     avg_body_lookback_end = i - 3
                     avg_body_context = np.mean(body_sizes[avg_body_lookback_start:avg_body_lookback_end])
                     
                     body_context = body_sizes[engulf_context_idx] #abs(open_p[engulf_context_idx] - close_p[engulf_context_idx])
                     if avg_body_context > 1e-9: # Avoid division by zero
                         engulfing_has_small_prev_context = body_context < avg_body_context
            

            # --- Combine Checks for Each Pattern --- 
            
            # Hammer Check (Pattern at i, Confirmed at i+1)
            if hammer[pattern_idx] > 0:
                # Added high volume check on confirmation candle
                if is_strong_hammer and trend_down and is_high_volume_patt and is_high_volume_conf and confirm_bullish:
                    confirmed_hammer_arr[pattern_idx] = True
                        
            # Shooting Star Check
            if shooting_star[pattern_idx] < 0:
                 # Added high volume check on confirmation candle
                if is_strong_shooting_star and trend_up and is_high_volume_patt and is_high_volume_conf and confirm_bearish:
                    confirmed_shooting_star_arr[pattern_idx] = True
            
            # Bullish Engulfing Check
            if bullish_engulfing_raw[pattern_idx]:
                 # Added high volume check on confirmation candle and small prev context check
                if is_strong_engulfing and trend_down and is_high_volume_patt and is_high_volume_conf and engulfing_has_small_prev_context and confirm_bullish:
                    confirmed_bullish_engulfing_arr[pattern_idx] = True
            
            # Bearish Engulfing Check
            if bearish_engulfing_raw[pattern_idx]:
                  # Added high volume check on confirmation candle and small prev context check
                 if is_strong_engulfing and trend_up and is_high_volume_patt and is_high_volume_conf and engulfing_has_small_prev_context and confirm_bearish:
                    confirmed_bearish_engulfing_arr[pattern_idx] = True
        
        # --- Prepare Return Value --- 
        results_all = {
            "confirmed_hammer": confirmed_hammer_arr,
            "confirmed_shooting_star": confirmed_shooting_star_arr,
            "confirmed_bullish_engulfing": confirmed_bullish_engulfing_arr,
            "confirmed_bearish_engulfing": confirmed_bearish_engulfing_arr
        }

        if return_all:
            return results_all
        else:
            # Return the status for the pattern detected at index -2 (confirmed by -1)
            latest_results = {}
            pattern_check_idx = -2 # Check pattern at -2, confirmed by -1
            if len(kline_data) > abs(pattern_check_idx): # Ensure index exists
                 for key, arr in results_all.items():
                     latest_results[key] = arr[pattern_check_idx]
            else:
                 latest_results = default_result_latest # Not enough data for lookback
                 
            # Log the latest detected confirmed patterns
            detected = [name for name, value in latest_results.items() if value]
            if detected:
                logger.info(f"Latest confirmed patterns (at index -2): {', '.join(detected)}")
                
            return latest_results
        
    except Exception as e:
        logger.error(f"Error detecting confirmed candlestick patterns: {e}")
        return default_result_all if return_all else default_result_latest

def analyze_technicals(kline_data):
    """
    Orchestrator function to perform all technical analysis.

    Args:
        kline_data: List of candlestick data dictionaries.

    Returns:
        A dictionary containing the latest technical analysis results:
        {
            'rsi': float,        # Latest RSI value
            'sma': float,        # Latest SMA value
            'volume': dict,     # Latest volume analysis dictionary
            'patterns': dict,   # Latest confirmed patterns dictionary
            'latest_close': float # Latest closing price
        }
        Returns None if critical errors occur or insufficient data for basic analysis.
    """
    
    results = {
        "rsi": 50.0, # Default neutral
        "sma": None,
        "volume": analyze_volume([], return_all=False), # Get default structure
        "patterns": detect_candlestick_patterns([], [], [], [], [], [], {}, return_all=False), # Get default structure
        "latest_close": None
    }
    
    if not kline_data:
        logger.error("analyze_technicals: Received empty kline data.")
        return None
        
    results['latest_close'] = kline_data[-1]['close']
    results['sma'] = results['latest_close'] # Default SMA to latest close

    try:
        # --- Calculate base indicators (requesting arrays for pattern checks) ---
        open_p, high_p, low_p, close_p, volume_p = convert_klines_to_numpy(kline_data)
        
        # Calculate latest values directly where possible
        latest_rsi = calculate_rsi(kline_data, return_all=False)
        if latest_rsi is not None: results['rsi'] = latest_rsi
        
        latest_sma = calculate_sma(kline_data, return_all=False)
        if latest_sma is not None: results['sma'] = latest_sma
            
        latest_volume = analyze_volume(kline_data, return_all=False)
        if latest_volume is not None: results['volume'] = latest_volume
            
        # --- Calculate arrays needed ONLY for pattern detection --- 
        # Avoid recalculating if not needed, but pattern function requires them
        sma_arr = calculate_sma(kline_data, return_all=True)
        volume_analysis_arr = analyze_volume(kline_data, return_all=True)

        # --- Perform pattern detection --- 
        # Ensure required arrays are valid before calling pattern detection
        if sma_arr is not None and volume_analysis_arr is not None:
            latest_patterns = detect_candlestick_patterns(
                kline_data, open_p, high_p, low_p, close_p, 
                sma_arr, volume_analysis_arr, 
                return_all=False
            )
            if latest_patterns is not None: results['patterns'] = latest_patterns
        else:
            logger.warning("Skipping pattern detection due to missing SMA or Volume arrays.")
            # Keep default pattern results

        return results

    except Exception as e:
        logger.error(f"Error during analyze_technicals: {e}", exc_info=True)
        # Return results with defaults populated where possible
        return results 
