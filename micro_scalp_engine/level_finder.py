import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from sklearn.linear_model import LinearRegression

def find_horizontal_levels(df: pd.DataFrame, lookback: int = 120, touch_threshold: float = 0.0025, touch_count: int = 3) -> list:
    """
    Identifies horizontal support and resistance levels based on price turning points.

    Args:
        df: DataFrame with at least 'high' and 'low' columns.
        lookback: Number of recent candles to analyze.
        touch_threshold: How close the price must be to a level to be considered a "touch" (as a percentage).
        touch_count: Minimum number of touches for a level to be considered valid.

    Returns:
        A list of dictionaries, where each dictionary represents a valid S/R level.
    """
    if df.empty or len(df) < lookback:
        return []

    data = df.tail(lookback).copy()

    # Find local minima and maxima
    local_maxima_indices = argrelextrema(data['high'].values, np.greater_equal, order=5)[0]
    local_minima_indices = argrelextrema(data['low'].values, np.less_equal, order=5)[0]
    
    potential_levels = pd.concat([data.iloc[local_maxima_indices]['high'], data.iloc[local_minima_indices]['low']]).unique()
    
    valid_levels = []
    for level in potential_levels:
        # Corrected Logic:
        # 1. Create two boolean Series first.
        high_touches = abs(data['high'] - level) / level < touch_threshold
        low_touches = abs(data['low'] - level) / level < touch_threshold
        
        # 2. Combine the boolean Series with the OR operator.
        all_touches = high_touches | low_touches
        
        # 3. Count the number of True values (the touches).
        touch_count_for_level = all_touches.sum()

        if touch_count_for_level >= touch_count:
            # Determine if it's currently acting as support or resistance
            level_type = 'support' if data['close'].iloc[-1] > level else 'resistance'
            
            # Get the timestamps of the actual touches for metadata
            touch_indices = data[all_touches].index
            
            valid_levels.append({
                "level_price": level,
                "type": level_type,
                "touches": touch_count_for_level,
                "first_touch_ts": touch_indices.min(),
                "last_touch_ts": touch_indices.max()
            })
            
    return valid_levels 

def find_diagonal_trendlines(df: pd.DataFrame, lookback_swings: int = 200, r_squared_threshold: float = 0.7) -> list:
    """
    Identifies diagonal support and resistance trend lines using linear regression on swing points.

    Args:
        df: DataFrame with at least 'high' and 'low' columns.
        lookback_swings: Number of recent swing points to consider for regression.
        r_squared_threshold: The R² value the regression must exceed to be considered a valid trend.

    Returns:
        A list containing up to two dictionaries (one support, one resistance) for valid trend lines.
    """
    if df.empty or len(df) < 50: # Need a reasonable number of candles to find swings
        return []

    data = df.copy()
    # Timestamps need to be converted to numerical type for regression
    data['timestamp_ordinal'] = pd.to_datetime(data.index).map(pd.Timestamp.toordinal)

    # Find swing highs and lows
    swing_highs = data.iloc[argrelextrema(data['high'].values, np.greater_equal, order=5)[0]]
    swing_lows = data.iloc[argrelextrema(data['low'].values, np.less_equal, order=5)[0]]

    valid_trendlines = []

    # --- Resistance Trend Line (from Swing Highs) ---
    if len(swing_highs) > 2:
        recent_swing_highs = swing_highs.tail(lookback_swings)
        X = recent_swing_highs[['timestamp_ordinal']]
        y = recent_swing_highs['high']
        
        model = LinearRegression()
        model.fit(X, y)
        r_squared = model.score(X, y)

        if r_squared >= r_squared_threshold:
            # Predict start and end points for the trendline
            start_x = data['timestamp_ordinal'].iloc[0]
            end_x = data['timestamp_ordinal'].iloc[-1]
            start_y = model.predict([[start_x]])[0]
            end_y = model.predict([[end_x]])[0]
            
            valid_trendlines.append({
                "type": "resistance",
                "r_squared": r_squared,
                "start_price": start_y,
                "end_price": end_y,
                "slope": model.coef_[0]
            })

    # --- Support Trend Line (from Swing Lows) ---
    if len(swing_lows) > 2:
        recent_swing_lows = swing_lows.tail(lookback_swings)
        X = recent_swing_lows[['timestamp_ordinal']]
        y = recent_swing_lows['low']
        
        model = LinearRegression()
        model.fit(X, y)
        r_squared = model.score(X, y)

        if r_squared >= r_squared_threshold:
            start_x = data['timestamp_ordinal'].iloc[0]
            end_x = data['timestamp_ordinal'].iloc[-1]
            start_y = model.predict([[start_x]])[0]
            end_y = model.predict([[end_x]])[0]

            valid_trendlines.append({
                "type": "support",
                "r_squared": r_squared,
                "start_price": start_y,
                "end_price": end_y,
                "slope": model.coef_[0]
            })
            
    return valid_trendlines 