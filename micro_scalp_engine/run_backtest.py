"""Run backtest with specified parameters and generate reports."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import ccxt

from backtest_perp_engine import BacktestEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Strategy Parameters
PARAMS = {
    'channel_touch_tolerance': 0.001,  # 0.1% from regression channel
    'sr_zone_distance': 0.002,  # 0.2% from S/R zone
    'min_bias_confidence': 0.85,
    'bias_flip_confirmations': 4,  # 20min for confirmation
    'trail_activate_pct': 0.005,  # 0.5% to activate trailing stop
    'trail_offset_pct': 0.002,  # 0.2% trailing distance (tighter than before)
    'margin_topup_distance': 0.15,  # Add margin when within 15% of liquidation
    'margin_topup_size': 0.25,  # Add 25% of position size
    'max_topups': 4,  # Maximum number of margin top-ups
    'position_size_pct': 0.10,  # 10% of balance per trade
    'initial_leverage': 10  # 10x leverage
}

# Coin-specific configurations
COIN_CONFIGS = {
    'BTCUSDT': {
        'min_volume_usdt': 1000000,  # Minimum 1M USDT volume
        'volatility_threshold': 0.004,  # 0.4% price movement
        'param_grid': {
            'ema': [20, 50, 100],  # Longer timeframes for BTC
            'rsi_period': [14, 21],
            'volume_factor': [1.5, 2.0],  # Higher volume requirements
            'max_daily_trades': [5],  # More conservative
        }
    },
    'ETHUSDT': {
        'min_volume_usdt': 500000,  # Minimum 500k USDT volume
        'volatility_threshold': 0.006,  # 0.6% price movement
        'param_grid': {
            'ema': [15, 30, 50],
            'rsi_period': [10, 14],
            'volume_factor': [1.2, 1.5],
            'max_daily_trades': [8],
        }
    },
    'SOLUSDT': {
        'min_volume_usdt': 200000,
        'volatility_threshold': 0.012,  # 1.2% price movement
        'param_grid': {
            'ema': [5, 10, 20],  # Shorter timeframes
            'rsi_period': [6, 10],  # Faster RSI
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [12],  # More aggressive
        }
    },
    'XRPUSDT': {
        'min_volume_usdt': 150000,
        'volatility_threshold': 0.008,
        'param_grid': {
            'ema': [10, 20, 30],
            'rsi_period': [8, 12],
            'volume_factor': [1.1, 1.3],
            'max_daily_trades': [10],
        }
    },
    'ADAUSDT': {
        'min_volume_usdt': 100000,
        'volatility_threshold': 0.01,
        'param_grid': {
            'ema': [8, 15, 25],
            'rsi_period': [8, 12],
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [10],
        }
    },
    'SEIUSDT': {
        'min_volume_usdt': 50000,
        'volatility_threshold': 0.02,  # Higher volatility threshold
        'param_grid': {
            'ema': [3, 5, 10],  # Very short timeframes
            'rsi_period': [4, 6, 8],  # Quick RSI
            'volume_factor': [0.8, 1.0],  # Lower volume requirements
            'max_daily_trades': [15],  # Very aggressive
        }
    },
    'SUIUSDT': {
        'min_volume_usdt': 75000,
        'volatility_threshold': 0.018,
        'param_grid': {
            'ema': [3, 5, 10],
            'rsi_period': [4, 6, 8],
            'volume_factor': [0.8, 1.0],
            'max_daily_trades': [15],
        }
    },
    'DOGEUSDT': {
        'min_volume_usdt': 100000,
        'volatility_threshold': 0.015,
        'param_grid': {
            'ema': [5, 10, 15],
            'rsi_period': [6, 8, 10],
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [12],
        }
    },
    'MATICUSDT': {
        'min_volume_usdt': 150000,
        'volatility_threshold': 0.01,
        'param_grid': {
            'ema': [8, 15, 25],
            'rsi_period': [8, 12],
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [10],
        }
    },
    'AVAXUSDT': {
        'min_volume_usdt': 200000,
        'volatility_threshold': 0.012,
        'param_grid': {
            'ema': [5, 10, 20],
            'rsi_period': [6, 10],
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [12],
        }
    },
    'INJUSDT': {
        'min_volume_usdt': 75000,
        'volatility_threshold': 0.016,
        'param_grid': {
            'ema': [3, 5, 10],
            'rsi_period': [4, 6, 8],
            'volume_factor': [0.8, 1.0],
            'max_daily_trades': [15],
        }
    },
    'OPUSDT': {
        'min_volume_usdt': 100000,
        'volatility_threshold': 0.012,
        'param_grid': {
            'ema': [5, 10, 20],
            'rsi_period': [6, 10],
            'volume_factor': [1.0, 1.2],
            'max_daily_trades': [12],
        }
    }
}

# Default configuration for any other coins
DEFAULT_CONFIG = {
    'min_volume_usdt': 50000,
    'volatility_threshold': 0.01,
    'param_grid': {
        'ema': [10, 20],
        'rsi_period': [10, 14],
        'volume_factor': [1.0, 1.5],
        'max_daily_trades': [8],
    }
}

def get_coin_config(symbol: str) -> dict:
    """Get coin-specific configuration."""
    return COIN_CONFIGS.get(symbol, DEFAULT_CONFIG)

def run_optimization(symbol: str, start_date: datetime, end_date: datetime, output_dir: str):
    """
    Run parameter optimization for a symbol.
    """
    logging.info(f"\n{'='*50}")
    logging.info(f"Starting optimization for {symbol}")
    logging.info(f"Period: {start_date} to {end_date}")
    logging.info(f"{'='*50}\n")
    
    # Fetch historical data
    logging.info("Fetching historical data...")
    df = fetch_historical_data(symbol, start_date, end_date)
    if df.empty:
        logging.error(f"No data available for {symbol}")
        return None
    
    df_dict = df.to_dict('records')  # Convert DataFrame to dict for JSON serialization
    logging.info(f"Fetched {len(df_dict)} data points")
    
    # Generate parameter combinations
    fixed_params = {k: v for k, v in PARAMS.items() 
                   if k not in ['channel_touch_tolerance', 'sr_zone_distance', 'min_bias_confidence', 'bias_flip_confirmations', 'trail_activate_pct', 'trail_offset_pct', 'margin_topup_distance', 'margin_topup_size', 'max_topups', 'position_size_pct', 'initial_leverage']}
    
    # Generate base combinations
    base_combinations = [dict(zip(fixed_params.keys(), v)) 
                        for v in itertools.product(*fixed_params.values())]
    
    total_combinations = len(base_combinations)
    logging.info(f"\nTesting {total_combinations} parameter combinations")
    
    results = []
    for i, params in enumerate(base_combinations, 1):
        logging.info(f"\nTesting combination {i}/{total_combinations}")
        logging.info(f"Parameters: {json.dumps(params, indent=2)}")
        
        try:
            trades_log, equity_curve = run_backtest(symbol, start_date, end_date, params)
            if trades_log:
                performance = calculate_performance(trades_log, equity_curve, params)
                results.append({
                    'params': params,
                    'performance': performance
                })
                logging.info(f"Results:")
                logging.info(f"- Total trades: {performance['num_trades']}")
                logging.info(f"- Win rate: {performance['win_rate']:.2%}")
                logging.info(f"- Net PnL: {performance['net_pnl']:.2%}")
                logging.info(f"- Max drawdown: {performance['max_drawdown']:.2%}")
                logging.info(f"- Sharpe ratio: {performance['sharpe_ratio']:.2f}")
            else:
                logging.warning("No trades generated with these parameters")
        except Exception as e:
            logging.error(f"Error testing parameters: {str(e)}")
            continue
    
    if results:
        # Sort by Sharpe ratio
        results.sort(key=lambda x: x['performance']['sharpe_ratio'], reverse=True)
        best_result = results[0]
        
        logging.info(f"\n{'='*50}")
        logging.info("Optimization complete!")
        logging.info(f"Best parameters:")
        logging.info(json.dumps(best_result['params'], indent=2))
        logging.info(f"Performance:")
        logging.info(json.dumps(best_result['performance'], indent=2))
        logging.info(f"{'='*50}\n")
        
        # Generate report for best parameters
        report_path = generate_performance_report(
            trades_log,
            equity_curve,
            best_result['params'],
            output_dir
        )
        logging.info(f"Report generated at: {report_path}")
    else:
        logging.error("No valid results found during optimization")

def display_results(results: dict, scenario: str):
    """Display backtest results for a given scenario."""
    trades = results[scenario]['trades']
    logging.info(f"\n{scenario.replace('_', ' ').title()}:")
    logging.info(f"Total Trades: {trades}")
    
    if trades > 0:
        win_rate = results[scenario]['profitable_trades'] / trades
        logging.info(f"Win Rate: {win_rate:.2%}")
        logging.info(f"Total PnL: ${results[scenario]['total_pnl']:.2f}")
        logging.info(f"Max Drawdown: {results[scenario]['max_drawdown']:.2%}")
        logging.info(f"Average Trade Duration: {results[scenario]['avg_trade_duration']:.1f} hours")
        logging.info(f"Total Fees Paid: ${results[scenario]['total_fees']:.2f}")
    else:
        logging.info("No trades executed during the test period.")

def load_data(symbol, period_days=90):
    """Load historical data for backtesting."""
    logger.info(f"Loading {period_days} days of data for {symbol}")
    
    # Load from CSV if exists
    csv_path = f'candle_cache/{symbol}_data.csv'
    if Path(csv_path).exists():
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df['symbol'] = symbol
        logger.info(f"Loaded data from cache: {csv_path}")
        return df
    
    # If no cache, fetch from exchange
    try:
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        # Calculate timeframes
        end = datetime.now()
        start = end - timedelta(days=period_days)
        
        # Fetch 1-minute candles for more opportunities
        timeframe = '1m'
        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=int(start.timestamp() * 1000),
            limit=1000
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(
            candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df['symbol'] = symbol
        
        # Add technical indicators
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['rsi'] = calculate_rsi(df['close'])
        
        # Simulate macro bias (using 4h EMA slope for now)
        df['macro_bias'] = get_macro_bias(df)
        df['bias_confidence'] = 0.90  # Simplified for now
        
        # Add regression channel and S/R zones (simplified)
        df['reg_channel_distance'] = calculate_channel_distance(df)
        df['sr_zone_distance'] = calculate_sr_distance(df)
        
        # Save to cache
        Path('candle_cache').mkdir(exist_ok=True)
        df.to_csv(csv_path)
        logger.info(f"Saved data to cache: {csv_path}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise

def calculate_rsi(close, period=14):
    """Calculate RSI."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_macro_bias(df):
    """Generate macro bias based on 4h EMA slope."""
    # Resample to 4h
    df_4h = df['close'].resample('4H').last()
    ema = df_4h.ewm(span=20).mean()
    
    # Calculate slope
    slope = ema.diff() / ema
    
    # Map slope to bias
    bias = pd.Series(index=df.index, dtype='object')
    for i in range(len(slope)):
        if i == 0:
            continue
            
        start_time = slope.index[i-1]
        end_time = slope.index[i]
        
        if slope.iloc[i] > 0.001:  # 0.1% slope threshold
            bias_value = 'LONG'
        elif slope.iloc[i] < -0.001:
            bias_value = 'SHORT'
        else:
            bias_value = 'NEUTRAL'
            
        bias.loc[start_time:end_time] = bias_value
    
    return bias.ffill()  # Forward fill any gaps

def calculate_channel_distance(df):
    """Calculate distance from regression channel."""
    # Use 30-minute rolling regression
    window = 30
    y = df['close'].rolling(window=window).mean()
    x = np.arange(len(df))
    
    def rolling_regression(y):
        if len(y) < window:
            return 0
        x_local = np.arange(len(y))
        slope, intercept = np.polyfit(x_local, y, 1)
        return y.iloc[-1] - (slope * (len(y)-1) + intercept)
    
    distances = y.rolling(window=window).apply(rolling_regression)
    return distances / df['close']  # Return as percentage

def calculate_sr_distance(df):
    """Calculate distance from nearest S/R zone."""
    # Simplified: use recent highs/lows as S/R
    highs = df['high'].rolling(window=240).max()  # 4h highs
    lows = df['low'].rolling(window=240).min()   # 4h lows
    
    current = df['close']
    high_dist = (highs - current) / current
    low_dist = (current - lows) / current
    
    return pd.concat([high_dist, low_dist], axis=1).min(axis=1)

def analyze_results(trades_log, equity_curve):
    """Generate detailed performance metrics."""
    if not trades_log:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }
    
    df_trades = pd.DataFrame(trades_log)
    
    # Calculate metrics
    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades['pnl'] > 0])
    win_rate = winning_trades / total_trades * 100
    
    avg_profit = df_trades['pnl'].mean()
    max_profit = df_trades['pnl'].max()
    max_loss = df_trades['pnl'].min()
    
    # Calculate hold times
    avg_hold_time = df_trades['hold_time_minutes'].mean()
    
    # Calculate drawdown
    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.expanding().max()
    drawdowns = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdowns.min()
    
    # Calculate Sharpe ratio (assuming risk-free rate of 0)
    returns = equity_series.pct_change().dropna()
    sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()
    
    # Analyze margin usage
    avg_topups = df_trades['margin_topups'].mean()
    max_topups = df_trades['margin_topups'].max()
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_profit': avg_profit,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'avg_hold_time_minutes': avg_hold_time,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'avg_margin_topups': avg_topups,
        'max_margin_topups': max_topups
    }

def plot_results(equity_curve, trades_log, output_dir='backtest_results'):
    """Generate performance visualizations."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert trades to DataFrame
    df_trades = pd.DataFrame(trades_log)
    df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time'])
    
    # 1. Equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve)
    plt.title('Equity Curve')
    plt.grid(True)
    plt.savefig(f'{output_dir}/equity_curve.png')
    plt.close()
    
    # 2. Trade duration distribution
    plt.figure(figsize=(10, 6))
    plt.hist(df_trades['hold_time_minutes'], bins=50)
    plt.title('Trade Duration Distribution (minutes)')
    plt.xlabel('Duration (minutes)')
    plt.ylabel('Count')
    plt.grid(True)
    plt.savefig(f'{output_dir}/duration_dist.png')
    plt.close()
    
    # 3. P&L vs Duration scatter
    plt.figure(figsize=(10, 6))
    plt.scatter(df_trades['hold_time_minutes'], df_trades['pnl'])
    plt.title('P&L vs Trade Duration')
    plt.xlabel('Duration (minutes)')
    plt.ylabel('P&L')
    plt.grid(True)
    plt.savefig(f'{output_dir}/pnl_vs_duration.png')
    plt.close()
    
    # 4. Quick wins vs Managed trades comparison
    quick_wins = df_trades[
        (df_trades['pnl'] > 0) & 
        (df_trades['hold_time_minutes'] <= 60)
    ]
    managed_trades = df_trades[df_trades['margin_topups'] > 0]
    
    plt.figure(figsize=(10, 6))
    data = [
        quick_wins['pnl'].mean() if len(quick_wins) > 0 else 0,
        managed_trades['pnl'].mean() if len(managed_trades) > 0 else 0
    ]
    plt.bar(['Quick Wins', 'Managed Trades'], data)
    plt.title('Average P&L: Quick Wins vs Managed Trades')
    plt.ylabel('Average P&L per Trade')
    plt.grid(True)
    plt.savefig(f'{output_dir}/quick_vs_managed.png')
    plt.close()

def print_results(metrics):
    """Print backtest results in a readable format."""
    print("\n=== Backtest Results ===")
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Win Rate: {metrics['win_rate']:.2f}%")
    print(f"Average Profit: ${metrics['avg_profit']:.2f}")
    print(f"Max Profit: ${metrics['max_profit']:.2f}")
    print(f"Max Loss: ${metrics['max_loss']:.2f}")
    print(f"Average Hold Time: {metrics['avg_hold_time_minutes']:.1f} minutes")
    print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Average Margin Top-ups: {metrics['avg_margin_topups']:.1f}")
    print(f"Max Margin Top-ups: {metrics['max_margin_topups']}")
    
def main():
    """Run backtest and display results."""
    # Load data
    df = load_data('SOLUSDT', period_days=90)
    
    # Run backtest
    engine = BacktestEngine()
    engine.run(df, PARAMS)
    
    # Analyze results
    metrics = analyze_results(engine.trades_log, engine.equity_curve)
    
    # Print results
    print_results(metrics)

if __name__ == '__main__':
    main() 