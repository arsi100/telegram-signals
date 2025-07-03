import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load and prepare data
df = pd.read_csv('candle_cache/SOLUSDT_data.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Resample to 1h candles
hourly = df.resample('1H', on='timestamp').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
}).dropna()

# Calculate price movements
hourly['move_pct'] = (hourly['high'] - hourly['low']) / hourly['low'] * 100
hourly['up_move'] = (hourly['high'] - hourly['open']) / hourly['open'] * 100
hourly['down_move'] = (hourly['low'] - hourly['open']) / hourly['open'] * 100

# Find significant moves (>0.5% potential for 5% return on 10x leverage)
significant_moves = hourly[hourly['move_pct'] > 0.5].copy()

# Analyze the moves
analysis = {
    'total_opportunities': len(significant_moves),
    'avg_move_size': significant_moves['move_pct'].mean(),
    'max_move_size': significant_moves['move_pct'].max(),
    'min_move_size': significant_moves['move_pct'].min(),
    'opportunities_per_day': len(significant_moves) / (len(hourly) / 24),
    'best_hours': significant_moves.groupby(significant_moves.index.hour)['move_pct'].count().sort_values(ascending=False).head(),
    'avg_volume': significant_moves['volume'].mean(),
}

# Save detailed moves to CSV
significant_moves.to_csv('analysis_results/sol_opportunities.csv')

# Print analysis
print("\nSOL 1h Movement Analysis")
print("========================")
print(f"Total Opportunities: {analysis['total_opportunities']}")
print(f"Opportunities per Day: {analysis['opportunities_per_day']:.1f}")
print(f"\nMove Sizes:")
print(f"Average: {analysis['avg_move_size']:.2f}%")
print(f"Maximum: {analysis['max_move_size']:.2f}%")
print(f"Minimum: {analysis['min_move_size']:.2f}%")
print(f"\nBest Hours (UTC):")
for hour, count in analysis['best_hours'].items():
    print(f"{hour:02d}:00 - {count} opportunities")

# Save full analysis
with open('analysis_results/sol_analysis_summary.txt', 'w') as f:
    f.write("SOL Trading Opportunities Analysis\n")
    f.write("================================\n\n")
    f.write(f"Analysis Period: {hourly.index[0]} to {hourly.index[-1]}\n\n")
    f.write(f"Total Hours Analyzed: {len(hourly)}\n")
    f.write(f"Total Days: {len(hourly) / 24:.1f}\n\n")
    f.write(f"Opportunities Found: {analysis['total_opportunities']}\n")
    f.write(f"Daily Average: {analysis['opportunities_per_day']:.1f} opportunities\n\n")
    f.write("Move Characteristics:\n")
    f.write(f"- Average Size: {analysis['avg_move_size']:.2f}%\n")
    f.write(f"- Maximum Size: {analysis['max_move_size']:.2f}%\n")
    f.write(f"- Minimum Size: {analysis['min_move_size']:.2f}%\n\n")
    f.write("Best Trading Hours (UTC):\n")
    for hour, count in analysis['best_hours'].items():
        f.write(f"{hour:02d}:00 - {count} opportunities\n") 