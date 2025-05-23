# main.py
# Last modified: 2025-05-21 - Force rebuild for Telegram secret refresh
# Last modified: 2025-05-21 - Force rebuild
import functions_framework
import logging
import os
import sys
from telegram import Bot

# Suppress pandas warnings to reduce log noise
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- Fix excessive logging: Set appropriate levels ---
# Suppress urllib3 DEBUG logs (causes ~22 connection logs per execution)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# --- End httpx logging configuration ---

# --- Suppress telegram bot DEBUG logs --- 
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.ExtBot").setLevel(logging.WARNING)
logging.getLogger("telegram.bot").setLevel(logging.WARNING)
# --- End python-telegram-bot logging ---

# Configure logging using config setting instead of hardcoded DEBUG
log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
# Import config first to get LOG_LEVEL
from . import config
log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level, format=log_format, force=True)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# Global flags and db client
IMPORTS_SUCCESSFUL = False
FIREBASE_INITIALIZED = False
db = None

# Import and initialize Firebase at the top level
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from . import config
    from .kraken_api import fetch_kline_data
    from .technical_analysis import analyze_technicals
    from .position_manager import get_open_position, save_position, update_position, close_position, record_signal_ts
    from .telegram_bot import send_telegram_message
    from .confidence_calculator import get_confidence_score
    from .signal_generator import process_crypto_data
    IMPORTS_SUCCESSFUL = True

    if not firebase_admin._apps:
        firebase_admin.initialize_app() # Use Application Default Credentials
        db = firestore.client()
        FIREBASE_INITIALIZED = True
    else:
        db = firestore.client()
        FIREBASE_INITIALIZED = True

except ImportError as e:
    logger.error(f"Failed to import required modules at top level: {e}", exc_info=True)
    # IMPORTS_SUCCESSFUL remains False
except Exception as e:
    logger.error(f"Unexpected error during top-level imports or Firebase init: {e}", exc_info=True)
    # IMPORTS_SUCCESSFUL and FIREBASE_INITIALIZED might be False

@functions_framework.http
def run_signal_generation(request):
    """
    Google Cloud Function entry point.
    Orchestrates fetching data, analysis, signal generation, and notification.
    """
    global db # Ensure we use the potentially initialized global db client

    try:
        logger.info("-------------------------------------------")
        logger.info("Starting signal generation cycle...")

        if not IMPORTS_SUCCESSFUL:
            error_message = "CRITICAL: Required modules failed to import during top-level load. Aborting."
            logger.critical(error_message)
            return "Internal Server Error: Module import failed", 500

        if not FIREBASE_INITIALIZED or db is None:
            error_message = "CRITICAL: Firebase not initialized or DB client is None. Aborting function execution."
            logger.critical(error_message)
            # Attempt re-initialization as a fallback (might not be effective if top-level failed badly)
            try:
                if not firebase_admin._apps:
                    firebase_admin.initialize_app()
                    db = firestore.client()
                elif db is None:
                    db = firestore.client()
                if db is None: raise Exception("Failed to get valid DB client after re-attempt.")
            except Exception as init_err:
                logger.error(f"Firebase re-initialization failed: {init_err}", exc_info=True)
                return "Internal Server Error: Firebase re-initialization failed", 500
            # If still not good, abort.
            if not db:
                 return "Internal Server Error: Firebase client unavailable after re-attempt", 500

        all_results = []

        for coin_pair in config.TRACKED_COINS:
            logger.info(f"Processing coin: {coin_pair}")
            current_position = get_open_position(coin_pair, db)
            
            signal = None # Initialize signal for normal processing
            # Cooldown check is now inside process_crypto_data, but we might want to record successful signal timestamps here
            # if is_in_cooldown_period(coin_pair, db, config.SIGNAL_COOLDOWN_MINUTES):
            #     logger.info(f"Coin {coin_pair} is in cooldown. Skipping.")
            #     all_results.append(f"{coin_pair}: In cooldown.")
            #     continue
                
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

            # --- Call signal_generator.process_crypto_data ---
            # This function now handles cooldown checks, TA, confidence, and all signal logic (ENTRY, EXIT, AVG_UP/DOWN)
            generated_signal_details = process_crypto_data(coin_pair, kline_data, db)
            logger.info(f"[DEBUG MAIN] For {coin_pair}, process_crypto_data returned: {generated_signal_details}")

            if generated_signal_details and isinstance(generated_signal_details, dict):
                signal_type = generated_signal_details.get("type")
                signal_price = generated_signal_details.get("price")
                log_message = f"{coin_pair}: {signal_type} signal generated at {signal_price}. Confidence: {generated_signal_details.get('confidence')}."
                logger.info(log_message)

                action_taken = False
                if signal_type in ["LONG", "SHORT"]: # New entry signals
                    position_ref = save_position(generated_signal_details, db)
                    if position_ref:
                        send_telegram_message(generated_signal_details)
                        record_signal_ts(coin_pair, db) # Record timestamp for new LONG/SHORT
                        all_results.append(f"{log_message} Saved and Notified.")
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to save position.")
                
                elif signal_type == "EXIT":
                    position_ref_path = generated_signal_details.get("position_ref")
                    if position_ref_path and close_position(position_ref_path, signal_price, db):
                        send_telegram_message(generated_signal_details)
                        # record_signal_ts(coin_pair, db) # Do not record cooldown for EXIT
                        all_results.append(f"{log_message} Position Closed and Notified.")
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to close position or missing ref_path.")

                elif signal_type and (signal_type.startswith("AVG_DOWN") or signal_type.startswith("AVG_UP")):
                    position_ref_path = generated_signal_details.get("position_ref")
                    if position_ref_path and update_position(position_ref_path, generated_signal_details, db):
                        send_telegram_message(generated_signal_details)
                        # record_signal_ts(coin_pair, db) # Do not record cooldown for AVG signals
                        all_results.append(f"{log_message} Position Updated and Notified.")
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to update position or missing ref_path.")
                
                if not action_taken and signal_type: # If a signal type was returned but not handled above
                     all_results.append(f"{log_message} Signal type {signal_type} not processed for action.")
                elif not signal_type: # if generated_signal_details was returned, but no type (should not happen)
                     all_results.append(f"{coin_pair}: process_crypto_data returned details but no signal type.")

            else: # No signal generated by process_crypto_data
                logger.info(f"No signal generated for {coin_pair} by process_crypto_data.")
                all_results.append(f"{coin_pair}: No signal from process_crypto_data.")

        logger.info("Signal generation cycle finished.")
        return f"Signal generation finished. Results: {'; '.join(all_results)}", 200
    
    except Exception as e:
        final_error_message = f"***** CRITICAL ERROR in run_signal_generation: {e} *****"
        logger.error(final_error_message, exc_info=True)
        return f"Internal Server Error: {e}", 500

# Ensure this is the ONLY content in the file.
