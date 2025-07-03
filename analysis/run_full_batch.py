import sys
from pathlib import Path
import logging
from datetime import timedelta
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINS = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT",
    "XRPUSDT", "AVAXUSDT", "MATICUSDT", "DOTUSDT", "ATOMUSDT",
    "SEIUSDT", "SUIUSDT", "PEPEUSDT", "FARTUSDT", "HBARUSDT", "CROUSDT",
    "XMRUSDT", "PENGUUSDT", "TRMPUSDT"
]

INTERVAL = "60"  # 1h
LOOKBACK_DAYS = 90
TP_PCT = 0.5   # take-profit %
TRAIL_GAP = 0.3  # trail stop gap % below peak

OUT_DIR = Path("analysis_results/batch")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_candles(symbol: str) -> pd.DataFrame:
    kl = fetch_kline_data(symbol, interval=INTERVAL, limit=2000, category="linear")
    if not kl:
        return pd.DataFrame()
    df = pd.DataFrame(kl, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df[["open", "high", "low", "close", "volume", "turnover"]] = df[["open", "high", "low", "close", "volume", "turnover"]].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    recent_cut = df["timestamp"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
    df = df[df["timestamp"] >= recent_cut].reset_index(drop=True)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["sma10"] = df["close"].rolling(10).mean()
    df["ema10"] = df["close"].ewm(span=10).mean()
    df["price_vs_ema10"] = (df["close"] - df["ema10"]) / df["ema10"] * 100
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    roll_up = pd.Series(gain).rolling(14).mean()
    roll_down = pd.Series(loss).rolling(14).mean()
    rs = roll_up / roll_down
    df["rsi14"] = 100 - (100 / (1 + rs))
    df["move_pct"] = (df["high"] - df["low"]) / df["low"] * 100
    return df


def evaluate_signals(df: pd.DataFrame, symbol: str):
    # Identify signals (rule hits)
    opps = df[df["move_pct"] > 0.5].copy()
    signals = opps[(opps["rsi14"].between(40, 60)) & (opps["price_vs_ema10"].between(-0.3, 0.3))].copy()
    records = []
    for idx, row in signals.iterrows():
        entry_price = row["open"]
        entry_time = row["timestamp"]

        # scan forward up to 48 hours for TP & trailing stop
        tp_time = None
        trail_time = None
        outcome = "open"
        peak = row["high"]
        future = df.iloc[idx: idx + 48]  # includes current row
        for i, fut in future.iterrows():
            high = fut["high"]
            low = fut["low"]
            if high > peak:
                peak = high
            # check TP first
            if tp_time is None and (high - entry_price) / entry_price * 100 >= TP_PCT:
                tp_time = fut["timestamp"]
            # check trailing after TP achieved
            if tp_time is not None:
                if (peak - low) / peak * 100 >= TRAIL_GAP:
                    trail_time = fut["timestamp"]
                    break
        if tp_time is not None and trail_time is None:
            outcome = "tp_hit_no_trail"
        elif tp_time is not None and trail_time is not None:
            outcome = "trail_exit"
        else:
            outcome = "no_tp"
        records.append({
            "timestamp": entry_time,
            "tp_minutes": None if tp_time is None else (tp_time - entry_time).total_seconds() / 60,
            "trail_minutes": None if trail_time is None else (trail_time - entry_time).total_seconds() / 60,
            "outcome": outcome
        })
    res_df = pd.DataFrame(records)
    summary = res_df["outcome"].value_counts().to_dict()
    summary_path = OUT_DIR / f"{symbol}_summary.txt"
    with open(summary_path, "w") as f:
        f.write(f"Symbol: {symbol}\n")
        for k, v in summary.items():
            f.write(f"{k}: {v}\n")
    res_df.to_csv(OUT_DIR / f"{symbol}_signals.csv", index=False)
    logger.info("%s done. Signals: %d", symbol, len(res_df))


def main():
    for sym in COINS:
        logger.info("Processing %s", sym)
        df = fetch_candles(sym)
        if df.empty:
            logger.warning("No data for %s", sym)
            continue
        df = compute_indicators(df)
        evaluate_signals(df, sym)

    logger.info("Batch complete. Results in %s", OUT_DIR)

if __name__ == "__main__":
    main() 