import os
import time
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from google.cloud import bigtable
from google.cloud.bigtable.row_set import RowSet
from google.cloud import pubsub_v1
import json
import pandas_ta as ta
import mplfinance as mpf
import matplotlib
import threading # For background subscriber
import uuid # For generating unique trade IDs
import csv
from . import risk_management 
from . import order_execution
from .macro_integration import MacroIntegration

# --- Configuration ---
# Trading Configuration
SYMBOLS_TO_ANALYZE = [
    "BTCUSDT", "SOLUSDT", "ETHUSDT", "XRPUSDT", "DOGEUSDT", 
    "SEIUSDT", "LINKUSDT", "SUIUSDT", "ADAUSDT"
]
ANALYSIS_INTERVAL_SECONDS = 15 
PAPER_TRADING = False
PAPER_TRADE_LOG_FILE = "paper_trades_log.csv"

# --- V5.2 "CHAMPION" STRATEGY PARAMETERS ---
STRATEGY_CONFIG = {
    "default": {
        "rsi_period": 14, "rsi_overbought": 75, "rsi_oversold": 25,
        "volume_factor": 1.5, "tp_pct": 0.015, "sl_pct": 0.007,
    },
    "DOGEUSDT": {
        "rsi_period": 14, "rsi_overbought": 75, "rsi_oversold": 25,
        "volume_factor": 1.5, "tp_pct": 0.015, "sl_pct": 0.007,
    },
}

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variables that will be initialized in start_logic_engine
table = None
publisher = None
signal_topic_path = None
macro_integration = None

matplotlib.use("Agg")
os.makedirs("charts", exist_ok=True)

def fetch_recent_data(symbol, lookback_candles=100):
    """Fetches recent candle data from Bigtable."""
    if not table:
        logging.error("Bigtable client not available.")
        return pd.DataFrame()
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=lookback_candles)
        start_key = f"{symbol}#{int(start_time.timestamp())}".encode('utf-8')
        end_key = f"{symbol}#{int(end_time.timestamp())}".encode('utf-8')
        row_set = RowSet()
        row_set.add_row_range_from_keys(start_key, end_key)
        rows = table.read_rows(row_set=row_set)
        data = []
        for row in rows:
            record = {'timestamp': datetime.fromtimestamp(int(row.row_key.decode('utf-8').split('#')[1]), tz=timezone.utc)}
            for cf, cols in row.cells.items():
                for col, cell_list in cols.items():
                    record[col.decode('utf-8')] = float(cell_list[0].value.decode('utf-8'))
            data.append(record)
        if not data: return pd.DataFrame()
        return pd.DataFrame(data).set_index('timestamp').sort_index()
    except Exception as e:
        logging.error(f"Failed to fetch data for {symbol}: {e}")
        return pd.DataFrame()

def publish_trade_signal(signal):
    """Publishes a trade signal."""
    if not publisher:
        logging.error("Publisher not available. Cannot send signal.")
        return
    try:
        message = json.dumps(signal).encode('utf-8')
        future = publisher.publish(signal_topic_path, message)
        future.result()
        logging.critical(f"TRADE SIGNAL PUBLISHED: {signal}")
    except Exception as e:
        logging.error(f"Failed to publish trade signal: {e}")

def analyze_market_data(symbol: str):
    """Analyzes market data for a symbol and generates trade signals."""
    params = STRATEGY_CONFIG.get(symbol, STRATEGY_CONFIG['default'])
    df = fetch_recent_data(symbol, lookback_candles=100)
    if df.empty or len(df) < params["rsi_period"] + 1:
        return
    df.ta.rsi(length=params['rsi_period'], append=True)
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    rsi_col = f"RSI_{params['rsi_period']}"
    if rsi_col not in df.columns:
        return
    current_candle = df.iloc[-1]
    rsi_val = current_candle[rsi_col]
    volume_ma = current_candle['volume_ma']
    if pd.isna(rsi_val) or pd.isna(volume_ma):
        return
    is_oversold = rsi_val <= params['rsi_oversold']
    is_overbought = rsi_val >= params['rsi_overbought']
    has_volume_spike = current_candle['volume'] > (volume_ma * params['volume_factor'])
    
    log_msg = (f"[{symbol}] RSI: {rsi_val:.2f} (Oversold:{is_oversold}, Overbought:{is_overbought}) | "
               f"Vol: {current_candle['volume']:.2f} | Vol MA: {volume_ma:.2f} | Spike: {has_volume_spike}")
    logging.info(log_msg)

    side = None
    if is_oversold and has_volume_spike: side = 'LONG'
    elif is_overbought and has_volume_spike: side = 'SHORT'
    
    if side:
        # Check macro bias before proceeding
        if not macro_integration.should_allow_trade(symbol, side):
            logging.info(f"Signal for {symbol} suppressed due to macro bias.")
            return
            
        # Check for position conflicts
        size_multiplier = macro_integration.get_position_size_multiplier(symbol)
        
        if order_execution.is_position_open(symbol):
            logging.info(f"Signal for {symbol} suppressed. Position already open.")
            return
            
        entry_price = current_candle['close']
        trade_id = f"paper_{uuid.uuid4()}"
        tp_price, sl_price = risk_management.calculate_fixed_tp_sl(
            entry_price=entry_price, side=side,
            tp_pct=params['tp_pct'], sl_pct=params['sl_pct']
        )
        
        # Calculate position size with the multiplier from macro integration
        position_size = risk_management.calculate_dynamic_position_size(
            account_equity=order_execution.get_account_equity(),
            stop_loss_price=sl_price,
            entry_price=entry_price
        ) * size_multiplier
        
        signal = {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "trade_id": trade_id,
            "strategy_id": "v5.2-data-driven",
            "position_size": position_size
        }
        publish_trade_signal(signal)
        order_execution.record_new_position(
            symbol=symbol,
            trade_id=trade_id,
            side=side,
            entry_price=entry_price,
            tp_price=tp_price,
            sl_price=sl_price,
            position_size=position_size,
            is_paper=PAPER_TRADING
        )

def run_logic_cycle():
    """Main loop to analyze market data."""
    logging.info("--- Starting new logic cycle ---")
    for symbol in SYMBOLS_TO_ANALYZE:
        try:
            analyze_market_data(symbol)
        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {e}", exc_info=True)

def start_logic_engine():
    """Starts the logic engine service."""
    global table, publisher, signal_topic_path, macro_integration
    
    logging.info("Initializing logic engine service...")
    
    # Get PROJECT_ID
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
    if not PROJECT_ID:
        PROJECT_ID = "telegram-signals-205cc"
        logging.warning(f"Using hardcoded PROJECT_ID: {PROJECT_ID}")
    
    # Initialize Bigtable
    INSTANCE_ID = "cryptotracker-bigtable"
    TABLE_ID = "market-data-1m"
    try:
        bigtable_client = bigtable.Client(project=PROJECT_ID, admin=True)
        instance = bigtable_client.instance(INSTANCE_ID)
        table = instance.table(TABLE_ID)
        logging.info("Successfully connected to Bigtable.")
    except Exception as e:
        logging.error(f"Failed to connect to Bigtable: {e}")
        return

    # Initialize Pub/Sub
    SIGNAL_TOPIC_NAME = "trade-signals-micro"
    try:
        publisher = pubsub_v1.PublisherClient()
        signal_topic_path = publisher.topic_path(PROJECT_ID, SIGNAL_TOPIC_NAME)
        logging.info(f"Successfully connected to Pub/Sub topic '{SIGNAL_TOPIC_NAME}'.")
    except Exception as e:
        logging.error(f"Failed to initialize Pub/Sub publisher: {e}")
        return
    
    # Initialize macro integration
    macro_integration = MacroIntegration()
    
    # Start the macro bias subscriber
    macro_integration.start_bias_subscriber()
    logging.info("Started macro bias integration")
    
    logging.info("Starting MICRO-SCALP Logic Engine main loop...")
    
    # Run the main analysis loop
    while True:
        try:
            run_logic_cycle()
            logging.info(f"Cycle complete. Waiting {ANALYSIS_INTERVAL_SECONDS} seconds...")
            time.sleep(ANALYSIS_INTERVAL_SECONDS)
        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(ANALYSIS_INTERVAL_SECONDS)

if __name__ == '__main__':
    start_logic_engine()