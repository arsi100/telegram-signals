import os
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from google.cloud import bigtable
from google.cloud.bigtable.row_set import RowSet

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
INSTANCE_ID = "cryptotracker-bigtable"
TABLE_ID = "market-data-1m" # The table with OHLCV data

# --- Bigtable Client ---
# Initialize client and table objects globally for reuse
try:
    if PROJECT_ID:
        bigtable_client = bigtable.Client(project=PROJECT_ID)
        instance = bigtable_client.instance(INSTANCE_ID)
        table = instance.table(TABLE_ID)
        logging.info("Bigtable client initialized for data_fetcher.")
    else:
        table = None
        logging.warning("GCP_PROJECT_ID not set. Data fetcher will not work.")
except Exception as e:
    table = None
    logging.error(f"Failed to initialize Bigtable client: {e}")

async def fetch_historical_data(symbol: str, minutes_to_fetch: int) -> pd.DataFrame:
    """
    Asynchronously fetches the last N minutes of 1m candle data from Bigtable.
    This is designed to be called from the async notifier.
    """
    if not table:
        logging.error("Bigtable client not available.")
        return pd.DataFrame()

    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=minutes_to_fetch)
        
        start_key = f"{symbol}#{int(start_time.timestamp())}".encode('utf-8')
        end_key = f"{symbol}#{int(end_time.timestamp())}".encode('utf-8')

        row_set = RowSet()
        row_set.add_row_range_from_keys(start_key, end_key)

        # The read_rows method is synchronous, but we can call it from an async function.
        # For true async, one would use the gRPC asyncio API, but this is sufficient here.
        rows = table.read_rows(row_set=row_set)

        data = []
        for row in rows:
            row_key_str = row.row_key.decode('utf-8')
            parts = row_key_str.split('#')
            if len(parts) != 2:
                continue
            
            ts = int(parts[1])
            record = {'timestamp': datetime.fromtimestamp(ts, tz=timezone.utc)}
            
            for cf, cols in row.cells.items():
                for col, cell_list in cols.items():
                    if cell_list:
                        qualifier = col.decode('utf-8')
                        value = float(cell_list[0].value.decode('utf-8'))
                        record[qualifier] = value
            data.append(record)
            
        if not data:
            logging.warning(f"No data fetched for {symbol} in the last {minutes_to_fetch} minutes.")
            return pd.DataFrame()

        df = pd.DataFrame(data).set_index('timestamp').sort_index()
        # Ensure standard column names
        df.rename(columns={'time': 'timestamp', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True, errors='ignore')
        return df

    except Exception as e:
        logging.error(f"Failed to fetch data for {symbol} from Bigtable: {e}", exc_info=True)
        return pd.DataFrame() 