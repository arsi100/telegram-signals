import logging
import numpy as np
import talib

# Set up logging
logging.basicConfig(level=logging.DEBUG)
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

def detect_candlestick_patterns(kline_data):
    """
    Detect candlestick patterns using TA-Lib.
    
    Args:
        kline_data: List of candlestick data
        
    Returns:
        Dict of detected patterns and their values
    """
    try:
        # Convert klines to numpy arrays
        open_prices, high_prices, low_prices, close_prices, _ = convert_klines_to_numpy(kline_data)
        
        # Detect patterns using TA-Lib
        hammer = talib.CDLHAMMER(open_prices, high_prices, low_prices, close_prices)
        shooting_star = talib.CDLSHOOTINGSTAR(open_prices, high_prices, low_prices, close_prices)
        bullish_engulfing = talib.CDLENGULFING(open_prices, high_prices, low_prices, close_prices)
        bearish_engulfing = talib.CDLENGULFING(open_prices, high_prices, low_prices, close_prices)
        
        # Get the most recent values
        patterns = {
            "hammer": hammer[-1],
            "shooting_star": shooting_star[-1],
            "bullish_engulfing": bullish_engulfing[-1] if bullish_engulfing[-1] > 0 else 0,
            "bearish_engulfing": abs(bullish_engulfing[-1]) if bullish_engulfing[-1] < 0 else 0
        }
        
        # Log the detected patterns
        detected = [name for name, value in patterns.items() if value > 0]
        if detected:
            logger.info(f"Detected patterns: {', '.join(detected)}")
        
        return patterns
        
    except Exception as e:
        logger.error(f"Error detecting candlestick patterns: {str(e)}")
        # Return empty patterns on error
        return {
            "hammer": 0,
            "shooting_star": 0,
            "bullish_engulfing": 0,
            "bearish_engulfing": 0
        }

def calculate_rsi(kline_data, period=14):
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        kline_data: List of candlestick data
        period: RSI period (default: 14)
        
    Returns:
        RSI value (0-100)
    """
    try:
        _, _, _, close_prices, _ = convert_klines_to_numpy(kline_data)
        rsi = talib.RSI(close_prices, timeperiod=period)
        
        # Return the most recent RSI value
        return rsi[-1]
        
    except Exception as e:
        logger.error(f"Error calculating RSI: {str(e)}")
        return 50  # Return neutral RSI on error

def calculate_sma(kline_data, period=50):
    """
    Calculate Simple Moving Average (SMA).
    
    Args:
        kline_data: List of candlestick data
        period: SMA period (default: 50)
        
    Returns:
        SMA value
    """
    try:
        _, _, _, close_prices, _ = convert_klines_to_numpy(kline_data)
        sma = talib.SMA(close_prices, timeperiod=period)
        
        # Return the most recent SMA value
        return sma[-1]
        
    except Exception as e:
        logger.error(f"Error calculating SMA: {str(e)}")
        return close_prices[-1]  # Return current price on error

def analyze_volume(kline_data, period=50):
    """
    Analyze trading volume.
    
    Args:
        kline_data: List of candlestick data
        period: Period for volume average calculation (default: 50)
        
    Returns:
        Dict with volume analysis results
    """
    try:
        _, _, _, _, volume = convert_klines_to_numpy(kline_data)
        
        # Calculate volume metrics
        current_volume = volume[-1]
        avg_volume = np.mean(volume[-period:])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "high_volume": volume_ratio > 1.0  # Volume is above average
        }
        
    except Exception as e:
        logger.error(f"Error analyzing volume: {str(e)}")
        return {
            "current_volume": 0,
            "avg_volume": 0,
            "volume_ratio": 1.0,
            "high_volume": False
        }
