import os
import json
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from google.cloud import bigtable
import threading
import time

# --- Configuration ---
SUBSCRIPTION_NAME = "micro-scalp-ticker-data-processor"
INSTANCE_ID = "cryptotracker-bigtable"
TABLE_ID = "market-data-1m"
COLUMN_FAMILY_ID = "market"

# --- In-memory state for aggregating candles ---
# Format: {(symbol, minute_timestamp): {open:_ , high:_, low:_, close:_, volume:_}}
active_candles = {}
# A lock to ensure thread-safe access to the active_candles dictionary
candle_lock = threading.Lock()

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for table
table = None

def write_candle_to_bigtable(symbol, timestamp, candle):
    """Writes a completed candle to the Bigtable database."""
    if not table:
        logging.error("Bigtable client not available. Cannot write candle.")
        return

    try:
        row_key = f"{symbol}#{int(timestamp)}".encode('utf-8')
        row = table.direct_row(row_key)
        
        for key, value in candle.items():
            row.set_cell(COLUMN_FAMILY_ID, key, str(value).encode('utf-8'))
        
        row.commit()
        logging.info(f"Successfully wrote candle to Bigtable: {symbol} at {datetime.fromtimestamp(timestamp, tz=timezone.utc)}")
    except Exception as e:
        logging.error(f"Failed to write candle for {symbol} to Bigtable: {e}")

def process_message(message: pubsub_v1.subscriber.message.Message):
    """Callback function to process incoming tick data."""
    try:
        data_str = message.data.decode("utf-8")
        data = json.loads(data_str)
        
        if "topic" in data and data["topic"].startswith("tickers"):
            tick = data["data"]
            symbol = tick["symbol"]
            price = float(tick["lastPrice"])
            volume = float(tick.get("volume24h", 0))
            
            ts = int(data["ts"]) / 1000 # Convert ms to s
            dt_object = datetime.fromtimestamp(ts, tz=timezone.utc)
            minute_start_ts = (dt_object.replace(second=0, microsecond=0)).timestamp()
            
            key = (symbol, minute_start_ts)
            
            with candle_lock:
                if key not in active_candles:
                    active_candles[key] = {
                        "open": price, "high": price, "low": price, "close": price,
                        "volume": 0, "start_volume": volume, "tick_count": 0
                    }
                
                candle = active_candles[key]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                candle["tick_count"] += 1
                
        message.ack()
    except Exception as e:
        logging.error(f"Error processing message: {message.data}. Error: {e}", exc_info=True)
        message.nack()

def flush_candles(force=False):
    """
    Checks for and writes any completed candles to Bigtable.
    If 'force' is True, writes all candles regardless of completion time.
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    completed_keys = []
    
    with candle_lock:
        for key, candle in active_candles.items():
            symbol, minute_ts = key
            if force or (now_ts - minute_ts) > 60: # If the candle is over a minute old
                final_volume = candle.get("volume", 0)
                candle_to_write = {
                    "open": candle["open"], "high": candle["high"],
                    "low": candle["low"], "close": candle["close"],
                    "volume": final_volume
                }
                write_candle_to_bigtable(symbol, minute_ts, candle_to_write)
                completed_keys.append(key)
        
        for key in completed_keys:
            del active_candles[key]

def periodic_flusher():
    """Runs flush_candles periodically in a background thread."""
    while True:
        time.sleep(60) # Run every minute
        logging.info("Running periodic candle flush...")
        flush_candles()

def start_data_processor():
    """Starts the data processing service."""
    global table
    
    logging.info("Initializing data processor service...")
    
    # Get PROJECT_ID
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
    if not PROJECT_ID:
        PROJECT_ID = "telegram-signals-205cc"
        logging.warning(f"Using hardcoded PROJECT_ID: {PROJECT_ID}")
    
    # Initialize Bigtable client
    try:
        bigtable_client = bigtable.Client(project=PROJECT_ID)
        instance = bigtable_client.instance(INSTANCE_ID)
        table = instance.table(TABLE_ID)
        logging.info(f"Successfully connected to Bigtable table '{TABLE_ID}'.")
    except Exception as e:
        logging.error(f"Failed to connect to Bigtable: {e}")
        return

    logging.info(f"Starting data processor, subscribing to '{SUBSCRIPTION_NAME}'...")
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)

    # Start the periodic flusher thread
    flusher_thread = threading.Thread(target=periodic_flusher, daemon=True)
    flusher_thread.start()

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=process_message)
    logging.info(f"Listening for messages on {subscription_path}...")

    try:
        # The future will block indefinitely.
        streaming_pull_future.result()
    except TimeoutError:
        streaming_pull_future.cancel()
        streaming_pull_future.result()
    except Exception as e:
        logging.error(f"Data processor encountered an error: {e}")
        streaming_pull_future.cancel()

if __name__ == '__main__':
    start_data_processor()
