import requests
import logging
import datetime
import time
import math # Import math for timestamp calculation if needed

# Configure logging
logger = logging.getLogger(__name__)

# Base URL from Kraken Futures Charts API v1 documentation
KRAKEN_FUTURES_API_BASE_URL = "https://futures.kraken.com/api/charts/v1"

# Define constants
RESOLUTION = "5m" # Resolution parameter for the API path
TICK_TYPE = "trade" # Tick type parameter for the API path
# DATA_LIMIT = 150 # We don't use limit directly, API might have default or use from/to

def fetch_kline_data(symbol: str):
    """
    Fetches Kline (OHLCV) data for a given symbol from the Kraken Futures Charts API.

    Args:
        symbol: The trading pair symbol (e.g., 'PF_XBTUSD', 'PF_ETHUSD').

    Returns:
        A list of dictionaries, where each dictionary represents a candlestick
        in a standardized format ({'timestamp': epoch_sec, 'open': float, ...}),
        or None if an error occurs. Returns data in ascending time order (oldest first).
    """
    # Construct the endpoint using path parameters
    endpoint = f"/{TICK_TYPE}/{symbol}/{RESOLUTION}"
    
    # Optional: Calculate 'from' timestamp to fetch a specific number of candles
    # Example: Fetch last 150 candles (150 * 5 minutes = 750 minutes = 45000 seconds)
    # now_seconds = math.floor(time.time())
    # from_seconds = now_seconds - (150 * 5 * 60) 
    # params = {'from': from_seconds}
    
    # For now, fetch default (likely most recent) candles without from/to
    params = {} 
    
    api_url = f"{KRAKEN_FUTURES_API_BASE_URL}{endpoint}"
    
    logger.info(f"Fetching Kraken Kline data for {symbol} from {api_url}")
    
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