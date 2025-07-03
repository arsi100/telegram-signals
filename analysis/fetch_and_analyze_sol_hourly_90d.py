import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging
import sys, os

# Ensure project root is on path so `functions` package is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Local Bybit helper
from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

SYMBOL = "SOLUSDT"
INTERVAL_MINUTES = "60"  # 1-hour candles in Bybit v5
LOOKBACK_DAYS = 90

# ---------------------------------------------------------------------------
# 1. Fetch 90-day history (≈ 2160 candles)
# ---------------------------------------------------------------------------
logger.info("Fetching %d days of 1h candles for %s", LOOKBACK_DAYS, SYMBOL)

# Bybit allows up to 1000 candles per call. Do two calls with limit=1000 and
# then splice the results; if limit supports >1000 we still get full set.
all_klines = fetch_kline_data(SYMBOL, interval=INTERVAL_MINUTES, limit=2000, category="linear")
if not all_klines or len(all_klines) < 2000:
    # Fallback – attempt two calls using cursor logic is overkill; quickly fetch 2×1000 by trimming timestamp.
    logger.warning("Single call did not return ≥2000 candles (got %s). Switching to two-step fetch.", len(all_klines) if all_klines else None)
    recent_klines = fetch_kline_data(SYMBOL, interval=INTERVAL_MINUTES, limit=1000, category="linear")
    # Determine last timestamp of first batch and query earlier window
    if recent_klines:
        last_ts_ms = int(float(recent_klines[0][0]))  # Ensure numeric
        # Bybit timestamps are ms; convert to seconds for rounding then subtract 1000 hours.
        from_ms = last_ts_ms - 1000 * 60 * 60 * 1000
        older_url = "https://api.bybit.com/v5/market/kline"
        import requests
        params = {
            "symbol": SYMBOL,
            "interval": INTERVAL_MINUTES,
            "limit": 1000,
            "category": "linear",
            "end": last_ts_ms,
        }
        resp = requests.get(older_url, params=params, timeout=15)
        older_klines = []
        if resp.status_code == 200 and resp.json().get("retCode") == 0:
            older_klines = resp.json()["result"].get("list", [])
        all_klines = recent_klines + older_klines

if not all_klines:
    logger.error("Failed to fetch klines – exiting")
    exit(1)

logger.info("Fetched %d raw candles", len(all_klines))

# ---------------------------------------------------------------------------
# 2. Convert to DataFrame (Bybit returns newest-first list of lists)
#    Each list: [timestamp(ms), open, high, low, close, volume, turnover]
# ---------------------------------------------------------------------------
cols = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]
df = pd.DataFrame(all_klines, columns=cols)
# Convert and order oldest->newest
for c in ["open", "high", "low", "close", "volume", "turnover"]:
    df[c] = df[c].astype(float)
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.sort_values("timestamp").reset_index(drop=True)

# Keep the most recent 90 days exactly
cutoff = df["timestamp"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
df = df[df["timestamp"] >= cutoff].reset_index(drop=True)
logger.info("After trimming we have %d candles (expected ~2160)", len(df))

# ---------------------------------------------------------------------------
# 3. Compute intra-hour stats and identify opportunities (>0.5 % range)
# ---------------------------------------------------------------------------
df["move_pct"] = (df["high"] - df["low"]) / df["low"] * 100
opps_idx = df.index[df["move_pct"] > 0.5]

records = []

for idx in opps_idx:
    row = df.loc[idx]
    open_price = row["open"]
    high = row["high"]
    low = row["low"]
    move_pct = row["move_pct"]
    timestamp = row["timestamp"]

    # draw-down metrics within the trigger hour
    drawdown_pct = (low - open_price) / open_price * 100

    # Time to recovery → search forward until close >= open_price
    recovery_minutes = None
    max_gain_4h = None
    max_gain_8h = None
    max_gain_24h = None
    max_future_high = None

    # Look ahead up to 24 h
    future_slice = df.iloc[idx + 1 : idx + 1 + 24]
    if not future_slice.empty:
        # first candle where close >= open_price
        recovery_rows = future_slice[future_slice["close"] >= open_price]
        if not recovery_rows.empty:
            recovery_idx = recovery_rows.index[0]
            recovery_minutes = (df.loc[recovery_idx, "timestamp"] - timestamp).total_seconds() / 60

        # compute max gains in specified windows
        for horizon, label in [(4, "max_gain_4h"), (8, "max_gain_8h"), (24, "max_gain_24h")]:
            slice_h = future_slice.iloc[:horizon]
            if not slice_h.empty:
                max_high = slice_h["high"].max()
                gain_pct = (max_high - open_price) / open_price * 100
                locals()[label] = gain_pct

    records.append(
        {
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": row["close"],
            "range_pct": move_pct,
            "drawdown_pct": drawdown_pct,
            "recovery_minutes": recovery_minutes,
            "max_gain_4h_pct": max_gain_4h,
            "max_gain_8h_pct": max_gain_8h,
            "max_gain_24h_pct": max_gain_24h,
        }
    )

opps_df = pd.DataFrame(records)
logger.info("Identified %d opportunities (>0.5 %% hourly range)", len(opps_df))

# ---------------------------------------------------------------------------
# 4. Save results
# ---------------------------------------------------------------------------
opps_file = OUTPUT_DIR / "sol_90d_opportunities.csv"
opps_df.to_csv(opps_file, index=False)
logger.info("Detailed opportunities saved to %s", opps_file)

# Summary
summary = {
    "total_hours": len(df),
    "total_opportunities": len(opps_df),
    "avg_opportunities_per_day": len(opps_df) / LOOKBACK_DAYS,
    "avg_range_pct": opps_df["range_pct"].mean(),
    "avg_drawdown_pct": opps_df["drawdown_pct"].mean(),
    "worst_drawdown_pct": opps_df["drawdown_pct"].min(),
    "median_recovery_minutes": opps_df["recovery_minutes"].median(),
}

summary_file = OUTPUT_DIR / "sol_90d_summary.txt"
with open(summary_file, "w") as f:
    f.write("SOL – 90-day 1h Opportunity Analysis\n")
    f.write("===================================\n\n")
    for k, v in summary.items():
        f.write(f"{k}: {v}\n")
logger.info("Summary saved to %s", summary_file)

print("Analysis complete. See CSV and summary in analysis_results/.") 