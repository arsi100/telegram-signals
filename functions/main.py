import logging
import datetime
import time
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import scheduler_v1
from google.cloud.scheduler_v1.types import Job, HttpTarget

# Use absolute imports for modules within the 'functions' package
from functions import config
from functions.signal_generator import process_crypto_data
# from functions.utils import is_market_hours # Removed market hours check
# from functions.bybit_api import fetch_kline_data # Use Kraken instead
from functions.kraken_api import fetch_kline_data # Import from the new Kraken module
# from functions.telegram_bot import send_telegram_message # Import the specific function
# Use the new function name that accepts the signal dict
from functions.telegram_bot import send_telegram_message 
# Import position manager functions
from functions.position_manager import save_position, update_position, close_position

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
    logger.info("Starting signal generation process")
    
    # Initialize Firebase HERE if not already initialized
    # This needs to be done within the function scope for Cloud Functions
    global db
    if db is None:
        try:
            # Check if already initialized (can happen with warm instances)
            # It's generally safe to call initialize_app multiple times
            # if no name is provided, it initializes the default app.
            # Let's just attempt initialization directly.
            if not firebase_admin._apps: # Only initialize if default app doesn't exist
                firebase_admin.initialize_app()
            db = firestore.client()
            logger.info("Firebase initialized successfully within function")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            db = None # Ensure db is None if init fails

    # Check if db is valid before proceeding
    if db is None:
        logger.error("Firestore database client is not initialized. Exiting.")
        # Return an error status code for Cloud Run/Functions
        # Use Flask standard tuple return for response + status code
        return ("Firestore not initialized", 500) 
        
    logger.info("Firestore client seems initialized.") # Added log

    try:
        # Get coins to track from Firestore - USE PASSED db
        config_doc = db.collection('config').document('trading_pairs').get()
        coins_to_track = config.TRACKED_COINS
        if config_doc.exists:
            coins_config = config_doc.to_dict()
            if coins_config and 'pairs' in coins_config:
                coins_to_track = coins_config['pairs']

        signals_generated = []
        
        # Process each coin
        for coin in coins_to_track:
            logger.info(f"Processing {coin}")
            try:
                # Fetch kline data
                kline_data = fetch_kline_data(coin)
                if not kline_data:
                    logger.warning(f"No kline data returned for {coin}")
                    continue
                
                # Process data and generate signals - Pass db
                signal = process_crypto_data(coin, kline_data, db)
                
                # If we have a signal, process it
                if signal:
                    logger.info(f"Signal generated for {coin}: {signal}")
                    signal_type = signal.get('type', 'UNKNOWN').upper()
                    
                    # 1. Send Telegram Notification FIRST
                    # We send notification even if DB operation fails later
                    if not send_telegram_message(signal):
                         logger.error(f"Failed to send Telegram notification for {signal_type} signal on {coin}.")
                         # Continue processing even if Telegram fails?
                    
                    # 2. Update Position State in Firestore - Pass db
                    position_updated = False
                    try:
                        if signal_type in ["LONG", "SHORT"]:
                            position_ref = save_position(signal, db) # Pass db
                            if position_ref: position_updated = True
                        elif signal_type.startswith("AVG_DOWN") or signal_type.startswith("AVG_UP"):
                            if 'position_ref' in signal:
                                position_updated = update_position(signal['position_ref'], signal, db) # Pass db
                            else:
                                logger.error(f"Missing 'position_ref' in {signal_type} signal: {signal}")
                        elif signal_type == "EXIT":
                             if 'position_ref' in signal:
                                 position_updated = close_position(signal['position_ref'], signal['price'], db) # Pass db
                             else:
                                 logger.error(f"Missing 'position_ref' in EXIT signal: {signal}")
                        else:
                             logger.warning(f"Unknown signal type '{signal_type}' received, cannot update position.")
                             
                        if not position_updated:
                             logger.error(f"Failed to update Firestore for {signal_type} signal on {coin}.")
                             # Consider how to handle this - retry? alert?
                             
                    except Exception as db_err:
                        logger.exception(f"Database error processing signal {signal_type} for {coin}: {db_err}")
                        # DB error occurred, notification was already sent.

                    # 3. Log signal to a general signals collection (optional) - Use Passed db
                    try:
                        signal_doc = signal.copy()
                        # Ensure SERVER_TIMESTAMP is used correctly
                        signal_doc['signal_timestamp'] = firestore.SERVER_TIMESTAMP 
                        # Remove sensitive or redundant fields if needed before logging
                        if 'position_ref' in signal_doc: del signal_doc['position_ref'] 
                        db.collection('signals_log').add(signal_doc) # Use passed db
                    except Exception as log_err:
                        logger.error(f"Failed to log signal to signals_log collection: {log_err}")

                    signals_generated.append(signal)
                else:
                    logger.info(f"No signal generated for {coin}")
                    
            except Exception as e:
                logger.error(f"Error processing {coin}: {str(e)}", exc_info=True) # Added exc_info for more detail
        
        return {
            "status": "success", 
            "signals": len(signals_generated),
            "coins_processed": len(coins_to_track)
        }
    
    except Exception as e:
        logger.error(f"Error in run_signal_generation: {str(e)}", exc_info=True) # Added exc_info
        return {"status": "error", "message": str(e)}

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
