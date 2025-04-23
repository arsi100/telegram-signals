import logging
from firebase_admin import firestore
from technical_analysis import (detect_candlestick_patterns, calculate_rsi, 
                              calculate_sma, analyze_volume)
from confidence_calculator import get_confidence_score
from position_manager import update_position, save_position
from utils import is_in_cooldown_period

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def process_crypto_data(symbol, kline_data, db):
    """
    Process cryptocurrency data and generate trading signals based on 
    strict conditions for high-probability leveraged trades.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        kline_data: List of candlestick data
        db: Firestore database instance
    
    Returns:
        Signal dict or None if no signal generated
    """
    try:
        # Skip if in cooldown period
        if is_in_cooldown_period(symbol, db):
            logger.info(f"{symbol} is in cooldown period. Skipping.")
            return None
        
        # Get current position if any
        position_query = db.collection("positions").where("symbol", "==", symbol).where("status", "==", "open").limit(1).get()
        current_position = position_query[0].to_dict() if len(position_query) > 0 else None
        
        # Get latest price
        price = float(kline_data[-1]["close"])
        
        # ---------- Technical Analysis ----------
        
        # 1. Detect candlestick patterns (40% weight)
        patterns = detect_candlestick_patterns(kline_data)
        pattern_type = None
        
        if patterns["hammer"] > 0 or patterns["bullish_engulfing"] > 0:
            pattern_type = "bullish"
        elif patterns["shooting_star"] > 0 or patterns["bearish_engulfing"] > 0:
            pattern_type = "bearish"
            
        if not pattern_type:
            logger.info(f"No significant candlestick pattern detected for {symbol}")
            return None
            
        # 2. Calculate RSI (30% weight)
        rsi = calculate_rsi(kline_data)
        
        # 3. Volume analysis (20% weight)
        volume = float(kline_data[-1]["volume"])
        volume_analysis = analyze_volume(kline_data)
        
        if not volume_analysis["high_volume"]:
            logger.info(f"Volume not high enough for {symbol}")
            return None
            
        # 4. SMA trend confirmation (10% weight)
        sma = calculate_sma(kline_data)
        price_below_sma = price < sma
        
        # ---------- Calculate Confidence Score ----------
        confidence = get_confidence_score(
            pattern_type=pattern_type,
            rsi=rsi,
            volume_ratio=volume_analysis["volume_ratio"],
            price=price,
            sma=sma
        )
        
        logger.info(f"{symbol} analysis - Pattern: {pattern_type}, RSI: {rsi:.2f}, Volume Ratio: {volume_analysis['volume_ratio']:.2f}, SMA: {sma:.2f}, Confidence: {confidence:.2f}")
        
        # ---------- Generate Signal ----------
        # If confidence is too low, don't generate a signal
        if confidence < 80:
            logger.info(f"{symbol} confidence score {confidence:.2f} is below threshold (80)")
            return None
        
        # Generate signal based on current position status
        if current_position:
            # For existing positions, we can generate exit or average down signals
            position_type = current_position["type"]
            entry_price = current_position["entry_price"]
            
            if position_type == "long":
                # Check for exit conditions
                if price >= entry_price * 1.03 or (pattern_type == "bearish" and rsi > 70):
                    return {
                        "type": "exit",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_query[0].reference.path
                    }
                
                # Check for average down conditions
                if price <= entry_price * 0.98 and volume_analysis["high_volume"] and confidence > 80:
                    return {
                        "type": "avg_down_long",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_query[0].reference.path
                    }
                    
            elif position_type == "short":
                # Check for exit conditions
                if price <= entry_price * 0.97 or (pattern_type == "bullish" and rsi < 30):
                    return {
                        "type": "exit",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_query[0].reference.path
                    }
                
                # Check for average down conditions
                if price >= entry_price * 1.02 and volume_analysis["high_volume"] and confidence > 80:
                    return {
                        "type": "avg_down_short",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_query[0].reference.path
                    }
        else:
            # No open position, check for new entry conditions
            if pattern_type == "bullish" and rsi < 30 and price_below_sma:
                return {
                    "type": "long",
                    "symbol": symbol,
                    "price": price,
                    "confidence": confidence,
                    "volume": volume
                }
                
            if pattern_type == "bearish" and rsi > 70 and not price_below_sma:
                return {
                    "type": "short",
                    "symbol": symbol,
                    "price": price,
                    "confidence": confidence,
                    "volume": volume
                }
                
        return None
        
    except Exception as e:
        logger.error(f"Error processing data for {symbol}: {str(e)}")
        return None
