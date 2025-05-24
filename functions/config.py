import os
from dotenv import load_dotenv
import logging

# Setup logger for this module if needed for the info message
logger = logging.getLogger(__name__)

# Load environment variables from .env file at the start
# This makes them available via os.getenv throughout the application
load_dotenv()

# Firebase/Google Cloud configuration
# Use GOOGLE_CLOUD_PROJECT which is standard in GCP environments
FIREBASE_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") 
# If FIREBASE_PROJECT_ID is None here (e.g. local testing without this env var set),
# firebase_admin.initialize_app() will try to auto-discover it. For explicit use:
if FIREBASE_PROJECT_ID is None:
    # Fallback for local or if GOOGLE_CLOUD_PROJECT isn't set for some reason
    # You might want to set a default or raise an error if it's critical elsewhere
    logger.info("GOOGLE_CLOUD_PROJECT not set, relying on Firebase Admin SDK auto-discovery or pre-set FIREBASE_PROJECT_ID env var.")
    # Attempt to get it if specifically set via .env for local use as FIREBASE_PROJECT_ID
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# GOOGLE_APPLICATION_CREDENTIALS is used directly by firebase_admin/google libs
# We ensure it's loaded via load_dotenv() above.

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# API Keys for external services
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
LUNARCRUSH_API_KEY = os.getenv('LUNARCRUSH_API_KEY')
CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY') # Keep loading this if needed

# Trading parameters
TRACKED_COINS = [
    'PF_XBTUSD', 
    'PF_ETHUSD',
    'PF_XRPUSD',
    'PF_SOLUSD',
    'PF_ADAUSD',
    'PF_DOGEUSD',
    'PF_BNBUSD',  # Verify availability on Kraken Futures
    'PF_PEPEUSD', # Verify availability on Kraken Futures
    'PF_TRXUSD',
    'PF_LINKUSD',
    'PF_LTCUSD'
]

# Coin symbol mapping for LunarCrush API
LUNARCRUSH_SYMBOL_MAP = {
    'PF_XBTUSD': 'bitcoin',
    'PF_ETHUSD': 'ethereum',
    'PF_XRPUSD': 'ripple',
    'PF_SOLUSD': 'solana',
    'PF_ADAUSD': 'cardano',
    'PF_DOGEUSD': 'dogecoin',
    'PF_BNBUSD': 'binancecoin',
    'PF_PEPEUSD': 'pepe',
    'PF_TRXUSD': 'tron',
    'PF_LINKUSD': 'chainlink',
    'PF_LTCUSD': 'litecoin'
}

# Market hours configuration (UTC)
MARKET_HOURS = {
    'start_hour': 0,  # 24-hour format
    'end_hour': 23,   # Set to 23 for 24/7 monitoring
    'active_days': [0, 1, 2, 3, 4, 5, 6]  # 0 = Monday, 6 = Sunday
}

# Cooldown period in minutes
SIGNAL_COOLDOWN_MINUTES = 15

# Technical analysis parameters - Updated for Phase 1 optimization
RSI_PERIOD = 7
EMA_PERIOD = 20
SMA_PERIOD = 14
VOLUME_PERIOD = 10

# RSI Thresholds
RSI_OVERSOLD_THRESHOLD = 35
RSI_OVERBOUGHT_THRESHOLD = 65
RSI_NEUTRAL_ZONE_BUFFER = (45, 55)  # Narrowed for 5-minute charts, was 1

# Volume Analysis
VOLUME_EWMA_SHORT_PERIOD = 10  # Shortened, was implicitly part of VOLUME_PERIOD
VOLUME_EWMA_LONG_PERIOD = 20   # New, for advanced volume analysis
PRICE_RANGE_EWMA_PERIOD = 10   # New, for advanced volume analysis
VOLUME_TIER_THRESHOLDS = {    # New structure for tiered volume
    'EXTREME': 1.5,
    'VERY_HIGH': 1.3,
    'HIGH': 1.1,
    'ELEVATED': 1.0,
    'NORMAL': 0.8,
    'LOW': 0.5,
    'VERY_LOW': 0.0
}
# VOLUME_MULTIPLIER = 1.05 # Commented out, replaced by tiered approach

# Tiered Volume Analysis for Early Entry - Commented out, replaced by VOLUME_TIER_THRESHOLDS
# VOLUME_EARLY_ENTRY = 1.05
# VOLUME_NORMAL_ENTRY = 1.2
# VOLUME_HIGH_ENTRY = 1.5

# Volume Scoring Weights - Commented out, volume confidence handled differently now
# VOLUME_EARLY_WEIGHT = 0.8
# VOLUME_NORMAL_WEIGHT = 1.0
# VOLUME_HIGH_WEIGHT = 1.2

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Signal Generation Parameters
CONFIDENCE_THRESHOLD = 70  # Temporarily lowered from 80 to 70 for Phase 1 testing

# ATR Parameters
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
ATR_CONFIRMATION_WINDOW = 2 # Reduced, was not explicitly here but part of pattern logic
MIN_BODY_TO_ATR_RATIO = 0.2   # Reduced, was not explicitly here but part of pattern logic

# Kline Parameters
KLINE_INTERVAL = "5m"
KLINE_LIMIT = 2000

# Multi-timeframe Analysis
PRIMARY_TIMEFRAME = "5m"
SECONDARY_TIMEFRAMES = ["15m", "1h"]
MULTI_TIMEFRAME_ENABLED = True

# Candlestick Pattern Configuration
CANDLE_BODY_STRENGTH_FACTOR = 1.2
HAMMER_WICK_RATIO = 2.0
HAMMER_UPPER_WICK_MAX_RATIO = 0.3
SHOOTING_STAR_WICK_RATIO = 2.0
SHOOTING_STAR_LOWER_WICK_MAX_RATIO = 0.3
ENGULFING_BODY_FACTOR = 1.5

# Sentiment Analysis Configuration - ENABLED with LunarCrush
SENTIMENT_ANALYSIS_ENABLED = True  # Reverted back to True
SENTIMENT_WEIGHT = 0.20  # 20% of confidence score (NEW)
SENTIMENT_SOURCES = ['lunarcrush']  # Using LunarCrush as primary source
SENTIMENT_LOOKBACK_HOURS = 24
# SENTIMENT_THRESHOLD_BULLISH = 4.0 # Commented out, replaced by new thresholds
# SENTIMENT_THRESHOLD_BEARISH = 2.0 # Commented out, replaced by new thresholds
SOCIAL_VOLUME_MULTIPLIER = 1.5

# Sentiment Thresholds (Updated based on GROK ANALYSIS)
SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN = 0.2  # Widened, was -0.05
SENTIMENT_THRESHOLD_NEUTRAL = 0.05 # Was 0.2 in one Grok section, 0.05 in final config, was 0.05 originally
NEGATIVE_SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN = -0.1  # New for SHORTs
SENTIMENT_THRESHOLD_FOR_RSI_SHORT = 0.0  # New for RSI SHORTs

# Signal Generation Parameters
PROFIT_TARGET_PERCENT = 2.0
LOSS_TARGET_PERCENT = 2.0
MAX_AVG_DOWN_COUNT = 2

# Confidence Thresholds
MIN_CONFIDENCE_ENTRY = 10 # Lowered for testing, was 5 in one Grok section, 10 in final config, was 10 previously
MIN_CONFIDENCE_EXIT = 45
MIN_CONFIDENCE_AVG = 70

# Confidence Score Weights
CONFIDENCE_WEIGHTS = { # Updated weights
    'pattern': 0.2,
    'rsi': 0.3,
    'volume': 0.4,
    'sentiment': 0.1, # Was 0.0, now has weight
    'ema': 0.0,
    'multi_timeframe': 0.0,
    'social_volume': 0.0
}