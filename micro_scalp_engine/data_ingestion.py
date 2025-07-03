import os
import json
import logging
from pybit.unified_trading import WebSocket
from google.cloud import pubsub_v1

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# GCP Project ID and Pub/Sub Topic Name
# These should be set as environment variables for security and flexibility.
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
TOPIC_NAME = "raw-tick-data-bybit"
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

# --- WebSocket and Pub/Sub Client Initialization ---
try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
except Exception as e:
    logging.error(f"Failed to initialize Pub/Sub publisher: {e}")
    publisher = None
    topic_path = None

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
            logging.info(f"Published message to {TOPIC_NAME}: {data_str}")
        except Exception as e:
            logging.error(f"Error publishing message to Pub/Sub: {e}")
    else:
        logging.warning("Publisher not initialized, skipping message.")

def start_data_ingestion():
    """
    Initializes and starts the Bybit WebSocket connection.
    """
    logging.info("Starting data ingestion service...")
    
    if not PROJECT_ID:
        logging.error("GCP_PROJECT_ID environment variable not set. Exiting.")
        return

    # Initialize the WebSocket client for the public channel
    # testnet=False uses the mainnet
    ws = WebSocket(
        testnet=False,
        channel_type="linear",
    )

    # Subscribe to the public trade channel for the specified symbols
    for symbol in SYMBOLS:
        ws.trade_stream(
            symbol=symbol,
            callback=handle_message
        )
    
    logging.info(f"Subscribed to trade streams for: {', '.join(SYMBOLS)}")
    logging.info("Service is now listening for real-time market data...")

    # The WebSocket client runs in a background thread, so we just keep the main thread alive.
    # In a real Cloud Run service, the service would just stay running.
    # For local testing, we can use a simple loop.
    while True:
        pass

if __name__ == "__main__":
    # This block allows the script to be run directly for testing purposes.
    # In a production Cloud Run environment, you would use a web server like Gunicorn
    # to run the application and call start_data_ingestion().
    start_data_ingestion()
