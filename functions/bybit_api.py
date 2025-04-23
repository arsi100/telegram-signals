import logging
import requests
import json
import time
from cryptocompare_api import fetch_cryptocompare_kline

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fetch_kline_data(symbol, interval="5", limit=1000, category="linear"):
    """
    Fetch kline (candlestick) data from Bybit API.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        interval: Candlestick interval in minutes (default: "5")
        limit: Number of candlesticks to return (default: 1000)
        category: Market category, linear for futures (default: "linear")
        
    Returns:
        List of candlestick data or None on error
    """
    try:
        url = f"https://api.bybit.com/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("retCode") == 0 and data.get("result", {}).get("list"):
            # Bybit returns newest candles first, reverse to get chronological order
            klines = data["result"]["list"]
            klines.reverse()
            
            # Convert to a more usable format
            formatted_klines = []
            for k in klines:
                formatted_klines.append({
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "turnover": float(k[6])
                })
                
            logger.info(f"Successfully fetched {len(formatted_klines)} klines for {symbol} from Bybit")
            return formatted_klines
        else:
            logger.error(f"Error fetching kline data from Bybit: {data}")
            # Use backup source
            return fetch_cryptocompare_kline(symbol.replace("USDT", ""), "USDT")
    
    except Exception as e:
        logger.error(f"Exception in fetch_kline_data for {symbol}: {str(e)}")
        # Use backup source
        return fetch_cryptocompare_kline(symbol.replace("USDT", ""), "USDT")

def setup_websocket_connection(symbols):
    """
    Set up a WebSocket connection to Bybit for real-time kline data.
    This is an alternative to polling the REST API.
    
    Args:
        symbols: List of trading pair symbols
        
    Note: 
        This function is provided as an alternative implementation.
        The main application uses the REST API for simplicity.
    """
    import websocket
    import threading
    
    def on_message(ws, message):
        data = json.loads(message)
        if "topic" in data and data["topic"].startswith("kline.5."):
            symbol = data["topic"].split(".")[-1]
            kline = data["data"][0]
            logger.info(f"Received kline for {symbol}: {kline}")
            # Process the kline data here
    
    def on_error(ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
    
    def on_open(ws):
        logger.info("WebSocket connection opened")
        # Subscribe to kline topics
        topics = [f"kline.5.{symbol}" for symbol in symbols]
        ws.send(json.dumps({
            "op": "subscribe",
            "args": topics
        }))
    
    websocket_url = "wss://stream.bybit.com/v5/public/linear"
    ws = websocket.WebSocketApp(
        websocket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Start WebSocket in a new thread
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    return ws
