"""
Analyzes historical data to identify and analyze trading opportunities and performance metrics.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json

class OpportunityAnalyzer:
    def __init__(self, 
                 target_move: float = 0.005,    # 0.5% target move
                 taker_fee: float = 0.0006,     # 0.06% taker fee
                 funding_fee: float = 0.0001,   # 0.01% funding fee
                 initial_capital: float = 100000.0,  # $100,000
                 leverage: float = 10.0):        # 10x leverage
        """
        Initialize the analyzer with target move and fee settings.
        
        Args:
            target_move: Target price movement to identify opportunities (0.5%)
            taker_fee: Taker fee per trade (0.06%)
            funding_fee: Funding fee per 8 hours (0.01%)
            initial_capital: Initial capital for dollar-based calculations ($100,000)
            leverage: Leverage for dollar-based calculations (10x)
        """
        self.target_move = target_move
        self.taker_fee = taker_fee
        self.funding_fee = funding_fee
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position_size = initial_capital * leverage
        
    def analyze_price_moves(self, df: pd.DataFrame, lookback_periods: int = 12) -> pd.DataFrame:
        """
        Analyze price movements and identify trading opportunities.
        
        Args:
            df: DataFrame with OHLCV data
            lookback_periods: Number of periods to analyze pre-move conditions
            
        Returns:
            DataFrame with detailed move analysis
        """
        moves = []
        
        # Calculate technical indicators
        df['rsi'] = self._calculate_rsi(df['close'])
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['price_volatility'] = df['close'].pct_change().rolling(window=20).std()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['above_ema'] = df['close'] > df['ema_20']
        
        # Track continuous price movement
        for i in range(lookback_periods, len(df)-120):  # Look ahead up to 10 hours
            current_bar = df.iloc[i]
            pre_move_data = df.iloc[i-lookback_periods:i]
            entry_price = current_bar['close']
            
            # Look ahead for maximum movement
            future_data = df.iloc[i+1:i+121]  # 10 hours of future data
            
            # Track maximum movement in either direction
            max_high = future_data['high'].max()
            max_low = future_data['low'].min()
            
            long_move = (max_high - entry_price) / entry_price
            short_move = (entry_price - max_low) / entry_price
            
            # If we see a significant move in either direction
            if long_move >= self.target_move or short_move >= self.target_move:
                # Determine the direction with larger movement
                if long_move > short_move:
                    direction = 'long'
                    total_move = long_move
                    # Find when target was first hit
                    for j, row in future_data.iterrows():
                        move_to_target = (row['high'] - entry_price) / entry_price
                        if move_to_target >= self.target_move:
                            time_to_target = (j - current_bar.name).total_seconds() / 60
                            # Calculate drawdown before target
                            data_to_target = df.loc[current_bar.name:j]
                            min_before_target = data_to_target['low'].min()
                            max_drawdown = (min_before_target - entry_price) / entry_price
                            break
                else:
                    direction = 'short'
                    total_move = short_move
                    # Find when target was first hit
                    for j, row in future_data.iterrows():
                        move_to_target = (entry_price - row['low']) / entry_price
                        if move_to_target >= self.target_move:
                            time_to_target = (j - current_bar.name).total_seconds() / 60
                            # Calculate drawdown before target
                            data_to_target = df.loc[current_bar.name:j]
                            max_before_target = data_to_target['high'].max()
                            max_drawdown = (entry_price - max_before_target) / entry_price
                            break
                
                # Calculate dollar profit
                trade_size = self.position_size * 0.1  # 10% of leveraged capital per trade
                base_profit = trade_size * (self.target_move - (2 * self.taker_fee))
                max_profit = trade_size * (total_move - (2 * self.taker_fee))
                
                # Record the move
                moves.append({
                    'timestamp': current_bar.name,
                    'direction': direction,
                    'entry_price': entry_price,
                    'total_move_pct': total_move,
                    'time_to_target_minutes': time_to_target,
                    'max_drawdown': max_drawdown,
                    'volume_ratio': current_bar['volume'] / current_bar['volume_sma'],
                    'rsi': current_bar['rsi'],
                    'pre_move_volatility': pre_move_data['price_volatility'].mean(),
                    'trend': 'up' if current_bar['above_ema'] else 'down',
                    'base_profit_usd': base_profit,
                    'max_profit_usd': max_profit,
                    'pre_move_pattern': self._identify_pattern(pre_move_data)
                })
                
                # Skip ahead to avoid counting the same move multiple times
                i += int(time_to_target / 5)  # Skip ahead by the time it took to reach target
        
        return pd.DataFrame(moves)
    
    def _identify_pattern(self, data: pd.DataFrame) -> str:
        """Identify common chart patterns before the move."""
        # Calculate required indicators
        highs = data['high']
        lows = data['low']
        closes = data['close']
        opens = data['open']  # Fixed: using 'open' column
        volumes = data['volume']
        
        patterns = []
        
        # Bullish patterns
        if closes.iloc[-1] > closes.iloc[-2] and \
           closes.iloc[-2] < closes.iloc[-3] and \
           lows.iloc[-2] < lows.iloc[-3] and \
           lows.iloc[-2] < lows.iloc[-1]:
            patterns.append('Hammer')
            
        if closes.iloc[-1] > opens.iloc[-1] and \
           closes.iloc[-2] < opens.iloc[-2] and \
           closes.iloc[-1] > closes.iloc[-2]:
            patterns.append('Bullish Engulfing')
            
        # Bearish patterns
        if closes.iloc[-1] < closes.iloc[-2] and \
           closes.iloc[-2] > closes.iloc[-3] and \
           highs.iloc[-2] > highs.iloc[-3] and \
           highs.iloc[-2] > highs.iloc[-1]:
            patterns.append('Shooting Star')
            
        if closes.iloc[-1] < opens.iloc[-1] and \
           closes.iloc[-2] > opens.iloc[-2] and \
           closes.iloc[-1] < closes.iloc[-2]:
            patterns.append('Bearish Engulfing')
        
        # Flag patterns
        if len(data) >= 20:
            price_trend = np.polyfit(range(len(closes[-20:])), closes[-20:], 1)[0]
            volume_trend = np.polyfit(range(len(volumes[-20:])), volumes[-20:], 1)[0]
            
            if price_trend > 0 and volume_trend < 0:
                patterns.append('Bull Flag')
            elif price_trend < 0 and volume_trend < 0:
                patterns.append('Bear Flag')
        
        return ', '.join(patterns) if patterns else 'No Clear Pattern'
    
    def analyze_performance(self, moves_df: pd.DataFrame) -> Dict:
        """
        Analyze trading performance and opportunities.
        
        Args:
            moves_df: DataFrame with identified moves
            
        Returns:
            Dictionary with comprehensive analysis results
        """
        # Basic statistics
        total_moves = len(moves_df)
        moves_per_day = total_moves / 90  # Assuming 90 days
        
        # Direction distribution
        long_moves = len(moves_df[moves_df['direction'] == 'long'])
        short_moves = len(moves_df[moves_df['direction'] == 'short'])
        
        # Profit analysis
        moves_df['date'] = pd.to_datetime(moves_df['timestamp'])
        daily_profits = moves_df.groupby(moves_df['date'].dt.date)['base_profit_usd'].sum()
        weekly_profits = moves_df.groupby(pd.Grouper(key='date', freq='W'))['base_profit_usd'].sum()
        monthly_profits = moves_df.groupby(pd.Grouper(key='date', freq='ME'))['base_profit_usd'].sum()
        
        # Pattern analysis
        pattern_stats = {}
        for pattern in moves_df['pre_move_pattern'].unique():
            pattern_moves = moves_df[moves_df['pre_move_pattern'] == pattern]
            pattern_stats[pattern] = {
                'count': len(pattern_moves),
                'avg_move': float(pattern_moves['total_move_pct'].mean()),
                'avg_time': float(pattern_moves['time_to_target_minutes'].mean()),
                'avg_drawdown': float(pattern_moves['max_drawdown'].mean())
            }
        
        # Time analysis
        moves_df['hour'] = moves_df['date'].dt.hour
        hourly_distribution = moves_df.groupby('hour').size()
        
        # Move characteristics
        avg_total_move = moves_df['total_move_pct'].mean()
        max_total_move = moves_df['total_move_pct'].max()
        avg_drawdown = moves_df['max_drawdown'].mean()
        avg_time_to_target = moves_df['time_to_target_minutes'].mean()
        
        # Profit statistics
        total_profit = moves_df['base_profit_usd'].sum()
        max_possible_profit = moves_df['max_profit_usd'].sum()
        profit_capture_ratio = total_profit / max_possible_profit if max_possible_profit != 0 else 0
        
        # Convert date indices to strings for JSON serialization
        daily_profits_dict = {str(date): float(value) for date, value in daily_profits.items()}
        weekly_profits_dict = {str(date): float(value) for date, value in weekly_profits.items()}
        monthly_profits_dict = {str(date): float(value) for date, value in monthly_profits.items()}
        
        return {
            'basic_stats': {
                'total_moves': total_moves,
                'moves_per_day': moves_per_day,
                'long_moves': long_moves,
                'short_moves': short_moves
            },
            'profit_analysis': {
                'total_profit_usd': float(total_profit),
                'max_possible_profit_usd': float(max_possible_profit),
                'profit_capture_ratio': float(profit_capture_ratio),
                'daily_profit_mean_usd': float(daily_profits.mean()),
                'daily_profit_std_usd': float(daily_profits.std()),
                'weekly_profit_mean_usd': float(weekly_profits.mean()),
                'monthly_profit_mean_usd': float(monthly_profits.mean())
            },
            'move_characteristics': {
                'avg_total_move': float(avg_total_move),
                'max_total_move': float(max_total_move),
                'avg_drawdown': float(avg_drawdown),
                'avg_time_to_target': float(avg_time_to_target)
            },
            'pattern_analysis': pattern_stats,
            'time_analysis': {
                'hourly_distribution': hourly_distribution.to_dict()
            },
            'daily_profits': daily_profits_dict,
            'weekly_profits': weekly_profits_dict,
            'monthly_profits': monthly_profits_dict
        }
    
    def generate_analysis_plots(self, moves_df: pd.DataFrame, output_dir: str):
        """Generate comprehensive analysis visualizations."""
        os.makedirs(f"{output_dir}/plots", exist_ok=True)
        
        # Plot 1: Total Move Distribution
        plt.figure(figsize=(12, 6))
        sns.histplot(data=moves_df, x='total_move_pct', hue='direction', bins=50)
        plt.axvline(x=self.target_move, color='r', linestyle='--', label='Target Move')
        plt.title('Distribution of Total Price Movements')
        plt.savefig(f"{output_dir}/plots/move_distribution.png")
        plt.close()
        
        # Plot 2: Daily Profit
        plt.figure(figsize=(15, 6))
        moves_df.set_index('date')['base_profit_usd'].resample('D').sum().plot()
        plt.title('Daily Profit (USD)')
        plt.savefig(f"{output_dir}/plots/daily_profit.png")
        plt.close()
        
        # Plot 3: Pattern Performance
        plt.figure(figsize=(15, 8))
        pattern_performance = moves_df.groupby('pre_move_pattern')['total_move_pct'].mean().sort_values(ascending=False)
        pattern_performance.plot(kind='bar')
        plt.title('Average Move Size by Pattern')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/plots/pattern_performance.png")
        plt.close()
        
        # Plot 4: Time to Target vs Total Move
        plt.figure(figsize=(12, 6))
        sns.scatterplot(data=moves_df, x='time_to_target_minutes', y='total_move_pct', hue='direction')
        plt.title('Time to Target vs Total Move')
        plt.savefig(f"{output_dir}/plots/time_vs_move.png")
        plt.close()
        
        # Plot 5: Hourly Distribution
        plt.figure(figsize=(12, 6))
        moves_df.groupby(moves_df['date'].dt.hour).size().plot(kind='bar')
        plt.title('Hourly Distribution of Moves')
        plt.savefig(f"{output_dir}/plots/hourly_distribution.png")
        plt.close()
        
        # Plot 6: Pattern Distribution Over Time
        plt.figure(figsize=(15, 8))
        pattern_counts = moves_df.groupby([moves_df['date'].dt.date, 'pre_move_pattern']).size().unstack().fillna(0)
        pattern_counts.plot(kind='area', stacked=True)
        plt.title('Pattern Distribution Over Time')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/plots/pattern_distribution.png")
        plt.close()
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

def analyze_trading_opportunities(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: str
) -> None:
    """
    Perform comprehensive analysis of trading opportunities.
    
    Args:
        symbol: Trading pair symbol
        start_date: Start date
        end_date: End date
        output_dir: Directory to save analysis results
    """
    from .backtester import fetch_historical_data
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get historical data
    df = fetch_historical_data(symbol, start_date, end_date)
    
    # Initialize analyzer
    analyzer = OpportunityAnalyzer(
        target_move=0.005,      # 0.5% target move
        taker_fee=0.0006,       # 0.06% taker fee
        funding_fee=0.0001,     # 0.01% funding fee
        initial_capital=100000,  # $100,000
        leverage=10             # 10x leverage
    )
    
    # Analyze price moves
    moves_df = analyzer.analyze_price_moves(df)
    
    # Generate performance analysis
    analysis_results = analyzer.analyze_performance(moves_df)
    
    # Generate plots
    analyzer.generate_analysis_plots(moves_df, output_dir)
    
    # Save detailed results
    moves_df.to_csv(f"{output_dir}/opportunities.csv")
    with open(f"{output_dir}/analysis_results.json", 'w') as f:
        json.dump(analysis_results, f, indent=2, default=str)
    
    # Log summary
    logging.info("\nTrading Opportunity Analysis Results:")
    logging.info(f"Total Moves: {analysis_results['basic_stats']['total_moves']}")
    logging.info(f"Moves per Day: {analysis_results['basic_stats']['moves_per_day']:.1f}")
    logging.info(f"Long/Short Distribution: {analysis_results['basic_stats']['long_moves']}/{analysis_results['basic_stats']['short_moves']}")
    logging.info("\nProfit Analysis:")
    logging.info(f"Total Profit: ${analysis_results['profit_analysis']['total_profit_usd']:,.2f}")
    logging.info(f"Max Possible Profit: ${analysis_results['profit_analysis']['max_possible_profit_usd']:,.2f}")
    logging.info(f"Average Daily Profit: ${analysis_results['profit_analysis']['daily_profit_mean_usd']:,.2f}")
    logging.info(f"Average Weekly Profit: ${analysis_results['profit_analysis']['weekly_profit_mean_usd']:,.2f}")
    logging.info(f"Average Monthly Profit: ${analysis_results['profit_analysis']['monthly_profit_mean_usd']:,.2f}")
    logging.info(f"Profit Capture Ratio: {analysis_results['profit_analysis']['profit_capture_ratio']:.2%}")
    logging.info("\nMove Characteristics:")
    logging.info(f"Average Total Move: {analysis_results['move_characteristics']['avg_total_move']:.2%}")
    logging.info(f"Maximum Total Move: {analysis_results['move_characteristics']['max_total_move']:.2%}")
    logging.info(f"Average Drawdown: {analysis_results['move_characteristics']['avg_drawdown']:.2%}")
    logging.info(f"Average Time to Target: {analysis_results['move_characteristics']['avg_time_to_target']:.1f} minutes")
    logging.info("\nPattern Analysis:")
    for pattern, stats in analysis_results['pattern_analysis'].items():
        logging.info(f"\n{pattern}:")
        logging.info(f"  Count: {stats['count']}")
        logging.info(f"  Avg Move: {stats['avg_move']:.2%}")
        logging.info(f"  Avg Time: {stats['avg_time']:.1f} minutes")
        logging.info(f"  Avg Drawdown: {stats['avg_drawdown']:.2%}") 