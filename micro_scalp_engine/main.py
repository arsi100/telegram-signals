"""Async Telegram Notifier

This module connects to Google Pub/Sub, listens for trade signals, and forwards
them to a Telegram channel.

Key features:
- Fully asynchronous using python-telegram-bot v21.
- Direct asyncio integration for sending messages.
- Formats messages using HTML for a polished look.
- Handles graceful shutdown of Pub/Sub connections.
- Redis integration for editing messages on EXIT signals.
- On-demand chart generation.
"""

# --- asyncio Patch for environments like notebooks ---
import nest_asyncio
nest_asyncio.apply()
# --- End Patch ---

import asyncio
import json
import logging
import os
import threading
import redis
from datetime import datetime, timedelta
from google.cloud.bigtable import Client as BigTableClient
from google.cloud import pubsub_v1
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackContext, CommandHandler, CallbackQueryHandler

# --- Path Hack to find the `functions` module ---
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from functions.telegram_bot import _format_signal_message
from functions.chart_generator import generate_trade_chart
# --- End Path Hack ---

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SIGNAL_SUB_NAME = os.getenv("TELEGRAM_SIGNAL_SUB", "telegram-signal-sub")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Bigtable Config
BT_INSTANCE_ID = 'trade-signal-data'
BT_CANDLE_TABLE_ID = 'historical-candles'


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
)

# ---------------------------------------------------------------------------
# Redis & BigTable Clients
# ---------------------------------------------------------------------------
r_conn = None
try:
    r_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    r_conn.ping()
    logger.info(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}. Message editing will not work.")
    r_conn = None

bt_candle_table = None
try:
    bt_client = BigTableClient(project=PROJECT_ID)
    bt_instance = bt_client.instance(BT_INSTANCE_ID)
    bt_candle_table = bt_instance.table(BT_CANDLE_TABLE_ID)
    logger.info(f"Successfully connected to Bigtable instance '{BT_INSTANCE_ID}'")
except Exception as e:
    logger.error(f"Could not connect to BigTable: {e}. Chart generation will not work.")
    bt_candle_table = None


# ---------------------------------------------------------------------------
# Telegram UI Components
# ---------------------------------------------------------------------------
def get_signal_keyboard(trade_id: str) -> InlineKeyboardMarkup:
    """Creates the inline keyboard for a new trade signal message."""
    keyboard = [
        [InlineKeyboardButton("📊 Chart", callback_data=f"chart_{trade_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------------------------
# Data Fetcher
# ---------------------------------------------------------------------------
def fetch_historical_data(symbol: str, minutes_back: int = 120):
    """Fetches historical candle data from Bigtable for the given symbol."""
    if not bt_candle_table:
        logger.error("Bigtable client not available for fetching historical data.")
        return None

    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes_back)

        start_key = f"{symbol}#{int(start_time.timestamp())}"
        end_key = f"{symbol}#{int(end_time.timestamp())}"

        rows = bt_candle_table.read_rows(start_key=start_key.encode(), end_key=end_key.encode())

        data = []
        for row in rows:
            # Reconstruct the candle from Bigtable columns
            candle = {
                'timestamp': int(row.row_key.decode('utf-8').split('#')[1])
            }
            for cf, cols in row.cells.items():
                for col, cells in cols.items():
                    candle[col.decode('utf-8')] = float(cells[0].value.decode('utf-8'))
            data.append(candle)

        logger.info(f"Fetched {len(data)} candles for {symbol} from Bigtable.")
        return sorted(data, key=lambda x: x['timestamp'])

    except Exception as e:
        logger.error(f"Error fetching data from Bigtable for {symbol}: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Pub/Sub Listener
# ---------------------------------------------------------------------------
class PubSubListener:
    def __init__(self, application: Application):
        self._subscriber = pubsub_v1.SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(PROJECT_ID, SIGNAL_SUB_NAME)
        self._future = None
        self._bot = application.bot
        self._loop = asyncio.new_event_loop()
        self._stop_event = threading.Event()

    async def _send_and_store(self, trade_id: str, signal_payload: dict, *args, **kwargs):
        """A wrapper coroutine that sends a message and stores its ID in Redis."""
        try:
            msg = await self._bot.send_message(*args, **kwargs)
            if r_conn and trade_id:
                # Store message_id and the full payload for later use (editing, charting)
                redis_key = f"trade:{trade_id}"
                redis_payload = {
                    'message_id': msg.message_id,
                    'chat_id': msg.chat.id,
                    'signal': signal_payload # Store the whole signal
                }
                r_conn.set(redis_key, json.dumps(redis_payload))
                logger.info(f"Stored message ID {msg.message_id} and payload for trade {trade_id}")
        except Exception as e:
            logger.error(f"Failed to send message or store ID for trade {trade_id}: {e}", exc_info=True)

    def _callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """Callback executed for each Pub/Sub message."""
        try:
            signal_data = json.loads(message.data.decode("utf-8"))
            message_text = _format_signal_message(signal_data)

            if not message_text:
                logger.warning(f"Could not format message from payload: {signal_data}")
                message.ack()
                return

            trade_id = signal_data.get('trade_id')
            signal_type = signal_data.get('type', 'ENTRY').upper()

            if signal_type == 'EXIT' and trade_id and r_conn:
                self._edit_existing_message(trade_id, message_text)
            else:
                reply_markup = get_signal_keyboard(trade_id) if trade_id else None
                asyncio.run_coroutine_threadsafe(
                    self._send_and_store(
                        trade_id,
                        signal_data,
                        chat_id=CHAT_ID,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    ),
                    self._loop
                )
            message.ack()

        except Exception as e:
            logger.error(f"Error processing Pub/Sub message: {e}", exc_info=True)
            message.nack()

    def _edit_existing_message(self, trade_id: str, new_text: str):
        """Edits an existing Telegram message based on trade_id."""
        try:
            redis_key = f"trade:{trade_id}"
            stored_data_str = r_conn.get(redis_key)
            if stored_data_str:
                stored_data = json.loads(stored_data_str)
                chat_id = stored_data['chat_id']
                message_id = stored_data['message_id']

                logger.info(f"Editing message for trade {trade_id}")
                asyncio.run_coroutine_threadsafe(
                    self._bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=new_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=None  # Remove buttons on exit
                    ),
                    self._loop
                )
                r_conn.delete(redis_key) # Clean up after exit
            else:
                logger.warning(f"Could not find message data for trade {trade_id} to edit.")
        except Exception as e:
            logger.error(f"Error retrieving from Redis or editing message for trade {trade_id}: {e}", exc_info=True)

    def start(self) -> None:
        """Starts the Pub/Sub listener in a separate thread."""
        thread = threading.Thread(target=self._run_subscriber)
        thread.daemon = True
        thread.start()
        logger.info("Pub/Sub listener thread started.")

    def _run_subscriber(self):
        """Runs the subscriber loop and sets the event loop for the thread."""
        asyncio.set_event_loop(self._loop)
        self._future = self._subscriber.subscribe(self._subscription_path, self._callback)
        logger.info(f"Listening for messages on {self._subscription_path}...")
        
        while not self._stop_event.is_set():
            try:
                self._future.result(timeout=1)
            except (TimeoutError, asyncio.TimeoutError):
                continue # This is expected, allows checking the stop event
            except Exception as e:
                logger.error(f"Pub/Sub listener thread has crashed: {e}", exc_info=True)
                self._future.cancel()
                break

    def shutdown(self):
        """Stops the Pub/Sub listener."""
        logger.info("Shutting down Pub/Sub listener...")
        self._stop_event.set()
        if self._future:
            self._future.cancel()
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._subscriber.close()
        logger.info("Pub/Sub listener has been shut down.")


# ---------------------------------------------------------------------------
# Telegram Bot Handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text("CryptoSignalTracker Notifier is running.")

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and generates a chart."""
    query = update.callback_query
    await query.answer("Generating chart...")

    try:
        action, trade_id = query.data.split("_", 1)
        if action == "chart":
            redis_key = f"trade:{trade_id}"
            
            signal_payload = None
            if r_conn:
                stored_data_str = r_conn.get(redis_key)
                if stored_data_str:
                    signal_payload = json.loads(stored_data_str).get('signal')

            if not signal_payload:
                await context.bot.send_message(chat_id=query.message.chat_id, text="Sorry, the original signal data has expired and a chart cannot be generated.")
                return

            symbol = signal_payload.get('symbol')
            if not symbol:
                await context.bot.send_message(chat_id=query.message.chat_id, text="Could not generate chart: Symbol not found in signal data.")
                return

            historical_data = fetch_historical_data(symbol)
            if historical_data:
                chart_file = generate_trade_chart(historical_data, title=f"{symbol} 1-Min Chart")
                with open(chart_file, 'rb') as chart:
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=chart, caption=f"Chart for {symbol}")
                os.remove(chart_file)
            else:
                await context.bot.send_message(chat_id=query.message.chat_id, text="Could not generate chart: No data available.")
    except Exception as e:
        logger.error(f"Error in button callback: {e}", exc_info=True)
        await context.bot.send_message(chat_id=query.message.chat_id, text="An error occurred while processing your request.")

# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
def main() -> None:
    """Runs the bot."""
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    listener = PubSubListener(application=application)

    async def on_startup(app: Application):
        listener.start()

    async def on_shutdown(app: Application):
        listener.shutdown()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.post_init = on_startup
    application.post_shutdown = on_shutdown

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
