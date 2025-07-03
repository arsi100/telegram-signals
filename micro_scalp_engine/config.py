"""
Configuration settings for the micro-scalp engine.
"""

COIN_CONFIGS = {
    'SOLUSDT': {
        'min_volume_usdt': 100000,  # Minimum 5-minute volume in USDT
        'volatility_threshold': 0.002,  # Minimum price change required (0.2%)
        'max_position_size': 100000,  # Maximum position size in USDT
        'max_daily_trades': 12,  # Maximum trades per day
        'funding_rate_threshold': 0.001  # Maximum acceptable funding rate
    },
    'BTCUSDT': {
        'min_volume_usdt': 500000,
        'volatility_threshold': 0.001,
        'max_position_size': 200000,
        'max_daily_trades': 10,
        'funding_rate_threshold': 0.001
    },
    'ETHUSDT': {
        'min_volume_usdt': 300000,
        'volatility_threshold': 0.0015,
        'max_position_size': 150000,
        'max_daily_trades': 10,
        'funding_rate_threshold': 0.001
    }
}

def get_coin_config(symbol: str) -> dict:
    """Get configuration for a specific coin."""
    if symbol not in COIN_CONFIGS:
        raise ValueError(f"No configuration found for {symbol}")
    return COIN_CONFIGS[symbol] 