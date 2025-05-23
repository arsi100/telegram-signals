import requests
import logging
import datetime
import time
import math # Import math for timestamp calculation if needed
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

# Base URL from Kraken Futures Charts API v1 documentation
KRAKEN_FUTURES_API_BASE_URL = "https://futures.kraken.com/api/charts/v1"

# Define constants
RESOLUTION = "5m" # Resolution parameter for the API path
TICK_TYPE = "trade" # Tick type parameter for the API path
# DATA_LIMIT = 150 # We don't use limit directly, API might have default or use from/to

def fetch_kline_data(symbol: str, resolution: str = "5m", limit: Optional[int] = None, from_timestamp_sec: Optional[int] = None, to_timestamp_sec: Optional[int] = None):
    """
    Fetches Kline (OHLCV) data for a given symbol from the Kraken Futures Charts API.

    Args:
        symbol: The trading pair symbol (e.g., 'PF_XBTUSD').
        resolution: Candlestick resolution (e.g., '5m', '15m', '1h').
        limit: Number of candles to fetch (used to calculate 'from_timestamp_sec' if 'from_timestamp_sec' is not set and 'to_timestamp_sec' is now).
        from_timestamp_sec: Start timestamp in seconds.
        to_timestamp_sec: End timestamp in seconds.

    Returns:
        A list of dictionaries, where each dictionary represents a candlestick
        in a standardized format ({'timestamp': epoch_sec, 'open': float, ...}),
        or None if an error occurs. Returns data in ascending time order (oldest first).
    """
    # Construct the endpoint using path parameters
    endpoint = f"/{TICK_TYPE}/{symbol}/{resolution}"
    api_url = f"{KRAKEN_FUTURES_API_BASE_URL}{endpoint}"
    
    params = {}
    if to_timestamp_sec:
        params['to'] = to_timestamp_sec
    if from_timestamp_sec:
        params['from'] = from_timestamp_sec
    elif limit and not from_timestamp_sec: # Use limit to calculate 'from' if 'from' is not specified
        # If 'to' is also not specified, assume we want N most recent candles up to now.
        # If 'to' IS specified, 'limit' might be tricky as Kraken prioritizes from/to.
        # For now, we'll calculate 'from' to get 'limit' candles ending 'now' or at 'to_timestamp_sec'.
        
        end_time_for_limit_calc = to_timestamp_sec if to_timestamp_sec else math.floor(time.time())
        
        res_seconds = 0
        if "m" in resolution:
            res_val = resolution.replace("m", "")
            if res_val.isdigit():
                res_seconds = int(res_val) * 60
        elif "h" in resolution:
            res_val = resolution.replace("h", "")
            if res_val.isdigit():
                res_seconds = int(res_val) * 3600
        
        if res_seconds > 0:
            params['from'] = end_time_for_limit_calc - (limit * res_seconds)
            if not to_timestamp_sec: # If 'to' wasn't specified, set it to now
                 params['to'] = end_time_for_limit_calc
        else:
            logger.warning(f"Could not parse resolution '{resolution}' for limit calculation or resolution was 0. Fetching default for {symbol}.")
    
    logger.info(f"Fetching Kraken Kline data for {symbol} ({resolution}) from {api_url} with params: {params}")
    
    try:
        response = requests.get(api_url, params=params, timeout=15) # Increased timeout slightly
        response.raise_for_status() 
        
        data = response.json()
        
        # --- Data Processing Section ---
        processed_klines = []
        # Response contains a 'candles' key with a list of candle objects
        if isinstance(data, dict) and 'candles' in data and isinstance(data['candles'], list):
             raw_klines = data['candles']
             for kline in raw_klines:
                  # Check if kline is a dictionary with expected keys
                  if isinstance(kline, dict) and all(k in kline for k in ['time', 'open', 'high', 'low', 'close', 'volume']):
                       try:
                            # Convert timestamp from milliseconds to seconds
                            timestamp_sec = int(kline['time']) // 1000 
                            
                            processed_klines.append({
                                 'timestamp': timestamp_sec,
                                 'open': float(kline['open']),
                                 'high': float(kline['high']),
                                 'low': float(kline['low']),
                                 'close': float(kline['close']),
                                 # Convert volume to float to handle decimals
                                 'volume': float(kline['volume']) 
                            })
                       except (ValueError, TypeError) as conv_err:
                            logger.warning(f"Skipping kline due to conversion error: {conv_err} - Data: {kline}")
                  else:
                       logger.warning(f"Skipping malformed kline data point: {kline}")
             
             # Sort by timestamp ascending just in case API doesn't guarantee order
             processed_klines.sort(key=lambda x: x['timestamp'])
             
             logger.info(f"Successfully processed {len(processed_klines)} kline data points for {symbol}")
             # ---- ADDED DEBUG LOG ----
             if processed_klines:
                 logger.debug(f"Last processed kline for {symbol}: {processed_klines[-1]}")
             else:
                 logger.debug(f"Processed klines list is empty for {symbol}.")
             # ---- END DEBUG LOG ----
             return processed_klines
        else:
             logger.error(f"Unexpected response structure from Kraken API for {symbol}. 'candles' key missing or not a list. Response: {data}")
             return None
        # --- End Data Processing Section ---

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Kraken Kline data for {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred processing Kraken data for {symbol}: {e}")
        return None

# Example usage (for testing):
if __name__ == '__main__':
    # Only configure logging when running as standalone script
    logging.basicConfig(level=logging.INFO)
    # Using a known Kraken Futures symbol format
    test_symbol = 'PF_XBTUSD' 
    kline_data = fetch_kline_data(test_symbol)
    if kline_data:
        print(f"Fetched {len(kline_data)} candles for {test_symbol}. Sample of the most recent candle:")
        # Print the last candle (most recent)
        print(kline_data[-1]) 
    else:
        print(f"Failed to fetch data for {test_symbol}") 