# main.py
# Last modified: 2025-05-23 - Fixed logging duplication issue
# Last modified: 2025-05-21 - Force rebuild for Telegram secret refresh
# Last modified: 2025-05-21 - Force rebuild
# Last modified: 2025-07-04 - Fixed send_telegram_message import error
import functions_framework
import logging
import os
import sys
from telegram import Bot
import json
import traceback
from flask import jsonify # Flask is available in GCP Cloud Functions Python runtime

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

# --- FIXED LOGGING CONFIGURATION for Google Cloud Functions ---
# Clear any existing handlers to prevent duplication
root_logger = logging.getLogger()
root_logger.handlers.clear()

# Import config first to get LOG_LEVEL
from . import config
log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

# Create a single StreamHandler that writes to stdout only
# Google Cloud Functions will capture stdout properly without duplication
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
handler.setFormatter(formatter)

# Configure root logger with single handler
root_logger.addHandler(handler)
root_logger.setLevel(log_level)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(log_level)
# --- END FIXED LOGGING CONFIGURATION ---

# Global flags and db client
IMPORTS_SUCCESSFUL = False
FIREBASE_INITIALIZED = False
db = None

# Import and initialize Firebase at the top level
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    import pandas as pd # Add pandas import
    from . import config
    from .kraken_api import fetch_kline_data
    from .technical_analysis import analyze_technicals
    from .position_manager import get_open_position, record_new_position, update_avg_down_position, close_open_position, record_signal_ts
    # REMOVED: from .telegram_bot import send_telegram_message  # Function removed in favor of async notifier
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
                
            kline_data_list = fetch_kline_data(coin_pair) # Renamed to kline_data_list

            if kline_data_list is None:
                logger.warning(f"Could not fetch kline data for {coin_pair}.")
                all_results.append(f"{coin_pair}: No kline data.")
                continue

            # Convert list of dicts to DataFrame
            kline_data = pd.DataFrame(kline_data_list)
            
            # Now check if the DataFrame is empty
            if kline_data.empty:
                logger.warning(f"Kline data for {coin_pair} is empty after DataFrame conversion.")
                all_results.append(f"{coin_pair}: Empty kline data.")
                continue

            required_points = max(config.SMA_PERIOD, config.RSI_PERIOD) + 5 # Ensure this uses attributes from config
            if len(kline_data) < required_points:
                logger.warning(f"Not enough data points ({len(kline_data)} < {required_points}) for {coin_pair}.")
                all_results.append(f"{coin_pair}: Not enough data ({len(kline_data)} points).")
                continue

            # Fetch 4h data for multi-timeframe analysis
            logger.info(f"Fetching 4h kline data for {coin_pair} for multi-timeframe analysis")
            kline_data_4h_list = fetch_kline_data(coin_pair, resolution="4h")  # Changed from "240m" to "4h"
            
            if kline_data_4h_list is None:
                logger.warning(f"Could not fetch 4h kline data for {coin_pair}. Using original analysis.")
                # Fall back to original single-timeframe analysis
                from .technical_analysis import analyze_technicals_original
                technicals = analyze_technicals_original(kline_data_list, symbol=coin_pair, interval_str="5m")
            else:
                # Convert 4h data to DataFrame
                kline_data_4h = pd.DataFrame(kline_data_4h_list)
                if kline_data_4h.empty:
                    logger.warning(f"4h kline data for {coin_pair} is empty. Using original analysis.")
                    from .technical_analysis import analyze_technicals_original
                    technicals = analyze_technicals_original(kline_data_list, symbol=coin_pair, interval_str="5m")
                else:
                    # Use multi-timeframe analysis
                    # Note: analyze_technicals expects 15m and 4h data, but we have 5m data
                    # We'll pass the 5m data as the first parameter for now
                    technicals = analyze_technicals(kline_data_list, kline_data_4h_list, symbol=coin_pair, interval_str="5m")
            
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
                signal_price = generated_signal_details.get("price") # This is entry or exit price depending on type
                confidence = generated_signal_details.get('confidence')
                sentiment_score = generated_signal_details.get('sentiment_score') # Assuming it's there
                rsi_value = generated_signal_details.get('rsi') # Assuming it's there

                log_message = f"{coin_pair}: {signal_type} signal generated at {signal_price}. Confidence: {confidence}."
                logger.info(log_message)

                action_taken = False
                if signal_type in ["LONG", "SHORT"]: # New entry signals
                    pos_id, _ = record_new_position(
                        symbol=coin_pair, 
                        signal_type=signal_type, 
                        entry_price=signal_price, 
                        db=db,
                        signal_data=generated_signal_details # Pass the whole dict here
                    )
                    if pos_id:
                        # DISABLED: send_telegram_message(generated_signal_details)  # Now handled by async notifier
                        record_signal_ts(coin_pair, db) # Record timestamp for new LONG/SHORT
                        all_results.append(f"{log_message} Saved (ID: {pos_id}).")  # Removed "and Notified"
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to save position.")
                
                elif signal_type == "EXIT" or signal_type == "EXIT_LONG" or signal_type == "EXIT_SHORT": # Modified condition
                    # position_id_to_close = generated_signal_details.get("position_ref") # This should be the ID
                    # The signal_generator now includes 'original_position_id' for exits
                    position_id_to_close = generated_signal_details.get("original_position_id") 
                    exit_price = signal_price # For EXIT, signal_price is the exit_price
                    
                    if not position_id_to_close:
                        logger.error(f"[{coin_pair}] {signal_type} signal received but 'original_position_id' is missing in signal_details: {generated_signal_details}")
                        all_results.append(f"{log_message} {signal_type} FAILED: Missing original_position_id.")
                    elif close_open_position(position_id_to_close, exit_price, db):
                        # DISABLED: send_telegram_message(generated_signal_details)  # Now handled by async notifier
                        # record_signal_ts(coin_pair, db) # Cooldown for exits? Generally no, but can be added.
                        all_results.append(f"{log_message} Position {position_id_to_close} Closed.")  # Removed "and Notified"
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to close position {position_id_to_close}.")

                elif signal_type and (signal_type.startswith("AVG_DOWN") or signal_type.startswith("AVG_UP")):
                    # For now, assuming AVG_UP uses the same logic as AVG_DOWN for update
                    position_id_to_update = generated_signal_details.get("position_ref") # This should be the ID
                    new_entry_price_for_avg = signal_price
                    # def update_avg_down_position(position_id, new_entry_price, additional_quantity_percentage, db)
                    # Passing 0 for additional_quantity_percentage as it's not used by current manager and not in signal_details
                    if position_id_to_update and update_avg_down_position(position_id_to_update, new_entry_price_for_avg, 0, db):
                        # DISABLED: send_telegram_message(generated_signal_details)  # Now handled by async notifier
                        all_results.append(f"{log_message} Position {position_id_to_update} Updated.")  # Removed "and Notified"
                        action_taken = True
                    else:
                        all_results.append(f"{log_message} FAILED to update position {position_id_to_update} or missing ID.")
                
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
