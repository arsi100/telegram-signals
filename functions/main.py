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
    print("***** MAIN.PY TOP LEVEL: Attempting imports... *****")
    import firebase_admin
    from firebase_admin import credentials, firestore
    from . import config
    from .kraken_api import fetch_kline_data
    from .technical_analysis import analyze_technicals
    from .position_manager import get_open_position, save_position, is_in_cooldown_period
    from .telegram_bot import send_telegram_message
    from .confidence_calculator import get_confidence_score
    print("***** MAIN.PY TOP LEVEL: Application imports successful *****")
    IMPORTS_SUCCESSFUL = True

    if not firebase_admin._apps:
        print("***** MAIN.PY TOP LEVEL: Initializing Firebase Admin... *****")
        firebase_admin.initialize_app() # Use Application Default Credentials
        db = firestore.client()
        print("***** MAIN.PY TOP LEVEL: Firebase Admin initialized. *****")
        FIREBASE_INITIALIZED = True
    else:
        db = firestore.client()
        print("***** MAIN.PY TOP LEVEL: Firebase Admin already initialized. *****")
        FIREBASE_INITIALIZED = True

except ImportError as e:
    print(f"***** MAIN.PY TOP LEVEL IMPORT ERROR: {e} *****")
    logger.error(f"Failed to import required modules at top level: {e}", exc_info=True)
    # IMPORTS_SUCCESSFUL remains False
except Exception as e:
    print(f"***** MAIN.PY TOP LEVEL UNEXPECTED ERROR (likely during Firebase init): {e} *****")
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
        for coin_pair in config.COINS_TO_TRACK:
            logger.info(f"Processing coin: {coin_pair}")
            current_position = get_open_position(coin_pair, db)
            if is_in_cooldown_period(coin_pair, db, config.COOLDOWN_PERIOD_MINUTES):
                logger.info(f"Coin {coin_pair} is in cooldown. Skipping.")
                all_results.append(f"{coin_pair}: In cooldown.")
                continue

            kline_data = fetch_kline_data(coin_pair, interval=config.KLINE_INTERVAL, limit=config.KLINE_LIMIT)
            if kline_data is None or kline_data.empty:
                logger.warning(f"Could not fetch kline data for {coin_pair}.")
                all_results.append(f"{coin_pair}: No kline data.")
                continue

            required_points = max(config.SMA_PERIOD_LONG, config.RSI_PERIOD) + 5
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

            signal = None
            if technicals.get('pattern_detected') and confidence_score >= config.CONFIDENCE_THRESHOLD:
                if technicals['pattern_bullish'] and technicals['rsi'] < config.RSI_OVERSOLD and technicals['volume_increase'] and technicals['sma_cross_bullish']:
                    if current_position is None or current_position.get('status') == 'closed':
                        signal = 'buy'
                elif technicals['pattern_bearish'] and technicals['rsi'] > config.RSI_OVERBOUGHT and technicals['volume_increase'] and technicals['sma_cross_bearish']:
                    if current_position and current_position.get('status') == 'open':
                        signal = 'sell'
            
            if signal:
                logger.info(f"{signal.upper()} signal generated for {coin_pair}")
                save_position(db, coin_pair, signal, technicals, confidence_score, current_position)
                message = (
                    f"*{signal.upper()} Signal for {coin_pair}*\n\n"
                    f"Pattern: {technicals.get('pattern_name', 'N/A')} ({'Bullish' if technicals.get('pattern_bullish') else 'Bearish' if technicals.get('pattern_bearish') else 'Neutral'})\n"
                    f"RSI: {technicals.get('rsi', 'N/A'):.2f}\n"
                    f"Volume Incr: {technicals.get('volume_increase', 'N/A')}\n"
                    f"SMA Cross: {'Bullish' if technicals.get('sma_cross_bullish') else 'Bearish' if technicals.get('sma_cross_bearish') else 'None'}\n"
                    f"Price: {technicals.get('current_price', 'N/A')}"
                )
                send_telegram_message(message)
                all_results.append(f"{coin_pair}: {signal.toUpperCase()} signal generated and notified.") # Corrected to signal.upper()
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
