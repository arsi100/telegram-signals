import sys, logging
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List

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

INTERVAL_PRIMARY = "15"  # Primary trading timeframe
INTERVAL_MACRO = "240"   # 4-hour timeframe for trend filter

# --- Strategy Parameters ---
TP = 0.5   # %
SL = -1.0  # %
RSI_MIN, RSI_MAX = 45, 60
LOOKBACK_DAYS = 90
MAX_CONCURRENT = 5 # Increased to allow more trades
RANGE_MIN_PCT = 0.4 # Slightly relaxed for 15m timeframe

# --- Output ---
OUT = Path(f"analysis_results/macro_v1_{INTERVAL_PRIMARY}m"); OUT.mkdir(parents=True, exist_ok=True)


def get_data(sym: str) -> pd.DataFrame:
    """
    Fetches primary and macro kline data, calculates indicators,
    and merges them into a single DataFrame.
    """
    # Fetch data using the caching function
    df_primary = fetch_kline_extended(sym, interval=INTERVAL_PRIMARY, days=LOOKBACK_DAYS)
    df_macro = fetch_kline_extended(sym, interval=INTERVAL_MACRO, days=LOOKBACK_DAYS)

    if df_primary.empty or df_macro.empty:
        logger.warning(f"No data for {sym} on one of the timeframes.")
        return pd.DataFrame()

    # --- Calculate Indicators for Primary Timeframe ---
    df_primary["ema10"] = df_primary["close"].ewm(span=10).mean()
    df_primary["price_vs_ema10"] = (df_primary["close"] - df_primary["ema10"]) / df_primary["ema10"] * 100
    delta = df_primary["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    df_primary["rsi14"] = 100 - 100 / (1 + pd.Series(gain).rolling(14).mean() / pd.Series(loss).rolling(14).mean())
    df_primary["rsi_slope"] = df_primary["rsi14"].diff()
    df_primary["vol_z"] = (df_primary["vol"] - df_primary["vol"].rolling(20).mean()) / df_primary["vol"].rolling(20).std()
    df_primary["range_pct"] = (df_primary["high"] - df_primary["low"]) / df_primary["low"] * 100

    # --- Calculate Macro Trend Indicator ---
    df_macro['ema_4h'] = df_macro['close'].ewm(span=10).mean()
    
    # Merge macro trend into primary timeframe
    df_merged = pd.merge_asof(df_primary, df_macro[['ts', 'ema_4h']], on='ts', direction='backward')
    df_merged['price_above_ema_4h'] = df_merged['close'] > df_merged['ema_4h']
    
    return df_merged


def select_signals(df: pd.DataFrame) -> pd.Index:
    """
    Selects trade entry points based on a combination of primary indicators
    and the macro trend filter.
    """
    base = (
        (df["range_pct"] > RANGE_MIN_PCT)
        & df["rsi14"].between(RSI_MIN, RSI_MAX)
        & (df["rsi_slope"] >= 0)
        & (df["vol_z"] > 0)
        & (df["price_vs_ema10"].between(-0.3, 0.3))
        & (df["price_above_ema_4h"] == True)  # Macro Filter
    )
    return df.index[base]


def simulate(sym: str):
    """
    Runs the backtest for a single symbol using simple TP/SL logic.
    """
    df = get_data(sym)
    if df.empty:
        return None

    sig_idx = select_signals(df)
    logger.info(f"{sym} generated {len(sig_idx)} signals over {LOOKBACK_DAYS} days.")

    positions, trades = [], []
    active_trade_timestamps = set()

    for idx, row in df.iterrows():
        # --- Manage open positions ---
        remaining_positions = []
        for p in positions:
            # Check for TP or SL hit
            if (row['high'] - p['entry_price']) / p['entry_price'] * 100 >= TP:
                trades.append({'pnl_pct': TP, 'type': 'win'})
                active_trade_timestamps.remove(p['entry_ts'])
                continue # Position closed
            elif (row['low'] - p['entry_price']) / p['entry_price'] * 100 <= SL:
                trades.append({'pnl_pct': SL, 'type': 'loss'})
                active_trade_timestamps.remove(p['entry_ts'])
                continue # Position closed
            
            remaining_positions.append(p)
        positions = remaining_positions

        # --- Open new positions ---
        # Prevent taking a new signal if one was just taken in the last 2 candles
        # to avoid multiple signals for the same "event"
        if idx in sig_idx and len(positions) < MAX_CONCURRENT:
            if not any(ts > row['ts'] - pd.Timedelta(minutes=30) for ts in active_trade_timestamps):
                positions.append({'entry_price': row['open'], 'entry_ts': row['ts']})
                active_trade_timestamps.add(row['ts'])

    # Close any remaining open positions at the end of the backtest as 'undecided'
    # For this simple model, we will just discard them to not skew results.

    if not trades:
        return {"symbol": sym, "trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pct": 0}

    tr = pd.DataFrame(trades)
    wins = (tr["type"] == 'win').sum()
    losses = (tr["type"] == 'loss').sum()
    total_trades = len(tr)
    
    return {
        "symbol": sym,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / max(total_trades, 1),
        "total_pct": tr["pnl_pct"].sum(),
    }


def main():
    results = []
    for coin in COINS:
        logger.info(f"--- Processing {coin} ---")
        res = simulate(coin)
        if res:
            results.append(res)
    
    if not results:
        logger.warning("No results generated. Exiting.")
        return

    df = pd.DataFrame(results)
    df.to_csv(OUT / "summary.csv", index=False)
    
    total_trades = df['trades'].sum()
    total_wins = df['wins'].sum()
    avg_trades_per_day = total_trades / LOOKBACK_DAYS

    print("\n--- Backtest Summary ---")
    print(df)
    print("\n--- Aggregates ---")
    print(f"Total Trades over {LOOKBACK_DAYS} days: {total_trades}")
    print(f"Average Trades per Day: {avg_trades_per_day:.2f}")
    print(f"Overall Win Rate: {(total_wins / max(total_trades, 1)):.2%}")
    print(f"Total Spot PnL (% of notional): {df['total_pct'].sum():.2f}%")


if __name__ == "__main__":
    main() 