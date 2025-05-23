import logging
from firebase_admin import firestore
import datetime
import pytz
from . import config # Import config for cooldown period

# Get logger (logging configuration handled by main.py)
logger = logging.getLogger(__name__)

# Firestore Collection Names
POSITIONS_COLLECTION = "positions"
TIMESTAMPS_COLLECTION = "signal_timestamps"

def get_open_position(symbol: str, db):
    """
    Retrieves the currently open position document for a given symbol.
    
    Args:
        symbol: The trading symbol (e.g., 'PF_XBTUSD').
        db: Firestore client instance.

    Returns:
        A dictionary containing the position data including 'ref_path',
        or None if no open position is found or an error occurs.
    """
    try:
        query = db.collection(POSITIONS_COLLECTION)\
                  .where("symbol", "==", symbol)\
                  .where("status", "==", "open")\
                  .limit(1)\
                  .stream() # Use stream for potentially single result
        
        position_doc = next(query, None) # Get the first result or None

        if position_doc:
            position_data = position_doc.to_dict()
            position_data["ref_path"] = position_doc.reference.path # Add reference path
            position_data["id"] = position_doc.id # Add document ID
            logger.info(f"Found open {position_data.get('type', '')} position for {symbol}: {position_doc.id}")
            return position_data
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error getting open position for {symbol}: {e}", exc_info=True)
        return None

def record_signal_ts(symbol: str, db):
    """
    Records the current timestamp for the latest LONG/SHORT signal for a symbol.

    Args:
        symbol: The trading symbol.
        db: Firestore client instance.
    """
    try:
        doc_ref = db.collection(TIMESTAMPS_COLLECTION).document(symbol)
        doc_ref.set({"last_signal_ts": firestore.SERVER_TIMESTAMP}, merge=True)
        logger.info(f"Recorded signal timestamp for {symbol}")
        return True
    except Exception as e:
        logger.error(f"Error recording signal timestamp for {symbol}: {e}", exc_info=True)
        return False

def is_in_cooldown_period(symbol: str, db, cooldown_minutes: int):
    """
    Checks if the symbol is currently within the cooldown period.

    Args:
        symbol: The trading symbol.
        db: Firestore client instance.
        cooldown_minutes: The cooldown duration in minutes.
        
    Returns:
        True if within cooldown, False otherwise.
    """
    try:
        doc_ref = db.collection(TIMESTAMPS_COLLECTION).document(symbol)
        doc_snapshot = doc_ref.get()

        if not doc_snapshot.exists:
            return False # No timestamp means not in cooldown

        timestamp_data = doc_snapshot.to_dict()
        last_signal_ts = timestamp_data.get("last_signal_ts")

        if not last_signal_ts:
             logger.warning(f"Timestamp document exists for {symbol} but key 'last_signal_ts' is missing.")
             return False # Missing timestamp data

        # Ensure timestamp is timezone-aware (Firestore timestamps are UTC)
        if last_signal_ts.tzinfo is None:
             last_signal_ts = last_signal_ts.replace(tzinfo=pytz.UTC)
             
        now_utc = datetime.datetime.now(pytz.UTC)
        cooldown_delta = datetime.timedelta(minutes=cooldown_minutes)
        
        if (now_utc - last_signal_ts) < cooldown_delta:
            logger.info(f"{symbol} is within {cooldown_minutes}m cooldown period. Last signal: {last_signal_ts}")
            return True
        else:
            # Only log if actually in cooldown - remove routine "outside cooldown" DEBUG logs
            return False

    except Exception as e:
        logger.error(f"Error checking cooldown period for {symbol}: {e}", exc_info=True)
        return False # Assume not in cooldown if error occurs

def save_position(signal: dict, db):
    """
    Saves a new position to Firestore based on a LONG or SHORT signal.
    """
    try:
        entry_price = signal['price']
        position_type_raw = signal['type'] # Should be BUY, SELL, etc.
        
        # Map BUY/SELL to LONG/SHORT for SL/TP logic consistency
        position_type_for_logic = None
        if position_type_raw == "BUY":
            position_type_for_logic = "LONG"
        elif position_type_raw == "SELL":
            position_type_for_logic = "SHORT"

        # Calculate initial SL/TP (optional but good practice)
        if position_type_for_logic == "LONG":
            initial_stop_loss = entry_price * (1 - 0.02) # 2% SL
            initial_take_profit = entry_price * (1 + 0.03) # 3% TP
        elif position_type_for_logic == "SHORT":
             initial_stop_loss = entry_price * (1 + 0.02) # 2% SL
             initial_take_profit = entry_price * (1 - 0.03) # 3% TP
        else:
            initial_stop_loss = None
            initial_take_profit = None
            
        position_data = {
            "symbol": signal["symbol"],
            "type": position_type_raw, # Store the original type e.g. BUY/SELL
            "entry_price": entry_price,
            "avg_price": entry_price, # Initial average price is entry price
            "confidence": signal["confidence"],
            "status": "open",
            "avg_down_count": 0,
            "avg_up_count": 0,
            "initial_stop_loss": initial_stop_loss,
            "initial_take_profit": initial_take_profit,
            "entry_timestamp": firestore.SERVER_TIMESTAMP,
            "last_update_timestamp": firestore.SERVER_TIMESTAMP
            # Add other relevant info from signal if needed, e.g., volume, rsi
        }
        
        # Add the position to Firestore
        _ , position_ref = db.collection(POSITIONS_COLLECTION).add(position_data)
        logger.info(f"Saved new {position_type_raw} position for {signal['symbol']} at {entry_price:.2f}. Ref: {position_ref.id}")
        return position_ref
        
    except Exception as e:
        logger.error(f"Error saving position for {signal.get('symbol')}: {e}", exc_info=True)
        return None

def update_position(position_ref_path: str, signal: dict, db):
    """
    Updates an existing position for AVG_DOWN or AVG_UP signals.
    (Closing is handled by close_position)
    """
    try:
        position_ref = db.document(position_ref_path)
        position_snapshot = position_ref.get()
        
        if not position_snapshot.exists:
            logger.error(f"Position {position_ref_path} does not exist for update.")
            return False
            
        position_data = position_snapshot.to_dict()
        update_payload = {"last_update_timestamp": firestore.SERVER_TIMESTAMP}
        signal_price = signal['price']
        signal_type = signal['type']
        
        # --- Average Down Logic --- 
        if signal_type.startswith("AVG_DOWN"):
            current_avg_price = position_data.get("avg_price", position_data["entry_price"])
            avg_down_count = position_data.get("avg_down_count", 0)
            # Simple assumption: averaging doubles the position size notionally for price calc
            new_avg_price = (current_avg_price + signal_price) / 2 
            
            update_payload["avg_price"] = new_avg_price
            update_payload["avg_down_count"] = avg_down_count + 1
            # Potentially update SL based on new avg_price?
            # update_payload["current_stop_loss"] = ...
            logger.info(f"Averaging down {position_data['type']} position {position_ref.id} for {signal['symbol']} at {signal_price:.2f}. New avg price: {new_avg_price:.2f}")

        # --- Average Up Logic --- 
        elif signal_type.startswith("AVG_UP"):
            current_avg_price = position_data.get("avg_price", position_data["entry_price"])
            avg_up_count = position_data.get("avg_up_count", 0)
            # Simple assumption: averaging doubles the position size notionally for price calc
            new_avg_price = (current_avg_price + signal_price) / 2
            
            update_payload["avg_price"] = new_avg_price
            update_payload["avg_up_count"] = avg_up_count + 1
            # Trailing stop adjustment would happen elsewhere based on price movement
            logger.info(f"Averaging up {position_data['type']} position {position_ref.id} for {signal['symbol']} at {signal_price:.2f}. New avg price: {new_avg_price:.2f}")
            
        else:
            logger.warning(f"update_position called with unexpected signal type: {signal_type}")
            return False
        
        position_ref.update(update_payload)
        return True
        
    except Exception as e:
        logger.error(f"Error updating position {position_ref_path}: {e}", exc_info=True)
        return False

def close_position(position_ref_path: str, exit_price: float, db):
    """
    Closes an open position in Firestore.
    """
    try:
        position_ref = db.document(position_ref_path)
        position_snapshot = position_ref.get()
        
        if not position_snapshot.exists:
            logger.error(f"Position {position_ref_path} does not exist for closing.")
            return False
            
        position_data = position_snapshot.to_dict()
        
        if position_data.get("status") != "open":
            logger.warning(f"Attempted to close position {position_ref_path} which is not open (status: {position_data.get('status')}).")
            return False # Or True, as it's already closed?
            
        # Calculate P/L using the final average price
        avg_price = position_data.get("avg_price", position_data.get("entry_price"))
        position_type = position_data.get("type")
        profit_percentage = 0
        if avg_price and position_type:
             if position_type == "LONG":
                 profit_percentage = ((exit_price - avg_price) / avg_price) * 100
             elif position_type == "SHORT":
                 profit_percentage = ((avg_price - exit_price) / avg_price) * 100
                 
        update_payload = {
            "status": "closed",
            "exit_price": exit_price,
            "profit_percentage": profit_percentage,
            "exit_timestamp": firestore.SERVER_TIMESTAMP,
            "last_update_timestamp": firestore.SERVER_TIMESTAMP
        }
            
        position_ref.update(update_payload)
        logger.info(f"Closed {position_type} position {position_ref.id} for {position_data.get('symbol')} at {exit_price:.2f}. P/L: {profit_percentage:.2f}%")
        return True
        
    except Exception as e:
         logger.error(f"Error closing position {position_ref_path}: {e}", exc_info=True)
         return False

# Keep calculate_profit_percentage as a helper if needed elsewhere, or remove if only used in close_position
# def calculate_profit_percentage(position_type, entry_price, exit_price): ...

# Remove get_open_positions if get_open_position(symbol, db) is sufficient
# def get_open_positions(db): ...
