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
RSI_PERIOD = 7  # Changed from 14 to 7 for more responsive 5-minute charts
EMA_PERIOD = 20  # Changed from 50 to 20 for faster signals
VOLUME_PERIOD = 10  # Changed from 20 to 10 for more responsive volume analysis

# RSI Thresholds - Phase 1 optimization
RSI_OVERSOLD_THRESHOLD = 35  # Changed from 30 to 35 for more signals
RSI_OVERBOUGHT_THRESHOLD = 65  # Changed from 70 to 65 for more signals

# Volume Analysis - Phase 1 optimization with tiered approach
VOLUME_MULTIPLIER = 1.05  # Changed from 1.5 to 1.05 for early entry

# Tiered Volume Analysis for Early Entry
VOLUME_EARLY_ENTRY = 1.05    # 1.05x average for early trend detection
VOLUME_NORMAL_ENTRY = 1.2    # 1.2x average for standard entries  
VOLUME_HIGH_ENTRY = 1.5      # 1.5x average for late but strong entries

# Volume Scoring Weights
VOLUME_EARLY_WEIGHT = 0.8    # 80% volume score for early entries
VOLUME_NORMAL_WEIGHT = 1.0   # 100% volume score for normal entries
VOLUME_HIGH_WEIGHT = 1.2     # 120% volume score for high volume entries

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Signal Generation Parameters
CONFIDENCE_THRESHOLD = 70  # Temporarily lowered from 80 to 70 for Phase 1 testing

# ATR Parameters
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5

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
SENTIMENT_ANALYSIS_ENABLED = True
SENTIMENT_WEIGHT = 0.1  # 10% of confidence score
SENTIMENT_SOURCES = ['lunarcrush']  # Using LunarCrush as primary source
SENTIMENT_LOOKBACK_HOURS = 24
SENTIMENT_THRESHOLD_BULLISH = 4.0  # ASS > 4.0 for bullish sentiment
SENTIMENT_THRESHOLD_BEARISH = 2.0  # ASS < 2.0 for bearish sentiment
SOCIAL_VOLUME_MULTIPLIER = 1.5  # Social volume > 1.5x average for bonus points

# Signal Generation Parameters
PROFIT_TARGET_PERCENT = 2.0
LOSS_TARGET_PERCENT = 2.0
MAX_AVG_DOWN_COUNT = 2

# Confidence Thresholds
MIN_CONFIDENCE_ENTRY = 60
MIN_CONFIDENCE_EXIT = 45
MIN_CONFIDENCE_AVG = 70

# Confidence Score Weights
CONFIDENCE_WEIGHTS = {
    'pattern': 0.35,      # 35% for pattern detection
    'rsi': 0.25,          # 25% for RSI
    'volume': 0.20,       # 20% for volume analysis
    'ema': 0.10,          # 10% for EMA trend
    'multi_timeframe': 0.10,  # 10% for multi-timeframe confirmation
    'sentiment': 0.10,    # 10% for sentiment analysis
    'social_volume': 0.05  # 5% bonus for high social volume
}