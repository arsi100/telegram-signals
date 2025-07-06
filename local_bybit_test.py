import logging
import sys
from pybit.unified_trading import WebSocket
from time import sleep

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# List of symbols to subscribe to
SYMBOLS = [
    "BTCUSDT",
    "SOLUSDT",
    "ETHUSDT",
]

def handle_message(message):
    """Callback function to handle incoming WebSocket messages."""
    logger.info(f"RECEIVED MESSAGE: {message}")

def main():
    """Main function to connect to WebSocket and subscribe to topics."""
    logger.info("--- Starting Local Bybit WebSocket Test ---")
    
    # Initialize WebSocket - this is the correct way for pybit v5
    ws = WebSocket(
        testnet=False,
        channel_type="linear"
    )
    
    logger.info("WebSocket object created")
    
    # Subscribe to ticker streams for each symbol
    # This is the correct method name and usage pattern
    for symbol in SYMBOLS:
        logger.info(f"Subscribing to ticker for: {symbol}")
        ws.ticker_stream(
            symbol=symbol,
            callback=handle_message
        )
    
    logger.info("All subscription requests sent. Waiting for messages...")
    logger.info("Press Ctrl+C to stop")
    
    # Keep the script running - WebSocket runs in background threads
    try:
        while True:
            sleep(60)
            logger.info("Heartbeat - still listening...")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        ws.exit()
        logger.info("WebSocket connection closed")

if __name__ == "__main__":
    main() 