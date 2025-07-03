import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PatternSuccessAnalyzer:
    def __init__(self, lookback_window_minutes: int = 60):
        self.lookback_window = lookback_window_minutes
        self.pattern_stats = {
            'Hammer': {'total': 0, 'success': 0},
            'Shooting Star': {'total': 0, 'success': 0},
            'Bullish Engulfing': {'total': 0, 'success': 0},
            'Bearish Engulfing': {'total': 0, 'success': 0},
            'Bull Flag': {'total': 0, 'success': 0},
            'Bear Flag': {'total': 0, 'success': 0}
        }
        
    def analyze_pattern_success(self, df: pd.DataFrame, target_move_percent: float = 0.5) -> Dict:
        """
        Analyze success rate of patterns in leading to target price moves.
        
        Args:
            df: DataFrame with OHLCV data
            target_move_percent: Target price movement percentage (e.g., 0.5 for 0.5%)
            
        Returns:
            Dictionary with pattern statistics
        """
        if df.empty or len(df) < 3:
            logger.warning("Insufficient data for pattern analysis")
            return self.pattern_stats
            
        # Reset stats for new analysis
        for pattern in self.pattern_stats:
            self.pattern_stats[pattern] = {'total': 0, 'success': 0}
            
        # Analyze each candle for patterns
        for i in range(2, len(df)-1):  # Start at 3rd candle to have enough history
            current_slice = df.iloc[i-2:i+1]  # Get 3 candles for pattern detection
            patterns = self._identify_patterns(current_slice)
            
            if patterns:
                # For each detected pattern
                for pattern in patterns:
                    # Skip if pattern not in our tracking
                    if pattern not in self.pattern_stats:
                        continue
                        
                    self.pattern_stats[pattern]['total'] += 1
                    
                    # Get future price data within lookback window
                    future_slice = df.iloc[i+1:i+int(self.lookback_window/5)]  # Assuming 5-min candles
                    
                    # Check if target move was achieved
                    current_price = df.iloc[i]['close']
                    if self._check_target_reached(pattern, current_price, future_slice, target_move_percent):
                        self.pattern_stats[pattern]['success'] += 1
                        
        # Calculate success rates
        results = {}
        for pattern, stats in self.pattern_stats.items():
            total = stats['total']
            success = stats['success']
            success_rate = (success / total * 100) if total > 0 else 0
            results[pattern] = {
                'total_occurrences': total,
                'successful_predictions': success,
                'success_rate_percent': success_rate,
                'failure_rate_percent': 100 - success_rate
            }
            
        return results
    
    def _identify_patterns(self, df_slice: pd.DataFrame) -> List[str]:
        """Identify chart patterns in a 3-candle window."""
        if len(df_slice) < 3:
            return []
            
        patterns = []
        highs = df_slice['high']
        lows = df_slice['low']
        closes = df_slice['close']
        opens = df_slice['open']
        
        # Current candle (last in slice)
        curr_open = opens.iloc[-1]
        curr_close = closes.iloc[-1]
        curr_high = highs.iloc[-1]
        curr_low = lows.iloc[-1]
        
        # Previous candle
        prev_open = opens.iloc[-2]
        prev_close = closes.iloc[-2]
        prev_high = highs.iloc[-2]
        prev_low = lows.iloc[-2]
        
        # Hammer
        body = abs(curr_close - curr_open)
        lower_wick = min(curr_open, curr_close) - curr_low
        upper_wick = curr_high - max(curr_open, curr_close)
        if lower_wick > 2 * body and upper_wick < 0.3 * body:
            patterns.append('Hammer')
            
        # Shooting Star
        if upper_wick > 2 * body and lower_wick < 0.3 * body:
            patterns.append('Shooting Star')
            
        # Bullish Engulfing
        if curr_close > curr_open and \
           curr_open < prev_close and \
           curr_close > prev_open and \
           abs(curr_close - curr_open) > abs(prev_close - prev_open):
            patterns.append('Bullish Engulfing')
            
        # Bearish Engulfing
        if curr_close < curr_open and \
           curr_open > prev_close and \
           curr_close < prev_open and \
           abs(curr_close - curr_open) > abs(prev_close - prev_open):
            patterns.append('Bearish Engulfing')
            
        # Flag patterns (simplified)
        if len(df_slice) >= 3:
            price_trend = np.polyfit(range(len(closes)), closes, 1)[0]
            volume_trend = np.polyfit(range(len(df_slice['volume'])), df_slice['volume'], 1)[0]
            
            if price_trend > 0 and volume_trend < 0:
                patterns.append('Bull Flag')
            elif price_trend < 0 and volume_trend < 0:
                patterns.append('Bear Flag')
                
        return patterns
    
    def _check_target_reached(self, pattern: str, entry_price: float, future_data: pd.DataFrame, 
                            target_percent: float) -> bool:
        """Check if the target move was achieved within the lookback window."""
        if future_data.empty:
            return False
            
        # Calculate target prices
        upside_target = entry_price * (1 + target_percent/100)
        downside_target = entry_price * (1 - target_percent/100)
        
        # For bullish patterns
        if pattern in ['Hammer', 'Bullish Engulfing', 'Bull Flag']:
            return (future_data['high'] >= upside_target).any()
            
        # For bearish patterns
        if pattern in ['Shooting Star', 'Bearish Engulfing', 'Bear Flag']:
            return (future_data['low'] <= downside_target).any()
            
        return False 