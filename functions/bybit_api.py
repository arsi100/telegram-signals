import os
import time
import json
import logging
import requests
import websocket
import threading
from . import config

# Set up logging
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
        url = "https://api.bybit.com/v5/market/kline"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "category": category
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data["retCode"] == 0 and "list" in data["result"]:
            # Format: [timestamp, open, high, low, close, volume, turnover]
            return data["result"]["list"]
        else:
            logger.error(f"Failed to fetch kline data: {data.get('retMsg', 'Unknown error')}")
            return None
    except Exception as e:
        logger.error(f"Error fetching kline data: {e}")
        return None

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
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            if "data" in data:
                logger.info(f"Received kline data: {data['data'][0]}")
                # Process the real-time data here
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_error(ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
    
    def on_open(ws):
        logger.info("WebSocket connection established")
        # Subscribe to kline data for the symbols
        for symbol in symbols:
            ws.send(json.dumps({
                "op": "subscribe",
                "args": [f"kline.5.{symbol}"]
            }))
    
    # Set up WebSocket connection
    ws = websocket.WebSocketApp(
        "wss://stream.bybit.com/v5/public/linear",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    
    # Run WebSocket in a separate thread
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    return ws