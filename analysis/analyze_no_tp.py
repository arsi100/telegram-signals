import sys, logging, json
from pathlib import Path
from datetime import timedelta
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_DIR = Path("analysis_results/batch")
INTERVAL = "60"
LOOKAHEAD_HOURS = 48
LIQUIDATION_THRESH = -9.0  # % spot move for 10x isolated

def process_coin(symbol: str):
    sig_file = BATCH_DIR / f"{symbol}_signals.csv"
    if not sig_file.exists():
        logger.warning("Signals file not found for %s", symbol)
        return None
    sigs = pd.read_csv(sig_file, parse_dates=["timestamp"])
    no_tp = sigs[sigs["outcome"] == "no_tp"].copy()
    if no_tp.empty:
        return {"symbol": symbol, "no_tp_count": 0}
    # Fetch candle data for window covering earliest to latest + 2 days
    start_ts = no_tp["timestamp"].min()
    end_ts = no_tp["timestamp"].max() + pd.Timedelta(hours=LOOKAHEAD_HOURS)
    # Bybit returns latest first; we'll just fetch last 1000 candles and slice
    kl = fetch_kline_data(symbol, interval=INTERVAL, limit=2000, category="linear")
    if not kl:
        logger.warning("No candle data for %s", symbol)
        return None
    df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close", "vol", "turn"])
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms", utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    records = []
    for _, row in no_tp.iterrows():
        entry_ts = row["timestamp"]
        entry_row = df[df["ts"] == entry_ts]
        if entry_row.empty:
            continue
        idx = entry_row.index[0]
        future = df.iloc[idx: idx + LOOKAHEAD_HOURS]
        if future.empty:
            continue
        entry_price = entry_row.iloc[0]["open"]
        final_price = future.iloc[-1]["close"]
        pnl_pct = (final_price - entry_price) / entry_price * 100
        min_low = future["low"].min()
        max_drawdown = (min_low - entry_price) / entry_price * 100
        records.append({"ts": entry_ts, "pnl_pct": pnl_pct, "drawdown_pct": max_drawdown})
    df_res = pd.DataFrame(records)
    if df_res.empty:
        return None
    summar = {
        "symbol": symbol,
        "no_tp_count": len(df_res),
        "avg_pnl_pct": df_res["pnl_pct"].mean(),
        "worst_pnl_pct": df_res["pnl_pct"].min(),
        "pct_liquidations": (df_res["drawdown_pct"] <= LIQUIDATION_THRESH).mean() * 100,
        "avg_drawdown_pct": df_res["drawdown_pct"].mean(),
    }
    return summar


def main():
    summaries = []
    for file in BATCH_DIR.glob("*_signals.csv"):
        symbol = file.stem.split("_")[0]
        s = process_coin(symbol)
        if s:
            summaries.append(s)
    out = pd.DataFrame(summaries)
    out.to_csv(BATCH_DIR / "no_tp_summary.csv", index=False)
    print(out)

if __name__ == "__main__":
    main() 