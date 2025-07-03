import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Any

# --- Setup Project Root ---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Local Imports ---
from functions.historical_cache import fetch_kline_extended

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COINS: List[str] = [
    "SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT", "ATOMUSDT", "HBARUSDT",
    "CROUSDT", "SUIUSDT", "LINKUSDT", "ADAUSDT"
]

INTERVAL_PRIMARY = "15"
INTERVAL_MACRO = "240"
LOOKBACK_DAYS = 90

# --- Strategy Parameters for Analysis ---
TP = 0.5   # %
LIQUIDATION_SL = -10.0  # %
RSI_MIN, RSI_MAX = 45, 60
RANGE_MIN_PCT = 0.4

# --- Output ---
OUT = Path(f"analysis_results/signal_potential_analysis_{INTERVAL_PRIMARY}m"); OUT.mkdir(parents=True, exist_ok=True)


def get_data(sym: str) -> pd.DataFrame:
    """Fetches and prepares data, same as the macro_v1 script."""
    df_primary = fetch_kline_extended(sym, interval=INTERVAL_PRIMARY, days=LOOKBACK_DAYS)
    df_macro = fetch_kline_extended(sym, interval=INTERVAL_MACRO, days=LOOKBACK_DAYS)
    if df_primary.empty or df_macro.empty: return pd.DataFrame()

    df_primary["ema10"] = df_primary["close"].ewm(span=10).mean()
    df_primary["price_vs_ema10"] = (df_primary["close"] - df_primary["ema10"]) / df_primary["ema10"] * 100
    delta = df_primary["close"].diff(); gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
    df_primary["rsi14"] = 100 - 100 / (1 + pd.Series(gain).rolling(14).mean() / pd.Series(loss).rolling(14).mean())
    df_primary["rsi_slope"] = df_primary["rsi14"].diff()
    df_primary["vol_z"] = (df_primary["vol"] - df_primary["vol"].rolling(20).mean()) / df_primary["vol"].rolling(20).std()
    df_primary["range_pct"] = (df_primary["high"] - df_primary["low"]) / df_primary["low"] * 100
    df_macro['ema_4h'] = df_macro['close'].ewm(span=10).mean()
    df_merged = pd.merge_asof(df_primary, df_macro[['ts', 'ema_4h']], on='ts', direction='backward')
    df_merged['price_above_ema_4h'] = df_merged['close'] > df_merged['ema_4h']
    return df_merged

def select_signals(df: pd.DataFrame) -> pd.Index:
    """Selects the same entry signals as the macro_v1 script."""
    base = (
        (df["range_pct"] > RANGE_MIN_PCT)
        & df["rsi14"].between(RSI_MIN, RSI_MAX)
        & (df["rsi_slope"] >= 0)
        & (df["vol_z"] > 0)
        & (df["price_vs_ema10"].between(-0.3, 0.3))
        & (df["price_above_ema_4h"] == True)
    )
    return df.index[base]


def analyze_signal_potential(sym: str) -> Dict[str, Any]:
    """
    Analyzes each signal to see if it hits TP or Liquidation first,
    and measures the max drawdown on winners.
    """
    df = get_data(sym)
    if df.empty: return None

    sig_idx = select_signals(df)
    logger.info(f"Analyzing {len(sig_idx)} signals for {sym}...")

    results = []
    for idx in sig_idx:
        entry_price = df.loc[idx, 'open']
        future_candles = df.loc[idx + 1:]
        
        outcome = 'undecided'
        max_drawdown = 0.0

        for _, row in future_candles.iterrows():
            high_pct = (row['high'] - entry_price) / entry_price * 100
            low_pct = (row['low'] - entry_price) / entry_price * 100

            # Update max drawdown
            if low_pct < max_drawdown:
                max_drawdown = low_pct

            # Check for liquidation first
            if low_pct <= LIQUIDATION_SL:
                outcome = 'loss'
                break
            
            # Check for TP
            if high_pct >= TP:
                outcome = 'win'
                break
        
        results.append({'outcome': outcome, 'max_drawdown_pct': max_drawdown})

    if not results:
        return {"symbol": sym, "trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_max_dd_winners": 0}

    res_df = pd.DataFrame(results)
    wins = res_df[res_df['outcome'] == 'win']
    losses = res_df[res_df['outcome'] == 'loss']
    
    return {
        "symbol": sym,
        "trades": len(res_df),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / max(len(res_df), 1),
        "avg_max_dd_winners": wins['max_drawdown_pct'].mean(),
    }


def main():
    all_results = []
    for coin in COINS:
        logger.info(f"--- Starting Potential Analysis for {coin} ---")
        res = analyze_signal_potential(coin)
        if res:
            all_results.append(res)
    
    if not all_results:
        logger.error("No analysis results generated.")
        return

    summary_df = pd.DataFrame(all_results)
    summary_df.to_csv(OUT / "summary_potential.csv", index=False)

    total_trades = summary_df['trades'].sum()
    total_wins = summary_df['wins'].sum()
    total_losses = summary_df['losses'].sum()

    print("\n--- Signal Potential Analysis (90-Day Hold) ---")
    print(summary_df)
    print("\n--- Aggregates ---")
    print(f"Total Signals Analyzed: {total_trades}")
    print(f"Total Wins (hit +0.5%): {total_wins}")
    print(f"Total Losses (hit -10%): {total_losses}")
    print(f"Overall Win Rate (Hold Strategy): {(total_wins / max(total_trades, 1)):.2%}")
    
    # Calculate weighted average drawdown
    summary_df['weighted_dd'] = summary_df['avg_max_dd_winners'] * summary_df['wins']
    weighted_avg_dd = summary_df['weighted_dd'].sum() / total_wins
    print(f"Average Max Drawdown on Winning Trades: {weighted_avg_dd:.2f}%")


if __name__ == "__main__":
    main() 