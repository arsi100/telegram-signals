import os
import json
import logging
from datetime import datetime, timezone
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from google.cloud import bigtable
import threading

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
SUBSCRIPTION_NAME = "raw-tick-data-bybit-sub" # A dedicated subscription for this processor
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

# --- Bigtable Client ---
try:
    bigtable_client = bigtable.Client(project=PROJECT_ID)
    instance = bigtable_client.instance(INSTANCE_ID)
    table = instance.table(TABLE_ID)
    logging.info(f"Successfully connected to Bigtable table '{TABLE_ID}'.")
except Exception as e:
    logging.error(f"Failed to connect to Bigtable: {e}")
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

def process_message(message: pubsub_v1.subscriber.message.Message) -> None:
    """Callback function to process each Pub/Sub message."""
    try:
        data = json.loads(message.data.decode("utf-8"))
        
        # We only care about the 'data' part of the Bybit message which contains trades
        trades = data.get("data", [])
        if not trades:
            message.ack()
            return
            
        # Acquire lock to safely modify the shared active_candles dictionary
        with candle_lock:
            for trade in trades:
                price = float(trade['p'])
                volume = float(trade['v'])
                symbol = trade['s']
                # Bybit timestamp is in milliseconds
                trade_time = datetime.fromtimestamp(int(trade['T']) / 1000, tz=timezone.utc)

                # Aggregate into 1-minute candles
                minute_timestamp = int(trade_time.replace(second=0, microsecond=0).timestamp())
                candle_key = (symbol, minute_timestamp)

                if candle_key not in active_candles:
                    # If this is the first tick for a new minute, process any old candles
                    flush_completed_candles(minute_timestamp)
        
                    # Start a new candle
                    active_candles[candle_key] = {
                        'open': price,
                        'high': price,
                        'low': price,
                        'close': price,
                        'volume': volume
                    }
                else:
                    # Update the existing candle
                    candle = active_candles[candle_key]
                    candle['high'] = max(candle['high'], price)
                    candle['low'] = min(candle['low'], price)
                    candle['close'] = price
                    candle['volume'] += volume

        message.ack()
    except Exception as e:
        logging.error(f"Error processing message: {e}", exc_info=True)
        message.nack()

def flush_completed_candles(current_minute_timestamp):
    """
    Finds and writes any candles that are now complete.
    IMPORTANT: This must be called from a block that already holds the candle_lock.
    """
    completed_keys = []
    # Create a copy of the items to iterate over, which is safer.
    for (symbol, ts), candle in list(active_candles.items()):
        if ts < current_minute_timestamp:
            write_candle_to_bigtable(symbol, ts, candle)
            completed_keys.append((symbol, ts))
            
    # Remove the flushed candles from our active state
    for key in completed_keys:
        del active_candles[key]

def main():
    """Starts the data processing service."""
    if not table:
        logging.critical("Exiting: Bigtable is not configured.")
        return

    logging.info(f"Starting data processor, subscribing to '{SUBSCRIPTION_NAME}'...")
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)

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

if __name__ == "__main__":
    main()
