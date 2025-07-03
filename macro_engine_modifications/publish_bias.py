import os
import json
import logging
from google.cloud import pubsub_v1
from datetime import datetime, timedelta

# --- Configuration ---
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = "macro-bias-updates"
TTL_HOURS = 4  # TTL for macro bias

# --- Publisher ---
publisher = None
topic_path = None
if PROJECT_ID:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def publish_macro_bias(symbol: str, confidence: float, direction: str):
    """
    Publishes the MACRO engine's directional bias to Pub/Sub.
    This function would be called within the MACRO engine's logic
    whenever a new SWING signal is generated or updated.
    
    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        confidence: Confidence score (0-100)
        direction: "LONG" or "SHORT"
    """
    if not publisher or not topic_path:
        logging.warning("[MACRO_ENGINE] Publisher not initialized. Cannot send bias update.")
        return

    # Calculate expiration time (4 hours from now)
    expires_at = (datetime.utcnow() + timedelta(hours=TTL_HOURS)).isoformat()

    payload = {
        "symbol": symbol,
        "macro_confidence": confidence,
        "macro_direction": direction,  # "LONG" or "SHORT"
        "source": "macro_engine",
        "expires_at": expires_at,
        "published_at": datetime.utcnow().isoformat()
    }
    message_data = json.dumps(payload).encode("utf-8")
    
    try:
        future = publisher.publish(topic_path, message_data)
        message_id = future.result()
        logging.info(f"Published macro bias for {symbol}: {direction} ({confidence}%). Message ID: {message_id}")
        logging.info(f"Bias will expire at {expires_at}")
        return message_id
    except Exception as e:
        logging.error(f"Failed to publish macro bias for {symbol}: {e}")
        return None

# --- Example Usage (to be integrated into the actual MACRO engine) ---
if __name__ == '__main__':
    # This is a simulation of the MACRO engine generating a signal
    logging.basicConfig(level=logging.INFO)
    if not PROJECT_ID:
        print("GCP_PROJECT_ID environment variable not set. This is a dry run.")
    
    print("Simulating MACRO engine generating a strong LONG signal for BTCUSDT...")
    publish_macro_bias(symbol="BTCUSDT", confidence=85.0, direction="LONG")
    
    print("Simulating MACRO engine generating a weaker SHORT signal for ETHUSDT...")
    publish_macro_bias(symbol="ETHUSDT", confidence=72.0, direction="SHORT") 