import os
from dotenv import load_dotenv
import logging

# Setup logger for this module if needed for the info message
logger = logging.getLogger(__name__)

# Load environment variables from .env file at the start
# This makes them available via os.getenv throughout the application
load_dotenv()

# Define MODE first as other constants depend on it
MODE = os.getenv('MODE', 'TEST') # Ensure this is defined (TEST, SANDBOX, PRODUCTION)
logger.info(f"Configuration loaded for MODE: {MODE}")

# Environment Variable for Firebase Project ID (for local testing or explicit setting)
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "default-project-id") # Added default

# API Keys - Best practice is to use Secret Manager in GCP
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "your_kraken_api_key")
KRAKEN_PRIVATE_KEY = os.getenv("KRAKEN_PRIVATE_KEY", "your_kraken_private_key")
LUNARCRUSH_API_KEY = os.getenv("LUNARCRUSH_API_KEY", "your_lunarcrush_api_key")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_telegram_bot_token")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "your_telegram_chat_id")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # For Gemini AI integration

# Gemini Analysis Configuration
ENABLE_GEMINI_ANALYSIS = True  # Master switch for enabling/disabling Gemini calls
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # Model to use for analysis (Grok suggested gemini-pro, flash is faster/cheaper for now)
GEMINI_TEMPERATURE = 0.6 # Controls randomness (0.0-1.0)
GEMINI_KLINE_LIMIT = 50  # Number of kline candles to send to Gemini
GEMINI_CONFIDENCE_THRESHOLD_TO_OVERRIDE = 0.65 # Grok: Default override
GEMINI_FALLBACK_TO_RULES_ON_ERROR = True # If Gemini call fails, fallback to rule-based
GEMINI_MAX_TOKENS = 1000

# Sentiment Thresholds
# Grok: These are for pattern-based logic primarily. Reduced overall sentiment impact via CONFIDENCE_WEIGHTS.
SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN = 0.0  # For pattern-based SHORTs, if sentiment is <= this (Grok: tightened from 0.2)
SENTIMENT_THRESHOLD_FOR_RSI_SHORT = 0.0        # For RSI-based SHORTs, if sentiment is <= this (Grok: confirmed 0.0)
SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN = 0.2 # Min sentiment for bullish pattern if sentiment not strongly bullish
SENTIMENT_THRESHOLD_NEUTRAL = 0.05             # General neutral threshold for LONGs (e.g. RSI based)
SENTIMENT_WEIGHT = 0.25 # Max contribution from sentiment score to confidence (align with CONFIDENCE_WEIGHTS['sentiment_score'])
SOCIAL_VOLUME_MULTIPLIER = 2.0 # Placeholder, as social volume data is currently unreliable from LunarCrush v4

# Sentiment Analysis
SENTIMENT_ANALYSIS_ENABLED = True # Master switch for enabling/disabling sentiment analysis (e.g. LunarCrush calls)
USE_NEUTRAL_SENTIMENT_ON_ERROR = True  # NEW: If True, use neutral score if LunarCrush fails
NEUTRAL_SENTIMENT_SCORE_ON_ERROR = 0.0 # NEW: The neutral score to use on API error
SENTIMENT_WEIGHT_FOR_RULES = 1.0 # Factor to apply to raw sentiment score for rule-based intent checking (e.g. for threshold checks)

SENTIMENT_ADJUSTMENT_FACTORS = {
    "LONG": {"multiplier": 1.1, "cap": 1.0},  # Boost positive sentiment for LONG, cap at 1.0
    "SHORT": {"multiplier": 1.1, "cap": -1.0} # Make score more negative for SHORT if it's already negative, cap at -1.0
    # If raw sentiment is 0-1, this SHORT logic might need adjustment based on how calculate_directional_sentiment_adjustment works.
    # Current implementation of calculate_directional_sentiment_adjustment seems to handle this by applying multiplier and then cap.
}

# Volume Analysis
# Grok: Updated volume tiers as per recommendations
VOLUME_TIER_THRESHOLDS = {
    'EXTREME': 1.5,
    'VERY_HIGH': 1.2,
    'HIGH': 1.0,
    'ELEVATED': 0.8,
    'NORMAL': 0.4,
    'LOW': 0.2,
    'VERY_LOW': 0.0
}
VOLUME_EWMA_SHORT_PERIOD = 10 # For volume moving average
VOLUME_EWMA_LONG_PERIOD = 20  # Grok: For volume moving average (previously 50)
PRICE_RANGE_EWMA_PERIOD = 10  # Grok: For price range EWMA in volume analysis

# Candlestick Patterns
# Grok: Updated based on recommendations for 5-min charts
ATR_CONFIRMATION_WINDOW = 2 # Number of candles to confirm pattern (e.g. for engulfing)
MIN_BODY_TO_ATR_RATIO = 0.2 # Minimum body size relative to ATR for a candle to be significant in a pattern
FILTER_PATTERNS_BY_ATR = True # Whether to filter patterns if candle size < ATR_FILTER_THRESHOLD * ATR
ATR_FILTER_THRESHOLD = 0.5    # If candle_range / ATR < this, pattern might be weak

# Confidence Thresholds
MIN_CONFIDENCE_ENTRY = 20  # Overall confidence score required to generate a new entry signal (Grok Step 4: lowered from 30)
MIN_CONFIDENCE_EXIT = 20   # Overall confidence score required to generate an exit signal (Grok Step 4: lowered from 30)
MIN_CONFIDENCE_AVG = 30 # Minimum confidence for averaging down (Grok: should be lower than entry, e.g. 20-25, but start same as entry)

# Grok: Updated confidence weights
CONFIDENCE_WEIGHTS = {
    'pattern': 0.15,       # Weight for candlestick pattern score
    'rsi': 0.40,           # Weight for RSI score
    'volume_tier': 0.40,   # Weight for volume tier score
    'sentiment_overall_contribution': 0.05, # Weight for sentiment's direct part in the 0-1 sum before multiplying by 100
    'ema_trend': 0.00,     # Weight for EMA trend (currently not explicitly scored, set to 0)
    'multi_timeframe': 0.0, # Placeholder for future multi-timeframe analysis
    'social_volume': 0.05  # Added for potential bonus from social volume (from get_sentiment_confidence)
}

# Technical Analysis Parameters
# Grok: Updated RSI thresholds
RSI_PERIOD = 7
RSI_OVERSOLD_THRESHOLD = 25    # RSI below this is considered oversold
RSI_OVERBOUGHT_THRESHOLD = 75  # RSI above this is considered overbought
# Buffers for neutral zone, used by the original linear scaling.
# Grok's new RSI confidence logic in confidence_calculator.py directly uses RSI_OVERSOLD/OVERBOUGHT and 50.
RSI_NEUTRAL_LOWER_BUFFER = 35
RSI_NEUTRAL_UPPER_BUFFER = 65

EMA_SHORT_PERIOD = 10 # For faster trend/momentum indication
SMA_PERIOD = 14 # Simple Moving Average period
EMA_PERIOD = 20         # Primary EMA for trend
VOLUME_PERIOD = 10      # Lookback period for volume calculations if not using EWMA specific periods
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0    # Multiplier for ATR based calculations (e.g. filters, stops)

# Pattern Confirmation Parameters (Potentially for more granular TA control if TA-Lib patterns are too broad)
# These might be used if we build custom pattern logic on top of TA-Lib
CANDLE_BODY_STRENGTH_FACTOR = 1.2 # Example: body must be 1.2x the wick for strong Marubozu
HAMMER_WICK_RATIO = 2.0
HAMMER_UPPER_WICK_MAX_RATIO = 0.3
SHOOTING_STAR_WICK_RATIO = 2.0
SHOOTING_STAR_LOWER_WICK_MAX_RATIO = 0.3
ENGULFING_BODY_FACTOR = 1.1 # Engulfing body must be 1.1x the previous body

# Signal Generation & Position Management
# CONFIDENCE_THRESHOLD = 10 # Replaced by MIN_CONFIDENCE_ENTRY
SIGNAL_COOLDOWN_MINUTES = 15 # Cooldown period in minutes before generating another signal for the same coin
MAX_AVG_DOWN_COUNT = 2      # Max times to average down
PROFIT_TARGET_PERCENT = 2.0 # Target PNL for exiting a position
LOSS_TARGET_PERCENT = 1.0   # PNL threshold that might trigger averaging down (or exit if avg down fails)
AVOID_LATE_ENTRIES = False # If true, might avoid entries if a move seems too extended (e.g. based on X candles of strong trend)
LATE_ENTRY_CANDLE_THRESHOLD = 5 # Number of candles to consider for "late entry"

# Coin List
COIN_LIST_KRAKEN_FUTURES = [
    'PF_XBTUSD', 'PF_ETHUSD', 'PF_SOLUSD', 'PF_BNBUSD',
    'PF_LTCUSD', 'PF_XRPUSD', 'PF_ADAUSD', 'PF_DOGEUSD',
    'PF_TRXUSD', 'PF_LINKUSD', 'PF_PEPEUSD'
]

TRACKED_COINS = COIN_LIST_KRAKEN_FUTURES # Alias for use in main.py and tests

# Firestore Collection Names
FIRESTORE_COLLECTION_POSITIONS = f"crypto_positions_{MODE.lower()}"
FIRESTORE_COLLECTION_SIGNALS = "signalsV2"     # For overall signal history
FIRESTORE_COLLECTION_TIMESTAMPS = f"crypto_signals_cooldown_{MODE.lower()}"

# LunarCrush Symbol Mapping (if different from Kraken symbol)
LUNARCRUSH_SYMBOL_MAP = {
    "PF_XBTUSD": "bitcoin",
    "PF_ETHUSD": "ethereum",
    "PF_SOLUSD": "solana",
    "PF_BNBUSD": "binance-coin", # Check exact symbol on LunarCrush
    "PF_LTCUSD": "litecoin",
    "PF_XRPUSD": "ripple",       # Check exact symbol
    "PF_ADAUSD": "cardano",
    "PF_DOGEUSD": "dogecoin",
    "PF_TRXUSD": "tron",
    "PF_LINKUSD": "chainlink",
    "PF_PEPEUSD": "pepe"         # Check if available and symbol name
    # Add other mappings as necessary
}

# Market Hours (UTC) - Example: 24/7 for crypto
MARKET_OPEN_HOUR_UTC = 0
MARKET_OPEN_MINUTE_UTC = 0
MARKET_CLOSE_HOUR_UTC = 23
MARKET_CLOSE_MINUTE_UTC = 59
ENABLE_MARKET_HOURS_CHECK = False # Set to True to enable market hours check

# Logging Configuration
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Multi-Timeframe Analysis Configuration
MULTI_TIMEFRAME_ENABLED = False # Master switch for enabling/disabling Multi-Timeframe Analysis features
MULTI_TIMEFRAME_HIGHER_INTERVAL = '15m' # Example: 15-minute for higher timeframe trend

# Miscellaneous
USE_REAL_MONEY = False # Safety switch for any live trading integration (FUTURE)
DEFAULT_RISK_PER_TRADE = 0.01 # 1% of capital (FUTURE)

# Parameters from previous GROK ANALYSIS that are being consolidated or adjusted:
# RSI_LOWER_THRESHOLD = 30 -> RSI_OVERSOLD_THRESHOLD = 35
# RSI_UPPER_THRESHOLD = 70 -> RSI_OVERBOUGHT_THRESHOLD = 65
# RSI_NEUTRAL_LOWER = 45 -> Handled by (OVERSOLD + NEUTRAL_ZONE_BUFFER)
# RSI_NEUTRAL_UPPER = 55 -> Handled by (OVERBOUGHT - NEUTRAL_ZONE_BUFFER)
# SENTIMENT_THRESHOLD_STRONG_POSITIVE = 0.5 -> Not directly used, specific thresholds above are preferred
# SENTIMENT_THRESHOLD_POSITIVE = 0.1 -> SENTIMENT_THRESHOLD_NEUTRAL = 0.05
# SENTIMENT_THRESHOLD_NEGATIVE = -0.1 -> Covered by new SHORT thresholds
# SENTIMENT_THRESHOLD_STRONG_NEGATIVE = -0.5 -> Not directly used
# VOLUME_SPIKE_MULTIPLIER_STRONG = 2.5 -> VOLUME_TIER_THRESHOLDS['EXTREME'] = 1.5
# VOLUME_SPIKE_MULTIPLIER_MODERATE = 1.5 -> VOLUME_TIER_THRESHOLDS['HIGH'] = 1.1 / ['ELEVATED'] = 1.0
# CANDLESTICK_SCORE_STRONG = 20 -> Covered by CONFIDENCE_WEIGHTS['pattern']
# CANDLESTICK_SCORE_MODERATE = 10 -> Covered by CONFIDENCE_WEIGHTS['pattern']
# CANDLESTICK_SCORE_WEAK = 5 -> Covered by CONFIDENCE_WEIGHTS['pattern']
# MIN_VOLUME_RATIO_FOR_PATTERN = 0.8 -> Volume check is separate in signal_generator

# Old Volume Params (commented out for clarity, replaced by TIER_THRESHOLDS and EWMAs)
# VOLUME_LOOKBACK_PERIOD = 20
# MIN_VOLUME_INCREASE_FACTOR = 1.5
# MIN_PRICE_RANGE_INCREASE_FACTOR_SHORT = 1.2
# MIN_PRICE_RANGE_INCREASE_FACTOR_LONG = 1.2
# LATE_ENTRY_CANDLE_THRESHOLD_SHORT = 3
# LATE_ENTRY_CANDLE_THRESHOLD_LONG = 3
# EARLY_ENTRY_CANDLE_THRESHOLD_SHORT = 1
# EARLY_ENTRY_CANDLE_THRESHOLD_LONG = 1

# Sentiment thresholds that were iterative and are now being consolidated:
# SENTIMENT_THRESHOLD_NEGATIVE_FOR_RSI_SHORT = -0.05 -> SENTIMENT_THRESHOLD_FOR_RSI_SHORT = 0.0
# SENTIMENT_THRESHOLD_NEUTRAL_FOR_RSI_LONG = 0.05 -> SENTIMENT_THRESHOLD_NEUTRAL = 0.05

# Ensure all necessary os.getenv calls have defaults if the variable might not be set,
# especially for non-critical settings or for local development.
# API keys should ideally not have default actual keys in committed code.
# The "your_..._key" are placeholders.

logger.info(f"Config module fully loaded for MODE: {MODE}.") # Confirmation log at the end