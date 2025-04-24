import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase configuration is handled via service-account.json or environment
GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT')

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# API Keys for external services
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
CRYPTOCOMPARE_API_KEY = os.environ.get('CRYPTOCOMPARE_API_KEY')

# Trading parameters
WATCHLIST = [
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'BNBUSDT',
    'DOGEUSDT',
    'XRPUSDT',
    'ADAUSDT',
    'AVAXUSDT'
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