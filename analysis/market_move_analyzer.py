import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MarketMoveAnalyzer:
    def __init__(self):
        self.pattern_stats = {
            'Hammer': {'total': 0, 'success': 0},
            'Shooting Star': {'total': 0, 'success': 0},
            'Bullish Engulfing': {'total': 0, 'success': 0},
            'Bearish Engulfing': {'total': 0, 'success': 0},
            'Bull Flag': {'total': 0, 'success': 0},
            'Bear Flag': {'total': 0, 'success': 0}
        }
        self.move_stats = {
            'total_moves': 0,
            'upward_moves': 0,
            'downward_moves': 0,
            'avg_move_size': 0.0,
            'max_move_size': 0.0,
            'avg_time_to_target': 0.0,
            'patterns_present': {}
        }
        
    def analyze_market(self, df: pd.DataFrame, target_move_percent: float = 0.5,
                      max_lookback_minutes: int = 60) -> Dict:
        """
        Comprehensive market analysis that tracks both:
        1. Pattern success rates (forward-looking)
        2. Market moves analysis (backward-looking)
        
        Args:
            df: DataFrame with OHLCV data
            target_move_percent: Target price movement percentage
            max_lookback_minutes: Maximum time to look for move completion
            
        Returns:
            Dictionary with both pattern and move statistics
        """
        if df.empty or len(df) < 3:
            logger.warning("Insufficient data for analysis")
            return {'pattern_stats': self.pattern_stats, 'move_stats': self.move_stats}
            
        # Reset stats
        self._reset_stats()
        
        # 1. Forward Analysis (Pattern Success)
        pattern_results = self._analyze_pattern_success(df, target_move_percent, max_lookback_minutes)
        
        # 2. Backward Analysis (Move Analysis)
        move_results = self._analyze_price_moves(df, target_move_percent)
        
        return {
            'pattern_stats': pattern_results,
            'move_stats': move_results
        }
        
    def _reset_stats(self):
        """Reset all statistics for new analysis."""
        for pattern in self.pattern_stats:
            self.pattern_stats[pattern] = {'total': 0, 'success': 0}
            
        self.move_stats = {
            'total_moves': 0,
            'upward_moves': 0,
            'downward_moves': 0,
            'avg_move_size': 0.0,
            'max_move_size': 0.0,
            'avg_time_to_target': 0.0,
            'patterns_present': {pattern: 0 for pattern in self.pattern_stats}
        }
        
    def _analyze_pattern_success(self, df: pd.DataFrame, target_percent: float,
                               max_lookback_minutes: int) -> Dict:
        """Analyze how often patterns lead to successful moves."""
        results = {}
        lookback_candles = int(max_lookback_minutes / 5)  # Assuming 5-min candles
        
        for i in range(2, len(df)-1):
            current_slice = df.iloc[i-2:i+1]
            patterns = self._identify_patterns(current_slice)
            
            if patterns:
                for pattern in patterns:
                    if pattern not in self.pattern_stats:
                        continue
                        
                    self.pattern_stats[pattern]['total'] += 1
                    
                    # Look forward for target move
                    future_slice = df.iloc[i+1:i+1+lookback_candles]
                    current_price = df.iloc[i]['close']
                    
                    if self._check_target_reached(pattern, current_price, future_slice, target_percent):
                        self.pattern_stats[pattern]['success'] += 1
                        
        # Calculate success rates
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
        
    def _analyze_price_moves(self, df: pd.DataFrame, target_percent: float) -> Dict:
        """Analyze all price moves meeting or exceeding the target percentage."""
        moves = []
        move_in_progress = False
        move_start_idx = 0
        move_start_price = 0
        move_direction = None
        
        for i in range(1, len(df)):
            current_price = df.iloc[i]['close']
            
            if not move_in_progress:
                # Look for new move start
                price_change_up = (current_price / df.iloc[i-1]['close'] - 1) * 100
                price_change_down = ((df.iloc[i-1]['close'] / current_price) - 1) * 100
                
                if price_change_up >= target_percent:
                    move_in_progress = True
                    move_start_idx = i-1
                    move_start_price = df.iloc[i-1]['close']
                    move_direction = 'up'
                elif price_change_down >= target_percent:
                    move_in_progress = True
                    move_start_idx = i-1
                    move_start_price = df.iloc[i-1]['close']
                    move_direction = 'down'
                    
            else:
                # Track ongoing move
                if move_direction == 'up':
                    move_size = (current_price / move_start_price - 1) * 100
                    if move_size < target_percent * 0.2:  # Changed from 0.5 to 0.2 - end move if retraced 80% of target
                        moves.append({
                            'start_idx': move_start_idx,
                            'end_idx': i-1,
                            'direction': move_direction,
                            'size': (df.iloc[i-1]['close'] / move_start_price - 1) * 100,
                            'duration': (i-1 - move_start_idx) * 5  # Duration in minutes
                        })
                        move_in_progress = False
                else:  # down move
                    move_size = (move_start_price / current_price - 1) * 100
                    if move_size < target_percent * 0.2:  # Changed from 0.5 to 0.2
                        moves.append({
                            'start_idx': move_start_idx,
                            'end_idx': i-1,
                            'direction': move_direction,
                            'size': (move_start_price / df.iloc[i-1]['close'] - 1) * 100,
                            'duration': (i-1 - move_start_idx) * 5  # Duration in minutes
                        })
                        move_in_progress = False
                        
        # Analyze moves
        if moves:
            self.move_stats['total_moves'] = len(moves)
            self.move_stats['upward_moves'] = sum(1 for m in moves if m['direction'] == 'up')
            self.move_stats['downward_moves'] = sum(1 for m in moves if m['direction'] == 'down')
            self.move_stats['avg_move_size'] = sum(m['size'] for m in moves) / len(moves)
            self.move_stats['max_move_size'] = max(m['size'] for m in moves)
            self.move_stats['avg_time_to_target'] = sum(m['duration'] for m in moves) / len(moves)
            
            # Analyze patterns present before moves
            for move in moves:
                start_idx = move['start_idx']
                if start_idx >= 2:
                    pre_move_slice = df.iloc[start_idx-2:start_idx+1]
                    patterns = self._identify_patterns(pre_move_slice)
                    for pattern in patterns:
                        if pattern in self.move_stats['patterns_present']:
                            self.move_stats['patterns_present'][pattern] += 1
                            
        return self.move_stats
        
    def _identify_patterns(self, df_slice: pd.DataFrame) -> List[str]:
        """Identify chart patterns in a 3-candle window."""
        if len(df_slice) < 3:
            return []
            
        patterns = []
        highs = df_slice['high']
        lows = df_slice['low']
        closes = df_slice['close']
        opens = df_slice['open']
        
        # Current candle
        curr_open = opens.iloc[-1]
        curr_close = closes.iloc[-1]
        curr_high = highs.iloc[-1]
        curr_low = lows.iloc[-1]
        
        # Previous candle
        prev_open = opens.iloc[-2]
        prev_close = closes.iloc[-2]
        
        # Hammer - more lenient conditions
        body = abs(curr_close - curr_open)
        lower_wick = min(curr_open, curr_close) - curr_low
        upper_wick = curr_high - max(curr_open, curr_close)
        if lower_wick > 1.5 * body and upper_wick < 0.5 * body:  # Changed from 2x to 1.5x and 0.3x to 0.5x
            patterns.append('Hammer')
            
        # Shooting Star - more lenient conditions
        if upper_wick > 1.5 * body and lower_wick < 0.5 * body:  # Changed from 2x to 1.5x and 0.3x to 0.5x
            patterns.append('Shooting Star')
            
        # Bullish Engulfing - more lenient conditions
        if (curr_close > curr_open and 
            curr_open <= prev_close and  # Changed from < to <=
            curr_close > prev_open and
            abs(curr_close - curr_open) >= abs(prev_close - prev_open) * 0.8):  # Changed from > to >= 0.8x
            patterns.append('Bullish Engulfing')
            
        # Bearish Engulfing - more lenient conditions
        if (curr_close < curr_open and 
            curr_open >= prev_close and  # Changed from > to >=
            curr_close < prev_open and
            abs(curr_close - curr_open) >= abs(prev_close - prev_open) * 0.8):  # Changed from > to >= 0.8x
            patterns.append('Bearish Engulfing')
            
        # Flag patterns - more lenient conditions
        if len(df_slice) >= 3:
            price_trend = np.polyfit(range(len(closes)), closes, 1)[0]
            volume_trend = np.polyfit(range(len(df_slice['volume'])), df_slice['volume'], 1)[0]
            
            if price_trend > 0:  # Removed volume condition for bull flag
                patterns.append('Bull Flag')
            elif price_trend < 0:  # Removed volume condition for bear flag
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