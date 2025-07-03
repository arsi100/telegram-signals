import os
import json
import uuid
import logging
from google.cloud import pubsub_v1

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "telegram-signals-205cc")
TOPIC_NAME = "trade-signals"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_dummy_signal():
    """Publishes a hardcoded dummy trade signal to the Pub/Sub topic."""
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        logging.info(f"Connected to Pub/Sub topic: {topic_path}")
    except Exception as e:
        logging.error(f"Failed to initialize Pub/Sub publisher: {e}")
        return

    # Create a realistic, but fake, trade signal
    trade_id = f"test_{uuid.uuid4()}"
    dummy_signal = {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "entry_price": 69420.69,
        "tp_price": 70114.90,
        "sl_price": 69073.58,
        "trade_id": trade_id,
        "strategy_id": "v9.9-telegram-test",
        "timestamp": "2025-06-28T18:00:00Z",
        "confidence": 99.9,
        "reason": "Manual test signal for Telegram formatting."
    }

    try:
        message_data = json.dumps(dummy_signal).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        message_id = future.result()
        logging.info(f"Successfully published dummy signal to {TOPIC_NAME}.")
        logging.info(f"Message ID: {message_id}")
        logging.info(f"Trade ID: {trade_id}")
        print("\n✅ Dummy signal sent successfully!")
        print("Please check your Telegram channel for the message.")

    except Exception as e:
        logging.error(f"Error publishing message to Pub/Sub: {e}")
        print(f"\n❌ Failed to send dummy signal. Error: {e}")

if __name__ == "__main__":
    send_dummy_signal() 