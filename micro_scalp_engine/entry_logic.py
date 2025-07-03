"""
Core entry logic for the micro-scalping strategy.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Dict, Tuple, Optional

# --- Exhaustion & Entry Check Functions ---

def check_rsi_exhaustion(df: pd.DataFrame, rsi_period: int = 7, overbought_threshold: int = 80, oversold_threshold: int = 20) -> str:
    """
    Checks if the RSI indicates an overbought or oversold condition.

    Args:
        df: DataFrame with a 'close' column.
        rsi_period: The period to use for the RSI calculation.
        overbought_threshold: The RSI level to consider as overbought.
        oversold_threshold: The RSI level to consider as oversold.

    Returns:
        'overbought', 'oversold', or 'neutral'.
    """
    if df.empty or len(df) < rsi_period:
        return 'neutral'
    
    rsi = df.ta.rsi(length=rsi_period)
    if rsi is None or rsi.empty:
        return 'neutral'

    latest_rsi = rsi.iloc[-1]
    if latest_rsi > overbought_threshold:
        return 'overbought'
    if latest_rsi < oversold_threshold:
        return 'oversold'
    return 'neutral'

def check_low_volume(df: pd.DataFrame, volume_ema_period: int = 20, threshold_multiplier: float = 0.75) -> bool:
    """
    Checks if the volume of the last candle is significantly lower than the recent average volume.

    Args:
        df: DataFrame with a 'volume' column.
        volume_ema_period: The period for the Volume EMA.
        threshold_multiplier: The factor by which the latest volume must be below the EMA.

    Returns:
        True if volume is low, False otherwise.
    """
    if df.empty or 'volume' not in df.columns or len(df) < volume_ema_period:
        return False
        
    volume_ema = df['volume'].ewm(span=volume_ema_period, adjust=False).mean()
    latest_volume = df['volume'].iloc[-1]
    volume_threshold = volume_ema.iloc[-1] * threshold_multiplier

    return latest_volume < volume_threshold

def check_double_wick(df: pd.DataFrame, wick_percent_threshold: float = 0.60, price_proximity_threshold: float = 0.001) -> str:
    """
    Checks for a double bottom or double top pattern based on long wicks.

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close' columns.
        wick_percent_threshold: Minimum percentage of the candle range that must be wick.
        price_proximity_threshold: How close the two wick tips must be.

    Returns:
        'double_top', 'double_bottom', or 'none'.
    """
    if len(df) < 2:
        return 'none'
        
    prev_candle = df.iloc[-2]
    last_candle = df.iloc[-1]

    # Calculate ranges and wick sizes
    last_range = last_candle['high'] - last_candle['low']
    prev_range = prev_candle['high'] - prev_candle['low']
    
    if last_range == 0 or prev_range == 0:
        return 'none'

    last_upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
    last_lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
    prev_upper_wick = prev_candle['high'] - max(prev_candle['open'], prev_candle['close'])
    prev_lower_wick = min(prev_candle['open'], prev_candle['close']) - prev_candle['low']

    # Check for Double Top
    is_strong_upper_wick_last = (last_upper_wick / last_range) > wick_percent_threshold
    is_strong_upper_wick_prev = (prev_upper_wick / prev_range) > wick_percent_threshold
    are_highs_close = abs(last_candle['high'] - prev_candle['high']) / prev_candle['high'] < price_proximity_threshold

    if is_strong_upper_wick_last and is_strong_upper_wick_prev and are_highs_close:
        return 'double_top'

    # Check for Double Bottom
    is_strong_lower_wick_last = (last_lower_wick / last_range) > wick_percent_threshold
    is_strong_lower_wick_prev = (prev_lower_wick / prev_range) > wick_percent_threshold
    are_lows_close = abs(last_candle['low'] - prev_candle['low']) / prev_candle['low'] < price_proximity_threshold

    if is_strong_lower_wick_last and is_strong_lower_wick_prev and are_lows_close:
        return 'double_bottom'
        
    return 'none'

def check_order_book_flip(order_book_snapshot: dict, liquidity_shift_ratio: float = 1.5) -> str:
    """
    Analyzes an L2 order book snapshot for a significant liquidity shift.
    NOTE: This is a placeholder. A real implementation requires a stream of L2 data
    to compare before/after states. This function simulates a check on a single snapshot.

    Args:
        order_book_snapshot: A dict with 'bids' and 'asks' lists, e.g., {'bids': [[price, size], ...], 'asks': [...]}.
        liquidity_shift_ratio: How much larger one side's liquidity must be than the other.

    Returns:
        'bullish_flip' (asks flipped to bids), 'bearish_flip' (bids flipped to asks), or 'none'.
    """
    bids = order_book_snapshot.get('bids', [])
    asks = order_book_snapshot.get('asks', [])

    if not bids or not asks:
        return 'none'

    total_bid_liquidity = sum(price * size for price, size in bids)
    total_ask_liquidity = sum(price * size for price, size in asks)
    
    if total_ask_liquidity == 0 or total_bid_liquidity == 0:
        return 'none'

    # If bid liquidity suddenly dominates, it's a bullish signal
    if total_bid_liquidity / total_ask_liquidity > liquidity_shift_ratio:
        return 'bullish_flip'
        
    # If ask liquidity suddenly dominates, it's a bearish signal
    if total_ask_liquidity / total_bid_liquidity > liquidity_shift_ratio:
        return 'bearish_flip'

    return 'none'

def check_entry_conditions(
    current_bar: pd.Series,
    prev_bar: pd.Series,
    indicators: Dict,
    params: Dict
) -> Tuple[bool, str, float]:
    """
    Check if entry conditions are met.
    
    Args:
        current_bar: Current price bar
        prev_bar: Previous price bar
        indicators: Dictionary of technical indicators
        params: Strategy parameters
        
    Returns:
        Tuple of (entry_signal, direction, suggested_entry_price)
    """
    # Volume check
    volume_threshold = indicators['volume_sma'] * params['volume_factor']
    if current_bar['volume'] < volume_threshold:
        return False, "", 0.0
        
    # Volatility check
    price_change = abs(current_bar['close'] - current_bar['open']) / current_bar['open']
    if price_change < params['volatility_threshold']:
        return False, "", 0.0
        
    # Trend check
    trend_bullish = current_bar['close'] > indicators['ema']
    
    # RSI conditions
    rsi = indicators['rsi']
    prev_rsi = indicators['prev_rsi']
    
    # Long entry conditions
    if (rsi <= params['rsi_oversold'] and 
        prev_rsi > params['rsi_oversold'] and
        trend_bullish):
        return True, "long", current_bar['close']
        
    # Short entry conditions
    if (rsi >= params['rsi_overbought'] and 
        prev_rsi < params['rsi_overbought'] and
        not trend_bullish):
        return True, "short", current_bar['close']
        
    return False, "", 0.0

def calculate_position_size(
    equity: float,
    volatility: float,
    risk_per_trade: float = 0.02
) -> float:
    """
    Calculate position size based on equity and volatility.
    
    Args:
        equity: Current equity
        volatility: Current volatility (ATR or similar)
        risk_per_trade: Maximum risk per trade as decimal
        
    Returns:
        Position size in base currency
    """
    # More conservative position sizing for higher volatility
    risk_adjustment = 1.0 / (1.0 + volatility)
    position_size = equity * risk_per_trade * risk_adjustment
    
    return position_size

def check_exit_conditions(
    position: Dict,
    current_bar: pd.Series,
    indicators: Dict,
    params: Dict
) -> Tuple[bool, str, float]:
    """
    Check if exit conditions are met.
    
    Args:
        position: Current position information
        current_bar: Current price bar
        indicators: Dictionary of technical indicators
        params: Strategy parameters
        
    Returns:
        Tuple of (exit_signal, reason, suggested_exit_price)
    """
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
        tp_price = position['entry_price'] * (1 + params['tp_pct'])
        sl_price = position['entry_price'] * (1 - params['sl_pct'])
        
        if current_bar['high'] >= tp_price:
            return True, "tp", tp_price
        if current_bar['low'] <= sl_price:
            return True, "sl", sl_price
            
    else:  # short position
        tp_price = position['entry_price'] * (1 - params['tp_pct'])
        sl_price = position['entry_price'] * (1 + params['sl_pct'])
        
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
        tp_price = position['entry_price'] + (atr * params['atr_multiplier_tp'])
        sl_price = position['entry_price'] - (atr * params['atr_multiplier_sl'])
        
        if current_bar['high'] >= tp_price:
            return True, "tp", tp_price
        if current_bar['low'] <= sl_price:
            return True, "sl", sl_price
            
    else:  # short position
        tp_price = position['entry_price'] - (atr * params['atr_multiplier_tp'])
        sl_price = position['entry_price'] + (atr * params['atr_multiplier_sl'])
        
        if current_bar['low'] <= tp_price:
            return True, "tp", tp_price
        if current_bar['high'] >= sl_price:
            return True, "sl", sl_price
            
    return False, "", 0.0 