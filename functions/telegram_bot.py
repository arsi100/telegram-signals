import os
import requests
import logging
import re # For Markdown escaping
from . import config

# Configure logging - Handled by basicConfig in technical_analysis.py or main entry point
logger = logging.getLogger(__name__)


def _format_signal_message(signal: dict) -> str:
    """
    Formats a signal dictionary into a Telegram message string.
    NOTE: Does NOT escape markdown characters.
    """
    signal_type_raw = signal.get("type", "UNKNOWN").upper()
    symbol = signal.get("symbol", "N/A")
    price = signal.get("price", 0.0)
    confidence = signal.get("confidence", 0.0)
    long_term_trend = "Bullish" # Placeholder - TODO: Integrate real trend
    pnl_percent = signal.get("pnl_percent", None) # Placeholder - TODO: Calculate in exit logic
    trailing_stop = signal.get("trailing_stop", None) # Placeholder - TODO: Calculate in avg up logic
    
    # Map BUY/SELL to LONG/SHORT for formatting consistency
    if signal_type_raw == "BUY":
        signal_type_for_format = "LONG"
    elif signal_type_raw == "SELL":
        signal_type_for_format = "SHORT"
    else:
        signal_type_for_format = signal_type_raw # EXIT, AVG_DOWN etc. or UNKNOWN

    message = f"ℹ️ Unknown Signal: {signal_type_raw} for {symbol} at ${price:,.2f}" # Default message if not LONG/SHORT/EXIT etc.

    # --- Format based on Signal Type --- 
    if signal_type_for_format == "LONG":
        stop_loss = price * (1 - 0.02) # 2% SL
        message = (
            f"📈 LONG {symbol} at ${price:,.2f}, "
            f"Confidence: {confidence:.0f}%, Target: 1-3%, "
            f"Stop Loss: ${stop_loss:,.2f} (10x leverage), "
            f"Long-term: {long_term_trend}"
        )
    elif signal_type_for_format == "SHORT":
        stop_loss = price * (1 + 0.02) # 2% SL
        message = (
            f"📉 SHORT {symbol} at ${price:,.2f}, "
            f"Confidence: {confidence:.0f}%, Target: 1-3%, "
            f"Stop Loss: ${stop_loss:,.2f} (10x leverage), "
            f"Long-term: {long_term_trend}"
        )
    elif signal_type_raw == "EXIT":
        # TODO: Determine original position type (LONG/SHORT) for message
        original_type = "" # e.g., " LONG" or " SHORT"
        pnl_str = f", Profit: {pnl_percent:.2f}%" if pnl_percent is not None else ""
        message = (
            f"🚪 EXIT{original_type} {symbol} at ${price:,.2f}{pnl_str}"
        )
    elif signal_type_raw.startswith("AVG_DOWN"):
        # position_type = "LONG" if "LONG" in signal_type_raw else "SHORT" # This logic was a bit flawed
        # Determine if original position was LONG or SHORT based on future DB structure
        # For now, let's assume if it's AVG_DOWN it's for a LONG position
        position_type = "LONG" 
        message = (
            f"⏬ AVERAGE DOWN {position_type} {symbol} at ${price:,.2f}, "
            f"Confidence: {confidence:.0f}%"
        )
    elif signal_type_raw.startswith("AVG_UP"):
        # position_type = "LONG" if "LONG" in signal_type_raw else "SHORT"
        # For now, let's assume if it's AVG_UP it's for a LONG position
        position_type = "LONG" 
        # TODO: Calculate Trailing Stop value properly
        ts_str = f", Trailing Stop: ${trailing_stop:,.2f}" if trailing_stop is not None else ""
        message = (
            f"⏫ AVERAGE UP {position_type} {symbol} at ${price:,.2f}, "
            f"Confidence: {confidence:.0f}%{ts_str}"
        )
        
    return message


def send_telegram_message(signal: dict, parse_mode="MarkdownV2"):
    """
    Formats a signal dictionary and sends it via Telegram Bot API.
    Handles MarkdownV2 escaping.
    """
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    
    if not token or not chat_id:
        logger.warning("Telegram bot token or chat ID not found. Cannot send message.")
        return False
    
    if not signal or not isinstance(signal, dict):
         logger.error("send_telegram_message received invalid signal object.")
         return False
         
    # 1. Format the base message text
    message_text = _format_signal_message(signal)
    
    # 2. Escape for MarkdownV2 if needed
    message_to_send = message_text
    if parse_mode == "MarkdownV2":
        escape_chars = r'_[]()~`>#+-=|{}.!' # Chars Telegram requires escaping
        # Escape character needs escaping itself in the regex pattern and replacement
        try:
            # Use re.escape to handle special characters within the character set correctly
            pattern = f'([{re.escape(escape_chars)}])'
            message_to_send = re.sub(pattern, r'\\\1', message_text)
        except Exception as escape_err:
             logger.error(f"Error escaping message for MarkdownV2: {escape_err}. Sending plain text.")
             message_to_send = message_text # Send unescaped on error
             parse_mode = None # Send as plain text

    logger.info(f"Sending Telegram notification for signal type {signal.get('type')}")
    logger.debug(f"Formatted message (unescaped): {message_text}") 
    logger.debug(f"Sending message (escaped for {parse_mode or 'plain'}): {message_to_send}")
    
    # 3. Send the message
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_to_send
        }
        # Only include parse_mode if it's set (e.g., not None after escaping error)
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data.get("ok"):
            logger.info(f"Message successfully sent to Telegram chat ID {chat_id}.")
        return True
        else:
            error_desc = response_data.get('description', 'Unknown error')
            logger.error(f"Telegram API error response: {error_desc} (Payload text: {message_to_send[:100]}...)") # Log partial payload
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Error sending Telegram message: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}", exc_info=True)
        return False

# Removed startup notification function