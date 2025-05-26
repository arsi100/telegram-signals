import logging
import datetime
import pytz
import json
import inspect
import pandas as pd
from google.cloud import firestore
from typing import Optional, Dict

# Use relative imports
from .technical_analysis import analyze_technicals
from .confidence_calculator import get_confidence_score, should_generate_signal
from .position_manager import get_open_position, is_in_cooldown_period
from .sentiment_analysis import get_sentiment_score, get_sentiment_confidence, calculate_directional_sentiment_adjustment
from .utils import is_market_hours
from . import config
from .gemini_analyzer import get_gemini_analysis

# Set up logging
logger = logging.getLogger(__name__)

def process_crypto_data(symbol: str, kline_data: pd.DataFrame, db: firestore.Client) -> Optional[Dict]:
    """
    Processes crypto data to generate trading signals, incorporating technical analysis,
    sentiment analysis, and potentially Gemini AI meta-analysis.
    Handles cooldown periods and checks for existing positions.
    Args:
        symbol: The cryptocurrency symbol (e.g., 'PF_ETHUSD').
        kline_data: Pandas DataFrame of OHLCV kline data.
        db: Firestore client for database interactions.
    Returns:
        A dictionary with signal details if a signal is generated, otherwise None.
    """
    logger.info(f"Processing {symbol} in signal_generator.process_crypto_data")

    # Initial data validation
    # Ensure kline_data is a DataFrame and has necessary data
    if not isinstance(kline_data, pd.DataFrame) or kline_data.empty:
        logger.warning(f"[{symbol}] Kline data is not a valid DataFrame or is empty in process_crypto_data.")
        return None
    if 'close' not in kline_data.columns:
        logger.warning(f"[{symbol}] 'close' column missing from kline data in process_crypto_data.")
        return None
    # Check if the 'close' column has any valid (non-NaN) data, especially the last one.
    if kline_data['close'].isnull().all():
        logger.warning(f"[{symbol}] All 'close' prices are NaN in process_crypto_data.")
        return None
    if pd.isna(kline_data['close'].iloc[-1]):
        logger.warning(f"[{symbol}] The last 'close' price is NaN in process_crypto_data.")
        return None
            
    # Cooldown Check
    if is_in_cooldown_period(symbol, db):
        logger.info(f"[{symbol}] is in cooldown period. Skipping signal generation.")
        return None
        
    # Get the latest close price from the DataFrame (already validated to exist and be non-NaN)
    latest_close = float(kline_data['close'].iloc[-1])

    technicals = analyze_technicals(kline_data, symbol=symbol, interval_str="5min")
    if not technicals:
        logger.warning(f"[{symbol}] Technical analysis failed or returned no data. Skipping signal generation.")
        return None
            
    rsi = float(technicals.get('rsi', 50.0))
    ema = float(technicals.get('ema', latest_close)) if technicals.get('ema') is not None else latest_close
    volume_analysis = technicals.get('volume_analysis', {})
    pattern = technicals.get('pattern', {})
    pattern_name = pattern.get("pattern_name", "N/A")
    pattern_type = pattern.get("pattern_type", "neutral") # "bullish", "bearish", "neutral"
    pattern_detected = pattern.get("pattern_detected_raw", False) # boolean

    # Get the single dictionary returned by get_sentiment_score
    sentiment_data_dict = get_sentiment_score(symbol)
    
    # Extract the raw sentiment score
    raw_sentiment_score = float(sentiment_data_dict.get('sentiment_score_raw', 0.0)) if sentiment_data_dict else 0.0
    
    # sentiment_metrics_dict is now essentially sentiment_data_dict itself, or parts of it.
    # For Gemini context, we will pass relevant parts of sentiment_data_dict later.

    # Initialize variables for rule-based signal generation
    rule_based_signal_intent = None  # "LONG", "SHORT"
    
    # --- Determine Rule-Based Signal Intent (Pre-Gemini) ---
    # Prioritize pattern_name if it's not "N/A", even if pattern_detected_raw (from latest confirmed/raw) is False
    # This allows us to react to patterns logged in summary (e.g. "hammer(1)") even if not on the very last candle
    if pattern_name != "N/A": # Check pattern_name first
        logger.debug(f"[SG_DEBUG_RULES] {symbol}: Pattern found by name - Name: {pattern_name}, Type: {pattern_type}. Raw Sentiment: {raw_sentiment_score:.2f}")
        # Simplified check: if pattern_type is bullish/bearish and sentiment aligns.
        if pattern_type == "bullish" and raw_sentiment_score >= config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN:
            rule_based_signal_intent = "LONG"
        elif pattern_type == "bearish" and raw_sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN:
            rule_based_signal_intent = "SHORT"
        # Add a specific check for raw patterns if the type isn't immediately bullish/bearish from pattern_type
        elif "hammer" in pattern_name.lower() and raw_sentiment_score >= config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN: # Catches "Raw Hammer"
            rule_based_signal_intent = "LONG"
            logger.debug(f"[SG_DEBUG_RULES] {symbol}: Caught raw bullish-like pattern by name: {pattern_name}")
        elif "shooting star" in pattern_name.lower() and raw_sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN: # Catches "Raw Shooting Star"
             rule_based_signal_intent = "SHORT"
             logger.debug(f"[SG_DEBUG_RULES] {symbol}: Caught raw bearish-like pattern by name: {pattern_name}")

    # Fallback to RSI/Sentiment if no pattern intent was derived from pattern_name
    if not rule_based_signal_intent:
        logger.debug(f"[SG_DEBUG_RULES] {symbol}: No pattern intent from name. Checking RSI/Sentiment. RSI: {rsi:.2f}, Raw Sentiment: {raw_sentiment_score:.2f}")
        
        # Condition for LONG in overbought bullish trend (Grok's suggestion)
        if rsi > config.RSI_OVERBOUGHT_THRESHOLD and latest_close > ema and raw_sentiment_score >= config.SENTIMENT_THRESHOLD_NEUTRAL:
            rule_based_signal_intent = "LONG"
            logger.info(f"[{symbol}] Rule-based LONG intent due to RSI overbought ({rsi:.2f} > {config.RSI_OVERBOUGHT_THRESHOLD}) with price > EMA and favorable sentiment.")
        # Original RSI-based LONG for non-overbought bullish conditions
        elif rsi > config.RSI_NEUTRAL_UPPER_BUFFER and raw_sentiment_score >= config.SENTIMENT_THRESHOLD_NEUTRAL: # e.g. RSI > 65 and sentiment not bearish
            rule_based_signal_intent = "LONG"
            logger.info(f"[{symbol}] Rule-based LONG intent due to RSI bullish ({rsi:.2f} > {config.RSI_NEUTRAL_UPPER_BUFFER}) and favorable sentiment.")
        # RSI-based SHORT for oversold bearish conditions
        elif rsi < config.RSI_NEUTRAL_LOWER_BUFFER and raw_sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_RSI_SHORT: # e.g. RSI < 35 and sentiment not bullish
            rule_based_signal_intent = "SHORT"
            logger.info(f"[{symbol}] Rule-based SHORT intent due to RSI bearish ({rsi:.2f} < {config.RSI_NEUTRAL_LOWER_BUFFER}) and favorable sentiment.")

    # Adjust sentiment score based on preliminary rule_based_signal_intent FOR RULE-BASED CONFIDENCE
    sentiment_score_for_rule_confidence = raw_sentiment_score
    if rule_based_signal_intent:
        sentiment_score_for_rule_confidence = calculate_directional_sentiment_adjustment(
            raw_score=raw_sentiment_score, # Pass the raw score directly
            signal_direction=rule_based_signal_intent, 
            multiplier=config.SENTIMENT_ADJUSTMENT_FACTORS.get(rule_based_signal_intent, {}).get("multiplier", 1.0),
            cap=config.SENTIMENT_ADJUSTMENT_FACTORS.get(rule_based_signal_intent, {}).get("cap", None)
        )
        logger.info(f"[{symbol}] Rule-based intent: {rule_based_signal_intent}. Raw sent: {raw_sentiment_score:.2f}, Adjusted sent for rule conf: {sentiment_score_for_rule_confidence:.2f}")
    
    # --- Prepare Data for Gemini Analysis ---
    gemini_analysis_result = None
    final_signal_source = "RULE_BASED" # Default source

    if config.ENABLE_GEMINI_ANALYSIS:
        logger.info(f"[{symbol}] Preparing data for Gemini analysis.")
        
        ohlcv_for_gemini = []
        # kline_data is already validated to be a non-empty DataFrame with required columns.
        # The 'timestamp' column in kline_data should be datetime objects at this point.
        # If not, ensure conversion or handle appropriately.
        df_for_gemini = kline_data.tail(config.GEMINI_KLINE_LIMIT)
        for index, row in df_for_gemini.iterrows():
            # Ensure timestamp is converted to a Unix timestamp integer for Gemini
            timestamp_val = row['timestamp']
            if isinstance(timestamp_val, pd.Timestamp):
                unix_timestamp = int(timestamp_val.timestamp())
            elif isinstance(timestamp_val, (int, float)): # Already a numeric timestamp
                unix_timestamp = int(timestamp_val)
            else: 
                logger.warning(f"[{symbol}] Unexpected timestamp format in df_for_gemini: {type(timestamp_val)}. Skipping row for Gemini.")
                continue # Or handle as an error
                
            ohlcv_for_gemini.append([
                unix_timestamp,
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['volume'])
            ])
        
        ta_indicators_for_gemini = {
            "rsi": rsi, "ema_20": ema, "atr": float(technicals.get('atr', 0.0)),
            "volume_tier": volume_analysis.get('volume_tier', 'UNKNOWN'),
            "volume_ratio": float(volume_analysis.get('volume_ratio', 0.0)),
            "candlestick_pattern": pattern_name if pattern_name != "N/A" else None,
            "candlestick_type": pattern_type if pattern_type != "neutral" else None
        }
        
        # Use sentiment_data_dict for detailed LunarCrush fields for Gemini
        sentiment_for_gemini = {
            "lc_galaxy_score": float(sentiment_data_dict.get('galaxy_score')) if sentiment_data_dict and sentiment_data_dict.get('galaxy_score') is not None else None,
            "lc_alt_rank": int(sentiment_data_dict.get('alt_rank')) if sentiment_data_dict and sentiment_data_dict.get('alt_rank') is not None else None,
            "lc_social_volume_24h": float(sentiment_data_dict.get('social_volume_24h')) if sentiment_data_dict and sentiment_data_dict.get('social_volume_24h') is not None else None,
            # "lc_social_score_24h": float(sentiment_data_dict.get('social_score_24h')) if sentiment_data_dict and sentiment_data_dict.get('social_score_24h') is not None else None, # This key might not exist, check LunarCrush output
            "calculated_sentiment_score_raw": raw_sentiment_score 
        }

        open_pos_for_gemini = get_open_position(symbol, db)
        position_context_for_gemini = {
            "current_position_type": open_pos_for_gemini['type'] if open_pos_for_gemini else None,
            "entry_price": float(open_pos_for_gemini['entry_price']) if open_pos_for_gemini and open_pos_for_gemini.get('entry_price') is not None else None,
            "unrealized_pnl_pct": float(open_pos_for_gemini.get('unrealized_pnl_pct', 0.0)) if open_pos_for_gemini and open_pos_for_gemini.get('unrealized_pnl_pct') is not None else None,
            "avg_down_count": int(open_pos_for_gemini.get('avg_down_count', 0)) if open_pos_for_gemini else 0
        }
        
        latest_timestamp_for_gemini = None
        if ohlcv_for_gemini and not kline_data.empty and 'timestamp' in kline_data.columns:
            # The 'timestamp' column in kline_data should be datetime objects.
            # Convert the latest one to Unix timestamp for Gemini.
            ts_val = kline_data['timestamp'].iloc[-1]
            if isinstance(ts_val, pd.Timestamp):
                latest_timestamp_for_gemini = int(ts_val.timestamp())
            elif isinstance(ts_val, (int, float)):
                latest_timestamp_for_gemini = int(ts_val) # Already a numeric timestamp
            else:
                logger.warning(f"[{symbol}] Unexpected latest timestamp format for Gemini: {type(ts_val)}")

        market_data_for_gemini = {
            "pair": symbol,
            "timestamp_utc_latest_candle": latest_timestamp_for_gemini,
            "ohlcv_5min_last_n_candles": ohlcv_for_gemini,
            "technical_indicators": ta_indicators_for_gemini,
            "sentiment_analysis_data": sentiment_for_gemini,
            "current_position_context": position_context_for_gemini,
            # "additional_notes": "Consider overall market trends and recent news if available through other tools."
        }
        
        try:
            market_data_json_str = json.dumps(market_data_for_gemini)
            # --- DEBUGGING IMPORT --- 
            try:
                gemini_func_file = inspect.getsourcefile(get_gemini_analysis)
                logger.info(f"[{symbol}] DEBUG: get_gemini_analysis is from file: {gemini_func_file}")
            except Exception as inspect_e:
                logger.error(f"[{symbol}] DEBUG: Error inspecting get_gemini_analysis: {inspect_e}")
            # --- END DEBUGGING IMPORT ---
            logger.info(f"[{symbol}] Calling Gemini for analysis...")
            gemini_analysis_result = get_gemini_analysis(market_data_json_str, symbol)
            
            if gemini_analysis_result and isinstance(gemini_analysis_result, dict):
                logger.info(f"[{symbol}] Gemini Analysis Received: Signal={gemini_analysis_result.get('signal_type')}, Conf={gemini_analysis_result.get('confidence')}, Rationale={gemini_analysis_result.get('rationale')}")
            else:
                logger.warning(f"[{symbol}] Gemini analysis returned None or invalid. Proceeding with rule-based logic only.")
        except TypeError as te:
            logger.error(f"[{symbol}] TypeError during JSON serialization for Gemini: {te}. Data sample: {str(market_data_for_gemini)[:300]}...", exc_info=True)
        except Exception as e:
            logger.error(f"[{symbol}] Error during Gemini data preparation or call: {e}", exc_info=True)
    else:
        logger.info(f"[{symbol}] Gemini analysis is disabled. Using rule-based logic only.")

    # --- Determine Final Signal Intent and Confidence ---
    final_signal_details = None 
    open_pos = get_open_position(symbol, db) # Get current position status for decision making

    # Decide if Gemini's signal will be used
    use_gemini_signal = False
    if config.ENABLE_GEMINI_ANALYSIS and gemini_analysis_result and isinstance(gemini_analysis_result, dict):
        gemini_signal_type = gemini_analysis_result.get("signal_type", "").upper()
        gemini_confidence = float(gemini_analysis_result.get("confidence", 0.0))
        
        if gemini_signal_type in ["LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", "EXIT"] and \
           gemini_confidence >= config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE:
            use_gemini_signal = True
            final_signal_source = "GEMINI_AI"
            logger.info(f"[{symbol}] Gemini signal '{gemini_signal_type}' (conf: {gemini_confidence:.2f}) meets override threshold {config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE}. Will use Gemini signal.")
        elif gemini_signal_type in ["LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", "EXIT"]:
             logger.info(f"[{symbol}] Gemini signal '{gemini_signal_type}' (conf: {gemini_confidence:.2f}) is below override threshold {config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE}. Evaluating rule-based signal.")
        else: # NEUTRAL or missing/invalid signal type
            logger.info(f"[{symbol}] Gemini signal is '{gemini_signal_type}' (conf: {gemini_confidence:.2f}) or invalid. Evaluating rule-based signal.")

    if use_gemini_signal:
        signal_intent = gemini_analysis_result.get("signal_type").upper() # LONG, SHORT, EXIT, EXIT_LONG, EXIT_SHORT
        # Map simple "EXIT" from Gemini to specific EXIT_LONG/EXIT_SHORT if a position is open
        if signal_intent == "EXIT" and open_pos:
            signal_intent = f"EXIT_{open_pos['type']}"
        elif signal_intent == "EXIT" and not open_pos:
            logger.warning(f"[{symbol}] Gemini suggested EXIT but no open position found. Treating as NEUTRAL.")
            signal_intent = "NEUTRAL" # Or handle as an error/ignore

        if signal_intent != "NEUTRAL":
            final_confidence = float(gemini_analysis_result.get("confidence", 0.0)) * 100.0 # SCALED HERE
            final_signal_details = {
                "symbol": symbol, "type": signal_intent, "price": latest_close, 
                "confidence": final_confidence, "source": final_signal_source,
                "rsi": rsi, "sentiment_score_raw": raw_sentiment_score, # Log raw sentiment used by Gemini
                "pattern_name": pattern_name, "volume_tier": volume_analysis.get('volume_tier', 'UNKNOWN'),
                "gemini_rationale": gemini_analysis_result.get("rationale", []),
                "gemini_price_targets": gemini_analysis_result.get("price_targets"),
                "gemini_position_size_pct": gemini_analysis_result.get("position_size_pct")
            }
            if open_pos and "EXIT" in signal_intent:
                final_signal_details["original_position_id"] = open_pos['id']
            logger.info(f"[{symbol}] Using Gemini Signal: Type={signal_intent}, Price={latest_close:.2f}, Confidence={final_confidence:.4f}")
        else: # Gemini said NEUTRAL or EXIT on no position
             logger.info(f"[{symbol}] Gemini suggested NEUTRAL or unfulfillable EXIT. No Gemini signal generated.")


    # Fallback to rule-based logic or if Gemini signal is not used / not actionable
    if not final_signal_details: # Covers cases where Gemini is off, failed, or its signal wasn't used
        logger.info(f"[{symbol}] Using rule-based signal logic. Preliminary intent: {rule_based_signal_intent}")
        final_signal_source = "RULE_BASED" # Ensure source is rule-based if we reach here
        
        if open_pos:
            logger.info(f"[{symbol}] Rule-based: Open position ({open_pos['type']}) found. Evaluating for EXIT.")
            exit_signal_intent = None
            if open_pos['type'] == 'LONG':
                if ((pattern_type == "bearish" and sentiment_score_for_rule_confidence <= config.SENTIMENT_THRESHOLD_EXIT_STRONG_NEGATIVE) or 
                   (rsi >= config.RSI_OVERBOUGHT_THRESHOLD - config.RSI_NEUTRAL_ZONE_BUFFER and sentiment_score_for_rule_confidence < config.SENTIMENT_THRESHOLD_EXIT_NEGATIVE)):
                    exit_signal_intent = "EXIT_LONG"
            elif open_pos['type'] == 'SHORT':
                if ((pattern_type == "bullish" and sentiment_score_for_rule_confidence >= config.SENTIMENT_THRESHOLD_EXIT_STRONG_POSITIVE) or 
                   (rsi <= config.RSI_OVERSOLD_THRESHOLD + config.RSI_NEUTRAL_ZONE_BUFFER and sentiment_score_for_rule_confidence > config.SENTIMENT_THRESHOLD_EXIT_POSITIVE)):
                    exit_signal_intent = "EXIT_SHORT"

            if exit_signal_intent:
                # Use the pre-weighted sentiment contribution from sentiment_analysis.py
                sentiment_contribution_for_total_score = sentiment_data_dict.get('sentiment_confidence_final_RULE_WEIGHTED', 0.0)
                logger.debug(f"[{symbol}] For EXIT intent {exit_signal_intent}, using sentiment_confidence_final_RULE_WEIGHTED: {sentiment_contribution_for_total_score:.4f}")

                rule_based_confidence = get_confidence_score(
                    tech_results=technicals, # Pass the whole technicals dict
                    sentiment_confidence=sentiment_contribution_for_total_score, # Use the value weighted by 'sentiment_overall_contribution'
                    signal_direction=exit_signal_intent # Pass exit_signal_intent
                )
                final_signal_details = {
                    "symbol": symbol, "type": exit_signal_intent, "price": latest_close, 
                    "confidence": rule_based_confidence, "source": final_signal_source + "_EXIT",
                    "rsi": rsi, "sentiment_score": sentiment_score_for_rule_confidence, 
                    "pattern_name": pattern_name, "volume_tier": volume_analysis.get('volume_tier', 'UNKNOWN'),
                    "original_position_id": open_pos['id']
                }
                logger.info(f"[{symbol}] Rule-Based EXIT Signal: Type={exit_signal_intent}, Price={latest_close:.2f}, Confidence={rule_based_confidence:.4f}")
            else: # This else corresponds to 'if exit_signal_intent:'
                logger.info(f"[{symbol}] Rule-based: No EXIT condition met for open {open_pos['type']} position.")
        
        elif rule_based_signal_intent: # Rule-based LONG or SHORT intent for NEW position; this elif corresponds to 'if open_pos:'
            logger.debug(f"[SG_DEBUG_RULES] {symbol}: Evaluating NEW rule-based position for intent: {rule_based_signal_intent}")
            current_volume_tier = volume_analysis.get('volume_tier', 'UNKNOWN')
            
            # Refined volume_tier_ok logic for Step 2
            volume_tier_ok = current_volume_tier not in ['UNKNOWN'] and (
                current_volume_tier != 'VERY_LOW' or
                (current_volume_tier == 'VERY_LOW' and (
                    # Allow VERY_LOW if RSI is strong for the intent direction AND price confirms trend vs EMA
                    (rsi > config.RSI_OVERBOUGHT_THRESHOLD and latest_close > ema and rule_based_signal_intent == "LONG") or 
                    (rsi < config.RSI_OVERSOLD_THRESHOLD and latest_close < ema and rule_based_signal_intent == "SHORT")
                ))
            )
            
            late_warning = volume_analysis.get('late_entry_warning', False)
            
            sentiment_aligned_for_rule = False
            if rule_based_signal_intent == "LONG":
                sentiment_aligned_for_rule = sentiment_score_for_rule_confidence >= config.SENTIMENT_THRESHOLD_NEUTRAL 
            elif rule_based_signal_intent == "SHORT":
                sentiment_aligned_for_rule = sentiment_score_for_rule_confidence <= config.SENTIMENT_THRESHOLD_FOR_RSI_SHORT
            
            logger.debug(f"[SG_DEBUG_RULES] {symbol}: Checks for NEW rule-based {rule_based_signal_intent}: Vol Tier='{current_volume_tier}'(OK={volume_tier_ok}), Sent Aligned={sentiment_aligned_for_rule}(Score={sentiment_score_for_rule_confidence:.2f}), Late Warn={late_warning}")

            is_late = config.AVOID_LATE_ENTRIES and late_warning
            logger.info(f"[{symbol}] generate_signal_from_intent PRE-CHECK: intent={rule_based_signal_intent}, is_sentiment_aligned={sentiment_aligned_for_rule}, is_volume_sufficient={volume_tier_ok}, is_late={is_late} (config.AVOID_LATE_ENTRIES={config.AVOID_LATE_ENTRIES})")

            if not (sentiment_aligned_for_rule and volume_tier_ok and not is_late):
                logger.info(f"[{symbol}] Conditions for rule-based NEW {rule_based_signal_intent} signal not met (Sentiment Align: {sentiment_aligned_for_rule}, Volume Suff: {volume_tier_ok}, Not Late: {not is_late}).")
                # Removed erroneous return None here; if conditions not met, it will fall through to the end and return None if final_signal_details is still None
            else: # Conditions ARE met for a new rule-based signal
                # Use the pre-weighted sentiment contribution from sentiment_analysis.py
                sentiment_contribution_for_total_score = sentiment_data_dict.get('sentiment_confidence_final_RULE_WEIGHTED', 0.0)
                logger.debug(f"[{symbol}] For NEW intent {rule_based_signal_intent}, using sentiment_confidence_final_RULE_WEIGHTED: {sentiment_contribution_for_total_score:.4f}")
                
                rule_based_confidence = get_confidence_score(
                    tech_results=technicals, # Pass the whole technicals dict
                    sentiment_confidence=sentiment_contribution_for_total_score, # Use the value weighted by 'sentiment_overall_contribution'
                    signal_direction=rule_based_signal_intent # Pass rule_based_signal_intent
                )
                # Ensure rule_based_confidence is a float for logging, 
                # especially if get_confidence_score was mocked and might not be called as expected in some test paths.
                log_confidence_val = rule_based_confidence if isinstance(rule_based_confidence, (int, float)) else str(rule_based_confidence)
                logger.info(f"[{symbol}] Rule-based new signal intent: {rule_based_signal_intent}, Calculated Confidence: {log_confidence_val if isinstance(log_confidence_val, str) else f'{log_confidence_val:.4f}'}")

                if should_generate_signal(confidence=rule_based_confidence, signal_type=rule_based_signal_intent):
                    final_signal_details = {
                        "symbol": symbol, "type": rule_based_signal_intent, "price": latest_close,
                        "confidence": rule_based_confidence, "source": final_signal_source + "_NEW",
                        "rsi": rsi, "sentiment_score": sentiment_score_for_rule_confidence,
                        "pattern_name": pattern_name, "volume_tier": current_volume_tier,
                    }
                    logger.info(f"[{symbol}] Rule-Based NEW Signal: Type={rule_based_signal_intent}, Price={latest_close:.2f}, Confidence={rule_based_confidence:.4f}")
                else:
                    logger.info(f"[{symbol}] Rule-based signal confidence {rule_based_confidence:.4f} for {rule_based_signal_intent} is below MIN_CONFIDENCE_ENTRY {config.MIN_CONFIDENCE_ENTRY}.")
        else: # This else corresponds to 'elif rule_based_signal_intent:' (and implicitly 'if open_pos:')
            logger.info(f"[{symbol}] No rule-based signal intent determined (pattern or RSI/Sentiment) and no open position for EXIT.")

    # --- Final Signal Output ---
    # Grok Step 3: Logging for exit signal confidence check validation
    if final_signal_details:
        log_signal_type = final_signal_details.get("type", "UNKNOWN_TYPE")
        log_confidence = final_signal_details.get("confidence", 0.0)
        log_required_threshold = config.MIN_CONFIDENCE_EXIT if "EXIT" in log_signal_type else config.MIN_CONFIDENCE_ENTRY
        logger.debug(f"[{symbol}] Final check PRE-should_generate_signal: Signal={log_signal_type}, Conf={log_confidence:.2f}, ReqThreshold={log_required_threshold:.2f}, Source={final_signal_details.get('source')}")

    if final_signal_details and should_generate_signal(confidence=final_signal_details.get("confidence", 0.0), signal_type=final_signal_details.get("type")):
        # Ensure essential fields from Gemini are carried over if it was the source
        if final_signal_details.get("source") == "GEMINI_AI" and gemini_analysis_result:
            final_signal_details["gemini_rationale"] = gemini_analysis_result.get("rationale", [])
            final_signal_details["gemini_price_targets"] = gemini_analysis_result.get("price_targets")
            final_signal_details["gemini_position_size_pct"] = gemini_analysis_result.get("position_size_pct")
        
        logger.info(f"[{symbol}] Final signal generated ({final_signal_details.get('source')}): {final_signal_details.get('type')} with conf {final_signal_details.get('confidence'):.4f}")
        return final_signal_details
    elif final_signal_details: 
        # Log still needs to be more informative about which threshold was missed
        signal_type_for_log = final_signal_details.get("type", "UNKNOWN_TYPE")
        required_conf_for_log = config.MIN_CONFIDENCE_EXIT if "EXIT" in signal_type_for_log else config.MIN_CONFIDENCE_ENTRY
        logger.info(f"[{symbol}] Final signal ({final_signal_details.get('source')}) for {signal_type_for_log} with confidence {final_signal_details.get('confidence', 0):.4f} was below required threshold {required_conf_for_log:.2f}. No signal.")
        return None
    else:
        logger.info(f"[{symbol}] No actionable signal generated (neither Gemini nor rule-based met criteria).")
        return None

def is_sentiment_aligned_for_signal(score: float, intent: str, config_module) -> bool:
    """
    Checks if the sentiment score aligns with the signal intent based on config thresholds.
    """
    aligned = False
    if intent == "LONG":
        threshold = config_module.SENTIMENT_THRESHOLD_NEUTRAL
        aligned = score >= threshold
        logger.debug(f"is_sentiment_aligned_for_signal (LONG): score={score}, threshold={threshold}, aligned={aligned}") # DEBUG LOG
    elif intent == "SHORT":
        threshold = config_module.SENTIMENT_THRESHOLD_FOR_RSI_SHORT
        aligned = score <= threshold
        logger.debug(f"is_sentiment_aligned_for_signal (SHORT): score={score}, threshold={threshold}, aligned={aligned}") # DEBUG LOG
    return aligned
