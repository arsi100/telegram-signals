# Trading pairs to monitor by default
# This can be overridden from Firestore config
TRACKED_COINS = [
    "BTCUSDT",  # Bitcoin
    "ETHUSDT",  # Ethereum
    "SOLUSDT",  # Solana
    "XRPUSDT",   # XRP
    "AVAXUSDT"  # Avalanche
]

# Market hours in UTC
# Format: list of (start_hour, start_minute), (end_hour, end_minute) tuples
MARKET_HOURS = [
    # 00:00–02:30
    ((0, 0), (2, 30)),
    
    # 05:30–07:00
    ((5, 30), (7, 0)),
    
    # 07:45–10:00
    ((7, 45), (10, 0)),
    
    # 20:00–23:00
    ((20, 0), (23, 0)),
    
    # 04:00–06:00 next day window
    ((4, 0), (6, 0))
]

# Technical Analysis Parameters
TA_PARAMS = {
    "rsi_period": 14,
    "sma_period": 50,
    "volume_period": 50
}

# Signal Confidence Threshold
CONFIDENCE_THRESHOLD = 80

# Profit and Loss Parameters
PROFIT_TARGET_PERCENTAGE = 3.0  # 3% profit target
STOP_LOSS_PERCENTAGE = 2.0     # 2% stop loss
AVG_DOWN_THRESHOLD = 2.0       # 2% price drop for average down
