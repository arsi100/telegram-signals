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

# --- Final Hybrid Strategy Parameters ---
TP1 = 0.5          # % - First take-profit to scale out
SL = -1.5          # % - Wider, hard stop-loss
TRAIL_GAP = 0.25   # % - Trailing stop gap, activated after TP1
RSI_MIN, RSI_MAX = 45, 60
RANGE_MIN_PCT = 0.4
MAX_CONCURRENT = 5

# --- Output ---
OUT = Path(f"analysis_results/final_strategy_{INTERVAL_PRIMARY}m"); OUT.mkdir(parents=True, exist_ok=True)


def get_data(sym: str) -> pd.DataFrame:
    """Fetches and prepares data."""
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
    """Selects entry signals."""
    base = (
        (df["range_pct"] > RANGE_MIN_PCT)
        & df["rsi14"].between(RSI_MIN, RSI_MAX)
        & (df["rsi_slope"] >= 0)
        & (df["vol_z"] > 0)
        & (df["price_vs_ema10"].between(-0.3, 0.3))
        & (df["price_above_ema_4h"] == True)
    )
    return df.index[base]


def simulate(sym: str):
    df = get_data(sym)
    if df.empty: return None

    sig_idx = select_signals(df)
    logger.info(f"Simulating {sym} with {len(sig_idx)} signals...")

    positions, trades = [], []
    active_trade_timestamps = set()

    for idx, row in df.iterrows():
        # --- Manage open positions ---
        remaining_positions = []
        for p in positions:
            high, low = row['high'], row['low']
            
            # --- Scale-out at TP1 ---
            if not p['scaled'] and (high - p['entry_price']) / p['entry_price'] * 100 >= TP1:
                p['scaled'] = True
                p['peak'] = high
                p['realized_pnl'] = TP1 * 0.5  # 50% of position closed for TP1 gain

            # --- Trailing Stop on Remainder ---
            if p['scaled']:
                if high > p['peak']:
                    p['peak'] = high  # Update peak for trail
                
                if (p['peak'] - low) / p['peak'] * 100 >= TRAIL_GAP:
                    rem_pnl = (low - p['entry_price']) / p['entry_price'] * 100 * 0.5
                    final_pnl = p['realized_pnl'] + rem_pnl
                    trades.append({'pnl_pct': final_pnl}); active_trade_timestamps.remove(p['entry_ts'])
                    continue

            # --- Hard Stop-Loss ---
            if (low - p['entry_price']) / p['entry_price'] * 100 <= SL:
                stop_pnl = SL * (0.5 if p['scaled'] else 1)
                final_pnl = p.get('realized_pnl', 0) + stop_pnl
                trades.append({'pnl_pct': final_pnl}); active_trade_timestamps.remove(p['entry_ts'])
                continue
            
            remaining_positions.append(p)
        positions = remaining_positions

        # --- Open new positions ---
        if idx in sig_idx and len(positions) < MAX_CONCURRENT:
            if not any(ts > row['ts'] - pd.Timedelta(minutes=30) for ts in active_trade_timestamps):
                positions.append({
                    'entry_price': row['open'], 
                    'entry_ts': row['ts'], 
                    'scaled': False, 
                    'peak': row['high']
                })
                active_trade_timestamps.add(row['ts'])

    # Close any positions still open at the end of the backtest
    if positions:
        final_price = df.iloc[-1]['close']
        for p in positions:
            rem_pnl = (final_price - p['entry_price']) / p['entry_price'] * 100 * (0.5 if p['scaled'] else 1)
            final_pnl = p.get('realized_pnl', 0) + rem_pnl
            trades.append({'pnl_pct': final_pnl})

    if not trades:
        return {"symbol": sym, "trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pct": 0}
    
    tr = pd.DataFrame(trades)
    wins = (tr['pnl_pct'] >= 0).sum()
    return {
        "symbol": sym, "trades": len(tr), "wins": wins, "losses": len(tr) - wins,
        "win_rate": wins / len(tr), "total_pct": tr['pnl_pct'].sum()
    }

def main():
    results = []
    for coin in COINS:
        res = simulate(coin)
        if res: results.append(res)
    
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(OUT / "summary.csv", index=False)

    total_trades = summary_df['trades'].sum()
    total_wins = summary_df['wins'].sum()
    avg_trades_per_day = total_trades / LOOKBACK_DAYS

    print("\n--- Final Hybrid Strategy Backtest ---")
    print(summary_df.to_string())
    print("\n--- Aggregates ---")
    print(f"Total Trades over {LOOKBACK_DAYS} days: {total_trades}")
    print(f"Average Trades per Day: {avg_trades_per_day:.2f}")
    print(f"Overall Win Rate: {(total_wins / max(total_trades, 1)):.2%}")
    total_pnl = summary_df['total_pct'].sum()
    print(f"Total Spot PnL (% of notional): {total_pnl:.2f}%")
    
    # Dollar value calculation
    notional_per_trade = 100000
    total_dollar_profit = (total_pnl / 100) * notional_per_trade
    print(f"Total Dollar Profit (on ${notional_per_trade:,} notional per trade): ${total_dollar_profit:,.2f}")

if __name__ == "__main__":
    main() 