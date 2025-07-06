"""
Data ingestion service for the micro scalp engine.
Connects to Bybit WebSocket and publishes ticker data to Pub/Sub.
"""

import os
import json
import logging
import sys
from pybit.unified_trading import WebSocket
from google.cloud import pubsub_v1
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT', 'telegram-signals-205cc')
TOPIC_NAME = 'micro-scalp-ticker-data'

# List of symbols to subscribe to
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "ATOMUSDT",
    "AVAXUSDT",
    "CROUSDT",
    "LDOUSDT",
    "WLDUSDT",
    "XRPUSDT"
]

# Global variables for publisher
publisher = None
topic_path = None

def initialize_publisher():
    """Initialize the Pub/Sub publisher."""
    global publisher, topic_path
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        logger.info(f"Publisher initialized for topic: {topic_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize publisher: {e}")
        return False

def handle_message(message):
    """Callback function to handle incoming WebSocket messages."""
    try:
        # Log the raw message for debugging
        logger.debug(f"Received raw message: {message}")
        
        # Extract the ticker data
        if 'topic' in message and message['topic'].startswith('tickers.'):
            symbol = message['topic'].replace('tickers.', '')
            
            # Prepare the message for Pub/Sub
            pubsub_message = {
                'symbol': symbol,
                'data': message['data'],
                'timestamp': message.get('ts', int(datetime.utcnow().timestamp() * 1000)),
                'type': message.get('type', 'snapshot')
            }
            
            # Convert to JSON
            message_json = json.dumps(pubsub_message)
            
            # Publish to Pub/Sub
            if publisher and topic_path:
                future = publisher.publish(
                    topic_path, 
                    message_json.encode('utf-8'),
                    symbol=symbol
                )
                logger.info(f"Published message to Pub/Sub for {symbol}, message_id: {future.result()}")
            else:
                logger.warning("Publisher not initialized, skipping message.")
    except Exception as e:
        logger.error(f"Error handling message: {e}")

def start_data_ingestion():
    """Initializes and starts the Bybit WebSocket subscription."""
    global publisher, topic_path
    
    logger.info("="*50)
    logger.info("Starting Data Ingestion Service")
    logger.info("="*50)
    
    # Initialize publisher
    if not initialize_publisher():
        logger.error("Failed to initialize publisher. Exiting.")
        return
    
    try:
        ws = WebSocket(testnet=False, channel_type="linear")
        logger.info("WebSocket client created")
        
        # Subscribe to each symbol using the correct ticker_stream method
        for symbol in SYMBOLS:
            ws.ticker_stream(
                symbol=symbol,
                callback=handle_message
            )
        
        logger.info(f"Subscription requests sent for: {', '.join(SYMBOLS)}")
    except Exception as e:
        logger.error(f"Error setting up WebSocket: {e}")
        return
    
    logger.info("Data ingestion service is now running...")
    logger.info("="*50)
    
    # Keep the service running
    while True:
        time.sleep(60)
        logger.info("Data ingestion service heartbeat - still running...")

if __name__ == "__main__":
    start_data_ingestion()
