import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINS = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "ADAUSDT", "LINKUSDT", "XRPUSDT",
    "AVAXUSDT", "DOTUSDT", "ATOMUSDT", "HBARUSDT", "CROUSDT", "XMRUSDT",
    "SEIUSDT", "SUIUSDT"
]

INTERVAL = "30"  # 30-minute candles in Bybit v5
LOOKBACK_DAYS = 90
TP = 0.5  # %
SL = -1.5 # % hard stop
RSI_MIN, RSI_MAX = 45, 60
CAPITAL = 100_000  # account equity USD
MARGIN_PER_TRADE = 0.10  # 10 % of equity per trade
MAX_CONCURRENT = int(CAPITAL * MARGIN_PER_TRADE // (CAPITAL * 0.10)) or 1  # 10 trades

OUT_DIR = Path("analysis_results/refined")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_df(symbol):
    kl = fetch_kline_data(symbol, interval=INTERVAL, limit=2000, category="linear")
    if not kl:
        return pd.DataFrame()
    df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close", "vol", "turn"])
    df[["open", "high", "low", "close", "vol"]] = df[["open", "high", "low", "close", "vol"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms", utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    recent_cut = df["ts"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
    return df[df["ts"] >= recent_cut].reset_index(drop=True)


def add_indicators(df):
    df["ema10"] = df["close"].ewm(span=10).mean()
    df["price_vs_ema10"] = (df["close"] - df["ema10"]) / df["ema10"] * 100
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    roll_up = pd.Series(gain).rolling(14).mean()
    roll_down = pd.Series(loss).rolling(14).mean()
    rs = roll_up / roll_down
    df["rsi14"] = 100 - (100 / (1 + rs))
    df["rsi_slope"] = df["rsi14"].diff()
    df["vol_z"] = (df["vol"] - df["vol"].rolling(20).mean()) / df["vol"].rolling(20).std()
    df["range_pct"] = (df["high"] - df["low"]) / df["low"] * 100
    return df


def simulate(symbol):
    df = fetch_df(symbol)
    if df.empty:
        logger.warning("No data for %s", symbol)
        return None
    df = add_indicators(df)
    signals_idx = df.index[(df["range_pct"] > 0.5) &
                           (df["rsi14"].between(RSI_MIN, RSI_MAX)) &
                           (df["rsi_slope"] >= 0) &
                           (df["vol_z"] > 0) &
                           (df["price_vs_ema10"].between(-0.3, 0.3))]

    trades = []
    open_positions = []  # list of dicts with idx, entry_price, entry_ts

    for idx in range(len(df)):
        row = df.iloc[idx]
        # Check exits for open positions
        still_open = []
        for pos in open_positions:
            high = row["high"]; low = row["low"]
            if (high - pos["entry"])/pos["entry"]*100 >= TP:
                pnl = TP
                trades.append({"entry_ts": pos["ts"], "exit_ts": row["ts"], "pnl_pct": pnl})
            elif (low - pos["entry"])/pos["entry"]*100 <= SL:
                pnl = SL
                trades.append({"entry_ts": pos["ts"], "exit_ts": row["ts"], "pnl_pct": pnl})
            else:
                still_open.append(pos)
        open_positions = still_open

        # New signal?
        if idx in signals_idx and len(open_positions) < MAX_CONCURRENT:
            open_positions.append({"idx": idx, "entry": row["open"], "ts": row["ts"]})

    # Force-close remaining
    for pos in open_positions:
        final_close = df.iloc[-1]["close"]
        pnl = (final_close - pos["entry"])/pos["entry"]*100
        trades.append({"entry_ts": pos["ts"], "exit_ts": df.iloc[-1]["ts"], "pnl_pct": pnl})

    tr_df = pd.DataFrame(trades)
    if tr_df.empty:
        return None
    tr_df.to_csv(OUT_DIR / f"{symbol}_trades.csv", index=False)
    summary = {
        "symbol": symbol,
        "trades": len(tr_df),
        "wins": (tr_df["pnl_pct"] > 0).sum(),
        "losses": (tr_df["pnl_pct"] < 0).sum(),
        "avg_pct": tr_df["pnl_pct"].mean(),
        "total_pct": tr_df["pnl_pct"].sum()
    }
    return summary


def main():
    summaries = []
    for sym in COINS:
        logger.info("Simulating %s", sym)
        s = simulate(sym)
        if s:
            summaries.append(s)
    pd.DataFrame(summaries).to_csv(OUT_DIR / "summary.csv", index=False)
    print(pd.DataFrame(summaries))

if __name__ == "__main__":
    main() 