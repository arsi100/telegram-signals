import sys, os, time, datetime, pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.bybit_api import fetch_kline_data

SYMBOL = "SOLUSDT"
INTERVAL = "5"  # 5-minute candles
LIMIT = 200  # ~16 hours of data
CATEGORY = "linear"

raw = fetch_kline_data(SYMBOL, INTERVAL, LIMIT, CATEGORY)
if not raw:
    print("Failed to fetch data")
    sys.exit(1)

# Bybit returns list of lists with strings
cols = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]
df = pd.DataFrame(raw, columns=cols)
# convert types
numeric_cols = cols[1:]
for c in numeric_cols:
    df[c] = pd.to_numeric(df[c])

df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

df.sort_values("timestamp", inplace=True)

df.set_index("timestamp", inplace=True)

# Simple indicators
window = 20

df["sma"] = df["close"].rolling(window).mean()
df["vol_ma"] = df["volume"].rolling(window).mean()

last = df.iloc[-1]
prev = df.iloc[-2]

print("=== QUICK 5-MIN CANDLE RESEARCH ===")
print(f"Last candle @ {last.name}: O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} Vol={last['volume']:.0f}")
print(f"20-candle SMA: {last['sma']:.2f} | Price %.2f%% above SMA" % ((last['close']/last['sma']-1)*100 if pd.notna(last['sma']) else float('nan')))
print(f"Volume %.2f× avg" % (last['volume']/last['vol_ma'] if pd.notna(last['vol_ma']) else float('nan')))
print("Prev candle close %.2f -> now %.2f (%.2f%%)" % (prev['close'], last['close'], (last['close']/prev['close']-1)*100))

# Detect simple pattern
if last['close'] > last['open'] and last['volume'] > 1.5 * last['vol_ma']:
    print("Bullish momentum candle with elevated volume.")
elif last['close'] < last['open'] and last['volume'] > 1.5 * last['vol_ma']:
    print("Bearish momentum candle with elevated volume.")

# Output recent min/max
recent_high = df['high'][-window:].max()
recent_low = df['low'][-window:].min()
print(f"Recent {window}-candle high {recent_high:.2f} | low {recent_low:.2f}") 