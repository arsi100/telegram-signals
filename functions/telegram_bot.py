import logging
import os
import requests

# Set up logging
logging.basicConfig(level=logging.DEBUG)
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
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            logger.error("Telegram bot token or chat ID not set in environment variables")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Failed to send Telegram message: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

def send_telegram_startup_notification():
    """
    Send a notification when the signal generator starts up.
    """
    message = (
        "🤖 *Crypto Trading Signal Bot Started* 🤖\n\n"
        "I'm now monitoring the crypto markets and will send you high-confidence trading signals during market hours.\n\n"
        "*Active Trading Pairs:*\n"
        "- BTCUSDT\n"
        "- ETHUSDT\n"
        "- SOLUSDT\n"
        "- XRPUSDT\n"
        "- AVAXUSDT\n\n"
        "*Current Market Hours (UTC):*\n"
        "- 00:00-02:30\n"
        "- 05:30-07:00\n"
        "- 07:45-10:00\n"
        "- 20:00-23:00\n"
        "- 04:00-06:00 (next day)\n\n"
        "*Signal Types:*\n"
        "- LONG: Entry signals for leveraged long positions\n"
        "- SHORT: Entry signals for leveraged short positions\n"
        "- EXIT: Signals to close positions at profit or to minimize loss\n"
        "- AVG_DOWN: Opportunities to average down existing positions"
    )
    
    return send_telegram_message(message)
