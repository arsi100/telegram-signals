"""generate_candles.py

Fetches raw 1-minute candles for requested symbols from Bigtable (same helper
used by the back-tester), enriches them with RSI(14) and 20-period volume MA,
then writes <symbol>_data.csv files into ./candle_cache/.

Run:
    python analysis/generate_candles.py --symbols SOLUSDT BTCUSDT ETHUSDT --days 30
"""
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add the parent directory to the Python path so we can import from functions/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.bybit_api import fetch_kline_data

def fetch_and_save_candles(symbol, interval="5", limit=1000, category="linear"):
    """
    Fetch candlestick data from Bybit and save to CSV.
    
    Args:
        symbol: Trading pair symbol (e.g., "SOLUSDT")
        interval: Candlestick interval in minutes (default: "5")
        limit: Number of candlesticks to fetch (default: 1000)
        category: Market category (default: "linear")
    """
    print(f"Fetching {limit} candles for {symbol}...")
    
    # Fetch the data
    candles = fetch_kline_data(symbol, interval, limit, category)
    
    if not candles:
        print(f"No data received for {symbol}")
        return
        
    # Convert to DataFrame
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Convert string values to float
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Sort by timestamp
    df = df.sort_values('timestamp')
    
    # Create candle_cache directory if it doesn't exist
    os.makedirs('candle_cache', exist_ok=True)
    
    # Save to CSV
    filename = f"candle_cache/{symbol}_data.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} candles to {filename}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

if __name__ == "__main__":
    # Fetch data for SOLUSDT
    df = fetch_and_save_candles("SOLUSDT")
    
    # Also fetch BTC and ETH for context
    fetch_and_save_candles("BTCUSDT")
    fetch_and_save_candles("ETHUSDT")