"""
Visualization module for backtest analysis.
Creates detailed plots and charts to analyze trading performance.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json
from typing import List, Dict

def plot_equity_curve(equity_curve: list, trades_log: list, save_path: str = None):
    """
    Plot equity curve with trade entries/exits and drawdown overlay.
    """
    # Convert equity curve to DataFrame
    df = pd.DataFrame({
        'equity': equity_curve,
        'drawdown': [0] * len(equity_curve)
    })
    
    # Calculate drawdown
    peak = df['equity'].expanding().max()
    df['drawdown'] = (peak - df['equity']) / peak * 100
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add equity curve
    fig.add_trace(
        go.Scatter(y=df['equity'], name="Equity"),
        secondary_y=False
    )
    
    # Add drawdown
    fig.add_trace(
        go.Scatter(y=df['drawdown'], name="Drawdown %"),
        secondary_y=True
    )
    
    # Add trade markers
    for trade in trades_log:
        if trade['pnl'] > 0:
            marker_color = 'green'
        else:
            marker_color = 'red'
            
        # Entry point
        fig.add_trace(
            go.Scatter(
                x=[trade['entry_time']],
                y=[trade['entry_price']],
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    size=10,
                    color=marker_color
                ),
                name=f"Entry ({trade['side']})"
            ),
            secondary_y=False
        )
        
        # Exit point
        fig.add_trace(
            go.Scatter(
                x=[trade['exit_time']],
                y=[trade['exit_price']],
                mode='markers',
                marker=dict(
                    symbol='triangle-down',
                    size=10,
                    color=marker_color
                ),
                name=f"Exit ({trade['exit_reason']})"
            ),
            secondary_y=False
        )
    
    # Update layout
    fig.update_layout(
        title="Equity Curve with Drawdown",
        xaxis_title="Time",
        yaxis_title="Equity",
        yaxis2_title="Drawdown %",
        showlegend=True
    )
    
    if save_path:
        fig.write_html(save_path)
    
    return fig

def plot_trade_distribution(trades_log: List[dict], save_path: str = None) -> plt.Figure:
    """
    Plot trade duration and PnL distributions.
    """
    df = pd.DataFrame(trades_log)
    
    # Calculate trade durations
    df['duration'] = pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])
    df['duration_minutes'] = df['duration'].dt.total_seconds() / 60
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    
    # Plot trade duration distribution
    sns.histplot(data=df, x='duration_minutes', bins=20, ax=ax1)
    ax1.set_title('Trade Duration Distribution')
    ax1.set_xlabel('Duration (minutes)')
    ax1.set_ylabel('Count')
    
    # Plot PnL distribution
    sns.histplot(data=df, x='pnl', bins=20, ax=ax2)
    ax2.set_title('PnL Distribution')
    ax2.set_xlabel('PnL')
    ax2.set_ylabel('Count')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
    
    return fig

def plot_parameter_heatmap(results_list: list, param1: str, param2: str, metric: str = 'total_pnl_pct', save_path: str = None):
    """
    Create a heatmap showing how different parameter combinations affect performance.
    """
    # Extract unique parameter values
    param1_values = sorted(list(set(r['params'][param1] for r in results_list)))
    param2_values = sorted(list(set(r['params'][param2] for r in results_list)))
    
    # Create matrix for heatmap
    matrix = np.zeros((len(param1_values), len(param2_values)))
    for i, p1 in enumerate(param1_values):
        for j, p2 in enumerate(param2_values):
            matching_results = [
                r[metric] for r in results_list 
                if r['params'][param1] == p1 and r['params'][param2] == p2
            ]
            if matching_results:
                matrix[i, j] = np.mean(matching_results)
    
    # Create heatmap
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        matrix,
        xticklabels=param2_values,
        yticklabels=param1_values,
        annot=True,
        fmt='.2f',
        cmap='RdYlGn'
    )
    plt.title(f'{metric} by {param1} and {param2}')
    plt.xlabel(param2)
    plt.ylabel(param1)
    
    if save_path:
        plt.savefig(save_path)
    return plt.gcf()

def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """
    Calculate maximum drawdown from equity curve.
    
    Args:
        equity_curve: List of equity values
        
    Returns:
        Maximum drawdown as a percentage
    """
    if not equity_curve:
        return 0.0
        
    peak = equity_curve[0]
    max_drawdown = 0.0
    
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        max_drawdown = max(max_drawdown, drawdown)
    
    return max_drawdown

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from a list of returns.
    
    Args:
        returns: List of returns as percentages
        risk_free_rate: Risk-free rate (default 0.0)
        
    Returns:
        Sharpe ratio
    """
    if not returns:
        return 0.0
        
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    if len(returns) < 2:
        return 0.0
        
    std_dev = np.std(excess_returns, ddof=1)
    if std_dev == 0:
        return 0.0
        
    mean_return = np.mean(excess_returns)
    sharpe = mean_return / std_dev
    
    return sharpe

def generate_performance_report(trades_log: List[dict], equity_curve: List[float], params: dict, output_dir: str) -> str:
    """
    Generate a comprehensive performance report with visualizations.
    
    Args:
        trades_log: List of trade dictionaries
        equity_curve: List of equity values
        params: Strategy parameters
        output_dir: Directory to save report files
        
    Returns:
        Path to the generated report
    """
    if not trades_log:
        return None
        
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert trades to DataFrame
    df = pd.DataFrame(trades_log)
    
    # Plot equity curve
    equity_plot_path = os.path.join(output_dir, 'equity_curve.png')
    plot_equity_curve(equity_curve, trades_log, equity_plot_path)
    
    # Plot trade distributions
    dist_plot_path = os.path.join(output_dir, 'trade_distributions.png')
    plot_trade_distribution(trades_log, dist_plot_path)
    
    # Calculate performance metrics
    metrics = {
        'Total Trades': len(trades_log),
        'Win Rate': len([t for t in trades_log if t['pnl'] > 0]) / len(trades_log) * 100,
        'Total PnL': sum(t['pnl'] for t in trades_log),
        'Average PnL': np.mean([t['pnl'] for t in trades_log]),
        'Max Drawdown': calculate_max_drawdown(equity_curve),
        'Sharpe Ratio': calculate_sharpe_ratio([t['pnl'] for t in trades_log]),
        'Average Trade Duration': np.mean([(pd.to_datetime(t['exit_time']) - pd.to_datetime(t['entry_time'])).total_seconds() / 60 for t in trades_log])
    }
    
    # Generate report
    report_path = os.path.join(output_dir, 'report.html')
    with open(report_path, 'w') as f:
        f.write('<html><body>\n')
        f.write('<h1>Backtest Performance Report</h1>\n')
        
        # Parameters section
        f.write('<h2>Strategy Parameters</h2>\n')
        f.write('<table border="1">\n')
        for k, v in params.items():
            f.write(f'<tr><td>{k}</td><td>{v}</td></tr>\n')
        f.write('</table>\n')
        
        # Performance metrics section
        f.write('<h2>Performance Metrics</h2>\n')
        f.write('<table border="1">\n')
        for k, v in metrics.items():
            f.write(f'<tr><td>{k}</td><td>{v:.2f}</td></tr>\n')
        f.write('</table>\n')
        
        # Plots section
        f.write('<h2>Performance Charts</h2>\n')
        f.write(f'<img src="equity_curve.png" /><br/>\n')
        f.write(f'<img src="trade_distributions.png" /><br/>\n')
        
        f.write('</body></html>\n')
    
    return report_path 