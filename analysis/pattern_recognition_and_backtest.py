import sys
from pathlib import Path
# Ensure root
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

try:
    import pandas_ta as ta
except ImportError:
    ta = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = Path("analysis_results/sol_90d_opportunities.csv")
CANDLE_FILE = Path("analysis_results/sol_full_1h.csv")  # will generate if missing

# ---------------------------------------------------------------------------
# Helper to load full candle data from cached fetch script
# ---------------------------------------------------------------------------

def load_full_candles() -> pd.DataFrame:
    if CANDLE_FILE.exists():
        df = pd.read_csv(CANDLE_FILE, parse_dates=["timestamp"])
        return df
    else:
        # fallback – regenerate from fetch script df variable if available
        try:
            from analysis.fetch_and_analyze_sol_hourly_90d import df as candle_df  # type: ignore
            candle_df.to_csv(CANDLE_FILE, index=False)
            return candle_df
        except Exception as e:
            logger.error("Unable to locate full candle data: %s", e)
            raise


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical features needed for clustering/back-test."""
    out = df.copy()
    # Percentage change from previous close
    out["ret1"] = out["close"].pct_change() * 100
    # 10-hour SMA and EMA
    out["sma10"] = out["close"].rolling(10).mean()
    out["ema10"] = out["close"].ewm(span=10).mean()
    out["price_vs_sma10"] = (out["close"] - out["sma10"]) / out["sma10"] * 100
    out["price_vs_ema10"] = (out["close"] - out["ema10"]) / out["ema10"] * 100
    # RSI 14 if pandas_ta available
    if ta is not None:
        out["rsi14"] = ta.rsi(out["close"], length=14)
    else:
        # simple RSI implementation
        delta = out["close"].diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        roll_up = pd.Series(gain).rolling(14).mean()
        roll_down = pd.Series(loss).rolling(14).mean()
        rs = roll_up / roll_down
        out["rsi14"] = 100 - (100 / (1 + rs))
    # ATR 14 using high/low/close
    if ta is not None:
        out["atr14"] = ta.atr(high=out["high"], low=out["low"], close=out["close"], length=14)
    else:
        tr = out[["high", "low", "close"]].copy()
        tr_shift = tr["close"].shift()
        tr["tr"] = np.maximum(tr["high"] - tr["low"], np.maximum(abs(tr["high"] - tr_shift), abs(tr["low"] - tr_shift)))
        out["atr14"] = tr["tr"].rolling(14).mean()
    # Volume z-score vs 20-hour mean/std
    out["vol_z20"] = (out["volume"] - out["volume"].rolling(20).mean()) / out["volume"].rolling(20).std()
    return out


def main():
    if not DATA_FILE.exists():
        logger.error("Opportunity CSV not found – run fetch_and_analyze_sol_hourly_90d.py first.")
        return

    opps = pd.read_csv(DATA_FILE)
    opps["timestamp"] = pd.to_datetime(opps["timestamp"], utc=True, errors='coerce')
    candles = load_full_candles()
    candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True, errors='coerce')
    candles = compute_features(candles)

    # Merge opportunity rows with their features (take row from same timestamp)
    opps_feat = pd.merge(opps, candles, on="timestamp", how="left", suffixes=("", "_feat"))

    # Select feature columns for clustering
    feat_cols = [
        "price_vs_sma10",
        "price_vs_ema10",
        "rsi14",
        "atr14",
        "vol_z20",
        "ret1",
    ]
    X = opps_feat[feat_cols].fillna(0).values

    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = 10
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    clusters = kmeans.fit_predict(X_scaled)
    opps_feat["cluster"] = clusters

    cluster_summary = (
        opps_feat.groupby("cluster")
        .agg(count=("cluster", "size"),
             avg_range=("range_pct", "mean"),
             avg_drawdown=("drawdown_pct", "mean"),
             median_recovery=("recovery_minutes", "median"),
             avg_gain_4h=("max_gain_4h_pct", "mean"))
        .reset_index()
        .sort_values("avg_gain_4h", ascending=False)
    )

    summary_path = Path("analysis_results/sol_pattern_clusters.csv")
    cluster_summary.to_csv(summary_path, index=False)
    logger.info("Cluster summary saved to %s", summary_path)

    # -------------------------------------------------------------------
    # SIMPLE PARAMETER TEST – example rule: rsi14 between 40-60 and price \n    # above ema10 by <0.3 %. Adjust as needed.
    # -------------------------------------------------------------------
    rule_hits = opps_feat[
        (opps_feat["rsi14"].between(40, 60)) &
        (opps_feat["price_vs_ema10"].between(-0.3, 0.3))
    ]

    logger.info("Rule would have triggered on %d / %d opportunities (%.1f%%)",
                len(rule_hits), len(opps_feat), len(rule_hits)/len(opps_feat)*100)

    hits_path = Path("analysis_results/sol_rule_hits.csv")
    rule_hits.to_csv(hits_path, index=False)
    logger.info("Detailed rule hits saved to %s", hits_path)

    print("Pattern clustering and simple rule test complete.")

if __name__ == "__main__":
    main() 