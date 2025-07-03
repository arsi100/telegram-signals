import os
import json
import logging
import requests
from google.cloud import pubsub_v1
from datetime import datetime, timezone

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# GCP Project and Pub/Sub Topic from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("KRAKEN_OHLC_TOPIC_ID", "ohlc-data-kraken")
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", 5)) # Use 5-min as per optimization note

# List of symbols to fetch from Kraken. Note: Kraken uses XBT for BTC.
# This list should be aligned with Kraken's pair naming conventions.
SYMBOLS = [
    "XBT/USD", "ETH/USD", "SOL/USD", "XRP/USD", "DOGE/USD", "ADA/USD",
    "MATIC/USD", "DOT/USD", "TRX/USD", "LTC/USD", "AVAX/USD", "LINK/USD",
    "ATOM/USD", "ETC/USD", "BCH/USD", "NEAR/USD", "UNI/USD", "AAVE/USD",
    "ALGO/USD", "XLM/USD", "MANA/USD", "SAND/USD"
]

# --- Pub/Sub Publisher ---
publisher = None
topic_path = None
if PROJECT_ID:
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        logging.info(f"Pub/Sub publisher initialized for topic: {topic_path}")
    except Exception as e:
        logging.error(f"Failed to initialize Pub/Sub client. Error: {e}")
        # In a Cloud Function, a hard exit might not be best.
        # Let the invocation fail naturally if the client is not available.
        publisher = None 
else:
    logging.warning("GCP_PROJECT_ID not set. Publisher will be in DRY_RUN mode.")

def fetch_kraken_ohlc(pair: str, interval: int) -> list:
    """Fetches OHLC data for a given pair from Kraken's public API."""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {
        "pair": pair,
        "interval": interval
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            logging.error(f"Kraken API error for {pair}: {data['error']}")
            return []

        # The actual OHLC data is nested under the pair name in the result
        result_pair_key = list(data.get("result", {}).keys())[0]
        ohlc_data = data.get("result", {}).get(result_pair_key, [])
        return ohlc_data
        
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP request to Kraken failed for {pair}: {e}")
        return []
    except (json.JSONDecodeError, IndexError) as e:
        logging.error(f"Failed to parse Kraken response for {pair}: {e}")
        return []

def handler(event, context):
    """
    Cloud Function entry point. Triggered by Cloud Scheduler.
    Fetches OHLC data for all symbols and publishes to Pub/Sub.
    """
    logging.info(f"Starting Kraken OHLC fetch cycle for {len(SYMBOLS)} symbols.")
    
    if not publisher or not topic_path:
        logging.critical("Publisher not initialized. Cannot send data. Exiting.")
        return 'Publisher not initialized', 500

    total_published = 0
    for symbol in SYMBOLS:
        # Kraken uses pair names without slashes in some contexts, but the API needs it.
        # We will use the format required by the API and store it that way.
        logging.info(f"Fetching OHLC for {symbol}...")
        ohlc_records = fetch_kraken_ohlc(symbol, FETCH_INTERVAL_MINUTES)
        
        for record in ohlc_records:
            # record format: [time, open, high, low, close, vwap, volume, count]
            try:
                payload = {
                    "symbol": symbol,
                    "timestamp": record[0],
                    "open": record[1],
                    "high": record[2],
                    "low": record[3],
                    "close": record[4],
                    "volume": record[6],
                    "source": "kraken",
                    "interval_minutes": FETCH_INTERVAL_MINUTES,
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
                message_data = json.dumps(payload).encode("utf-8")
                
                if publisher and topic_path:
                    publisher.publish(topic_path, message_data)
                    total_published += 1
                else:
                    logging.info(f"[DRY_RUN] Would publish: {payload}")

            except (TypeError, IndexError) as e:
                logging.error(f"Malformed OHLC record for {symbol}: {record}. Error: {e}")

    logging.info(f"Kraken OHLC fetch cycle complete. Published {total_published} messages.")
    return 'OK', 200

# To test locally without a GCP environment:
if __name__ == "__main__":
    logging.info("Running Kraken fetcher locally for a single test run...")
    handler(None, None) 