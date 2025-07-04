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

def process_crypto_data(symbol: str, db: firestore.Client, kline_data_15m: pd.DataFrame, kline_data_4h: pd.DataFrame) -> Optional[Dict]:
    """
    Processes crypto data to generate trading signals based on the validated 15m/4h strategy.
    """
    logger.info(f"[{symbol}] Starting signal generation process for 15m/4h strategy.")

    # Data is now passed in, no need to fetch.
    # The check below is now also redundant if we ensure data is passed correctly.
    # if not kline_data_15m or not kline_data_4h:
    #     logger.warning(f"[{symbol}] Could not fetch sufficient kline data for one or both timeframes. Aborting.")
    #     return None

    # --- 2. Cooldown and Position Check ---
    if is_in_cooldown_period(symbol, db):
        logger.info(f"[{symbol}] is in cooldown period. Skipping signal generation.")
        return None
        
    if get_open_position(symbol, db):
        logger.info(f"[{symbol}] already has an open position. Skipping signal generation.")
        return None

    # --- 3. Technical Analysis ---
    technicals = analyze_technicals(kline_data_15m, kline_data_4h, symbol=symbol)
    
    if not technicals:
        logger.warning(f"[{symbol}] Technical analysis failed or returned no data. Skipping signal generation.")
        return None

    # --- 4. Strategy Rule Engine ---
    signal_intent = None
    
    # Core conditions from the validated backtest
    is_macro_bullish = technicals['close'] > technicals['ema_4h']
    is_micro_bullish = technicals['close'] > technicals['ema_10']
    is_rsi_strong = technicals['rsi'] > 50 and technicals['rsi'] < 60
    is_rsi_slope_positive = technicals['rsi_slope'] > 0
    is_volume_high = technicals['vol_z'] > 1.0
    is_close_to_ema = technicals['dist_to_ema10'] < 1.0

    # Coin-specific rule
    is_bullish_candle_required = symbol in ['SOLUSDT', 'CROUSDT']
    passes_bullish_candle_filter = (not is_bullish_candle_required) or (is_bullish_candle_required and technicals['is_bullish'])

    # Combine all conditions
    if (is_macro_bullish and is_micro_bullish and is_rsi_strong and 
        is_rsi_slope_positive and is_volume_high and is_close_to_ema and
        passes_bullish_candle_filter):
        signal_intent = "LONG"
        logger.info(f"[{symbol}] LONG signal generated based on validated 15m/4h strategy.")
    else:
        # Log why no signal was generated for debugging
        logger.info(f"[{symbol}] No signal generated. Conditions check: macro_bullish={is_macro_bullish}, micro_bullish={is_micro_bullish}, rsi_strong={is_rsi_strong}, rsi_slope_pos={is_rsi_slope_positive}, vol_high={is_volume_high}, close_to_ema={is_close_to_ema}, candle_filter={passes_bullish_candle_filter}")
        return None

    # --- 5. Signal Generation ---
    # At this point, signal_intent is "LONG". We can now build the signal object.
    # The original function had complex confidence scoring. We are bypassing that
    # with our high-conviction signal. We can assign a static high confidence.
    confidence = 95.0 # Static confidence for our validated strategy
    final_signal_source = "MICRO_SCALP_V2" # A name for the new strategy

    signal_details = {
        "symbol": symbol,
        "signal_type": signal_intent,
        "source": final_signal_source,
        "confidence": confidence,
        "timestamp": datetime.datetime.now(pytz.utc).isoformat(),
        "price_at_signal": technicals['close'],
        "technicals": { # Include key technicals for context
            "rsi": technicals.get('rsi'),
            "ema_10": technicals.get('ema_10'),
            "ema_4h": technicals.get('ema_4h'),
            "volume_z_score": technicals.get('vol_z'),
            "rsi_slope": technicals.get('rsi_slope')
        },
        "tp_price": technicals['close'] * 1.005, # +0.5% TP
        "sl_price": technicals['close'] * 0.985, # -1.5% SL
    }

    logger.info(f"[{symbol}] Final signal object created: {signal_details}")
    return signal_details


def process_crypto_data_original(symbol: str, kline_data: pd.DataFrame, db: firestore.Client) -> Optional[Dict]:
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

    # Check if we're in market hours
    if not is_market_hours():
        logger.info(f"[{symbol}] Outside market hours. Skipping signal generation.")
        return None

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
        gemini_signal_type = gemini_analysis_result.get("signal_type", "").upper() # Ensure it's upper for reliable comparison
        gemini_confidence_raw = gemini_analysis_result.get("confidence", 0.0) # Raw confidence from Gemini (0-1 or 0-100)
        gemini_confidence_scaled = gemini_confidence_raw * 100 if gemini_confidence_raw <= 1.0 else gemini_confidence_raw

        gemini_rationale = gemini_analysis_result.get("rationale", "N/A")
        gemini_price_targets = gemini_analysis_result.get("price_targets", {}) # Grok's addition
        
        logger.debug(f"[{symbol}] Gemini Raw Output: Type='{gemini_signal_type}', ConfRaw={gemini_confidence_raw}, ConfScaled={gemini_confidence_scaled:.2f}, Targets={gemini_price_targets}")

        if gemini_signal_type in ["LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", "EXIT"] and \
           gemini_confidence_raw >= config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE: # Compare raw 0-1 confidence from Gemini
            use_gemini_signal = True
            final_signal_source = "GEMINI_AI"
            logger.info(f"[{symbol}] Gemini signal '{gemini_signal_type}' (raw conf: {gemini_confidence_raw:.2f}) meets override threshold {config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE}. Will use Gemini signal.")
            
            if gemini_signal_type in ["LONG", "EXIT_SHORT"]:
                # Corrected constant names to match config.py
                default_tp = latest_close * (1 + config.PROFIT_TARGET_PERCENT / 100)
                default_sl = latest_close * (1 - config.LOSS_TARGET_PERCENT / 100)
            elif gemini_signal_type in ["SHORT", "EXIT_LONG"]:
                # Corrected constant names to match config.py
                default_tp = latest_close * (1 - config.PROFIT_TARGET_PERCENT / 100)
                default_sl = latest_close * (1 + config.LOSS_TARGET_PERCENT / 100)
            else: 
                default_tp = None
                default_sl = None

            take_profit = gemini_price_targets.get("take_profit", default_tp)
            stop_loss = gemini_price_targets.get("stop_loss", default_sl)
            
            final_signal_details = {
                "signal_type": gemini_signal_type,
                "price": latest_close,
                "confidence_score": gemini_confidence_scaled,
                "source": final_signal_source,
                "reasoning": gemini_rationale,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "rsi": rsi, 
                "sentiment_score_raw": raw_sentiment_score,
                "pattern_name": pattern_name if pattern_name != "N/A" else "N/A",
                "volume_tier": volume_analysis.get('volume_tier', 'UNKNOWN'),
                "rule_based_intent": rule_based_signal_intent
            }
            logger.info(f"[{symbol}] Using Gemini signal: {final_signal_details}")

        elif gemini_signal_type in ["LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", "EXIT"]:
             logger.info(f"[{symbol}] Gemini signal '{gemini_signal_type}' (raw conf: {gemini_confidence_raw:.2f}) is Present BUT below override threshold {config.GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE}. Evaluating rule-based signal.")
        else: 
            logger.info(f"[{symbol}] Gemini signal is '{gemini_signal_type}' (conf: {gemini_confidence_raw:.2f}) or invalid. Evaluating rule-based signal.")

    # --- Rule-Based Signal Generation (if Gemini not used or below threshold) ---
    if not use_gemini_signal and rule_based_signal_intent:
        logger.info(f"[{symbol}] Proceeding with rule-based signal intent: {rule_based_signal_intent}.")
        
        current_confidence_score = get_confidence_score(
            tech_results=technicals, # Pass the entire technicals dictionary
            sentiment_confidence=sentiment_score_for_rule_confidence, # Pass the calculated sentiment score
            signal_direction=rule_based_signal_intent # Pass the determined signal intent ("LONG" or "SHORT")
        )
        logger.info(f"[{symbol}] Rule-based '{rule_based_signal_intent}' confidence score: {current_confidence_score:.2f}")

        # Initialize rule_based_tp and rule_based_sl before they are potentially assigned
        rule_based_tp = None
        rule_based_sl = None

        if rule_based_signal_intent == "LONG":
            rule_based_tp = latest_close * (1 + config.PROFIT_TARGET_PERCENT / 100)
            rule_based_sl = latest_close * (1 - config.LOSS_TARGET_PERCENT / 100)
        elif rule_based_signal_intent == "SHORT":
            rule_based_tp = latest_close * (1 - config.PROFIT_TARGET_PERCENT / 100)
            rule_based_sl = latest_close * (1 + config.LOSS_TARGET_PERCENT / 100)

        final_signal_type_for_rule = rule_based_signal_intent # Initialize with the intent

        if open_pos:
            logger.info(f"[{symbol}] Open position exists: {open_pos['type']}. Rule-based intent: {rule_based_signal_intent}.")
            if (open_pos['type'] == "LONG" and rule_based_signal_intent == "SHORT") or \
               (open_pos['type'] == "SHORT" and rule_based_signal_intent == "LONG"):
                final_signal_type_for_rule = f"EXIT_{open_pos['type']}"
                logger.info(f"[{symbol}] Rule-based intent {rule_based_signal_intent} suggests exiting existing {open_pos['type']} position. Final type: {final_signal_type_for_rule}")
                rule_based_tp = None 
                rule_based_sl = None 
            else:
                logger.info(f"[{symbol}] Rule-based intent '{rule_based_signal_intent}' matches or is not opposite to open position '{open_pos['type']}'. No rule-based entry/exit signal generated by this logic block.")
                rule_based_signal_intent = None 
        
        # Call should_generate_signal with confidence and the determined signal type (e.g., LONG, SHORT, EXIT_LONG)
        if rule_based_signal_intent and should_generate_signal(current_confidence_score, final_signal_type_for_rule):
            final_signal_details = {
                "signal_type": final_signal_type_for_rule,
                "price": latest_close,
                "confidence_score": current_confidence_score,
                "source": "RULE_BASED",
                "rsi": rsi,
                "sentiment_score_adjusted": sentiment_score_for_rule_confidence,
                "sentiment_score_raw": raw_sentiment_score,
                "pattern_name": pattern_name if pattern_name != "N/A" else "N/A",
                "pattern_type": pattern_type if pattern_type != "neutral" else "N/A",
                "volume_tier": technicals.get('volume_analysis', {}).get('volume_tier', 'UNKNOWN'),
                "primary_trend": technicals.get('primary_trend', 'UNKNOWN'),
                "take_profit": rule_based_tp,
                "stop_loss": rule_based_sl
            }
            # Add reason_for_exit if it's an exit signal
            if final_signal_type_for_rule.startswith("EXIT_"):
                final_signal_details["reason_for_exit"] = "Rule-based exit criteria met."
                logger.info(f"[{symbol}] Generating RULE-BASED EXIT signal: {final_signal_details}")
            else:
                logger.info(f"[{symbol}] Generating RULE-BASED ENTRY signal: {final_signal_details}")
        else:
            # This block is entered if rule_based_signal_intent was None OR should_generate_signal returned False
            if rule_based_signal_intent: # Log only if there was an intent but it didn't pass confidence
                logger.info(f"[{symbol}] Rule-based signal type '{final_signal_type_for_rule}' (original intent: {rule_based_signal_intent}, context: {open_pos['type'] if open_pos else 'new'}) with confidence {current_confidence_score:.2f} did NOT meet threshold via should_generate_signal. No rule-based signal generated.")
            # If rule_based_signal_intent was None initially, it means basic criteria (pattern/RSI + sentiment) were not met to even form an intent.
            # This case is implicitly handled as final_signal_details remains None.

    # --- Final Signal Processing & Return ---
    if final_signal_details:
        final_signal_details['symbol'] = symbol 
        final_signal_details['latest_kline_timestamp_utc'] = technicals.get('latest_timestamp').isoformat() if technicals.get('latest_timestamp') else datetime.datetime.now(pytz.utc).isoformat()
        
        logger.info(f"[{symbol}] Final signal generated: Type={final_signal_details['signal_type']}, Price={final_signal_details['price']}, Conf={final_signal_details['confidence_score']:.2f}, Source={final_signal_details['source']}")
        return final_signal_details
    else:
        logger.info(f"[{symbol}] No signal generated after all checks (Gemini and Rule-based).")
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
