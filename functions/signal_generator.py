import logging
import datetime
import pytz

# Use relative imports
from .technical_analysis import analyze_technicals
from .confidence_calculator import get_confidence_score, should_generate_signal
from .position_manager import get_open_position, is_in_cooldown_period, record_signal_ts
from .sentiment_analysis import get_sentiment_score, get_sentiment_confidence
from .utils import is_market_hours
from . import config

# Set up logging
logger = logging.getLogger(__name__)

def process_crypto_data(symbol, kline_data, db):
    """
    Processes crypto data, performs technical analysis, checks conditions,
    calculates confidence, and generates trading signals.
    """
    try:
        # 0. Market Hours Check
        current_time = datetime.datetime.now(pytz.UTC)
        if not is_market_hours(current_time):
            logger.info(f"Not in market hours, skipping {symbol}. Current time: {current_time.strftime('%H:%M:%S UTC')}")
            return None
            
        # 1. Cooldown Period Check
        if is_in_cooldown_period(symbol, db, config.SIGNAL_COOLDOWN_MINUTES):
            logger.info(f"{symbol} is in cooldown period. Skipping.")
            return None
        
        # 2. Perform Technical Analysis
        logger.info(f"Analyzing technicals for {symbol}...")
        tech_results = analyze_technicals(kline_data)
        if tech_results is None:
            logger.error(f"Technical analysis failed for {symbol}. Skipping.")
            return None
            
        # Extract key results
        price = tech_results.get('latest_close', 0)
        pattern = tech_results.get('pattern', {})
        rsi = tech_results.get('rsi', 50)
        ema = tech_results.get('ema', 0)
        volume_analysis = tech_results.get('volume_analysis', {})
        atr_filter = tech_results.get('atr_filter', False)

        # 3. Get Sentiment Analysis
        sentiment_score, sentiment_metrics = get_sentiment_score(symbol)
        sentiment_confidence = get_sentiment_confidence(sentiment_score, sentiment_metrics)

        logger.info(f"{symbol} TA Results - Price: {price:.2f}, RSI: {rsi:.2f}, EMA: {ema:.2f}")
        logger.info(f"Volume Analysis: {volume_analysis.get('volume_tier', 'UNKNOWN')} ({volume_analysis.get('volume_ratio', 0):.2f}x)")
        logger.info(f"Pattern: {pattern.get('pattern_name', 'N/A')}, ATR_filter: {atr_filter}")
        logger.info(f"Sentiment: Score={sentiment_score:.2f}, Confidence={sentiment_confidence:.2f}")

        # 4. Check Position Status
        current_position = get_open_position(symbol, db)
        position_type = current_position["type"] if current_position else None
        entry_price = current_position["entry_price"] if current_position else None
        position_ref_path = current_position["ref_path"] if current_position else None
        avg_down_count = current_position.get("avg_down_count", 0) if current_position else 0

        # 5. Determine Potential Signal Type based on patterns and sentiment
        signal_intent = None
        pattern_detected = pattern.get("pattern_detected_raw", False)
        pattern_type = pattern.get("pattern_type", "")
        
        if pattern_detected:
            if pattern_type == "bullish" and sentiment_score > 0:
                signal_intent = "LONG"
            elif pattern_type == "bearish" and sentiment_score < 0:
                signal_intent = "SHORT"
            
        # 6. Process Signals Based on Position Status
        final_signal = None
        
        # --- Logic for OPEN Positions ---
        if current_position:
            logger.info(f"Open {position_type} position found for {symbol} at {entry_price}.")
            
            # Calculate P/L
            if position_type == "LONG":
                pnl_percent = ((price - entry_price) / entry_price) * 100
            elif position_type == "SHORT":
                pnl_percent = ((entry_price - price) / entry_price) * 100
            else: 
                pnl_percent = 0
            logger.info(f"{symbol} position PNL: {pnl_percent:.2f}%")

            # --- EXIT Conditions ---
            exit_signal = False
            # Profit Target Exit
            if pnl_percent >= config.PROFIT_TARGET_PERCENT:
                logger.info(f"Exit condition met for {symbol}: Profit target reached.")
                exit_signal = True
            # Reversal Signal Exit with Sentiment Confirmation
            elif position_type == "LONG" and pattern_type == "bearish" and rsi > config.RSI_OVERBOUGHT_THRESHOLD and sentiment_score < 0:
                logger.info(f"Exit condition met for {symbol}: Bearish reversal pattern, RSI > 65, and bearish sentiment.")
                exit_signal = True
            elif position_type == "SHORT" and pattern_type == "bullish" and rsi < config.RSI_OVERSOLD_THRESHOLD and sentiment_score > 0:
                logger.info(f"Exit condition met for {symbol}: Bullish reversal pattern, RSI < 35, and bullish sentiment.")
                exit_signal = True
                 
            if exit_signal:
                # Calculate confidence for exit
                confidence = get_confidence_score(tech_results, sentiment_confidence)
                if should_generate_signal(confidence, "EXIT"):
                    final_signal = {
                        "type": "EXIT",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_ref_path,
                        "sentiment_score": sentiment_score,
                        "sentiment_metrics": sentiment_metrics
                    }
                
            # --- AVERAGE DOWN Conditions (Only if no exit signal) ---
            elif not exit_signal and avg_down_count < config.MAX_AVG_DOWN_COUNT:
                avg_down_signal = False
                # Loss Target Check with Sentiment Confirmation
                if pnl_percent <= -config.LOSS_TARGET_PERCENT:
                    # Check volume and sentiment conditions
                    if (volume_analysis.get('volume_tier') in ['ELEVATED', 'NORMAL'] and 
                        not volume_analysis.get('late_entry_warning', False) and
                        ((position_type == "LONG" and sentiment_score > 0) or 
                         (position_type == "SHORT" and sentiment_score < 0))):
                        confidence = get_confidence_score(tech_results, sentiment_confidence)
                        if should_generate_signal(confidence, f"AVG_DOWN_{position_type}"):
                            logger.info(f"Average Down condition met for {symbol}: Loss target, good volume, aligned sentiment, high confidence.")
                            avg_down_signal = True
                                
                if avg_down_signal:
                    final_signal = {
                        "type": f"AVG_DOWN_{position_type}",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_ref_path,
                        "sentiment_score": sentiment_score,
                        "sentiment_metrics": sentiment_metrics
                    }
                          
            # --- AVERAGE UP Conditions (Only if no exit or avg down signal) ---
            elif not exit_signal and avg_down_count == 0:
                avg_up_signal = False
                # Profit Target Check with Sentiment Confirmation
                if pnl_percent >= config.PROFIT_TARGET_PERCENT * 1.5:  # Higher threshold for averaging up
                    if (volume_analysis.get('volume_tier') in ['ELEVATED', 'NORMAL'] and 
                        not volume_analysis.get('late_entry_warning', False) and
                        ((position_type == "LONG" and sentiment_score > 0) or 
                         (position_type == "SHORT" and sentiment_score < 0))):
                        confidence = get_confidence_score(tech_results, sentiment_confidence)
                        if should_generate_signal(confidence, f"AVG_UP_{position_type}"):
                            logger.info(f"Average Up condition met for {symbol}: Profit target, good volume, aligned sentiment, high confidence.")
                            avg_up_signal = True
                                
                if avg_up_signal:
                    final_signal = {
                        "type": f"AVG_UP_{position_type}",
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "position_ref": position_ref_path,
                        "sentiment_score": sentiment_score,
                        "sentiment_metrics": sentiment_metrics
                    }
        
        # --- Logic for NEW Positions ---
        elif signal_intent and pattern_detected:
            # Check volume and sentiment conditions for new entries
            if (volume_analysis.get('volume_tier') in ['ELEVATED', 'NORMAL'] and 
                not volume_analysis.get('late_entry_warning', False) and
                ((signal_intent == "LONG" and sentiment_score > 0) or 
                 (signal_intent == "SHORT" and sentiment_score < 0))):
                # Calculate confidence using new system
                confidence = get_confidence_score(tech_results, sentiment_confidence)
                
                # Check if signal should be generated based on confidence
                if should_generate_signal(confidence, signal_intent):
                    logger.info(f"{symbol} {signal_intent} signal generated! Confidence: {confidence:.2f}")
                    final_signal = {
                        "type": signal_intent,
                        "symbol": symbol,
                        "price": price,
                        "confidence": confidence,
                        "rsi": rsi,
                        "ema": ema,
                        "volume_analysis": volume_analysis,
                        "pattern": pattern,
                        "atr_filter": atr_filter,
                        "sentiment_score": sentiment_score,
                        "sentiment_metrics": sentiment_metrics
                    }
                else:
                    logger.info(f"{symbol} {signal_intent} signal rejected. Confidence {confidence:.2f} below threshold.")

        # 7. Record Signal Timestamp (Only for new LONG/SHORT entries)
        if final_signal and final_signal['type'] in ["LONG", "SHORT"]:
            if not record_signal_ts(symbol, db):
                logger.error(f"Failed to record signal timestamp for {symbol}, cooldown might not work correctly.")
             
        return final_signal
        
    except Exception as e:
        logger.exception(f"Error processing data for {symbol}: {e}") 
        return None
