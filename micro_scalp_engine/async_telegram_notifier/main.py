"""Async Telegram Notifier

This module connects to Google Pub/Sub, listens for trade signals, and forwards
them to a Telegram channel.

Key features:
- Fully asynchronous using python-telegram-bot
- Proper asyncio integration
- Clean shutdown handling
- Message queue management
"""

import asyncio
import json
import logging
import os
import signal
import sys
from queue import Queue
from threading import Event, Thread
import time

from dotenv import load_dotenv
from google.cloud import pubsub_v1
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import Application, ContextTypes, CallbackQueryHandler

# Path hack for importing from parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from functions.telegram_bot import _format_signal_message
from functions.chart_generator import generate_trade_chart
from functions.bybit_api import fetch_kline_data
import pandas as pd

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SUBSCRIPTION_NAME = "telegram-signal-sub"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(threadName)s - %(message)s",
    handlers=[
        logging.FileHandler("notifier.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PubSubListener:
    """Handles Pub/Sub subscription and message processing."""
    
    def __init__(self):
        """Initialize the listener with a message queue and stop event."""
        if not PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID environment variable not set")
        
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            PROJECT_ID, SUBSCRIPTION_NAME
        )
        self.message_queue = Queue()
        self.stop_event = Event()
        self.subscriber_thread = None
        self.streaming_pull_future = None

    def message_callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """Callback for handling incoming Pub/Sub messages."""
        try:
            logger.info(f"Received message {message.message_id}")
            self.message_queue.put(message)
            message.ack()
        except Exception as e:
            logger.error(f"Error in message callback: {e}")
            message.nack()

    def run_subscriber(self) -> None:
        """Run the Pub/Sub subscriber in a separate thread."""
        try:
            logger.info(f"Starting Pub/Sub listener on {self.subscription_path}")
            self.streaming_pull_future = self.subscriber.subscribe(
                self.subscription_path,
                callback=self.message_callback
            )
            self.streaming_pull_future.result()  # Block until stop_event is set
        except Exception as e:
            logger.error(f"Error in subscriber thread: {e}")
        finally:
            logger.info("Pub/Sub listener stopped")

    def start(self) -> None:
        """Start the Pub/Sub listener thread."""
        self.subscriber_thread = Thread(
            target=self.run_subscriber,
            name="PubSubListenerThread",
            daemon=True
        )
        self.subscriber_thread.start()

    def stop(self) -> None:
        """Stop the Pub/Sub listener and clean up resources."""
        logger.info("Stopping Pub/Sub listener...")
        self.stop_event.set()
        
        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()
        
        if self.subscriber_thread:
            self.subscriber_thread.join(timeout=5)
            
        self.subscriber.close()
        logger.info("Pub/Sub listener stopped")

class SignalBot:
    """Main bot class that handles Telegram and Pub/Sub integration."""
    
    def __init__(self):
        """Initialize the bot and its components."""
        if not all([BOT_TOKEN, CHAT_ID]):
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.pubsub_listener = PubSubListener()
        self.stop_event = asyncio.Event()
        self.application.add_handler(CallbackQueryHandler(self.on_callback))

    async def process_messages(self) -> None:
        """Process messages from the Pub/Sub queue and send to Telegram."""
        while not self.stop_event.is_set():
            try:
                # Non-blocking check for messages
                if not self.pubsub_listener.message_queue.empty():
                    message = self.pubsub_listener.message_queue.get_nowait()
                    payload = json.loads(message.data.decode("utf-8"))
                    formatted_text = _format_signal_message(payload)
                    
                    if formatted_text:
                        # --- generate recent 5-minute chart buffer ---
                        chart_buf = None
                        try:
                            klines = fetch_kline_data(payload.get("symbol", "SOLUSDT"), interval="5", limit=120)
                            if klines:
                                cols = ["timestamp","open","high","low","close","volume","turnover"]
                                df = pd.DataFrame(klines, columns=cols)
                                for c in cols[1:]:
                                    df[c] = pd.to_numeric(df[c])
                                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                                df.set_index("timestamp", inplace=True)
                                chart_buf = generate_trade_chart(df, payload, lookback=120)
                        except Exception as e:
                            logger.error(f"Chart generation failed: {e}")

                        # --- inline keyboard ---
                        uid = payload.get("id") or str(int(time.time()*1000))
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ EXECUTE", callback_data=f"EXECUTE:{uid}"),
                             InlineKeyboardButton("❌ SKIP", callback_data=f"SKIP:{uid}")]
                        ])

                        if chart_buf:
                            await self.application.bot.send_photo(
                                chat_id=CHAT_ID,
                                photo=chart_buf,
                                caption=formatted_text,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
                        else:
                            await self.application.bot.send_message(
                                chat_id=CHAT_ID,
                                text=formatted_text,
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
                        logger.info("Sent signal with buttons to Telegram")
                    else:
                        logger.warning(f"Ignored malformed message: {message.message_id}")
                
                await asyncio.sleep(0.1)  # Prevent busy-waiting
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)  # Back off on error

    async def start(self) -> None:
        """Start the bot and message processing."""
        try:
            # Start Pub/Sub listener
            self.pubsub_listener.start()
            
            # Start message processor
            asyncio.create_task(self.process_messages())
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot started successfully")
            
            # Wait until stop is requested
            await self.stop_event.wait()
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            self.stop_event.set()

    async def stop(self) -> None:
        """Stop the bot and clean up resources."""
        logger.info("Stopping bot...")
        self.stop_event.set()
        
        # Stop Pub/Sub listener
        self.pubsub_listener.stop()
        
        # Stop Telegram bot
        await self.application.stop()
        await self.application.shutdown()
        
        logger.info("Bot stopped")

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button presses."""
        try:
            query = update.callback_query
            await query.answer()
            data = query.data
            action, uid = data.split(":", 1)
            if action == "EXECUTE":
                await query.edit_message_reply_markup(reply_markup=None)
                if query.message.photo:
                    await query.edit_message_caption(caption=query.message.caption + "\n\n🚀 Order sent (demo mode)")
                else:
                    await query.edit_message_text(text=query.message.text + "\n\n🚀 Order sent (demo mode)")
                logger.info(f"EXECUTE pressed for {uid}")
                # TODO: integrate order placement logic here
            else:
                await query.edit_message_reply_markup(reply_markup=None)
                if query.message.photo:
                    await query.edit_message_caption(caption=query.message.caption + "\n\n⏭️ Skipped")
                else:
                    await query.edit_message_text(text=query.message.text + "\n\n⏭️ Skipped")
                logger.info(f"SKIP pressed for {uid}")
        except Exception as e:
            logger.error(f"Callback handling failed: {e}")

async def main() -> None:
    """Main function to run the bot."""
    try:
        # Create and start the bot
        bot = SignalBot()
        
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(bot.stop())
            )
        
        # Run the bot
        await bot.start()
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C 