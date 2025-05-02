#!/usr/bin/env python
# Try importing core modules first and log any errors
try:
    import logging
    import datetime
    import time
    import pytz
    import firebase_admin
    from firebase_admin import firestore
    print("Successfully imported core libraries") # Use print for early feedback
except ImportError as e:
    print(f"CRITICAL: Failed to import core libraries: {e}")
    # If core libs fail, the function likely can't proceed
    raise # Re-raise the exception to ensure failure

# Try importing local/application modules
try:
    from . import config
    from .signal_generator import process_crypto_data
    from .kraken_api import fetch_kline_data
    from .telegram_bot import send_telegram_message
    from .position_manager import save_position, update_position, close_position
    print("Successfully imported application modules") # Use print
except ImportError as e:
    print(f"CRITICAL: Failed to import application modules: {e}")
    # Log the error before potentially failing
    # Get a logger instance here just in case logging *partially* works
    try:
        logger_init_fail = logging.getLogger(__name__)
        logger_init_fail.error(f"Failed to import application modules: {e}", exc_info=True)
    except Exception as log_e:
        print(f"Also failed to get logger during import error: {log_e}")
    raise # Re-raise the exception

# Set up logging *after* successful imports
logger = logging.getLogger(__name__)

# Global placeholder for db client - MUST be initialized by entry point
# This isn't ideal practice, passing db would be better, but simplifies refactoring for now
db = None

def run_signal_generation(request):
    """
    Cloud Function to generate trading signals.
    This is triggered by HTTP request from Cloud Scheduler.

    Args:
        request: Flask request object
    Returns:
        HTTP response
    """
    # --- ALTERNATIVE LOGGING CONFIGURATION (Testing) ---
    # Use basicConfig to set level AND ensure a handler is set up
    # Force=True ensures it reconfigures even if already configured elsewhere (less likely here)
    # Level=DEBUG to capture all logs
    # logging.basicConfig(level=logging.DEBUG, force=True) # REMOVED AGAIN
    # --- END LOGGING CONFIGURATION ---

    # --- ADDED VERY EARLY LOG ---
    # Let's see if the function even starts
    # logger.info("--- Simplified function execution START ---") # Keep commented
    
    # Initialize logging for this run
    logging.getLogger().setLevel(logging.DEBUG) # Re-enable setting level
    logger.info("Starting signal generation process")

    # Initialize Firebase HERE if not already initialized
    # This needs to be done within the function scope for Cloud Functions
    global db
    if not firebase_admin._apps: # Check if already initialized (simpler check)
        try:
            # It's generally safe to call initialize_app multiple times,
            # but checking first avoids potential warnings/overhead.
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized.")
        except Exception as e:
            logger.error(f"Error initializing Firebase Admin SDK: {e}", exc_info=True)
            # Depending on severity, you might want to exit or handle differently
            return ("Internal Server Error: Firebase initialization failed", 500)

    # Get Firestore client - ensure initialization happened
    try:
        # db = firestore.client() # Original location
        if db is None: # Initialize db if it's None
            db = firestore.client()
            logger.info("Firestore client obtained.")
    except Exception as e:
        logger.error(f"Error getting Firestore client: {e}", exc_info=True)
        return ("Internal Server Error: Firestore client failed", 500)

    logger.info(f"Processing coins: {config.COINS_TO_TRACK}")

    # --- Main logic - Uncommented ---
    try:
        for coin in config.COINS_TO_TRACK:
            logger.info(f"Processing coin: {coin}")
            # Fetch data (replace with actual API call logic)
            # kline_data = fetch_kline_data(coin, config.TIMEFRAME, limit=config.KLINE_LIMIT) # Replace with actual call
            kline_data = fetch_kline_data(coin) # Using kraken_api version
            if not kline_data:
                 logger.warning(f"No kline data returned for {coin}")
                 continue

            # ---- ADDED DEBUG LOG ----
            logger.debug(f"Passing {len(kline_data)} klines to process_crypto_data for {coin}")
            # ---- END DEBUG LOG ----

            # Process data and generate signals - Pass db
            signal = process_crypto_data(coin, kline_data, db)

            if signal:
                logger.info(f"Generated signal for {coin}: {signal['type']}")
                # Send notification (Implement telegram_bot.py)
                send_telegram_message(signal) # Pass the signal dictionary
                # Save/Update position in Firestore (Implement position_manager.py)
                # Simplified logic - assumes save_position handles new/existing
                # save_position(db, signal) # Removed, logic is within process_crypto_data
            else:
                logger.info(f"No signal generated for {coin}")

    except Exception as e:
        logger.error(f"An unexpected error occurred during signal generation loop: {e}", exc_info=True)
        # Decide if the entire function should fail or just log and continue
        return ("Internal Server Error during processing", 500)
    # --- End Main logic ---

    # logger.info("--- Simplified function execution END ---") # Keep commented
    logger.info("Signal generation process completed successfully.")
    return ("Signal generation process completed successfully", 200)

# === NEW TEST ENDPOINT === # REMOVED
# def test_endpoint(request):
#     """
#     Minimal test endpoint to check basic function execution.
#     """
#     # Try basic logging
#     try:
#         # Get a logger specific to this test function
#         # test_logger = logging.getLogger('test_endpoint') # Using print instead
#         # Ensure logging is configured (using basicConfig for simplicity here)
#         # logging.basicConfig(level=logging.INFO, force=True) # Using print instead
#         # test_logger.info("--- test_endpoint START --- ")
#         # test_logger.info("--- test_endpoint END --- ")
#         print("--- test_endpoint START (using print) ---")
#         print("--- test_endpoint END (using print) ---")
#         return ("Test endpoint executed successfully!", 200)
#     except Exception as e:
#         # Fallback if logging itself fails
#         print(f"Error in test_endpoint logging: {e}")
#         return ("Error during test endpoint execution", 500)
# === END TEST ENDPOINT === # REMOVED
