import requests
import logging
import datetime
import time
import math # Import math for timestamp calculation if needed
from typing import Optional
import json

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
    
    logger.info(f"Fetching Kraken Kline data for {symbol} ({resolution}). URL: {api_url}, Params: {params}")
    
    try:
        response = requests.get(api_url, params=params, timeout=15)
        logger.debug(f"Kraken API request for {symbol} sent. Status: {response.status_code}. Response headers: {response.headers}")
        
        response_text_snippet = response.text[:500] + "..." if len(response.text) > 500 else response.text
        logger.debug(f"Kraken API response text (snippet) for {symbol}: {response_text_snippet}")

        response.raise_for_status()
        
        if response.status_code == 200:
            try:
                raw_data = response.json()
                logger.debug(f"Kraken API response text (snippet) for {symbol}: {str(raw_data)[:200]}")
                
                if 'candles' not in raw_data or not isinstance(raw_data['candles'], list):
                    logger.error(f"Kraken API response for {symbol} is missing 'candles' array or it's not a list.")
                    return None

                processed_data = []
                for candle in raw_data['candles']:
                    # Convert Kraken's timestamp (milliseconds) to seconds for consistency
                    # and ensure all fields are present and correctly typed.
                    try:
                        processed_candle = {
                            'timestamp': int(candle['time']) // 1000, # ms to s
                            'open': float(candle['open']),
                            'high': float(candle['high']),
                            'low': float(candle['low']),
                            'close': float(candle['close']),
                            'volume': float(candle['volume'])
                        }
                        processed_data.append(processed_candle)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Skipping candle due to missing field or parsing error: {candle}. Error: {e}")
                        continue
                
                logger.info(f"Received {len(raw_data['candles'])} raw kline data points from Kraken API for {symbol}.")
                logger.info(f"Successfully processed {len(processed_data)} of {len(raw_data['candles'])} raw kline data points for {symbol}.")
                if processed_data:
                     logger.debug(f"Last processed kline for {symbol}: {processed_data[-1]}")
                return processed_data
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON response from Kraken for {symbol}. Response: {response.text}")
        else:
             logger.error(f"Unexpected response structure from Kraken API for {symbol}. 'candles' key missing or not a list. Full Response: {response.text}")
             return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Kraken Kline data for {symbol}: {e}")
        if e.response is not None:
            logger.error(f"Kraken API Error Status: {e.response.status_code}")
            logger.error(f"Kraken API Error Response Text: {e.response.text}")
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