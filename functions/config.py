import os
from dotenv import load_dotenv

# Load environment variables from .env file at the start
# This makes them available via os.getenv throughout the application
load_dotenv()

# Firebase/Google Cloud configuration
# GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT') # Old way
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
# GOOGLE_APPLICATION_CREDENTIALS is used directly by firebase_admin/google libs
# We ensure it's loaded via load_dotenv() above.
# GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") # No need to store in config var

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# API Keys for external services
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY') # Keep loading this if needed

# Trading parameters
TRACKED_COINS = [
    'PF_XBTUSD', # Example Kraken Symbol
    'PF_ETHUSD',
    # Add other Kraken perpetual symbols (check Markets endpoint)
    # 'SOLUSDT', # Bybit format
    # 'BNBUSDT',
    # 'DOGEUSDT',
    # 'XRPUSDT',
    # 'ADAUSDT',
    # 'AVAXUSDT'
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
VOLUME_PERIOD = 50

# Logging Configuration
LOG_LEVEL = "INFO" # Default logging level (e.g., DEBUG, INFO, WARNING, ERROR)

# Signal Generation Parameters
CONFIDENCE_THRESHOLD = 80 # Minimum confidence score (0-100) to generate a signal