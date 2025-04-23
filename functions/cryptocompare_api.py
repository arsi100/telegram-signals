import logging
import requests
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fetch_cryptocompare_kline(symbol, tsym="USDT", interval=5, limit=1000):
    """
    Fetch minute-level data from CryptoCompare API as a backup source.
    
    Args:
        symbol: Base symbol (e.g., "BTC")
        tsym: Quote symbol (default: "USDT")
        interval: Interval in minutes (default: 5)
        limit: Number of data points (default: 1000)
        
    Returns:
        List of candlestick data or None on error
    """
    try:
        api_key = os.environ.get("CRYPTOCOMPARE_API_KEY", "")
        
        # CryptoCompare endpoint for minute data
        url = "https://min-api.cryptocompare.com/data/v2/histominute"
        
        # Parameters for the API request
        params = {
            "fsym": symbol,
            "tsym": tsym,
            "limit": limit,
            "aggregate": interval,  # Aggregate by interval (5 minutes)
            "api_key": api_key
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("Response") == "Success" and "Data" in data:
            klines = data["Data"]["Data"]
            
            # Convert to the same format as Bybit data
            formatted_klines = []
            for k in klines:
                formatted_klines.append({
                    "timestamp": k["time"] * 1000,  # Convert to milliseconds
                    "open": float(k["open"]),
                    "high": float(k["high"]),
                    "low": float(k["low"]),
                    "close": float(k["close"]),
                    "volume": float(k["volumefrom"]),
                    "turnover": float(k["volumeto"])
                })
                
            logger.info(f"Successfully fetched {len(formatted_klines)} klines for {symbol}/{tsym} from CryptoCompare")
            return formatted_klines
        else:
            logger.error(f"Error fetching data from CryptoCompare: {data}")
            return None
    
    except Exception as e:
        logger.error(f"Exception in fetch_cryptocompare_kline for {symbol}: {str(e)}")
        return None
