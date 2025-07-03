"""
Script to analyze trading opportunities.
"""

import logging
from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from .opportunity_analyzer import analyze_trading_opportunities

logger = logging.getLogger(__name__)

class MultiTimeframeAnalyzer:
    def __init__(self):
        self.timeframes = ['1m', '5m', '15m', '30m', '1h']
        self.min_profit_threshold = 0.004  # 0.4% minimum movement
        
    def resample_data(self, df_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample 1-minute data to higher timeframes."""
        df = df_1m.copy()
        
        # Resample rules
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        return df.resample(timeframe).agg(agg_dict).dropna()
        
    def analyze_momentum(self, df: pd.DataFrame) -> Dict:
        """Analyze momentum using multiple indicators."""
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # Volume Profile
        volume_ma = df['volume'].rolling(20).mean()
        vol_ratio = df['volume'] / volume_ma
        
        return {
            'rsi': rsi.iloc[-1],
            'macd_hist': (macd - signal).iloc[-1],
            'vol_ratio': vol_ratio.iloc[-1]
        }
        
    def analyze_price_action(self, df: pd.DataFrame) -> Dict:
        """Analyze price action patterns."""
        # Candle analysis
        body = df['close'] - df['open']
        upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
        lower_wick = df[['open', 'close']].min(axis=1) - df['low']
        
        # Trend analysis
        sma20 = df['close'].rolling(20).mean()
        sma50 = df['close'].rolling(50).mean()
        
        return {
            'body_to_range': abs(body / (df['high'] - df['low'])).iloc[-1],
            'upper_wick_ratio': (upper_wick / abs(body)).iloc[-1],
            'lower_wick_ratio': (lower_wick / abs(body)).iloc[-1],
            'trend_strength': ((df['close'] - sma20) / sma20).iloc[-1],
            'trend_direction': 1 if sma20.iloc[-1] > sma50.iloc[-1] else -1
        }
        
    def find_opportunities(self, df_1m: pd.DataFrame) -> List[Dict]:
        """Find trading opportunities using multi-timeframe analysis."""
        opportunities = []
        
        # Analyze each timeframe
        timeframe_data = {}
        for tf in self.timeframes:
            if tf == '1m':
                df = df_1m
            else:
                df = self.resample_data(df_1m, tf)
                
            timeframe_data[tf] = {
                'momentum': self.analyze_momentum(df),
                'price_action': self.analyze_price_action(df)
            }
            
        # Look for setups where:
        # 1. 1h shows strong trend
        # 2. 5m shows momentum
        # 3. 1m shows entry timing
        for i in range(len(df_1m) - 1, max(0, len(df_1m) - 1440), -1):  # Last day
            current_price = df_1m['close'].iloc[i]
            
            # Check if price movement exceeds minimum threshold in any timeframe
            max_move = 0
            for tf in self.timeframes:
                if tf == '1m':
                    continue  # Skip 1m for movement calculation
                    
                df_tf = self.resample_data(df_1m.iloc[:i+1], tf)
                if len(df_tf) < 2:
                    continue
                    
                move = abs(df_tf['close'].iloc[-1] / df_tf['close'].iloc[-2] - 1)
                max_move = max(max_move, move)
            
            if max_move < self.min_profit_threshold:
                continue
                
            # Check momentum alignment
            h1_trend = timeframe_data['1h']['price_action']['trend_direction']
            m5_momentum = timeframe_data['5m']['momentum']['macd_hist']
            m1_volume = timeframe_data['1m']['momentum']['vol_ratio']
            
            # Strong trend + momentum + volume
            if (h1_trend > 0 and m5_momentum > 0 and m1_volume > 1.5) or \
               (h1_trend < 0 and m5_momentum < 0 and m1_volume > 1.5):
                
                opportunity = {
                    'timestamp': df_1m.index[i],
                    'price': current_price,
                    'direction': 'LONG' if h1_trend > 0 else 'SHORT',
                    'confidence': min(0.98, 0.7 + 0.1 * m1_volume + 0.1 * abs(m5_momentum)),
                    'timeframe_data': timeframe_data,
                    'suggested_targets': self.calculate_targets(df_1m.iloc[:i+1], h1_trend > 0)
                }
                
                opportunities.append(opportunity)
                
        return opportunities
        
    def calculate_targets(self, df: pd.DataFrame, is_long: bool) -> Dict:
        """Calculate entry and exit targets based on price action."""
        current_price = df['close'].iloc[-1]
        
        # Find recent swing points
        window = 20
        if is_long:
            resistance = df['high'].rolling(window).max().iloc[-1]
            support = df['low'].rolling(window).min().iloc[-1]
        else:
            resistance = df['high'].rolling(window).max().iloc[-1]
            support = df['low'].rolling(window).min().iloc[-1]
            
        # Calculate targets
        price_range = resistance - support
        r_ratio = 1.5  # Risk:Reward ratio
        
        if is_long:
            stop_loss = current_price - (price_range * 0.2)  # 20% of range
            take_profit = current_price + (price_range * 0.3)  # 30% of range
        else:
            stop_loss = current_price + (price_range * 0.2)
            take_profit = current_price - (price_range * 0.3)
            
        return {
            'entry': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_activation': 0.005,  # 0.5% profit to activate trailing
            'trailing_distance': 0.003  # 0.3% trailing distance
        }

def main():
    """Run opportunity analysis for SOL."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Set up analysis parameters
    symbol = 'SOLUSDT'
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # 3 months of data
    output_dir = 'analysis_results/SOL'
    
    logging.info(f"\nAnalyzing trading opportunities for {symbol}")
    logging.info(f"Period: {start_date.date()} to {end_date.date()}")
    
    # Run analysis
    analyze_trading_opportunities(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir
    )
    
    logging.info(f"\nAnalysis results saved to {output_dir}")

if __name__ == "__main__":
    main() 