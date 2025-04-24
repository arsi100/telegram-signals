import os
import requests
import logging
from . import config

# Set up logging
logger = logging.getLogger(__name__)

def send_telegram_message(message, parse_mode="Markdown"):
    """
    Send a message via Telegram Bot API.
    
    Args:
        message: Message text to send
        parse_mode: Parse mode for Telegram message formatting (default: Markdown)
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    
    if not token or not chat_id:
        logger.warning("Telegram bot token or chat ID not found in environment variables")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        logger.info(f"Message sent to Telegram: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def send_telegram_startup_notification():
    """
    Send a notification when the signal generator starts up.
    """
    message = """
🤖 *Crypto Trading Signal Generator*

The signal generator is now online and monitoring markets.
    
Monitored pairs: `BTC`, `ETH`, `SOL`, `BNB`, `DOGE`, `XRP`, `ADA`, `AVAX`
    
_You will receive trading signals with confidence scores when conditions are met._
    """
    
    return send_telegram_message(message)