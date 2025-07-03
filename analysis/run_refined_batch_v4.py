import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.bybit_api import fetch_kline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COINS = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT",
    "ATOMUSDT", "HBARUSDT", "CROUSDT", "SUIUSDT"
]

INTERVAL = "30"  # minutes
LOOKBACK_DAYS = 90
TP1 = 0.5  # %
TRAIL_GAP = 0.20  # % from peak
SL = -1.0  # %
RSI_MIN, RSI_MAX = 45, 60
MAX_CONCURRENT = 2

OUT = Path("analysis_results/refined_v4"); OUT.mkdir(parents=True, exist_ok=True)


def fetch_df(sym: str) -> pd.DataFrame:
    """Download klines and build indicator columns."""
    kl = fetch_kline_data(sym, interval=INTERVAL, limit=2000, category="linear")
    if not kl:
        return pd.DataFrame()
    df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close", "vol", "turn"])
    df[["open", "high", "low", "close", "vol"]] = df[["open", "high", "low", "close", "vol"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms", utc=True)
    df.sort_values("ts", inplace=True)

    # limit to recent window
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
        & (df["rsi14"].between(RSI_MIN, RSI_MAX))
        & (df["rsi_slope"] >= 0)
        & (df["vol_z"] > 0)
        & (df["price_vs_ema10"].between(-0.3, 0.3))
    )
    if sym == "ETHUSDT":
        extra = (df["bullish_pct"] > 0.10) & (df["ema_slope"] > 0)
        base &= extra
    elif sym == "XRPUSDT":
        extra = (df["bullish_pct"] > 0.25) & (df["ema_slope"] > 0)
        base &= extra
    elif sym == "SOLUSDT":
        extra = (df["bullish_pct"] > 0.10) & (df["ema_slope"] > 0)
        base &= extra
    elif sym == "CROUSDT":
        extra = (df["bullish_pct"] > 0.05) & (df["vol_z"] > 0.3)
        base &= extra
    elif sym == "SUIUSDT":
        extra = (df["bullish_pct"] > 0.10)
        base &= extra
    return df.index[base]


def simulate(sym: str):
    df = fetch_df(sym)
    if df.empty:
        logger.warning("No data for %s", sym)
        return None

    sig_idx = select_signals(df, sym)

    positions = []  # list of dicts per open position
    trades = []

    for idx, row in df.iterrows():
        # ---------- manage open positions ----------
        remaining = []
        for p in positions:
            high, low = row["high"], row["low"]
            # scale-out at TP1
            if not p["scaled"] and (high - p["entry"]) / p["entry"] * 100 >= TP1:
                p["scaled"] = True
                p["peak"] = high
                p["realized"] = TP1 * 0.5  # 50 % of position closed

            # trailing on remainder
            if p["scaled"]:
                if high > p["peak"]:
                    p["peak"] = high
                if (p["peak"] - low) / p["peak"] * 100 >= TRAIL_GAP:
                    rem_pnl = (low - p["entry"]) / p["entry"] * 100 * 0.5
                    trades.append(
                        {
                            "entry_ts": p["ts"],
                            "exit_ts": row["ts"],
                            "pnl_pct": p["realized"] + rem_pnl,
                        }
                    )
                    continue  # position closed

            # hard stop-loss
            if (low - p["entry"]) / p["entry"] * 100 <= SL:
                stop_pnl = SL * (0.5 if p["scaled"] else 1)
                trades.append(
                    {
                        "entry_ts": p["ts"],
                        "exit_ts": row["ts"],
                        "pnl_pct": p.get("realized", 0) + stop_pnl,
                    }
                )
                continue  # position closed
            remaining.append(p)
        positions = remaining

        # ---------- open new positions ----------
        if idx in sig_idx and len(positions) < MAX_CONCURRENT:
            positions.append({"entry": row["open"], "ts": row["ts"], "scaled": False, "peak": row["high"]})

    # close any remaining positions at final close
    final_close = df.iloc[-1]["close"]
    final_ts = df.iloc[-1]["ts"]
    for p in positions:
        rem = (final_close - p["entry"]) / p["entry"] * 100
        pnl = p.get("realized", 0) + rem * (0.5 if p["scaled"] else 1)
        trades.append({"entry_ts": p["ts"], "exit_ts": final_ts, "pnl_pct": pnl})

    tr = pd.DataFrame(trades)
    tr.to_csv(OUT / f"{sym}_trades.csv", index=False)

    tolerance = -0.15  # treat tiny negatives as breakeven
    wins = (tr["pnl_pct"] >= tolerance).sum()
    losses = (tr["pnl_pct"] < tolerance).sum()
    return {
        "symbol": sym,
        "trades": len(tr),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / max(len(tr), 1),
        "total_pct": tr["pnl_pct"].sum(),
    }


def main():
    results = []
    for coin in COINS:
        logger.info("Simulating %s", coin)
        res = simulate(coin)
        if res is not None:
            results.append(res)
    df = pd.DataFrame(results)
    df.to_csv(OUT / "summary.csv", index=False)
    print(df)
    overall_wr = df["wins"].sum() / df["trades"].sum()
    print("\nOverall win rate:", f"{overall_wr:.2%}")
    print("Total spot %:", df["total_pct"].sum())


if __name__ == "__main__":
    main() 