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

# Market hours configuration (UTC)
MARKET_HOURS = {
    'start_hour': 0,  # 24-hour format
    'end_hour': 23,   # Set to 23 for 24/7 monitoring
    'active_days': [0, 1, 2, 3, 4, 5, 6]  # 0 = Monday, 6 = Sunday
}

# Cooldown period in minutes
SIGNAL_COOLDOWN_MINUTES = 15

# Technical analysis parameters
RSI_PERIOD = 14
SMA_PERIOD = 50
VOLUME_PERIOD = 20

# RSI Thresholds - Phase 1 optimization
RSI_OVERSOLD_THRESHOLD = 35
RSI_OVERBOUGHT_THRESHOLD = 65

# Volume Analysis
VOLUME_MULTIPLIER = 1.5

# Logging Configuration
LOG_LEVEL = "INFO" # Default logging level (e.g., DEBUG, INFO, WARNING, ERROR)

# Signal Generation Parameters
CONFIDENCE_THRESHOLD = 70

# New additions
KLINE_INTERVAL = "15m"  # Default interval for kline data
KLINE_LIMIT = 100         # Default limit for kline data