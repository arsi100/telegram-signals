import os
import json
import logging
from pybit.unified_trading import WebSocket
from google.cloud import pubsub_v1
import time
import requests
import sys
import asyncio

# Configure logging with explicit handler
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variables that will be initialized in start_data_ingestion
publisher = None
topic_path = None

# The symbol(s) to subscribe to for real-time data
SYMBOLS = [
    "BTCUSDT",
    "SOLUSDT",
    "ETHUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "SEIUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "ADAUSDT"
]

def handle_message(message):
    """
    Callback function to process messages received from the Bybit WebSocket.
    This function publishes the message to a Google Cloud Pub/Sub topic.
    """
    if publisher and topic_path:
        try:
            # The message is a dictionary, convert it to a JSON string
            data_str = json.dumps(message)
            # Encode the JSON string to bytes, which is required by Pub/Sub
            data_bytes = data_str.encode("utf-8")
            
            # Publish the message to the Pub/Sub topic
            future = publisher.publish(topic_path, data_bytes)
            future.result()  # Wait for the publish operation to complete
            logger.info(f"Published message to Pub/Sub: {data_str[:100]}...")  # Log first 100 chars
        except Exception as e:
            logger.error(f"Error publishing message to Pub/Sub: {e}")
    else:
        logger.warning("Publisher not initialized, skipping message.")

def start_data_ingestion():
    """Initializes and starts the Bybit WebSocket subscription."""
    global publisher, topic_path
    
    # Force flush to ensure logs are visible
    sys.stdout.flush()
    
    # Initialize Pub/Sub inside the function
    logger.info("="*50)
    logger.info("STARTING DATA INGESTION SERVICE")
    logger.info("="*50)
    
    # Get PROJECT_ID with fallbacks
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
    logger.info(f"Environment GCP_PROJECT_ID: '{PROJECT_ID}'")
    
    if not PROJECT_ID:
        logger.info("PROJECT_ID not in environment, trying metadata server...")
        try:
            response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers={"Metadata-Flavor": "Google"},
                timeout=2
            )
            if response.status_code == 200:
                PROJECT_ID = response.text
                logger.info(f"Retrieved PROJECT_ID from metadata server: {PROJECT_ID}")
            else:
                logger.warning(f"Metadata server returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not retrieve PROJECT_ID from metadata server: {e}")
    
    if not PROJECT_ID:
        PROJECT_ID = "telegram-signals-205cc"
        logger.warning(f"Using hardcoded PROJECT_ID: {PROJECT_ID}")
    
    TOPIC_NAME = "raw-tick-data-bybit"
    
    # Initialize publisher
    logger.info(f"Initializing Pub/Sub publisher for project: '{PROJECT_ID}' and topic: '{TOPIC_NAME}'")
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        logger.info(f"Publisher client created successfully")
        logger.info(f"Topic path: {topic_path}")
        
        # Test publish to verify it works
        test_message = {"test": True, "timestamp": time.time()}
        test_future = publisher.publish(topic_path, json.dumps(test_message).encode('utf-8'))
        test_future.result()
        logger.info("TEST PUBLISH SUCCESSFUL - Publisher is working!")
        
    except Exception as e:
        logger.error(f"FATAL: Failed to initialize Pub/Sub publisher. Exception: {e}", exc_info=True)
        logger.error("Cannot continue without publisher. Exiting.")
        return

    # Initialize WebSocket
    logger.info("Initializing Bybit WebSocket connection...")
    try:
        ws = WebSocket(testnet=False, channel_type="linear")
        logger.info("WebSocket client created")
        
        # Build the list of topics to subscribe to
        topics = [f"tickers.{symbol}" for symbol in SYMBOLS]
        
        # Subscribe to the public tickers stream for multiple symbols
        ws.subscribe(
            topics,
            callback=handle_message
        )
        logger.info(f"Subscribed to tickers for: {', '.join(SYMBOLS)}")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket: {e}", exc_info=True)
        return
    
    # Keep the script running
    logger.info("Data ingestion service is now running...")
    logger.info("="*50)
    
    while True:
        time.sleep(60)
        logger.info("Data ingestion service heartbeat - still running...")

if __name__ == "__main__":
    start_data_ingestion()
