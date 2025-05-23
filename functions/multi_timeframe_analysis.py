import logging
import numpy as np
import pandas as pd
from . import config
from .kraken_api import fetch_kline_data
from .technical_analysis import calculate_rsi, calculate_ema

# Configure logging
logger = logging.getLogger(__name__)

def analyze_higher_timeframes(symbol):
    """
    Analyze higher timeframes (15m, 1h) for trend confirmation.
    Returns trend direction and strength for each timeframe.
    """
    if not config.MULTI_TIMEFRAME_ENABLED:
        logger.info("Multi-timeframe analysis disabled")
        return {"trend_confirmed": False, "trend_direction": "neutral"}
    
    try:
        timeframe_results = {}
        
        for timeframe in config.SECONDARY_TIMEFRAMES:
            logger.info(f"Analyzing {timeframe} timeframe for {symbol}")
            
            # Get kline data for higher timeframe
            kline_data = fetch_kline_data(symbol=symbol, resolution=timeframe, limit=100)
            if not kline_data:
                logger.warning(f"No kline data for {symbol} on {timeframe}")
                continue
                
            # Convert to DataFrame
            df = pd.DataFrame(kline_data)
            if df.empty or len(df) < 20:
                logger.warning(f"Insufficient data for {symbol} on {timeframe}")
                continue
                
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate indicators
            rsi = calculate_rsi(df)
            ema_20 = calculate_ema(df)
            current_price = df['close'].iloc[-1]
            
            # Determine trend direction
            trend_direction = "neutral"
            trend_strength = 0
            
            if current_price > ema_20:
                if rsi > 50:
                    trend_direction = "bullish"
                    trend_strength = min((current_price - ema_20) / ema_20 * 100, 100)
                else:
                    trend_direction = "weak_bullish"
                    trend_strength = 25
            elif current_price < ema_20:
                if rsi < 50:
                    trend_direction = "bearish"
                    trend_strength = min((ema_20 - current_price) / ema_20 * 100, 100)
                else:
                    trend_direction = "weak_bearish"
                    trend_strength = 25
            
            timeframe_results[timeframe] = {
                "trend_direction": trend_direction,
                "trend_strength": trend_strength,
                "rsi": rsi,
                "ema": ema_20,
                "price": current_price
            }
            
            logger.info(f"{symbol} {timeframe}: {trend_direction} (strength: {trend_strength:.1f})")
        
        # Analyze overall trend confirmation
        trend_confirmed = False
        overall_direction = "neutral"
        
        if len(timeframe_results) >= 2:
            directions = [result["trend_direction"] for result in timeframe_results.values()]
            
            # Check for bullish confirmation
            bullish_count = sum(1 for d in directions if "bullish" in d)
            bearish_count = sum(1 for d in directions if "bearish" in d)
            
            if bullish_count >= len(directions) * 0.6:  # 60% agreement
                overall_direction = "bullish"
                trend_confirmed = True
            elif bearish_count >= len(directions) * 0.6:
                overall_direction = "bearish"
                trend_confirmed = True
        
        result = {
            "trend_confirmed": trend_confirmed,
            "trend_direction": overall_direction,
            "timeframe_details": timeframe_results
        }
        
        logger.info(f"{symbol} multi-timeframe result: {overall_direction} (confirmed: {trend_confirmed})")
        return result
        
    except Exception as e:
        logger.error(f"Error in multi-timeframe analysis for {symbol}: {e}", exc_info=True)
        return {"trend_confirmed": False, "trend_direction": "neutral"}

def get_trend_confirmation_score(symbol, signal_direction):
    """
    Get trend confirmation score for signal direction.
    Returns score between 0-20 based on higher timeframe alignment.
    """
    try:
        mtf_result = analyze_higher_timeframes(symbol)
        
        if not mtf_result["trend_confirmed"]:
            return 5  # Neutral score when trend not confirmed
            
        trend_direction = mtf_result["trend_direction"]
        
        # Check alignment with signal direction
        if signal_direction.upper() == "LONG" and trend_direction == "bullish":
            return 20  # Full score for aligned bullish trend
        elif signal_direction.upper() == "SHORT" and trend_direction == "bearish":
            return 20  # Full score for aligned bearish trend
        elif signal_direction.upper() == "LONG" and trend_direction == "bearish":
            return 0   # No score for opposing trend
        elif signal_direction.upper() == "SHORT" and trend_direction == "bullish":
            return 0   # No score for opposing trend
        else:
            return 10  # Partial score for neutral/weak trends
            
    except Exception as e:
        logger.error(f"Error getting trend confirmation score for {symbol}: {e}")
        return 5  # Default neutral score 