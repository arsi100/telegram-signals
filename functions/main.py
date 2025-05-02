import logging
import datetime
import time
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import scheduler_v1
from google.cloud.scheduler_v1.types import Job, HttpTarget

# Use relative imports for modules within the 'functions' directory
# because --source=./functions puts these files at the root of /workspace
from . import config
from .signal_generator import process_crypto_data
# from .utils import is_market_hours # Removed market hours check
# from .bybit_api import fetch_kline_data # Use Kraken instead
from .kraken_api import fetch_kline_data # Import from the new Kraken module
# from .telegram_bot import send_telegram_message # Import the specific function
# Use the new function name that accepts the signal dict
from .telegram_bot import send_telegram_message 
# Import position manager functions
from .position_manager import save_position, update_position, close_position

# Set up logging
# logging.basicConfig(level=config.LOG_LEVEL) # REMOVED - Configuration should happen at entry point
logger = logging.getLogger(__name__) # Get logger for this module

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
    # --- ADDED LOGGING CONFIGURATION ---
    # Set root logger level to DEBUG to capture all logs
    # Note: Cloud Logging handler automatically set up by Functions Framework
    logging.getLogger().setLevel(logging.DEBUG)
    # --- END LOGGING CONFIGURATION ---
    
    logger.info("Starting signal generation process")
    
    # Initialize Firebase HERE if not already initialized
    # This needs to be done within the function scope for Cloud Functions
    global db
    if db is None:
        try:
            # Check if already initialized (can happen with warm instances)
            # It's generally safe to call initialize_app multiple times
            if not firebase_admin._apps:
                 firebase_admin.initialize_app()
                 logger.info("Firebase Admin SDK initialized.")
            else:
                logger.info("Firebase Admin SDK already initialized.")
            db = firestore.client()
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            return ("Error initializing Firebase", 500) # Stop execution if Firebase fails

    # --- Existing code continues below --- 
    # ---- ADDED DEBUG LOG ----
    logger.debug(f"Firestore client obtained: {db}") 
    # ---- END DEBUG LOG ----

    # Fetch list of coins to process from config
    coins_to_process = config.COINS_TO_PROCESS
    logger.info(f"Processing coins: {coins_to_process}")

    for coin in coins_to_process:
        try:
            logger.info(f"--- Processing {coin} ---")
            # Check cooldown period before fetching data
            if is_in_cooldown_period(coin, db):
                logger.info(f"Skipping {coin} due to cooldown period.")
                continue

            # Fetch kline data for the coin
            # Using Kraken API as per current implementation
            kline_data = fetch_kline_data(coin)
            if not kline_data:
                 logger.warning(f"No kline data returned for {coin}")
                 continue
            
            # ---- ADDED DEBUG LOG ----
            logger.debug(f"Passing {len(kline_data)} klines to process_crypto_data for {coin}")
            # ---- END DEBUG LOG ----
            
            # Process data and generate signals - Pass db
            signal = process_crypto_data(coin, kline_data, db)
            
            if signal:
                logger.info(f"Signal generated for {coin}: {signal['type']} at {signal['price']}")
                # Check confidence score
                confidence_score = get_confidence_score(
                    coin,
                    signal['type'],
                    signal['rsi'],
                    signal['sma_trend'],
                    signal['patterns']
                )
                signal['confidence_score'] = confidence_score
                logger.info(f"Confidence score for {coin} signal: {confidence_score}")

                if confidence_score >= config.CONFIDENCE_THRESHOLD:
                    # Save position and send notification only if confidence is high enough
                    save_position(signal, db)
                    send_telegram_message(signal) 
                else:
                    logger.info(f"Signal for {coin} did not meet confidence threshold ({confidence_score} < {config.CONFIDENCE_THRESHOLD}). Discarding.")
            else:
                logger.info(f"No signal generated for {coin}")

        except Exception as e:
            logger.error(f"Error processing {coin}: {e}", exc_info=True)
            # Continue to the next coin even if one fails

    logger.info("Signal generation process completed")
    return ("Signal generation process completed", 200)

def setup_cloud_scheduler(event, context):
    """
    Cloud Function to set up the Cloud Scheduler jobs.
    Triggered when the function is deployed.
    """
    logger.info("Setting up Cloud Scheduler")
    
    client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{context.project}/locations/us-central1"
    
    # Create a job that runs every 5 minutes
    job = Job(
        name=f"{parent}/jobs/crypto-signal-generation",
        http_target=HttpTarget(
            uri=f"https://us-central1-{context.project}.cloudfunctions.net/run_signal_generation",
            http_method=scheduler_v1.HttpMethod.GET
        ),
        schedule="*/5 * * * *"  # Every 5 minutes
    )
    
    try:
        response = client.create_job(parent=parent, job=job)
        logger.info(f"Created job: {response.name}")
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
