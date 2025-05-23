import logging
import datetime
import pytz

# Use relative imports
from .technical_analysis import analyze_technicals
from .confidence_calculator import get_confidence_score
from .position_manager import get_open_position, is_in_cooldown_period, record_signal_ts
from .utils import is_market_hours # Assuming utils.py exists and is needed
from . import config

# Set up logging
logger = logging.getLogger(__name__)

def calculate_local_confidence(tech_results):
    """
    Calculates a basic, weighted confidence score based on technical indicators.
    This can serve as a fallback or input to a more advanced scorer (e.g., Gemini).
    Weights: Pattern=40, RSI=30, Volume=20, EMA=10
    """
    score = 0
    components = {}

    patterns = tech_results['raw_patterns_result']
    rsi = tech_results['rsi']
    volume_high = tech_results['volume_increase']
    ema = tech_results['ema']  # Changed from sma to ema
    price = tech_results['latest_close']

    # Pattern Score (Max 40)
    # Check for confirmed patterns
    is_bullish_pattern = patterns.get('confirmed_hammer', False) or patterns.get('confirmed_bullish_engulfing', False) or patterns.get('confirmed_morning_star', False)
    is_bearish_pattern = patterns.get('confirmed_shooting_star', False) or patterns.get('confirmed_bearish_engulfing', False) or patterns.get('confirmed_evening_star', False)
    if is_bullish_pattern or is_bearish_pattern:
        score += 40
        components['pattern'] = 40
    else:
        components['pattern'] = 0

    # RSI Score (Max 30)
    rsi_score = 0
    if is_bullish_pattern and rsi < config.RSI_OVERSOLD_THRESHOLD: # Oversold for long
        # Score based on how deep into oversold (max score at RSI 10 or less)
        rsi_score = max(0, min(1, (config.RSI_OVERSOLD_THRESHOLD - rsi) / 25)) * 30
    elif is_bearish_pattern and rsi > config.RSI_OVERBOUGHT_THRESHOLD: # Overbought for short
        # Score based on how deep into overbought (max score at RSI 90 or more)
        rsi_score = max(0, min(1, (rsi - config.RSI_OVERBOUGHT_THRESHOLD) / 25)) * 30
    score += rsi_score
    components['rsi'] = rsi_score

    # Volume Score (Max 20)
    if volume_high:
        score += 20
        components['volume'] = 20
    else:
        components['volume'] = 0

    # EMA Score (Max 10) - Changed from SMA
    # Check for trend alignment with pattern
    if is_bullish_pattern and price < ema:
        score += 10
        components['ema'] = 10
    elif is_bearish_pattern and price > ema:
        score += 10
        components['ema'] = 10
    else:
        components['ema'] = 0

    logger.debug(f"Local score components: {components}")
    return min(score, 100) # Cap score at 100

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
        price = tech_results['latest_close']
        patterns = tech_results['raw_patterns_result']
        rsi = tech_results['rsi']
        ema = tech_results['ema']
        is_high_volume = tech_results['volume_increase']
        atr_filter_passed = tech_results.get('atr_filter_passed', False)  # Add ATR filter check

        logger.info(f"{symbol} TA Results - Price: {price:.2f}, RSI: {rsi:.2f}, EMA: {ema:.2f}, HighVol: {is_high_volume}, ATR_filter: {atr_filter_passed}, Patterns: {patterns}")

        # 3. Check Position Status
        current_position = get_open_position(symbol, db)
        position_type = current_position["type"] if current_position else None
        entry_price = current_position["entry_price"] if current_position else None
        position_ref_path = current_position["ref_path"] if current_position else None # Assuming get_open_position returns ref path
        avg_down_count = current_position.get("avg_down_count", 0) if current_position else 0

        # 4. Determine Potential Signal Type based on patterns
        signal_intent = None
        is_bullish_pattern = patterns.get('confirmed_hammer', False) or patterns.get('confirmed_bullish_engulfing', False) or patterns.get('confirmed_morning_star', False)
        is_bearish_pattern = patterns.get('confirmed_shooting_star', False) or patterns.get('confirmed_bearish_engulfing', False) or patterns.get('confirmed_evening_star', False)

        if is_bullish_pattern:
            signal_intent = "LONG"
        elif is_bearish_pattern:
            signal_intent = "SHORT"
            
        # 5. Strict Condition Checks & Confidence Calculation
        local_confidence = 0 # Initialize
        final_signal = None
        
        # --- Logic for OPEN Positions ---
        if current_position:
            logger.info(f"Open {position_type} position found for {symbol} at {entry_price}.")
            # Calculate P/L (simple % for now)
            if position_type == "LONG":
                pnl_percent = ((price - entry_price) / entry_price) * 100
            elif position_type == "SHORT":
                pnl_percent = ((entry_price - price) / entry_price) * 100
            else: 
                pnl_percent = 0
            logger.info(f"{symbol} position PNL: {pnl_percent:.2f}%" )

            # --- EXIT Conditions ---
            exit_signal = False
            # Profit Target Exit (1-3% specified, let's use >= 2% for now)
            if pnl_percent >= 2.0:
                 logger.info(f"Exit condition met for {symbol}: Profit target reached.")
                 exit_signal = True
            # Reversal Signal Exit 
            elif position_type == "LONG" and is_bearish_pattern and rsi > config.RSI_OVERBOUGHT_THRESHOLD:
                 logger.info(f"Exit condition met for {symbol}: Bearish reversal pattern and RSI > 70.")
                 exit_signal = True
            elif position_type == "SHORT" and is_bullish_pattern and rsi < config.RSI_OVERSOLD_THRESHOLD:
                 logger.info(f"Exit condition met for {symbol}: Bullish reversal pattern and RSI < 30.")
                 exit_signal = True
                 
            if exit_signal:
                local_confidence = calculate_local_confidence(tech_results) # Recalculate for context
                # TODO: Optionally call Gemini/external scorer for exit confidence?
                final_signal = {
                    "type": "EXIT",
                        "symbol": symbol,
                        "price": price,
                    "confidence": local_confidence, # Or external score
                    "position_ref": position_ref_path
                    }
                
            # --- AVERAGE DOWN Conditions (Only if no exit signal) ---
            elif not exit_signal and avg_down_count < 2: # Limit avg down attempts
                 avg_down_signal = False
                 # Loss Target Check (-2%)
                 if pnl_percent <= -2.0:
                      # Check secondary conditions
                      if is_high_volume: # Require high volume
                           local_confidence = calculate_local_confidence(tech_results) # Recalculate
                           if local_confidence > config.CONFIDENCE_THRESHOLD: # Require confidence > threshold
                                logger.info(f"Average Down condition met for {symbol}: Loss target, high volume, high confidence.")
                                avg_down_signal = True
                                
                 if avg_down_signal:
                      final_signal = {
                           "type": f"AVG_DOWN_{position_type.upper()}", # e.g., AVG_DOWN_LONG
                        "symbol": symbol,
                        "price": price,
                           "confidence": local_confidence, # Or external score
                           "position_ref": position_ref_path
                      }
                          
            # --- AVERAGE UP Conditions (Only if no exit or avg down signal) ---
            # Note: Trailing stop logic is NOT handled here, needs separate mechanism
            elif not exit_signal and avg_down_count == 0: # Only avg up if not already averaged down? Maybe allow 1?
                 avg_up_signal = False
                 # Profit Target Check (+3%)
                 if pnl_percent >= 3.0:
                      if is_high_volume:
                           local_confidence = calculate_local_confidence(tech_results)
                           if local_confidence > config.CONFIDENCE_THRESHOLD:
                                logger.info(f"Average Up condition met for {symbol}: Profit target, high volume, high confidence.")
                                avg_up_signal = True
                                
                 if avg_up_signal:
                      final_signal = {
                           "type": f"AVG_UP_{position_type.upper()}", # e.g., AVG_UP_LONG
                        "symbol": symbol,
                        "price": price,
                           "confidence": local_confidence, # Or external score
                           "position_ref": position_ref_path 
                    }
                
        # --- Logic for NO Open Position (New Entries) ---
        else:
            logger.info(f"No open position found for {symbol}. Checking for new entry.")
            entry_signal_conditions_met = False
            final_signal_type = None # Will be LONG or SHORT
            
            if signal_intent == "LONG":
                # Check all strict conditions for LONG entry including ATR filter
                if rsi < config.RSI_OVERSOLD_THRESHOLD and is_high_volume and (price < ema) and atr_filter_passed:
                    logger.info(f"Potential LONG entry conditions met for {symbol}.")
                    entry_signal_conditions_met = True
                    final_signal_type = "LONG"
            elif signal_intent == "SHORT":
                 # Check all strict conditions for SHORT entry including ATR filter
                 if rsi > config.RSI_OVERBOUGHT_THRESHOLD and is_high_volume and (price > ema) and atr_filter_passed:
                     logger.info(f"Potential SHORT entry conditions met for {symbol}.")
                     entry_signal_conditions_met = True
                     final_signal_type = "SHORT"
                     
            if entry_signal_conditions_met:
                # Calculate local confidence first as a mandatory step / fallback
                local_confidence = calculate_local_confidence(tech_results)
                logger.info(f"Calculated local confidence for {symbol} {final_signal_type}: {local_confidence:.2f}")
                
                # Attempt to get Gemini confidence score
                logger.info(f"Attempting to get Gemini confidence score for {symbol} {final_signal_type}...")
                gemini_confidence = get_confidence_score(symbol, final_signal_type, tech_results)
                
                final_confidence = local_confidence # Default to local score
                if gemini_confidence is not None:
                    logger.info(f"Received Gemini confidence score: {gemini_confidence:.2f}")
                    final_confidence = gemini_confidence # Use Gemini score if available
                else:
                    logger.warning(f"Gemini confidence score failed for {symbol} {final_signal_type}. Falling back to local score: {local_confidence:.2f}")

                # Final check against threshold
                if final_confidence >= config.CONFIDENCE_THRESHOLD:
                     logger.info(f"{symbol} {final_signal_type} signal generated! Final Confidence: {final_confidence:.2f} >= {config.CONFIDENCE_THRESHOLD}")
                     final_signal = {
                          "type": final_signal_type,
                    "symbol": symbol,
                    "price": price,
                          "confidence": final_confidence,
                          # Include context for notification/saving?
                          "rsi": rsi,
                          "ema": ema,
                          "volume_ratio": tech_results['raw_volume_analysis'].get('volume_ratio', 1.0)
                          # TODO: Add long-term trend from external AI?
                     }
                else:
                    logger.info(f"{symbol} {final_signal_type} signal final confidence {final_confidence:.2f} below threshold {config.CONFIDENCE_THRESHOLD}.")

        # 6. Record Signal Timestamp (Only for new LONG/SHORT entries)
        if final_signal and final_signal['type'] in ["LONG", "SHORT"]:
             # Check if recording was successful, though we proceed anyway
             if not record_signal_ts(symbol, db):
                  logger.error(f"Failed to record signal timestamp for {symbol}, cooldown might not work correctly.")
             
        return final_signal
        
    except Exception as e:
        logger.exception(f"Error processing data for {symbol}: {e}") 
        return None
