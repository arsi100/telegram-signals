"""Perpetual Futures Backtest Engine

This engine simulates the exact strategy:
- Primary: Quick scalps targeting 0.5%+ moves
- Safety Net: Position management if trade goes against us
- No stop-losses, use margin management instead
- Tight trailing stops after hitting profit target
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Account:
    def __init__(self, balance=100_000):
        self.initial_balance = balance
        self.balance = balance
        self.positions = {}  # symbol -> Position
        self.margin_used = 0
        self.unrealized_pnl = 0
        
    def get_available_margin(self):
        """Calculate available margin for new positions."""
        return self.balance - self.margin_used
        
    def can_add_margin(self, amount):
        """Check if we can add margin to a position."""
        return self.get_available_margin() >= amount
        
    def update_unrealized_pnl(self, current_prices):
        """Update unrealized PnL for all positions."""
        self.unrealized_pnl = sum(
            pos.calculate_pnl(current_prices[pos.symbol])
            for pos in self.positions.values()
        )
        
    def get_total_equity(self):
        """Get total account value including unrealized PnL."""
        return self.balance + self.unrealized_pnl

class Position:
    def __init__(self, symbol, side, entry_price, size, leverage=10, entry_time=None):
        self.symbol = symbol
        self.side = side  # 'LONG' or 'SHORT'
        self.entry_price = entry_price
        self.size = size  # Position size in USD
        self.leverage = leverage
        self.margin = size / leverage
        self.entry_time = entry_time
        
        # Position tracking
        self.topups_used = 0
        self.funding_paid = 0
        self.trail_active = False
        self.trail_price = None
        self.last_topup_price = entry_price
        
        # Calculate liquidation price
        self.liquidation_price = self.calculate_liquidation_price()
        
    def calculate_liquidation_price(self):
        """Calculate the liquidation price based on leverage."""
        if self.side == 'LONG':
            return self.entry_price * (1 - (1/self.leverage) + 0.001)  # +0.1% buffer
        else:
            return self.entry_price * (1 + (1/self.leverage) - 0.001)
            
    def calculate_pnl(self, current_price):
        """Calculate unrealized PnL."""
        if self.side == 'LONG':
            return (current_price - self.entry_price) * self.size / self.entry_price
        else:
            return (self.entry_price - current_price) * self.size / self.entry_price
            
    def needs_margin_topup(self, current_price):
        """Check if position needs margin top-up."""
        # Don't add margin if we've used all top-ups
        if self.topups_used >= 4:
            return False
            
        # Calculate distance to liquidation
        distance_to_liq = abs(current_price - self.liquidation_price) / current_price
        
        # Calculate price movement since last top-up
        price_move = abs(current_price - self.last_topup_price) / self.last_topup_price
        
        # Only top-up if:
        # 1. We're within 15% of liquidation AND
        # 2. Price has moved at least 5% since last top-up
        return distance_to_liq <= 0.15 and price_move >= 0.05
        
    def add_margin(self, amount):
        """Add margin to the position."""
        self.margin += amount
        self.leverage = self.size / self.margin
        self.liquidation_price = self.calculate_liquidation_price()
        self.topups_used += 1
        self.last_topup_price = self.entry_price  # Reset reference price
        
    def update_unrealized_pnl(self, current_price):
        """Update unrealized PnL and check trailing stop."""
        pnl = self.calculate_pnl(current_price)
        pnl_pct = pnl / self.margin
        
        # Activate trailing stop at 0.5%
        if not self.trail_active and pnl_pct >= 0.005:
            self.trail_active = True
            if self.side == 'LONG':
                self.trail_price = current_price * 0.998  # 0.2% below
            else:
                self.trail_price = current_price * 1.002  # 0.2% above
                
        # Update trail price if price moves in our favor
        elif self.trail_active:
            if self.side == 'LONG' and current_price * 0.998 > self.trail_price:
                self.trail_price = current_price * 0.998
            elif self.side == 'SHORT' and current_price * 1.002 < self.trail_price:
                self.trail_price = current_price * 1.002

class BacktestEngine:
    def __init__(self, account_size=100_000):
        self.account = Account(balance=account_size)
        self.trades_log = []
        self.equity_curve = []
        self.current_equity = account_size
        
    def run(self, df, params):
        """Run backtest over the DataFrame."""
        for i in range(len(df)):
            current_bar = df.iloc[i]
            
            # Update existing positions
            self._update_positions(current_bar)
            
            # Check for new entry signals
            if len(self.account.positions) == 0:  # Only enter if no positions open
                signal = self._check_entry_signal(df, i, params)
                if signal:
                    self._execute_entry(signal, current_bar, params)
            
            # Record equity
            self.current_equity = self.account.balance
            for pos in self.account.positions.values():
                self.current_equity += pos.calculate_pnl(current_bar['close'])
            self.equity_curve.append(self.current_equity)
    
    def _update_positions(self, current_bar):
        """Update all open positions."""
        # Create a list of positions to avoid dictionary size change during iteration
        positions = list(self.account.positions.values())
        
        for pos in positions:
            # Check for exits
            if self._should_exit(pos, current_bar):
                self._execute_exit(pos, current_bar)
            else:
                # Update unrealized PnL
                pos.update_unrealized_pnl(current_bar['close'])
                
                # Check if margin top-up needed
                if pos.needs_margin_topup(current_bar['close']):
                    self._add_margin(pos)
    
    def _should_exit(self, pos, current_bar):
        """Check if position should be closed."""
        # Exit on trailing stop hit
        if pos.trail_active:
            if pos.side == 'LONG' and current_bar['close'] <= pos.trail_price:
                return True
            elif pos.side == 'SHORT' and current_bar['close'] >= pos.trail_price:
                return True
            
        # Exit on macro bias flip (with 4 candle confirmation)
        if pos.side == 'LONG' and current_bar['macro_bias'] == 'SHORT':
            return True
        if pos.side == 'SHORT' and current_bar['macro_bias'] == 'LONG':
            return True
            
        return False
    
    def _execute_exit(self, pos, current_bar):
        """Close a position and log the trade."""
        exit_price = current_bar['close']
        pnl = pos.calculate_pnl(exit_price)
        
        # Calculate metrics
        hold_time = (current_bar.name - pos.entry_time).total_seconds() / 60
        pnl_pct = (pnl / pos.margin) * 100
        
        # Log the trade
        self.trades_log.append({
            'symbol': pos.symbol,
            'side': pos.side,
            'entry_price': pos.entry_price,
            'exit_price': exit_price,
            'size': pos.size,
            'initial_margin': pos.margin,
            'final_margin': pos.margin + (pos.topups_used * pos.size * 0.25),
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'hold_time_minutes': hold_time,
            'margin_topups': pos.topups_used,
            'funding_paid': pos.funding_paid,
            'exit_reason': 'trail_stop' if pos.trail_active else 'bias_flip',
            'entry_time': pos.entry_time,
            'exit_time': current_bar.name
        })
        
        # Update account
        self.account.balance += pnl
        self.account.positions.pop(pos.symbol)
        self.account.margin_used -= pos.margin
        
        # Log trade details
        logger.info(f"Closed {pos.side} position on {pos.symbol}:")
        logger.info(f"  Entry: ${pos.entry_price:.2f}, Exit: ${exit_price:.2f}")
        logger.info(f"  PnL: ${pnl:.2f} ({pnl_pct:.1f}%)")
        logger.info(f"  Hold Time: {hold_time:.1f} minutes")
        logger.info(f"  Margin Top-ups: {pos.topups_used}")
    
    def _check_entry_signal(self, df, i, params):
        """Check for entry signals."""
        current = df.iloc[i]
        
        # Basic checks
        if current['macro_bias'] not in ['LONG', 'SHORT']:
            return None
        if current['bias_confidence'] < params['min_bias_confidence']:
            return None
            
        # Channel touch - less strict
        if abs(current['reg_channel_distance']) > 0.005:  # 0.5% from channel
            return None
            
        # S/R zone - less strict
        if current['sr_zone_distance'] > 0.01:  # 1% from S/R
            return None
            
        # Generate signal
        return {
            'symbol': current['symbol'],
            'side': current['macro_bias'],
            'entry_price': current['close'],
            'timestamp': current.name
        }
    
    def _execute_entry(self, signal, current_bar, params):
        """Execute an entry signal."""
        # Calculate position size
        position_size = self.account.balance * params['position_size_pct']
        
        # Create position
        position = Position(
            symbol=signal['symbol'],
            side=signal['side'],
            entry_price=signal['entry_price'],
            size=position_size,
            leverage=params['initial_leverage'],
            entry_time=signal['timestamp']
        )
        
        # Update account
        self.account.positions[signal['symbol']] = position
        self.account.margin_used += position.margin
        
        # Log entry
        logger.info(f"Opened {position.side} position on {position.symbol}:")
        logger.info(f"  Price: ${position.entry_price:.2f}")
        logger.info(f"  Size: ${position_size:.2f}")
        logger.info(f"  Leverage: {position.leverage}x")
    
    def _add_margin(self, pos):
        """Add margin to a position that's approaching liquidation."""
        margin_topup = pos.size * 0.25  # Add 25% of position size
        
        if self.account.can_add_margin(margin_topup):
            pos.add_margin(margin_topup)
            self.account.margin_used += margin_topup
            self.account.balance -= margin_topup  # Deduct from available balance
            
            logger.info(f"Added {margin_topup:.2f} margin to {pos.symbol} position. New leverage: {pos.leverage:.2f}x")
    
    def get_statistics(self):
        """Calculate and return backtest statistics."""
        if not self.trades_log:
            return {}
            
        df_trades = pd.DataFrame(self.trades_log)
        df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
        
        # Weekly and monthly aggregations
        weekly_pnl = df_trades.set_index('entry_time').resample('W')['pnl'].sum()
        monthly_pnl = df_trades.set_index('entry_time').resample('M')['pnl'].sum()
        
        return {
            'total_trades': len(df_trades),
            'profitable_trades': len(df_trades[df_trades['pnl'] > 0]),
            'total_pnl': df_trades['pnl'].sum(),
            'max_drawdown': self._calculate_max_drawdown(),
            'avg_trade_duration': (df_trades['exit_time'] - df_trades['entry_time']).mean(),
            'total_funding_paid': df_trades['funding_paid'].sum(),
            'trades_needing_topup': len(df_trades[df_trades['margin_topups'] > 0]),
            'weekly_pnl': weekly_pnl.to_dict(),
            'monthly_pnl': monthly_pnl.to_dict()
        }
        
    def _calculate_max_drawdown(self):
        """Calculate maximum drawdown from equity curve."""
        peak = self.equity_curve[0]
        max_dd = 0
        
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
            
        return max_dd 