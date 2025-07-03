import os
import logging
from datetime import datetime, timezone
from google.cloud import bigtable

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
INSTANCE_ID = "cryptotracker-bigtable"
TABLE_ID = "live-positions" # Table for tracking open trades

# --- Bigtable Client ---
# This is a simplified client for this specific module's needs.
# The main logic_engine.py will have the primary client.
try:
    bigtable_client = bigtable.Client(project=PROJECT_ID)
    instance = bigtable_client.instance(INSTANCE_ID)
    positions_table = instance.table(TABLE_ID)
    logging.info("OrderExecution: Successfully connected to Bigtable positions table.")
except Exception as e:
    logging.error(f"OrderExecution: Failed to connect to Bigtable: {e}")
    positions_table = None

def is_position_open(symbol: str) -> bool:
    """
    Checks if a position for the given symbol is currently marked as open in Bigtable.
    A row key presence indicates an open position.
    """
    if not positions_table:
        logging.error("Bigtable client not available for position check.")
        # Fail safe: assume a position is open to prevent duplicate trades.
        return True 
        
    try:
        row_key = f"{symbol}".encode('utf-8')
        row = positions_table.read_row(row_key)
        if row:
            logging.info(f"Position for {symbol} is currently open. No new trade will be placed.")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to check position for {symbol}: {e}", exc_info=True)
        # Fail safe
        return True

def record_new_position(symbol: str, trade_id: str, side: str, entry_price: float, tp_price: float, sl_price: float, is_paper: bool):
    """
    Records a new open position in the Bigtable 'live-positions' table.
    The row key is the symbol, ensuring only one open position per symbol.
    """
    if not positions_table:
        logging.error("Bigtable client not available. Cannot record new position.")
        return

    try:
        row_key = f"{symbol}".encode('utf-8')
        row = positions_table.direct_row(row_key)
        
        ts = datetime.now(timezone.utc)
        
        # Column family 'details'
        row.set_cell("details", "trade_id", str(trade_id), timestamp=ts)
        row.set_cell("details", "side", str(side), timestamp=ts)
        row.set_cell("details", "entry_price", str(entry_price), timestamp=ts)
        row.set_cell("details", "tp_price", str(tp_price), timestamp=ts)
        row.set_cell("details", "sl_price", str(sl_price), timestamp=ts)
        row.set_cell("details", "is_paper", str(is_paper), timestamp=ts)
        
        positions_table.mutate_rows([row])
        logging.info(f"Successfully recorded new {'paper' if is_paper else 'live'} position for {symbol} with trade_id {trade_id}.")

    except Exception as e:
        logging.error(f"Failed to record new position for {symbol}: {e}", exc_info=True)

def close_position(symbol: str):
    """
    Deletes the row for a symbol from the 'live-positions' table, marking it as closed.
    This would be triggered by a separate process that monitors TP/SL hits.
    """
    if not positions_table:
        logging.error("Bigtable client not available. Cannot close position.")
        return
        
    try:
        row_key = f"{symbol}".encode('utf-8')
        row = positions_table.direct_row(row_key)
        row.delete()
        positions_table.mutate_rows([row])
        logging.info(f"Position for {symbol} has been marked as closed.")
    except Exception as e:
        logging.error(f"Failed to close position for {symbol}: {e}", exc_info=True)

# Note: The original BybitOrderPlacer class for live trading would be kept here
# or in a separate file. For now, this module is focused on position tracking. 