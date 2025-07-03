import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.historical_cache import fetch_kline_extended

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINS: List[str] = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT", "ATOMUSDT", "HBARUSDT",
    "CROUSDT", "SUIUSDT", "LINKUSDT", "ADAUSDT"
]

# Choose interval here ('15' or '5')
INTERVAL = "15"

# Rough TP/SL tuned for shorter intervals (adjust if INTERVAL == '5')
if INTERVAL == "15":
    TP1 = 0.3  # %
    TRAIL_GAP = 0.12  # %
    SL = -0.6  # %
elif INTERVAL == "5":
    TP1 = 0.2
    TRAIL_GAP = 0.08
    SL = -0.5
else:
    raise ValueError("Unsupported interval")

LOOKBACK_DAYS = 21 if INTERVAL == "15" else 7  # constrained by 2000-bar API limit
RSI_MIN, RSI_MAX = 45, 60
MAX_CONCURRENT = 2
BREAKEVEN_TOL = -0.15

OUT = Path(f"analysis_results/refined_v5_{INTERVAL}m"); OUT.mkdir(parents=True, exist_ok=True)


def fetch_df(sym: str) -> pd.DataFrame:
    df = fetch_kline_extended(sym, interval=INTERVAL, days=LOOKBACK_DAYS, category="linear")
    if df.empty:
        return df
    
    # ensure we only keep the lookback window in case cache has more
    cutoff = df["ts"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
    df = df[df["ts"] >= cutoff].reset_index(drop=True)

    # indicators
    df["ema10"] = df["close"].ewm(span=10).mean()
    df["ema_slope"] = df["ema10"] - df["ema10"].shift(1)
    df["price_vs_ema10"] = (df["close"] - df["ema10"]) / df["ema10"] * 100
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    df["rsi14"] = 100 - 100 / (1 + pd.Series(gain).rolling(14).mean() / pd.Series(loss).rolling(14).mean())
    df["rsi_slope"] = df["rsi14"].diff()
    df["vol_z"] = (df["vol"] - df["vol"].rolling(20).mean()) / df["vol"].rolling(20).std()
    df["range_pct"] = (df["high"] - df["low"]) / df["low"] * 100
    df["bullish_pct"] = (df["close"] - df["open"]) / df["open"] * 100
    return df


def select_signals(df: pd.DataFrame, sym: str) -> pd.Index:
    base = (
        (df["range_pct"] > 0.5)
        & df["rsi14"].between(RSI_MIN, RSI_MAX)
        & (df["rsi_slope"] >= 0)
        & (df["vol_z"] > 0)
        & (df["price_vs_ema10"].between(-0.3, 0.3))
    )
    if sym == "ETHUSDT":
        base &= (df["bullish_pct"] > 0.05) & (df["ema_slope"] > 0)
    elif sym == "XRPUSDT":
        base &= (df["bullish_pct"] > 0.15) & (df["ema_slope"] > 0)
    elif sym == "SOLUSDT":
        base &= (df["bullish_pct"] > 0.05) & (df["ema_slope"] > 0)
    elif sym == "CROUSDT":
        base &= (df["bullish_pct"] > 0.03) & (df["vol_z"] > 0.15)
    elif sym == "SUIUSDT":
        base &= (df["bullish_pct"] > 0.05)
    elif sym == "LINKUSDT":
        base &= (df["bullish_pct"] > 0.08) & (df["ema_slope"] > 0)
    elif sym == "ADAUSDT":
        base &= (df["bullish_pct"] > 0.06) & (df["ema_slope"] > 0)
    elif sym == "HBARUSDT":
        base &= (df["bullish_pct"] > 0.05) & (df["ema_slope"] > 0)
    return df.index[base]


def simulate(sym: str):
    df = fetch_df(sym)
    if df.empty:
        logger.warning("No data for %s", sym)
        return None
    sig_idx = select_signals(df, sym)
    positions, trades = [], []
    for idx, row in df.iterrows():
        remaining = []
        for p in positions:
            high, low = row["high"], row["low"]
            if not p["scaled"] and (high - p["entry"]) / p["entry"] * 100 >= TP1:
                p["scaled"] = True; p["peak"] = high; p["realized"] = TP1 * 0.5
            if p["scaled"]:
                if high > p["peak"]: p["peak"] = high
                if (p["peak"] - low) / p["peak"] * 100 >= TRAIL_GAP:
                    rem_pnl = (low - p["entry"]) / p["entry"] * 100 * 0.5
                    trades.append({"entry_ts": p["ts"], "exit_ts": row["ts"], "pnl_pct": p["realized"] + rem_pnl}); continue
            if (low - p["entry"]) / p["entry"] * 100 <= SL:
                stop_pnl = SL * (0.5 if p["scaled"] else 1)
                trades.append({"entry_ts": p["ts"], "exit_ts": row["ts"], "pnl_pct": p.get("realized", 0) + stop_pnl}); continue
            remaining.append(p)
        positions = remaining
        if idx in sig_idx and len(positions) < MAX_CONCURRENT:
            positions.append({"entry": row["open"], "ts": row["ts"], "scaled": False, "peak": row["high"]})
    final_close = df.iloc[-1]["close"]; final_ts = df.iloc[-1]["ts"]
    for p in positions:
        rem = (final_close - p["entry"]) / p["entry"] * 100
        pnl = p.get("realized", 0) + rem * (0.5 if p["scaled"] else 1)
        trades.append({"entry_ts": p["ts"], "exit_ts": final_ts, "pnl_pct": pnl})
    tr = pd.DataFrame(trades)
    tr.to_csv(OUT / f"{sym}_trades.csv", index=False)
    wins = (tr["pnl_pct"] >= BREAKEVEN_TOL).sum(); losses = (tr["pnl_pct"] < BREAKEVEN_TOL).sum()
    return {"symbol": sym, "trades": len(tr), "wins": wins, "losses": losses, "win_rate": wins / max(len(tr), 1), "total_pct": tr["pnl_pct"].sum()}


def main():
    results = []
    for c in COINS:
        logger.info("Simulating %s", c)
        res = simulate(c)
        if res: results.append(res)
    df = pd.DataFrame(results)
    df.to_csv(OUT / "summary.csv", index=False)
    print(df)
    print("\nOverall win rate:", f"{(df['wins'].sum()/df['trades'].sum()):.2%}")
    print("Total spot %:", df["total_pct"].sum())

if __name__ == "__main__":
    main() 