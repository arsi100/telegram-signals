"""exploratory_analysis.py

Phase-0 data-mining script.

Run:
    python analysis/exploratory_analysis.py \
        --trades backtest_trades_log.csv \
        --candle_dir ./candle_cache 

Outputs:
    • analysis/trade_correlations.png – grid of heat-maps / scatter plots
    • analysis/sweet_spots.txt        – JSON-style dict of candidate parameter ranges

Prereqs:
    pip install pandas matplotlib seaborn numpy
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

plt.style.use("seaborn-v0_8-darkgrid")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_and_prepare_data(symbol):
    """Load and prepare data from CSV."""
    df = pd.read_csv(f"candle_cache/{symbol}_data.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    return df

def analyze_price_action(df, start_time, end_time):
    """Analyze price action during a specific time period."""
    mask = (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)
    period_data = df[mask].copy()
    
    if period_data.empty:
        print("No data found for the specified time period")
        return
    
    # Calculate key metrics
    start_price = period_data['open'].iloc[0]
    end_price = period_data['close'].iloc[-1]
    high = period_data['high'].max()
    low = period_data['low'].min()
    price_change = ((end_price - start_price) / start_price) * 100
    
    print("\nPrice Action Analysis:")
    print(f"Start Price: {start_price:.3f}")
    print(f"End Price: {end_price:.3f}")
    print(f"High: {high:.3f}")
    print(f"Low: {low:.3f}")
    print(f"Price Change: {price_change:.2f}%")
    
    # Calculate volatility
    period_data['returns'] = period_data['close'].pct_change()
    volatility = period_data['returns'].std() * np.sqrt(len(period_data)) * 100
    print(f"Period Volatility: {volatility:.2f}%")
    
    return period_data

def analyze_volume_profile(df):
    """Analyze volume profile."""
    print("\nVolume Analysis:")
    avg_volume = df['volume'].mean()
    max_volume = df['volume'].max()
    volume_std = df['volume'].std()
    
    print(f"Average Volume: {avg_volume:.2f}")
    print(f"Max Volume: {max_volume:.2f}")
    print(f"Volume Std Dev: {volume_std:.2f}")
    
    # Find high volume bars
    high_volume_threshold = avg_volume + 2 * volume_std
    high_volume_bars = df[df['volume'] > high_volume_threshold]
    
    if not high_volume_bars.empty:
        print("\nHigh Volume Bars:")
        for idx, row in high_volume_bars.iterrows():
            price_change = ((row['close'] - row['open']) / row['open']) * 100
            print(f"Time: {row['timestamp']}, Volume: {row['volume']:.2f}, Price Change: {price_change:.2f}%")

def plot_price_action(df, title="Price Action"):
    """Plot price action with volume."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot price
    ax1.plot(df['timestamp'], df['close'], label='Close Price')
    ax1.set_title(title)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Price')
    ax1.grid(True)
    ax1.legend()
    
    # Plot volume
    ax2.bar(df['timestamp'], df['volume'], alpha=0.7, label='Volume')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Volume')
    ax2.grid(True)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('analysis/trade_correlations.png')
    plt.close()

# ---------------------------------------------------------------------------
# Main analysis routine
# ---------------------------------------------------------------------------

def main():
    # Load data
    sol_df = load_and_prepare_data("SOLUSDT")
    btc_df = load_and_prepare_data("BTCUSDT")
    eth_df = load_and_prepare_data("ETHUSDT")
    
    # Define analysis period (June 29-30)
    start_time = pd.Timestamp('2025-06-29 00:00:00')
    end_time = pd.Timestamp('2025-06-30 23:59:59')
    
    print("=== SOLUSDT Analysis ===")
    sol_period = analyze_price_action(sol_df, start_time, end_time)
    if sol_period is not None:
        analyze_volume_profile(sol_period)
        plot_price_action(sol_period, "SOLUSDT Price Action (June 29-30)")
    
    # Calculate correlations
    print("\nCorrelations during the period:")
    all_data = []
    for df, symbol in [(sol_df, "SOL"), (btc_df, "BTC"), (eth_df, "ETH")]:
        period_data = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)].copy()
        if not period_data.empty:
            period_data['returns'] = period_data['close'].pct_change()
            all_data.append((symbol, period_data['returns']))
    
    if len(all_data) == 3:
        returns_df = pd.DataFrame({symbol: returns for symbol, returns in all_data})
        corr_matrix = returns_df.corr()
        print("\nReturn Correlations:")
        print(corr_matrix)
        
        # Save correlations to file
        with open('analysis/sweet_spots.txt', 'w') as f:
            f.write("Price Action Analysis Results\n")
            f.write("============================\n\n")
            f.write(f"Analysis Period: {start_time} to {end_time}\n\n")
            f.write("Return Correlations:\n")
            f.write(str(corr_matrix))
            f.write("\n\nKey Observations:\n")
            f.write("1. Look for divergences between SOL and BTC/ETH\n")
            f.write("2. High volume bars often indicate potential trend changes\n")
            f.write("3. Monitor volatility spikes for potential trading opportunities\n")

if __name__ == '__main__':
    main() 