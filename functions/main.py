import logging
import datetime
import time
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import scheduler_v1
from google.cloud.scheduler_v1.types import Job, HttpTarget

from config import TRACKED_COINS, MARKET_HOURS
from signal_generator import process_crypto_data
from utils import is_market_hours
from bybit_api import fetch_kline_data
from telegram_bot import send_telegram_message

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Firebase app
try:
    firebase_admin.initialize_app()
    db = firestore.client()
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
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
    
    # Check if we're in market hours
    current_time = datetime.datetime.now(pytz.UTC)
    if not is_market_hours(current_time):
        logger.info(f"Not in market hours, skipping. Current time: {current_time.strftime('%H:%M:%S UTC')}")
        return {"status": "skipped", "reason": "Not in market hours"}
    
    try:
        # Get coins to track from Firestore
        config_doc = db.collection('config').document('trading_pairs').get()
        coins_to_track = TRACKED_COINS
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
                
                # Process data and generate signals
                signal = process_crypto_data(coin, kline_data, db)
                
                # If we have a signal, send it
                if signal:
                    logger.info(f"Signal generated for {coin}: {signal}")
                    
                    # Prepare message
                    message = format_signal_message(signal)
                    
                    # Send to Telegram
                    send_telegram_message(message)
                    
                    # Save signal to Firestore
                    signal_doc = signal.copy()
                    signal_doc['timestamp'] = firestore.SERVER_TIMESTAMP
                    db.collection('signals').add(signal_doc)
                    
                    signals_generated.append(signal)
                else:
                    logger.info(f"No signal generated for {coin}")
                    
            except Exception as e:
                logger.error(f"Error processing {coin}: {str(e)}")
        
        return {
            "status": "success", 
            "signals": len(signals_generated),
            "coins_processed": len(coins_to_track)
        }
    
    except Exception as e:
        logger.error(f"Error in run_signal_generation: {str(e)}")
        return {"status": "error", "message": str(e)}

def format_signal_message(signal):
    """Format a signal as a Telegram message"""
    signal_type = signal["type"].upper()
    
    # Format message differently based on signal type
    if signal_type in ["LONG", "SHORT"]:
        message = f"🚨 {signal_type} SIGNAL 🚨\n\n"
        message += f"Symbol: {signal['symbol']}\n"
        message += f"Entry Price: ${signal['price']:.2f}\n"
        message += f"Confidence: {signal['confidence']:.1f}/100\n"
        
        # Add profit targets
        if signal_type == "LONG":
            take_profit = signal['price'] * 1.03
            stop_loss = signal['price'] * 0.98
        else:  # SHORT
            take_profit = signal['price'] * 0.97
            stop_loss = signal['price'] * 1.02
            
        message += f"Take Profit: ${take_profit:.2f} (3%)\n"
        message += f"Stop Loss: ${stop_loss:.2f} (2%)\n"
        
    elif signal_type == "EXIT":
        message = f"⚠️ EXIT SIGNAL ⚠️\n\n"
        message += f"Symbol: {signal['symbol']}\n"
        message += f"Current Price: ${signal['price']:.2f}\n"
        message += f"Confidence: {signal['confidence']:.1f}/100\n"
        
    elif "AVG_DOWN" in signal_type:
        position_type = "LONG" if "LONG" in signal_type else "SHORT"
        message = f"📉 AVERAGE DOWN {position_type} SIGNAL 📉\n\n"
        message += f"Symbol: {signal['symbol']}\n"
        message += f"Current Price: ${signal['price']:.2f}\n"
        message += f"Confidence: {signal['confidence']:.1f}/100\n"
    
    return message

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
