import os
import json
import logging
from pybit.unified_trading import WebSocket
from google.cloud import pubsub_v1
import time
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# GCP Project ID and Pub/Sub Topic Name
# These should be set as environment variables for security and flexibility.
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")

# If PROJECT_ID is not set, try to get it from the metadata server (when running on GCP)
if not PROJECT_ID:
    try:
        response = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=2
        )
        if response.status_code == 200:
            PROJECT_ID = response.text
            logging.info(f"Retrieved PROJECT_ID from metadata server: {PROJECT_ID}")
    except Exception as e:
        logging.warning(f"Could not retrieve PROJECT_ID from metadata server: {e}")

if not PROJECT_ID:
    PROJECT_ID = "telegram-signals-205cc"  # Fallback to hardcoded value
    logging.warning(f"Using hardcoded PROJECT_ID: {PROJECT_ID}")

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
logging.info(f"Attempting to initialize Pub/Sub publisher for project: '{PROJECT_ID}' and topic: '{TOPIC_NAME}'")
try:
    if not PROJECT_ID:
        raise ValueError("GCP_PROJECT_ID environment variable is not set or empty.")
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    logging.info(f"Successfully initialized Pub/Sub publisher for topic: {topic_path}")
except Exception as e:
    logging.error(f"FATAL: Failed to initialize Pub/Sub publisher. Exception: {e}", exc_info=True)
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
    """Initializes and starts the Bybit WebSocket subscription."""
    if not publisher:
        logging.critical("Exiting: Publisher not initialized.")
        return

    # test=False for real connection, ws_proxy for proxy if needed
    ws = WebSocket(testnet=False, channel_type="linear")
    
    # Subscribe to the public tickers stream for multiple symbols
    ws.subscribe_public(
        symbol=",".join(SYMBOLS),
        callback=handle_message,
        topic="tickers"
    )
    logging.info(f"Subscribed to tickers for: {', '.join(SYMBOLS)}")
    
    # Keep the script running
    while True:
        # The sleep is to prevent the loop from consuming too much CPU.
        # The WebSocket client runs in its own thread.
        time.sleep(60)

if __name__ == "__main__":
    start_data_ingestion()
