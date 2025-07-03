import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

logger = logging.getLogger(__name__)

class TradeAnalyzer:
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        
    def analyze_exit_strategies(self, df: pd.DataFrame, entry_points: List[datetime],
                              pattern_features: Dict) -> Dict:
        """Analyze different exit strategies for a given set of entry points."""
        strategies = {
            'trailing_stop': self._simulate_trailing_stop,
            'fixed_target': self._simulate_fixed_target,
            'dynamic_target': self._simulate_dynamic_target,
            'momentum_based': self._simulate_momentum_exit
        }
        
        results = {}
        for name, strategy in strategies.items():
            trades = []
            equity_curve = [self.initial_capital]
            current_capital = self.initial_capital
            
            for entry_time in entry_points:
                entry_idx = df.index.get_loc(entry_time)
                entry_price = df['close'].iloc[entry_idx]
                
                # Simulate trade with current strategy
                exit_idx, exit_price, profit_pct = strategy(df, entry_idx)
                
                # Calculate trade metrics
                duration = (df.index[exit_idx] - entry_time).total_seconds() / 60
                max_profit = df['high'].iloc[entry_idx:exit_idx+1].max() / entry_price - 1
                max_loss = df['low'].iloc[entry_idx:exit_idx+1].min() / entry_price - 1
                
                # Update capital
                profit_amount = current_capital * profit_pct
                current_capital += profit_amount
                equity_curve.append(current_capital)
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': df.index[exit_idx],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit_pct': profit_pct,
                    'profit_amount': profit_amount,
                    'duration_minutes': duration,
                    'max_profit_potential': max_profit,
                    'max_drawdown': max_loss,
                    'captured_upside_pct': profit_pct / max_profit if max_profit > 0 else 1
                })
                
            results[name] = {
                'trades': pd.DataFrame(trades),
                'equity_curve': pd.Series(equity_curve),
                'total_return': (current_capital - self.initial_capital) / self.initial_capital,
                'avg_trade_duration': np.mean([t['duration_minutes'] for t in trades]),
                'avg_profit_capture': np.mean([t['captured_upside_pct'] for t in trades])
            }
            
        return results
        
    def _simulate_trailing_stop(self, df: pd.DataFrame, entry_idx: int,
                              initial_stop=0.002, trail_pct=0.001) -> Tuple[int, float, float]:
        """Simulate trailing stop exit strategy."""
        entry_price = df['close'].iloc[entry_idx]
        highest_price = entry_price
        stop_price = entry_price * (1 - initial_stop)
        
        for i in range(entry_idx + 1, len(df)):
            current_price = df['close'].iloc[i]
            
            # Update trailing stop if price moves in our favor
            if current_price > highest_price:
                highest_price = current_price
                stop_price = highest_price * (1 - trail_pct)
                
            # Check if stop is hit
            if current_price <= stop_price:
                return i, current_price, (current_price - entry_price) / entry_price
                
            # Exit after 60 minutes if no stop hit
            if i - entry_idx >= 60:
                return i, current_price, (current_price - entry_price) / entry_price
                
        return len(df)-1, df['close'].iloc[-1], (df['close'].iloc[-1] - entry_price) / entry_price
        
    def _simulate_fixed_target(self, df: pd.DataFrame, entry_idx: int,
                             target=0.006, stop=0.002) -> Tuple[int, float, float]:
        """Simulate fixed target exit strategy."""
        entry_price = df['close'].iloc[entry_idx]
        target_price = entry_price * (1 + target)
        stop_price = entry_price * (1 - stop)
        
        for i in range(entry_idx + 1, len(df)):
            current_price = df['close'].iloc[i]
            
            if current_price >= target_price:
                return i, current_price, target
            if current_price <= stop_price:
                return i, current_price, -stop
                
            if i - entry_idx >= 60:
                return i, current_price, (current_price - entry_price) / entry_price
                
        return len(df)-1, df['close'].iloc[-1], (df['close'].iloc[-1] - entry_price) / entry_price
        
    def _simulate_dynamic_target(self, df: pd.DataFrame, entry_idx: int) -> Tuple[int, float, float]:
        """Simulate dynamic target based on volatility."""
        entry_price = df['close'].iloc[entry_idx]
        
        # Calculate ATR-based targets
        atr = self._calculate_atr(df.iloc[max(0, entry_idx-14):entry_idx])
        target_multiple = 2.0  # Adjust target based on volatility
        stop_multiple = 1.0
        
        target_price = entry_price * (1 + atr * target_multiple)
        stop_price = entry_price * (1 - atr * stop_multiple)
        
        for i in range(entry_idx + 1, len(df)):
            current_price = df['close'].iloc[i]
            
            if current_price >= target_price:
                return i, current_price, (current_price - entry_price) / entry_price
            if current_price <= stop_price:
                return i, current_price, (current_price - entry_price) / entry_price
                
            if i - entry_idx >= 60:
                return i, current_price, (current_price - entry_price) / entry_price
                
        return len(df)-1, df['close'].iloc[-1], (df['close'].iloc[-1] - entry_price) / entry_price
        
    def _simulate_momentum_exit(self, df: pd.DataFrame, entry_idx: int) -> Tuple[int, float, float]:
        """Simulate momentum-based exit strategy."""
        entry_price = df['close'].iloc[entry_idx]
        profit_threshold = 0.004  # Minimum profit to start trailing
        
        # Calculate initial momentum
        initial_momentum = self._calculate_momentum_score(df, entry_idx)
        highest_price = entry_price
        current_stop = entry_price * 0.998  # Initial 0.2% stop
        
        for i in range(entry_idx + 1, len(df)):
            current_price = df['close'].iloc[i]
            current_momentum = self._calculate_momentum_score(df, i)
            
            # If we have profit and momentum weakens, exit
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= profit_threshold:
                if current_momentum < initial_momentum * 0.5:
                    return i, current_price, profit_pct
                    
                # Update trailing stop
                if current_price > highest_price:
                    highest_price = current_price
                    current_stop = highest_price * 0.997  # 0.3% trail
                elif current_price <= current_stop:
                    return i, current_price, (current_price - entry_price) / entry_price
                    
            # Stop loss if momentum reverses strongly
            elif current_momentum < -initial_momentum:
                return i, current_price, (current_price - entry_price) / entry_price
                
            if i - entry_idx >= 60:
                return i, current_price, (current_price - entry_price) / entry_price
                
        return len(df)-1, df['close'].iloc[-1], (df['close'].iloc[-1] - entry_price) / entry_price
        
    def _calculate_atr(self, df: pd.DataFrame, period=14) -> float:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.mean()
        
    def _calculate_momentum_score(self, df: pd.DataFrame, idx: int) -> float:
        """Calculate momentum score based on price and volume."""
        if idx < 5:
            return 0
            
        price_change = df['close'].iloc[idx] / df['close'].iloc[idx-5] - 1
        volume_change = df['volume'].iloc[idx] / df['volume'].iloc[idx-5:idx].mean()
        
        return np.sign(price_change) * (abs(price_change) * 0.7 + (volume_change - 1) * 0.3)
        
    def generate_trade_report(self, results: Dict, output_dir: Path):
        """Generate detailed trade analysis reports and visualizations."""
        output_dir.mkdir(exist_ok=True)
        
        # Generate CSV reports
        for strategy, data in results.items():
            trades_df = data['trades']
            trades_df.to_csv(output_dir / f'{strategy}_trades.csv')
            
            # Calculate strategy metrics
            metrics = {
                'Total Trades': len(trades_df),
                'Win Rate': (trades_df['profit_pct'] > 0).mean(),
                'Average Profit': trades_df['profit_pct'].mean(),
                'Average Duration': trades_df['duration_minutes'].mean(),
                'Max Drawdown': trades_df['max_drawdown'].min(),
                'Profit Factor': abs(trades_df[trades_df['profit_pct'] > 0]['profit_pct'].sum() /
                                   trades_df[trades_df['profit_pct'] < 0]['profit_pct'].sum()),
                'Average Upside Capture': trades_df['captured_upside_pct'].mean(),
                'Total Return': data['total_return']
            }
            
            pd.Series(metrics).to_csv(output_dir / f'{strategy}_metrics.csv')
            
            # Create equity curve plot
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=data['equity_curve'],
                name='Equity Curve',
                line=dict(color='blue')
            ))
            
            fig.update_layout(
                title=f'{strategy} Equity Curve',
                xaxis_title='Trade Number',
                yaxis_title='Account Value'
            )
            
            fig.write_html(output_dir / f'{strategy}_equity_curve.html')
            
            # Create trade duration vs profit scatter plot
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trades_df['duration_minutes'],
                y=trades_df['profit_pct'],
                mode='markers',
                name='Trades'
            ))
            
            fig.update_layout(
                title=f'{strategy} Trade Duration vs Profit',
                xaxis_title='Duration (minutes)',
                yaxis_title='Profit %'
            )
            
            fig.write_html(output_dir / f'{strategy}_duration_profit.html')
            
        # Create strategy comparison plot
        fig = make_subplots(rows=2, cols=2,
                           subplot_titles=['Equity Curves', 'Win Rates',
                                         'Average Profits', 'Upside Capture'])
        
        for i, (strategy, data) in enumerate(results.items()):
            # Equity curves
            fig.add_trace(
                go.Scatter(y=data['equity_curve'], name=strategy),
                row=1, col=1
            )
            
            # Win rates
            fig.add_trace(
                go.Bar(x=[strategy],
                      y=[(data['trades']['profit_pct'] > 0).mean()],
                      name=strategy),
                row=1, col=2
            )
            
            # Average profits
            fig.add_trace(
                go.Bar(x=[strategy],
                      y=[data['trades']['profit_pct'].mean()],
                      name=strategy),
                row=2, col=1
            )
            
            # Upside capture
            fig.add_trace(
                go.Bar(x=[strategy],
                      y=[data['trades']['captured_upside_pct'].mean()],
                      name=strategy),
                row=2, col=2
            )
            
        fig.update_layout(height=800, title_text="Strategy Comparison")
        fig.write_html(output_dir / 'strategy_comparison.html')
        
        # Generate summary report
        summary = []
        summary.append("=== Trade Analysis Summary ===\n")
        
        for strategy, data in results.items():
            trades_df = data['trades']
            
            summary.append(f"\n{strategy} Strategy:")
            summary.append(f"Total Trades: {len(trades_df)}")
            summary.append(f"Win Rate: {(trades_df['profit_pct'] > 0).mean():.1%}")
            summary.append(f"Average Profit: {trades_df['profit_pct'].mean():.2%}")
            summary.append(f"Average Duration: {trades_df['duration_minutes'].mean():.1f} minutes")
            summary.append(f"Profit Factor: {metrics['Profit Factor']:.2f}")
            summary.append(f"Average Upside Capture: {trades_df['captured_upside_pct'].mean():.1%}")
            summary.append(f"Total Return: {data['total_return']:.2%}")
            
            # Distribution of trade durations
            duration_bins = pd.cut(trades_df['duration_minutes'],
                                 bins=[0, 5, 15, 30, 60],
                                 labels=['0-5m', '5-15m', '15-30m', '30-60m'])
            duration_dist = duration_bins.value_counts()
            
            summary.append("\nTrade Duration Distribution:")
            for duration, count in duration_dist.items():
                summary.append(f"  {duration}: {count} trades")
                
            # Profit distribution
            profit_bins = pd.cut(trades_df['profit_pct'],
                               bins=[-np.inf, -0.005, 0, 0.005, 0.01, np.inf],
                               labels=['< -0.5%', '-0.5% to 0%', '0% to 0.5%',
                                     '0.5% to 1%', '> 1%'])
            profit_dist = profit_bins.value_counts()
            
            summary.append("\nProfit Distribution:")
            for profit_range, count in profit_dist.items():
                summary.append(f"  {profit_range}: {count} trades")
                
        with open(output_dir / 'trade_analysis_summary.txt', 'w') as f:
            f.write('\n'.join(summary)) 