import os
import logging
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timezone, timedelta
import itertools
import numpy as np
import argparse
from typing import List, Tuple, Dict

from google.cloud import bigtable
from google.cloud.bigtable.row_set import RowSet

# --- Custom Modules ---
from . import level_finder
from . import entry_logic

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
INSTANCE_ID = "cryptotracker-bigtable"
TABLE_ID = "market-data-1m"

# --- Strategy & Backtest Configuration ---
TRANSACTION_FEE_PCT = 0.06 / 100 # 0.06% taker fee
INITIAL_EQUITY = 10000 # Starting equity for simulation
SLIPPAGE_MODEL = {
    'base': 0.02 / 100,  # Base slippage 0.02%
    'volume_impact': 0.01 / 100,  # Additional slippage per 1M USD volume
    'volatility_impact': 0.005 / 100  # Additional slippage per 1% 5m volatility
}

# Account Configuration
INITIAL_CAPITAL = 100000  # $100,000
MAX_LEVERAGE = 10
MARGIN_PER_TRADE = 0.10   # 10% of capital as margin
TAKER_FEE = 0.0006       # 0.06% taker fee
FUNDING_INTERVAL = 8      # hours

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Bigtable Client ---
# Move client initialization into the main execution block
# to prevent it from running on import.
table = None

def get_bigtable_table():
    """Initializes and returns the Bigtable table object."""
    global table
    if table is not None:
        return table
    
    try:
        project_id = os.environ.get("GCP_PROJECT_ID")
        if not project_id:
            logging.error("GCP_PROJECT_ID environment variable not set.")
            return None
        
        bigtable_client = bigtable.Client(project=project_id, admin=True)
    instance = bigtable_client.instance(INSTANCE_ID)
    table = instance.table(TABLE_ID)
        logging.info("Successfully connected to Bigtable.")
        return table
except Exception as e:
    logging.error(f"Failed to connect to Bigtable: {e}")
        return None

def fetch_historical_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Fetch historical data from Bybit.
    
    Args:
        symbol: Trading pair symbol
        start_date: Start date
        end_date: End date
        
    Returns:
        DataFrame with OHLCV and funding rate data
    """
    # For now, let's create sample data for testing
    # In production, this would fetch from Bybit API
    periods = int((end_date - start_date).total_seconds() / 300)  # 5-minute intervals
    timestamps = pd.date_range(start=start_date, end=end_date, periods=periods)
    
    np.random.seed(42)  # For reproducibility
    
    # Generate more realistic price data for SOL
    base_price = 100.0  # Starting price for SOL
    prices = []
    current_price = base_price
    
    # Parameters for price movement
    trend = 0.0001  # Slight upward trend
    volatility = 0.002  # Base volatility
    momentum = 0  # Track momentum
    momentum_factor = 0.7  # Momentum persistence
    
    for _ in range(periods):
        # Add momentum effect
        momentum = momentum * momentum_factor + np.random.normal(0, 0.0005)
        
        # Combine trend, momentum and random walk
        change = trend + momentum + np.random.normal(0, volatility)
        
        # Add occasional volatility spikes
        if np.random.random() < 0.02:  # 2% chance of volatility spike
            change *= np.random.uniform(2, 4)
        
        current_price *= (1 + change)
        prices.append(current_price)
    
    # Generate realistic volume profile
    base_volume = 1000000  # Base volume in USDT
    volumes = []
    for price in prices:
        # Volume tends to spike with larger price moves
        vol_multiplier = 1 + abs(np.random.normal(0, 2))
        volume = base_volume * vol_multiplier
        volumes.append(volume)
    
    # Create DataFrame with realistic OHLCV data
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': prices,
        'close': prices,  # We'll adjust these next
        'volume': volumes
    })
    
    # Adjust OHLC to be more realistic
    for i in range(len(df)):
        price = df.iloc[i]['open']
        # High and low vary from open based on volatility
        high_low_range = price * volatility * np.random.uniform(0.5, 2.0)
        df.loc[df.index[i], 'high'] = price + high_low_range/2
        df.loc[df.index[i], 'low'] = price - high_low_range/2
        # Close varies from open
        df.loc[df.index[i], 'close'] = price * (1 + np.random.normal(0, volatility/2))
    
    # Add funding rates
    # Funding rates tend to be mean-reverting and correlated with price changes
    funding_rates = []
    base_funding = 0.0001  # 0.01% base rate
    funding_momentum = 0
    
    for i in range(len(df)):
        if i > 0:
            price_change = (df.iloc[i]['close'] - df.iloc[i-1]['close']) / df.iloc[i-1]['close']
            funding_momentum = funding_momentum * 0.95 + price_change * 0.1
        funding_rate = base_funding + funding_momentum + np.random.normal(0, 0.0002)
        funding_rates.append(funding_rate)
    
    df['funding_rate'] = funding_rates
    
    df.set_index('timestamp', inplace=True)
    return df

def apply_strategy(df: pd.DataFrame, params: dict):
    """Applies indicators based on the given parameter set."""
    if df.empty:
        return df
    
    # Calculate all indicators that might be needed by any strategy variation
    df.ta.ema(length=params.get('ema', 20), append=True)
    df.ta.rsi(length=params.get('rsi_period', 14), append=True)
    df.ta.atr(length=params.get('atr_period', 14), append=True)
    
    # Clean up column names for easier access
    df.rename(columns={
        f"EMA_{params.get('ema', 20)}": 'ema',
        f"RSI_{params.get('rsi_period', 14)}": 'rsi',
        f"ATRr_{params.get('atr_period', 14)}": 'atr'
    }, inplace=True, errors='ignore')

    # Add Volume MA for the new strategy
    df['volume_ma'] = df['volume'].rolling(window=20).mean()

    return df

def calculate_slippage(row: pd.Series, position_size: float) -> float:
    """
    Calculate realistic slippage based on position size, volume, and volatility.
    
    Args:
        row: DataFrame row with OHLCV data
        position_size: Size of the position in USD
        
    Returns:
        Slippage as a percentage
    """
    # Base slippage
    slippage = SLIPPAGE_MODEL['base']
    
    # Volume-based slippage
    volume_usd = row['volume'] * row['close']
    volume_impact = min(position_size / volume_usd, 1) * SLIPPAGE_MODEL['volume_impact']
    slippage += volume_impact
    
    # Volatility-based slippage
    volatility_pct = (row['high'] - row['low']) / row['close'] * 100
    volatility_impact = volatility_pct * SLIPPAGE_MODEL['volatility_impact']
    slippage += volatility_impact
    
    return slippage

def simulate_trades(df: pd.DataFrame, params: dict):
    """
    Simulates trades and returns a detailed log for each trade.
    Includes a "what-if" analysis for trades that hit a stop-loss.
    """
    if 'rsi' not in df.columns or 'atr' not in df.columns:
        logging.error("Required indicators not found in DataFrame.")
        return [], []

    trades_log = []
    equity = INITIAL_EQUITY
    equity_curve = [INITIAL_EQUITY]
    position = None 
    daily_trades = {}  # Track trades per day for trade frequency analysis
    consecutive_losses = 0  # Track consecutive losses for risk management

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        current_date = current_candle.name.date()
        
        # Reset daily trade counter
        if current_date not in daily_trades:
            daily_trades[current_date] = 0
        
        # --- Combined Entry/Exit Logic (v2) ---
        
        # 1. Check for EXIT first
        if position is not None:
            exit_price = None
            exit_reason = None
            
            # Calculate actual exit price with slippage
            slippage_pct = calculate_slippage(current_candle, position['size_usd'])
            
            if position['side'] == 'LONG':
                if current_candle['high'] >= position['tp_price']:
                    exit_price = min(position['tp_price'], 
                                   position['tp_price'] * (1 - slippage_pct))
                    exit_reason = 'TP'
                elif current_candle['low'] <= position['sl_price']:
                    exit_price = max(position['sl_price'],
                                   position['sl_price'] * (1 + slippage_pct))
                    exit_reason = 'SL'
            
            elif position['side'] == 'SHORT':
                if current_candle['low'] <= position['tp_price']:
                    exit_price = max(position['tp_price'],
                                   position['tp_price'] * (1 + slippage_pct))
                    exit_reason = 'TP'
                elif current_candle['high'] >= position['sl_price']:
                    exit_price = min(position['sl_price'],
                                   position['sl_price'] * (1 - slippage_pct))
                    exit_reason = 'SL'

            if exit_reason:
                # --- Record the trade ---
                pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
                if position['side'] == 'SHORT':
                    pnl_pct = -pnl_pct

                # Include transaction fees
                net_pnl_pct = pnl_pct - (2 * TRANSACTION_FEE_PCT)
                equity += equity * net_pnl_pct
                equity_curve.append(equity)
                
                # Update consecutive losses counter
                if net_pnl_pct < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0

                trade_result = {
                    "entry_timestamp": position['entry_timestamp'],
                    "exit_timestamp": current_candle.name,
                    "side": position['side'],
                    "entry_price": position['entry_price'],
                    "exit_price": exit_price,
                    "sl_price": position['sl_price'],
                    "tp_price": position['tp_price'],
                    "size_usd": position['size_usd'],
                    "slippage_pct": slippage_pct,
                    "pnl_pct": net_pnl_pct,
                    "exit_reason": exit_reason,
                    "params": f"ema:{params['ema']}_rsi:{params['rsi_period']}_{params['exit_strategy']}"
                }

                # --- "What If" Analysis for Stop-Loss ---
                if exit_reason == 'SL':
                    what_if_horizon = df.iloc[i+1 : i+1+240]  # Look 4 hours ahead
                    if not what_if_horizon.empty:
                        original_tp = position['tp_price']
                        if position['side'] == 'LONG':
                            would_have_hit_tp = (what_if_horizon['high'] >= original_tp).any()
                            max_profit_price = what_if_horizon['high'].max()
                            max_loss_price = what_if_horizon['low'].min()
                        else:  # SHORT
                            would_have_hit_tp = (what_if_horizon['low'] <= original_tp).any()
                            max_profit_price = what_if_horizon['low'].min()
                            max_loss_price = what_if_horizon['high'].max()

                        trade_result.update({
                            'sl_what_if_hit_tp': would_have_hit_tp,
                            'sl_what_if_max_profit_pct': ((max_profit_price - position['entry_price']) / position['entry_price'] if position['side'] == 'LONG' else (position['entry_price'] - max_profit_price) / position['entry_price']),
                            'sl_what_if_max_loss_pct': ((max_loss_price - position['entry_price']) / position['entry_price'] if position['side'] == 'LONG' else (position['entry_price'] - max_loss_price) / position['entry_price'])
                        })

                trades_log.append(trade_result)
                daily_trades[current_date] += 1
                position = None

        # 2. Check for ENTRY only if no position is currently open
        if position is None:
            # Skip if we've already hit daily trade limit
            if daily_trades[current_date] >= params.get('max_daily_trades', 6):
                continue
                
            # Skip if we've had too many consecutive losses
            if consecutive_losses >= params.get('max_consecutive_losses', 3):
                continue
                
            volume_ma = current_candle['volume_ma']
            if pd.isna(volume_ma):
                continue

            rsi_val = current_candle['rsi']
            is_oversold = rsi_val < params['rsi_oversold']
            is_overbought = rsi_val > params['rsi_overbought']
            
            # V5.1 Strategy: Re-introducing volume with data-driven parameters
            has_volume_spike = current_candle['volume'] > (volume_ma * params['volume_factor'])

            side = None
            if is_oversold and has_volume_spike:
                side = 'LONG'
            elif is_overbought and has_volume_spike:
                side = 'SHORT'
            
            if side:
                entry_price = current_candle['close']
                # Calculate entry slippage
                slippage_pct = calculate_slippage(current_candle, equity * 0.1)  # 10% of equity
                if side == 'LONG':
                    entry_price *= (1 + slippage_pct)
                else:
                    entry_price *= (1 - slippage_pct)
                
                position = {
                    "side": side,
                    "entry_price": entry_price,
                    "entry_timestamp": current_candle.name,
                    "size_usd": equity * 0.1  # 10% of equity per trade
                }
                
                if params['exit_strategy'] == 'fixed':
                    tp_mult = (1 + params['tp_pct']) if side == 'LONG' else (1 - params['tp_pct'])
                    sl_mult = (1 - params['sl_pct']) if side == 'LONG' else (1 + params['sl_pct'])
                    position['tp_price'] = entry_price * tp_mult
                    position['sl_price'] = entry_price * sl_mult
                elif params['exit_strategy'] == 'atr':
                    atr_val = current_candle['atr']
                    if side == 'LONG':
                        position['tp_price'] = entry_price + (params['atr_multiplier_tp'] * atr_val)
                        position['sl_price'] = entry_price - (params['atr_multiplier_sl'] * atr_val)
                    else:  # SHORT
                        position['tp_price'] = entry_price - (params['atr_multiplier_tp'] * atr_val)
                        position['sl_price'] = entry_price + (params['atr_multiplier_sl'] * atr_val)

    return trades_log, equity_curve

def calculate_performance(trades_log: List[dict], equity_curve: List[float], params: dict) -> dict:
    """
    Calculate comprehensive performance metrics from a list of trades.
    
    Args:
        trades_log: List of trade dictionaries
        equity_curve: List of equity values
        params: Strategy parameters
        
    Returns:
        Dictionary of performance metrics
    """
    if not trades_log:
        return None

    # Convert timestamps to datetime
    for trade in trades_log:
        trade['entry_time'] = pd.to_datetime(trade['entry_time'])
        trade['exit_time'] = pd.to_datetime(trade['exit_time'])
    
    # Core metrics
    num_trades = len(trades_log)
    num_wins = len([t for t in trades_log if t['pnl'] > 0])
    num_losses = len([t for t in trades_log if t['pnl'] <= 0])
    
    win_rate = num_wins / num_trades if num_trades > 0 else 0
    
    # PnL metrics
    total_pnl = sum(t['pnl'] for t in trades_log)
    total_pnl_pct = (equity_curve[-1] / equity_curve[0] - 1) * 100
    
    win_pnls = [t['pnl'] for t in trades_log if t['pnl'] > 0]
    loss_pnls = [t['pnl'] for t in trades_log if t['pnl'] <= 0]
    
    avg_win = np.mean(win_pnls) if win_pnls else 0
    avg_loss = np.mean(loss_pnls) if loss_pnls else 0
    max_win = max(win_pnls) if win_pnls else 0
    max_loss = min(loss_pnls) if loss_pnls else 0
    
    # Risk metrics
    equity_series = pd.Series(equity_curve)
    drawdown = (equity_series.expanding().max() - equity_series) / equity_series.expanding().max() * 100
    max_drawdown_pct = drawdown.max()
    
    # Trade duration metrics
    durations = [(t['exit_time'] - t['entry_time']).total_seconds() / 60 for t in trades_log]  # in minutes
    avg_duration = np.mean(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    max_duration = max(durations) if durations else 0
    
    # Daily statistics
    daily_pnls = {}
    for trade in trades_log:
        date = trade['exit_time'].date()
        daily_pnls[date] = daily_pnls.get(date, 0) + trade['pnl']
    
    profitable_days = len([pnl for pnl in daily_pnls.values() if pnl > 0])
    total_days = len(daily_pnls)
    daily_win_rate = profitable_days / total_days if total_days > 0 else 0
    
    # Risk-adjusted metrics
    returns = pd.Series(equity_curve).pct_change().dropna()
    if len(returns) > 1:
        sharpe_ratio = np.sqrt(252) * (returns.mean() / returns.std())
        sortino_ratio = np.sqrt(252) * (returns.mean() / returns[returns < 0].std())
    else:
        sharpe_ratio = 0
        sortino_ratio = 0
    
    # Exit analysis
    exit_types = {}
    for trade in trades_log:
        exit_type = trade['exit_reason']
        exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
    
    return {
        'params': params,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'total_pnl_pct': total_pnl_pct,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_win': max_win,
        'max_loss': max_loss,
        'max_drawdown_pct': max_drawdown_pct,
        'avg_duration_min': avg_duration,
        'min_duration_min': min_duration,
        'max_duration_min': max_duration,
        'daily_win_rate': daily_win_rate,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'exit_types': exit_types,
        'equity_curve': equity_curve
    }

def calculate_position_size(equity: float, risk_per_trade: float = 0.02) -> float:
    """
    Calculate position size based on equity and risk per trade.
    
    Args:
        equity: Current equity
        risk_per_trade: Percentage of equity to risk per trade (default 2%)
        
    Returns:
        Position size in base currency
    """
    position_size = equity * risk_per_trade
    return position_size

def calculate_pnl(position: dict, exit_price: float) -> float:
    """
    Calculate PnL for a position.
    
    Args:
        position: Dictionary containing position details
        exit_price: Exit price
        
    Returns:
        PnL in quote currency
    """
    if position['side'] == 'long':
        pnl = (exit_price - position['entry_price']) * position['position_size']
    else:  # short
        pnl = (position['entry_price'] - exit_price) * position['position_size']
    
    # Subtract transaction fees
    pnl -= position['position_value'] * TRANSACTION_FEE_PCT
    
    # Apply slippage
    slippage = calculate_slippage(position['position_value'])
    pnl -= position['position_value'] * slippage
    
    return pnl

def calculate_slippage(position_value: float) -> float:
    """
    Calculate slippage based on position size.
    
    Args:
        position_value: Position value in quote currency
        
    Returns:
        Slippage as a percentage
    """
    # Base slippage
    slippage = SLIPPAGE_MODEL['base']
    
    # Add volume impact (linear scaling with position size)
    volume_impact = min(position_value / 1_000_000, 1.0) * SLIPPAGE_MODEL['volume_impact']
    slippage += volume_impact
    
    return slippage

class Position:
    def __init__(self, side: str, entry_price: float, margin: float, leverage: float, entry_time: datetime):
        self.side = side
        self.entry_price = entry_price
        self.margin = margin
        self.leverage = leverage
        self.entry_time = entry_time
        self.size = margin * leverage
        self.funding_fees_paid = 0.0
        self.last_funding_time = entry_time
        
    def calculate_pnl(self, current_price: float, include_fees: bool = True) -> float:
        """Calculate PnL including trading and funding fees."""
        if self.side == 'long':
            price_pnl = (current_price - self.entry_price) / self.entry_price
        else:  # short
            price_pnl = (self.entry_price - current_price) / self.entry_price
            
        gross_pnl = price_pnl * self.size
        
        if include_fees:
            # Trading fees
            entry_fee = self.size * TAKER_FEE
            exit_fee = self.size * TAKER_FEE
            total_fees = entry_fee + exit_fee + self.funding_fees_paid
            return gross_pnl - total_fees
        return gross_pnl
        
    def update_funding_fees(self, current_time: datetime, funding_rate: float):
        """Update funding fees based on time elapsed."""
        while self.last_funding_time + timedelta(hours=FUNDING_INTERVAL) <= current_time:
            # Calculate funding payment
            funding_payment = self.size * funding_rate
            if self.side == 'long':
                self.funding_fees_paid += funding_payment
            else:  # short
                self.funding_fees_paid -= funding_payment
            
            self.last_funding_time += timedelta(hours=FUNDING_INTERVAL)

def run_backtest(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    params: dict,
    with_sl: bool = True  # Flag to enable/disable stop-loss
) -> Tuple[List[dict], List[float], Dict]:
    """
    Run backtest with enhanced tracking of PnL and fees.
    
    Args:
        symbol: Trading pair symbol
        start_date: Start date for backtest
        end_date: End date for backtest
        params: Strategy parameters
        with_sl: Whether to use stop-loss
        
    Returns:
        Tuple of (trades_log, equity_curve, metrics)
    """
    # Initialize tracking
    trades_log = []
    equity = INITIAL_CAPITAL
    equity_curve = [equity]
    current_position = None
    metrics = {
        'total_trades': 0,
        'profitable_trades': 0,
        'total_pnl': 0.0,
        'max_drawdown': 0.0,
        'avg_trade_duration': timedelta(0),
        'total_fees_paid': 0.0,
        'total_funding_paid': 0.0
    }
    
    # Get historical data including funding rates
    df = fetch_historical_data(symbol, start_date, end_date)
    
    for i in range(len(df) - 1):
        current_bar = df.iloc[i]
        next_bar = df.iloc[i + 1]
        current_time = pd.to_datetime(current_bar.name)
        
        # Update position funding fees if exists
        if current_position:
            current_position.update_funding_fees(
                current_time,
                current_bar['funding_rate']
            )
        
        # Check for exit if position exists
        if current_position:
            # Calculate current PnL
            current_pnl = current_position.calculate_pnl(
                current_bar['close'],
                include_fees=True
            )
            
            # Check stop-loss if enabled
            if with_sl and current_pnl <= -params['max_loss_pct'] * current_position.margin:
                # Close position at stop-loss
                trades_log.append({
                    'entry_time': current_position.entry_time,
                    'exit_time': current_time,
                    'side': current_position.side,
                    'entry_price': current_position.entry_price,
                    'exit_price': current_bar['close'],
                    'position_size': current_position.size,
                    'pnl': current_pnl,
                    'pnl_pct': current_pnl / current_position.margin,
                    'fees_paid': current_position.funding_fees_paid + (2 * TAKER_FEE * current_position.size),
                    'exit_reason': 'stop_loss'
                })
                
                equity += current_pnl
                equity_curve.append(equity)
                current_position = None
                continue
            
            # Check other exit conditions
            exit_signal, reason, exit_price = check_exit_conditions(
                current_position.__dict__,
                current_bar,
                calculate_indicators(df, i, params),
                params
            )
            
            if exit_signal:
                # Close position
                final_pnl = current_position.calculate_pnl(exit_price, include_fees=True)
                trades_log.append({
                    'entry_time': current_position.entry_time,
                    'exit_time': current_time,
                    'side': current_position.side,
                    'entry_price': current_position.entry_price,
                    'exit_price': exit_price,
                    'position_size': current_position.size,
                    'pnl': final_pnl,
                    'pnl_pct': final_pnl / current_position.margin,
                    'fees_paid': current_position.funding_fees_paid + (2 * TAKER_FEE * current_position.size),
                    'exit_reason': reason
                })
                
                equity += final_pnl
                equity_curve.append(equity)
                current_position = None
                continue
        
        # Check for entry if no position
        if not current_position:
            entry_signal, direction, entry_price = check_entry_conditions(
                current_bar,
                df.iloc[i-1] if i > 0 else current_bar,
                calculate_indicators(df, i, params),
                params
            )
            
            if entry_signal:
                # Calculate position size
                margin = min(
                    equity * MARGIN_PER_TRADE,
                    INITIAL_CAPITAL * MARGIN_PER_TRADE  # Cap at initial capital
                )
                
                # Open new position
                current_position = Position(
                    side=direction,
                    entry_price=entry_price,
                    margin=margin,
                    leverage=MAX_LEVERAGE,
                    entry_time=current_time
                )
    
    # Close any remaining position at the end
    if current_position:
        final_pnl = current_position.calculate_pnl(df.iloc[-1]['close'], include_fees=True)
        trades_log.append({
            'entry_time': current_position.entry_time,
            'exit_time': pd.to_datetime(df.index[-1]),
            'side': current_position.side,
            'entry_price': current_position.entry_price,
            'exit_price': df.iloc[-1]['close'],
            'position_size': current_position.size,
            'pnl': final_pnl,
            'pnl_pct': final_pnl / current_position.margin,
            'fees_paid': current_position.funding_fees_paid + (2 * TAKER_FEE * current_position.size),
            'exit_reason': 'end_of_period'
        })
        
        equity += final_pnl
        equity_curve.append(equity)
    
    # Calculate final metrics
    if trades_log:
        metrics['total_trades'] = len(trades_log)
        metrics['profitable_trades'] = len([t for t in trades_log if t['pnl'] > 0])
        metrics['total_pnl'] = equity - INITIAL_CAPITAL
        metrics['total_fees_paid'] = sum(t['fees_paid'] for t in trades_log)
        metrics['avg_trade_duration'] = sum(
            (t['exit_time'] - t['entry_time']) for t in trades_log
        ) / len(trades_log)
        
        # Calculate max drawdown
    peak = equity_curve[0]
    max_drawdown = 0
        for e in equity_curve:
            if e > peak:
                peak = e
            drawdown = (peak - e) / peak
            max_drawdown = max(max_drawdown, drawdown)
        metrics['max_drawdown'] = max_drawdown
    
    return trades_log, equity_curve, metrics

def calculate_indicators(df: pd.DataFrame, current_idx: int, params: dict) -> dict:
    """Calculate technical indicators for the current bar."""
    window = max(20, params['ema'], params['rsi_period'])  # Use the largest lookback period
    start_idx = max(0, current_idx - window)
    
    # Get data slice
    data_slice = df.iloc[start_idx:current_idx + 1].copy()
    
    # Calculate EMA
    ema = pd.Series(data_slice['close']).ewm(span=params['ema'], adjust=False).mean()
    
    # Calculate RSI
    delta = data_slice['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=params['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=params['rsi_period']).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Calculate Volume SMA
    volume_sma = data_slice['volume'].rolling(window=20).mean()
    
    # Calculate ATR
    high_low = data_slice['high'] - data_slice['low']
    high_close = abs(data_slice['high'] - data_slice['close'].shift())
    low_close = abs(data_slice['low'] - data_slice['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=params['atr_period']).mean()
    
    # Get the latest values
    indicators = {
        'ema': ema.iloc[-1] if not pd.isna(ema.iloc[-1]) else data_slice['close'].iloc[-1],
        'rsi': rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50,
        'prev_rsi': rsi.iloc[-2] if len(rsi) > 1 and not pd.isna(rsi.iloc[-2]) else 50,
        'volume_sma': volume_sma.iloc[-1] if not pd.isna(volume_sma.iloc[-1]) else data_slice['volume'].iloc[-1],
        'atr': atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else true_range.iloc[-1]
    }
    
    return indicators

def check_entry_conditions(
    current_bar: pd.Series,
    prev_bar: pd.Series,
    indicators: Dict,
    params: Dict
) -> Tuple[bool, str, float]:
    """Check if entry conditions are met."""
    # Volume check - more lenient
    min_volume = params['min_volume_usdt'] * 0.8
    if current_bar['volume'] * current_bar['close'] < min_volume:
        return False, "", 0.0
        
    # Volatility check - more lenient
    price_change = abs(current_bar['close'] - current_bar['open']) / current_bar['open']
    if price_change < params['volatility_threshold'] * 0.5:  # Halved threshold
        return False, "", 0.0
        
    # Trend check
    trend_bullish = current_bar['close'] > indicators['ema']
    
    # RSI conditions - more dynamic
    rsi = indicators['rsi']
    prev_rsi = indicators['prev_rsi']
    rsi_slope = rsi - prev_rsi
    
    # Long entry conditions - more aggressive
    if (
        # RSI conditions
        (rsi < 65 and rsi > 35) and  # Less extreme RSI levels
        rsi_slope > 0 and  # RSI turning up
        # Trend confirmation
        trend_bullish and
        # Volume confirmation
        current_bar['volume'] > indicators['volume_sma'] * 0.8
    ):
        return True, "long", current_bar['close']
        
    # Short entry conditions - more conservative
    if (
        # RSI conditions
        (rsi < 65 and rsi > 35) and  # Less extreme RSI levels
        rsi_slope < 0 and  # RSI turning down
        # Trend confirmation
        not trend_bullish and
        # Volume confirmation
        current_bar['volume'] > indicators['volume_sma'] * 1.0  # Stricter for shorts
    ):
        return True, "short", current_bar['close']
        
    return False, "", 0.0

def check_exit_conditions(
    position: Dict,
    current_bar: pd.Series,
    indicators: Dict,
    params: Dict
) -> Tuple[bool, str, float]:
    """Check if exit conditions are met."""
    if params['exit_strategy'] == 'fixed':
        return check_fixed_exits(position, current_bar, params)
    else:  # ATR-based exits
        return check_atr_exits(position, current_bar, indicators, params)

def check_fixed_exits(
    position: Dict,
    current_bar: pd.Series,
    params: Dict
) -> Tuple[bool, str, float]:
    """Check fixed take-profit and stop-loss levels."""
    if position['side'] == 'long':
        tp_price = position['entry_price'] * (1 + 0.002)  # 0.2% target
        sl_price = position['entry_price'] * (1 - 0.003)  # 0.3% stop loss
        
        if current_bar['high'] >= tp_price:
            return True, "tp", tp_price
        if current_bar['low'] <= sl_price:
            return True, "sl", sl_price
            
    else:  # short position
        tp_price = position['entry_price'] * (1 - 0.002)  # 0.2% target
        sl_price = position['entry_price'] * (1 + 0.003)  # 0.3% stop loss
        
        if current_bar['low'] <= tp_price:
            return True, "tp", tp_price
        if current_bar['high'] >= sl_price:
            return True, "sl", sl_price
            
    return False, "", 0.0

def check_atr_exits(
    position: Dict,
    current_bar: pd.Series,
    indicators: Dict,
    params: Dict
) -> Tuple[bool, str, float]:
    """Check ATR-based dynamic exits."""
    atr = indicators['atr']
    
    if position['side'] == 'long':
        tp_price = position['entry_price'] + (atr * 1.0)  # Reduced from 2.0
        sl_price = position['entry_price'] - (atr * 0.7)  # Reduced from 1.5
        
        if current_bar['high'] >= tp_price:
            return True, "tp", tp_price
        if current_bar['low'] <= sl_price:
            return True, "sl", sl_price
            
    else:  # short position
        tp_price = position['entry_price'] - (atr * 1.0)  # Reduced from 2.0
        sl_price = position['entry_price'] + (atr * 0.7)  # Reduced from 1.5
        
        if current_bar['low'] <= tp_price:
            return True, "tp", tp_price
        if current_bar['high'] >= sl_price:
            return True, "sl", sl_price
            
    return False, "", 0.0

if __name__ == "__main__":
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run a multi-variable backtest for crypto scalping strategies.")
    parser.add_argument(
        '--symbols', 
        nargs='+', 
        default=['SOLUSDT', 'BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'DOGEUSDT'],
        help='A list of symbols to backtest (e.g., SOLUSDT BTCUSDT).'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='The number of past days to fetch data for.'
    )
    args = parser.parse_args()

    # --- PHASE 4: Multi-Variable Parameter Optimization ---
    
    # 1. Define Parameter Grids - V5.2: "Contender" Grid with Micro-Scalp Targets
    param_grid = {
        'ema': [10],
        'rsi_period': [14],
        'rsi_overbought': [70, 73, 75],     # Data-driven sweet spot
        'rsi_oversold': [20, 23, 25],       # Data-driven sweet spot
        'volume_factor': [0.1, 1.0, 1.5, 2.0], # Wide range proved effective
        'exit_strategy': ['fixed'],
        # --- Fixed Exit ---
        'tp_pct': [0.005, 0.01, 0.015], # Added 0.5% micro-scalp target
        'sl_pct': [0.003, 0.005, 0.007], # Added 0.3% micro-scalp target
    }
    
    SYMBOLS_TO_TEST = args.symbols
    END_DATE = datetime.now(timezone.utc)
    START_DATE = END_DATE - timedelta(days=args.days)

    master_trade_log = []
    all_performance_results = []

    bt_table = get_bigtable_table()
    if not bt_table:
        logging.critical("Exiting: Bigtable client not configured.")
    else:
        for symbol in SYMBOLS_TO_TEST:
            print(f"\n=================================================")
            print(f"   BACKTESTING & OPTIMIZING FOR: {symbol}")
            print(f"=================================================")

            logging.info(f"Fetching historical data for {symbol} from {START_DATE} to {END_DATE}...")
            base_df = fetch_historical_data(symbol, START_DATE, END_DATE)

        if base_df.empty:
                logging.warning(f"Could not retrieve historical data for {symbol}. Skipping.")
                continue
            
            logging.info(f"Successfully fetched {len(base_df)} data points for {symbol}. Starting optimization...")
            
            keys, values = zip(*param_grid.items())
            # Filter out the commented-out keys before creating combinations
            active_keys = [k for k in keys if not k.startswith('#')]
            active_values = [v for k, v in zip(keys, values) if not k.startswith('#')]
            
            all_param_combos = [dict(zip(active_keys, v)) for v in itertools.product(*active_values)]
            symbol_results = []
            
            logging.info(f"Testing {len(all_param_combos)} parameter combinations...")

            for i, params in enumerate(all_param_combos):
                params['data'] = base_df
                # Handle the case where volume_factor might be missing
                params.setdefault('volume_factor', 1.0) # Default to 1.0, though it's unused
                params['name'] = f"ema:{params['ema']}_rsi:{params['rsi_period']}_{params['exit_strategy']}"
                
                if params['exit_strategy'] == 'fixed' and params.get('atr_period'): continue
                if params['exit_strategy'] == 'atr' and params.get('tp_pct'): continue

                trades_log, equity_curve, metrics = run_backtest(symbol, START_DATE, END_DATE, params, with_sl=True)
                if equity_curve:
                    symbol_results.append(equity_curve)
                    master_trade_log.extend(trades_log) # Add trades to the master log
                print(f"  Completed {i+1}/{len(all_param_combos)}", end='\r')

            if not symbol_results:
                logging.warning(f"Optimization run for {symbol} completed with no valid results.")
            else:
                best_result = max(symbol_results, key=lambda x: x[-1])
                all_performance_results.append(best_result)
                print(f"\n\n--- Best Performing Strategy for {symbol} ---")
                print(f"Tested {len(symbol_results)} parameter combinations over the last {args.days} days.")
                print(f"Parameters: {params['name']}")
                print(f"Total Trades: {len(trades_log)}")
                print(f"Final Equity: {best_result[-1]:.2f}")
                print("------------------------------------------\n")
        
        # --- Save Master Log to CSV ---
        if master_trade_log:
            log_df = pd.DataFrame(master_trade_log)
            # Reorder columns for clarity
            cols_order = [
                'symbol', 'entry_timestamp', 'exit_timestamp', 'side', 'entry_price', 'exit_price', 
                'pnl_pct', 'exit_reason', 'sl_price', 'tp_price', 
                'sl_what_if_hit_tp', 'sl_what_if_max_profit_pct', 'sl_what_if_max_loss_pct', 'params'
            ]
            log_df = log_df.reindex(columns=cols_order)
            
            output_filename = "backtest_trades_log.csv"
            log_df.to_csv(output_filename, index=False, float_format='%.5f')
            print(f"\n✅ Successfully saved detailed trade log for all symbols to '{output_filename}'")
            print("You can now analyze this CSV file to reverse-engineer and improve the strategy.") 