# main.py
# Last modified: 2025-05-21 - Force rebuild for Telegram secret refresh
# Last modified: 2025-05-21 - Force rebuild
import functions_framework
import logging
import os
import sys

# Configure logging (original position)
log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=log_format, force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Global flags and db client
IMPORTS_SUCCESSFUL = False
FIREBASE_INITIALIZED = False
db = None

# Import and initialize Firebase at the top level
try:
    print("***** MAIN.PY TOP LEVEL: START OF TRY BLOCK *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'import firebase_admin'... *****")
    import firebase_admin
    print("***** MAIN.PY TOP LEVEL: 'import firebase_admin' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from firebase_admin import credentials, firestore'... *****")
    from firebase_admin import credentials, firestore
    print("***** MAIN.PY TOP LEVEL: 'from firebase_admin import credentials, firestore' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from . import config'... *****")
    from . import config
    print("***** MAIN.PY TOP LEVEL: 'from . import config' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from .kraken_api import fetch_kline_data'... *****")
    from .kraken_api import fetch_kline_data
    print("***** MAIN.PY TOP LEVEL: 'from .kraken_api import fetch_kline_data' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from .technical_analysis import analyze_technicals'... *****")
    from .technical_analysis import analyze_technicals
    print("***** MAIN.PY TOP LEVEL: 'from .technical_analysis import analyze_technicals' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from .position_manager import ...'... *****")
    from .position_manager import get_open_position, save_position, is_in_cooldown_period
    print("***** MAIN.PY TOP LEVEL: 'from .position_manager import ...' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from .telegram_bot import send_telegram_message'... *****")
    from .telegram_bot import send_telegram_message
    print("***** MAIN.PY TOP LEVEL: 'from .telegram_bot import send_telegram_message' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Attempting 'from .confidence_calculator import get_confidence_score'... *****")
    from .confidence_calculator import get_confidence_score
    print("***** MAIN.PY TOP LEVEL: 'from .confidence_calculator import get_confidence_score' - SUCCESS *****")
    print("***** MAIN.PY TOP LEVEL: Application imports successful *****")
    IMPORTS_SUCCESSFUL = True

    if not firebase_admin._apps:
        print("***** MAIN.PY TOP LEVEL: Firebase not initialized. Attempting firebase_admin.initialize_app()... *****")
        firebase_admin.initialize_app() # Use Application Default Credentials
        db = firestore.client()
        print("***** MAIN.PY TOP LEVEL: firebase_admin.initialize_app() - SUCCESS. DB client obtained. *****")
        FIREBASE_INITIALIZED = True
    else:
        print("***** MAIN.PY TOP LEVEL: Firebase already initialized. Attempting firestore.client()... *****")
        db = firestore.client()
        print("***** MAIN.PY TOP LEVEL: firestore.client() - SUCCESS. DB client obtained. *****")
        FIREBASE_INITIALIZED = True

except ImportError as e:
    print(f"***** MAIN.PY TOP LEVEL IMPORT ERROR: Module -> {e.name}, Message -> {e.msg} *****")
    logger.error(f"Failed to import required modules at top level: {e}", exc_info=True)
    # IMPORTS_SUCCESSFUL remains False
except Exception as e:
    print(f"***** MAIN.PY TOP LEVEL UNEXPECTED ERROR (likely during Firebase init or other): {type(e).__name__} - {e} *****")
    logger.error(f"Unexpected error during top-level imports or Firebase init: {e}", exc_info=True)
    # IMPORTS_SUCCESSFUL and FIREBASE_INITIALIZED might be False
finally:
    print(f"***** MAIN.PY TOP LEVEL: END OF TRY-EXCEPT-FINALLY. IMPORTS_SUCCESSFUL: {IMPORTS_SUCCESSFUL}, FIREBASE_INITIALIZED: {FIREBASE_INITIALIZED} *****")


@functions_framework.http
def run_signal_generation(request):
    """
    Google Cloud Function entry point.
    Orchestrates fetching data, analysis, signal generation, and notification.
    """
    global db # Ensure we use the potentially initialized global db client

    try:
        print("***** FUNCTION run_signal_generation START *****")
        logger.info("-------------------------------------------")
        logger.info("Starting signal generation cycle...")

        if not IMPORTS_SUCCESSFUL:
            error_message = "CRITICAL: Required modules failed to import during top-level load. Aborting."
            print(error_message)
            logger.critical(error_message)
            return "Internal Server Error: Module import failed", 500

        if not FIREBASE_INITIALIZED or db is None:
            error_message = "CRITICAL: Firebase not initialized or DB client is None. Aborting function execution."
            print(error_message)
            logger.critical(error_message)
            # Attempt re-initialization as a fallback (might not be effective if top-level failed badly)
            try:
                if not firebase_admin._apps:
                    print("Attempting Firebase re-initialization inside function...")
                    firebase_admin.initialize_app()
                    db = firestore.client()
                    print("Firebase re-initialized successfully inside function.")
                elif db is None:
                    db = firestore.client()
                if db is None: raise Exception("Failed to get valid DB client after re-attempt.")
            except Exception as init_err:
                print(f"Firebase re-initialization failed: {init_err}")
                logger.error(f"Firebase re-initialization failed: {init_err}", exc_info=True)
                return "Internal Server Error: Firebase re-initialization failed", 500
            # If still not good, abort.
            if not db:
                 return "Internal Server Error: Firebase client unavailable after re-attempt", 500

        all_results = []
        forced_signal_for_first_coin = False # Flag to ensure we only force one signal

        for coin_pair in config.TRACKED_COINS:
            logger.info(f"Processing coin: {coin_pair}")
            current_position = get_open_position(coin_pair, db)
            
            # --- TEMPORARY MODIFICATION TO FORCE SIGNAL ---
            signal = None
            if not forced_signal_for_first_coin:
                logger.info(f"TEMP: Forcing BUY signal for {coin_pair} to test Telegram.")
                signal = 'buy'
                # Ensure technicals object exists and has some dummy data for the message
                technicals_for_forced_signal = {
                    'pattern_detected': True, 'pattern_bullish': True, 'pattern_bearish': False,
                    'rsi': 30, 'volume_increase': True, 'sma_cross_bullish': True, 'sma_cross_bearish': False,
                    'pattern_name': 'Forced Test Signal', 'current_price': 12345.67
                }
                confidence_score = 1.0 # Assign dummy confidence for the forced signal
                # Use these dummy technicals if we forced a signal
                # Original technical analysis is skipped for this forced signal
                if signal: # If we are in the forced signal block
                    technicals = technicals_for_forced_signal 
                forced_signal_for_first_coin = True
            # --- END OF TEMPORARY MODIFICATION ---
            else: # Original logic for subsequent coins OR if not forcing
                if is_in_cooldown_period(coin_pair, db, config.SIGNAL_COOLDOWN_MINUTES):
                    logger.info(f"Coin {coin_pair} is in cooldown. Skipping.")
                    all_results.append(f"{coin_pair}: In cooldown.")
                    continue
                    
                kline_data = fetch_kline_data(coin_pair)
                if kline_data is None or not kline_data:
                    logger.warning(f"Could not fetch kline data for {coin_pair}.")
                    all_results.append(f"{coin_pair}: No kline data.")
                    continue

                required_points = max(config.SMA_PERIOD, config.RSI_PERIOD) + 5
                if len(kline_data) < required_points:
                    logger.warning(f"Not enough data points ({len(kline_data)} < {required_points}) for {coin_pair}.")
                    all_results.append(f"{coin_pair}: Not enough data ({len(kline_data)} points).")
                    continue

                technicals = analyze_technicals(kline_data)
                if technicals is None:
                    logger.warning(f"Technical analysis failed for {coin_pair}.")
                    all_results.append(f"{coin_pair}: TA failed.")
                    continue

                confidence_score = 8 # Hardcoded for now
                logger.info(f"Confidence score for {coin_pair}: {confidence_score} (Using hardcoded value)")

                # Original signal decision logic (only if not forced)
                if technicals.get('pattern_detected') and confidence_score >= config.CONFIDENCE_THRESHOLD:
                    if technicals['pattern_bullish'] and technicals['rsi'] < config.RSI_OVERSOLD and technicals['volume_increase'] and technicals['sma_cross_bullish']:
                        if current_position is None or current_position.get('status') == 'closed':
                            signal = 'buy'
                    elif technicals['pattern_bearish'] and technicals['rsi'] > config.RSI_OVERBOUGHT and technicals['volume_increase'] and technicals['sma_cross_bearish']:
                        if current_position and current_position.get('status') == 'open':
                            signal = 'sell'
            
            if signal:
                logger.info(f"{signal.upper()} signal generated for {coin_pair}")
                
                # Prepare the data for save_position
                signal_data_for_firestore = {
                    "symbol": coin_pair,
                    "type": signal.upper(),  # 'buy' becomes 'BUY', 'sell' becomes 'SELL'
                    "price": technicals.get('current_price'), # From technical_analysis or forced_signal
                    "confidence": confidence_score,
                    # Optional: Add more details from technicals if save_position uses them
                    "rsi": technicals.get('rsi'),
                    "pattern_name": technicals.get('pattern_name'),
                    "volume_increase": technicals.get('volume_increase'),
                    "sma_cross_bullish": technicals.get('sma_cross_bullish', False), # Default to False if not present
                    "sma_cross_bearish": technicals.get('sma_cross_bearish', False)  # Default to False if not present
                }

                # Corrected call to save_position
                position_ref = save_position(signal_data_for_firestore, db)
                
                if position_ref:
                    message = (
                        f"*{signal.upper()} Signal for {coin_pair}*\n\n"
                        f"Pattern: {technicals.get('pattern_name', 'N/A')} ({'Bullish' if technicals.get('pattern_bullish') else 'Bearish' if technicals.get('pattern_bearish') else 'Neutral'})\n"
                        f"RSI: {technicals.get('rsi', 'N/A'):.2f}\n"
                        f"Volume Incr: {technicals.get('volume_increase', 'N/A')}\n"
                        f"SMA Cross: {'Bullish' if technicals.get('sma_cross_bullish') else 'Bearish' if technicals.get('sma_cross_bearish') else 'None'}\n"
                        f"Price: {technicals.get('current_price', 'N/A')}"
                    )
                    send_telegram_message(message)
                    all_results.append(f"{coin_pair}: {signal.upper()} signal generated and notified.")
                else:
                    all_results.append(f"{coin_pair}: {signal.upper()} signal generated but FAILED to save position.")
            else:
                logger.info(f"No signal generated for {coin_pair}.")
                all_results.append(f"{coin_pair}: No signal.")

        logger.info("Signal generation cycle finished.")
        return f"Signal generation finished. Results: {'; '.join(all_results)}", 200
    
    except Exception as e:
        final_error_message = f"***** CRITICAL ERROR in run_signal_generation: {e} *****"
        print(final_error_message)
        logger.error(final_error_message, exc_info=True)
        return f"Internal Server Error: {e}", 500

# Ensure this is the ONLY content in the file.
