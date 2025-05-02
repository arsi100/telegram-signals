#!/usr/bin/env python
import logging
import datetime
import time
import pytz
import firebase_admin
# from firebase_admin import credentials, firestore # Commented out
# from google.cloud import scheduler_v1 # Commented out
# from google.cloud.scheduler_v1.types import Job, HttpTarget # Commented out

# Use relative imports for modules within the 'functions' directory
# because --source=./functions puts these files at the root of /workspace
# from . import config # Commented out
# from .signal_generator import process_crypto_data # Commented out
# from .utils import is_market_hours # Removed market hours check
# from .bybit_api import fetch_kline_data # Use Kraken instead
# from .kraken_api import fetch_kline_data # Commented out
# from .telegram_bot import send_telegram_message # Import the specific function
# Use the new function name that accepts the signal dict
# from .telegram_bot import send_telegram_message # Commented out
# Import position manager functions
# from .position_manager import save_position, update_position, close_position # Commented out

# Set up logging
# logging.basicConfig(level=config.LOG_LEVEL) # REMOVED - Configuration should happen at entry point
logger = logging.getLogger(__name__) # Get logger for this module

# Global placeholder for db client - MUST be initialized by entry point
# This isn't ideal practice, passing db would be better, but simplifies refactoring for now
# db = None # Commented out

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
    # logging.basicConfig(level=logging.DEBUG, force=True) # REMOVED FOR TEST
    # --- END LOGGING CONFIGURATION ---

    # --- ADDED VERY EARLY LOG ---
    # Let's see if the function even starts
    logger.info("--- run_signal_generation function START (Simplified) ---")
    # --- END EARLY LOG ---

    # === ALL OTHER CODE COMMENTED OUT FOR TESTING ===
    
    # logger.info("Starting signal generation process")

    # # Initialize Firebase HERE if not already initialized
    # # This needs to be done within the function scope for Cloud Functions
    # global db
    # if db is None:
    #     logger.debug("Attempting Firebase initialization...") # Added debug
    #     try:
    #         # Check if already initialized (can happen with warm instances)
    #         # It's generally safe to call initialize_app multiple times
    #         if not firebase_admin._apps:
    #              firebase_admin.initialize_app()
    #              logger.info("Firebase Admin SDK initialized.")
    #         else:
    #             logger.info("Firebase Admin SDK already initialized.")
    #         db = firestore.client()
    #         logger.debug("Firestore client obtained successfully.") # Added debug
    #     except Exception as e:
    #         # Log the error BEFORE returning
    #         logger.error(f"Failed to initialize Firebase Admin SDK: {e}", exc_info=True) # Added exc_info
    #         return ("Error initializing Firebase", 500) # Stop execution if Firebase fails

    # # --- Existing code continues below --- 
    # # ---- ADDED DEBUG LOG ----
    # logger.debug(f"Firestore client obtained: {db}")
    # # ---- END DEBUG LOG ----

    # # Fetch list of coins to process from config
    # coins_to_process = config.COINS_TO_PROCESS
    # logger.info(f"Processing coins: {coins_to_process}")

    # for coin in coins_to_process:
    #     try:
    #         logger.info(f"--- Processing {coin} ---")
    #         # Check cooldown period before fetching data
    #         if is_in_cooldown_period(coin, db):
    #             logger.info(f"Skipping {coin} due to cooldown period.")
    #             continue

    #         # Fetch kline data for the coin
    #         # Using Kraken API as per current implementation
    #         kline_data = fetch_kline_data(coin)
    #         if not kline_data:
    #              logger.warning(f"No kline data returned for {coin}")
    #              continue
            
    #         # ---- ADDED DEBUG LOG ----
    #         logger.debug(f"Passing {len(kline_data)} klines to process_crypto_data for {coin}")
    #         # ---- END DEBUG LOG ----
            
    #         # Process data and generate signals - Pass db
    #         signal = process_crypto_data(coin, kline_data, db)
            
    #         if signal:
    #             logger.info(f"Signal generated for {coin}: {signal['type']} at {signal['price']}")
    #             # Check confidence score
    #             confidence_score = get_confidence_score(
    #                 coin,
    #                 signal['type'],
    #                 signal['rsi'],
    #                 signal['sma_trend'],
    #                 signal['patterns']
    #             )
    #             signal['confidence_score'] = confidence_score
    #             logger.info(f"Confidence score for {coin} signal: {confidence_score}")

    #             if confidence_score >= config.CONFIDENCE_THRESHOLD:
    #                 # Save position and send notification only if confidence is high enough
    #                 save_position(signal, db)
    #                 send_telegram_message(signal) 
    #             else:
    #                 logger.info(f"Signal for {coin} did not meet confidence threshold ({confidence_score} < {config.CONFIDENCE_THRESHOLD}). Discarding.")
    #         else:
    #             logger.info(f"No signal generated for {coin}")

    #     except Exception as e:
    #         logger.error(f"Error processing {coin}: {e}", exc_info=True)
    #         # Continue to the next coin even if one fails

    # logger.info("Signal generation process completed")
    # === END OF COMMENTED OUT CODE ===
    
    logger.info("--- Simplified function execution END ---")
    return ("Simplified function ran successfully", 200)

# === NEW TEST ENDPOINT ===
def test_endpoint(request):
    """
    Minimal test endpoint to check basic function execution.
    """
    # Try basic logging
    try:
        # Get a logger specific to this test function
        # test_logger = logging.getLogger('test_endpoint') # Using print instead
        # Ensure logging is configured (using basicConfig for simplicity here)
        # logging.basicConfig(level=logging.INFO, force=True) # Using print instead
        # test_logger.info("--- test_endpoint START --- ")
        # test_logger.info("--- test_endpoint END --- ")
        print("--- test_endpoint START (using print) ---")
        print("--- test_endpoint END (using print) ---")
        return ("Test endpoint executed successfully!", 200)
    except Exception as e:
        # Fallback if logging itself fails
        print(f"Error in test_endpoint logging: {e}") 
        return ("Test endpoint hit, but logging failed.", 500)
# === END TEST ENDPOINT ===

# def setup_cloud_scheduler(event, context):
#     """
#     Cloud Function to set up the Cloud Scheduler jobs.
#     Triggered when the function is deployed.
#     """
#     logger.info("Setting up Cloud Scheduler")
    
#     client = scheduler_v1.CloudSchedulerClient()
#     parent = f"projects/{context.project}/locations/us-central1"
    
#     # Create a job that runs every 5 minutes
#     job = Job(
#         name=f"{parent}/jobs/crypto-signal-generation",
#         http_target=HttpTarget(
#             uri=f"https://us-central1-{context.project}.cloudfunctions.net/run_signal_generation",
#             http_method=scheduler_v1.HttpMethod.GET
#         ),
#         schedule="*/5 * * * *"  # Every 5 minutes
#     )
    
#     try:
#         response = client.create_job(parent=parent, job=job)
#         logger.info(f"Created job: {response.name}")
#     except Exception as e:
#         logger.error(f"Error creating job: {str(e)}")
