import logging
from firebase_admin import firestore
import datetime
import pytz
from . import config # Import config for cooldown period
from typing import Optional, Tuple
from google.cloud import firestore # Added import
import firebase_admin

# Get logger (logging configuration handled by main.py)
logger = logging.getLogger(__name__)

# Constants from config
# POSITIONS_COLLECTION = "positions" # Now from config
# SIGNALS_COLLECTION = "signal_timestamps" # Now from config
# COOLDOWN_PERIOD_MINUTES = 60 # Now from config

def get_open_position(symbol, db):
    """Retrieve an open position for a given symbol."""
    try:
        positions_ref = db.collection(f'crypto_positions_{config.MODE.lower()}')
        # NOTE: The following query uses `firestore.FieldFilter`.
        # This requires `google-cloud-firestore` library version 2.11.0 or later.
        # If you see an `AttributeError: module 'google.cloud.firestore' has no attribute 'FieldFilter'`,
        # please upgrade your library by running:
        # pip install --upgrade google-cloud-firestore
        query = positions_ref.where(filter=firestore.FieldFilter('symbol', '==', symbol)) \
                           .where(filter=firestore.FieldFilter('status', '==', 'OPEN'))
        
        position_docs = query.limit(1).stream()

        for doc in position_docs:
            position_data = doc.to_dict()
            position_data['id'] = doc.id # Add document ID to the data
            logger.info(f"Found open {position_data.get('type')} position for {symbol}: {doc.id}")
            return position_data
        return None
    except Exception as e:
        logger.error(f"Error getting open position for {symbol}: {e}")
        return None

def record_new_position(
    symbol: str, 
    signal_type: str, 
    entry_price: float, 
    db: firestore.Client, 
    signal_data: dict  # This dictionary contains all other signal details like confidence, source, rsi, sentiment, gemini info etc.
) -> Tuple[Optional[str], Optional[dict]]:
    """Record a new open position in Firestore."""
    try:
        positions_collection_ref = db.collection(f'crypto_positions_{config.MODE.lower()}')
        new_position_doc_ref = positions_collection_ref.document() # Let Firestore generate ID
        
        payload = {
            "symbol": symbol,
            "type": signal_type,
            "entry_price": float(entry_price),
            "entry_timestamp": firestore.SERVER_TIMESTAMP,
            "status": "OPEN",
            "pnl_percentage": 0.0,
            "current_price": float(entry_price), 
            "avg_down_count": 0,
            "signal_id": new_position_doc_ref.id, # Store the ID of the signal document itself
            "ref_path": new_position_doc_ref.path, # Store the document path for easy reference
            # Spread all other details from signal_data (confidence, source, rsi, sentiment, gemini_*, etc.)
            **signal_data 
        }
        # Remove any redundant keys that are already explicitly defined if they also exist in signal_data
        # (e.g. if signal_data also had 'symbol', 'type', 'entry_price') - though it shouldn't if structured correctly
        # For safety, ensure explicit ones take precedence if necessary, but **signal_data should be primary for additional fields.

        logger.debug(f"[PM] Attempting to save new position with payload: {payload}") # Log the exact payload
        new_position_doc_ref.set(payload)
        logger.info(f"Recorded new {signal_type} position for {symbol} at {entry_price}, ID: {new_position_doc_ref.id}")
        
        record_signal_ts(symbol, db) # Record cooldown timestamp
        return new_position_doc_ref.id, payload # Return ID and payload

    except Exception as e:
        logger.error(f"Error recording new position for {symbol}: {e}", exc_info=True)
        return None, None

def close_open_position(position_id, exit_price, db):
    """Close an existing open position in Firestore."""
    try:
        position_ref = db.collection(f'crypto_positions_{config.MODE.lower()}').document(position_id)
        position_doc = position_ref.get()
        if not position_doc.exists:
            logger.warning(f"Position {position_id} not found, cannot close.")
            return None
        
        position_data = position_doc.to_dict()
        entry_price = position_data.get('entry_price', 0)
        signal_type = position_data.get('type', 'N/A')
        pnl_percentage = 0.0
        if entry_price != 0:
            if signal_type == 'LONG':
                pnl_percentage = ((exit_price - entry_price) / entry_price) * 100
            elif signal_type == 'SHORT':
                pnl_percentage = ((entry_price - exit_price) / entry_price) * 100

        position_ref.update({
            'status': 'CLOSED',
            'exit_price': exit_price,
            'closed_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'pnl_percentage': round(pnl_percentage, 2)
        })
        logger.info(f"Closed position {position_id} for {position_data.get('symbol')} at {exit_price}. PNL: {pnl_percentage:.2f}%")
        record_signal_ts(position_data.get('symbol'), db) # Record timestamp for cooldown
        return True
    except Exception as e:
        logger.error(f"Error closing position {position_id}: {e}")
        return False

def record_signal_ts(symbol, db):
    """Records the timestamp of the last signal for a symbol to manage cooldown."""
    try:
        doc_ref = db.collection(f'crypto_signals_cooldown_{config.MODE.lower()}').document(symbol)
        doc_ref.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'symbol': symbol
        })
        logger.info(f"Recorded signal timestamp for {symbol} for cooldown period.")
    except Exception as e:
        logger.error(f"Error recording signal timestamp for {symbol}: {e}")

def is_in_cooldown_period(symbol, db):
    """Checks if the symbol is currently in a cooldown period."""
    try:
        logger.debug(f"is_in_cooldown_period called for {symbol}")
        doc_ref = db.collection(f'crypto_signals_cooldown_{config.MODE.lower()}').document(symbol)
        doc_snapshot = doc_ref.get()

        logger.debug(f"For {symbol}, cooldown doc_snapshot ID: {doc_snapshot.id if hasattr(doc_snapshot, 'id') else 'N/A'}, exists: {doc_snapshot.exists}")
        if hasattr(doc_snapshot, 'to_dict') and callable(doc_snapshot.to_dict):
            logger.debug(f"For {symbol}, doc_snapshot.to_dict return_value type: {type(doc_snapshot.to_dict())}")

        if doc_snapshot.exists:
            last_signal_data = doc_snapshot.to_dict()
            logger.debug(f"For {symbol}, after to_dict(), last_signal_data is: {last_signal_data}")

            if not last_signal_data: # Check if to_dict() returned None or empty
                logger.warning(f"Timestamp data missing or empty (to_dict() returned None/Falsey) for {symbol} even though document exists. Assuming not in cooldown.")
                return False
            
            last_signal_ts_any = last_signal_data.get('timestamp')

            if not last_signal_ts_any:
                logger.warning(f"Timestamp field missing in cooldown record for {symbol} (ID: {doc_snapshot.id}). Assuming not in cooldown.")
                return False

            # Ensure last_signal_ts is timezone-aware (UTC)
            if isinstance(last_signal_ts_any, datetime.datetime):
                if last_signal_ts_any.tzinfo is None:
                    last_signal_ts = pytz.utc.localize(last_signal_ts_any)
                else:
                    last_signal_ts = last_signal_ts_any.astimezone(pytz.utc)
            else: # Handle non-datetime types after ensuring last_signal_ts_any is not None
                # Handle Firestore ServerTimestamp (which might not be a datetime obj immediately after fetch)
                # This case might need more robust handling depending on when this check is called relative to write
                logger.warning(f"Timestamp for {symbol} is not a datetime object: {type(last_signal_ts_any)}. Cooldown might be inaccurate.")
                # For safety, assume not in cooldown if type is unexpected, or treat as very old.
                # A more robust way would be to ensure it's converted from FieldValue.
                return False
        
            now_utc = datetime.datetime.now(pytz.utc)
            cooldown_delta = datetime.timedelta(minutes=config.SIGNAL_COOLDOWN_MINUTES)

            if (now_utc - last_signal_ts) < cooldown_delta:
                logger.info(f"{symbol} is in cooldown. Last signal: {last_signal_ts}, Now: {now_utc}")
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking cooldown period for {symbol}: {e}")
        return False # Fail safe: if error, assume not in cooldown

def update_avg_down_position(position_id, new_entry_price, additional_quantity_percentage, db):
    """Updates an existing position after an average down.
       This is a simplified example; actual averaging down involves quantity and average price recalculation.
       Here we just update entry price and increment a counter.
    """
    try:
        position_ref = db.collection(f'crypto_positions_{config.MODE.lower()}').document(position_id)
        position_doc = position_ref.get()
        if not position_doc.exists:
            logger.warning(f"Position {position_id} not found, cannot average down.")
            return False
            
        current_avg_down_count = position_doc.to_dict().get('avg_down_count', 0)

        position_ref.update({
            'entry_price': new_entry_price, # This would be a new weighted average price
            'avg_down_count': current_avg_down_count + 1,
            'updated_at': firestore.SERVER_TIMESTAMP
            # 'quantity': new_total_quantity, # Would also update quantity
        })
        logger.info(f"Averaged down position {position_id}. New count: {current_avg_down_count + 1}")
        record_signal_ts(position_doc.to_dict().get('symbol'), db) # Record timestamp for cooldown
        return True
    except Exception as e:
        logger.error(f"Error updating position {position_id} for averaging down: {e}")
        return False

def calculate_current_pnl(position_data: dict, current_price: float) -> dict:
    """
    Calculate current P/L and related metrics for an open position.
    
    Args:
        position_data: Dictionary containing position details
        current_price: Current market price
        
    Returns:
        Dictionary with P/L metrics:
        - pnl_percentage: Current P/L as percentage
        - pnl_absolute: Current P/L in absolute terms
        - is_profit: Boolean indicating if position is profitable
        - distance_from_entry: Percentage distance from entry
    """
    try:
        entry_price = float(position_data.get('entry_price', 0))
        position_type = position_data.get('type', 'UNKNOWN')
        
        if entry_price == 0:
            logger.warning(f"Invalid entry price (0) for position calculation")
            return {
                'pnl_percentage': 0.0,
                'pnl_absolute': 0.0,
                'is_profit': False,
                'distance_from_entry': 0.0
            }
            
        # Calculate P/L percentage based on position type
        if position_type == 'LONG':
            pnl_percentage = ((current_price - entry_price) / entry_price) * 100
            pnl_absolute = current_price - entry_price
        elif position_type == 'SHORT':
            pnl_percentage = ((entry_price - current_price) / entry_price) * 100
            pnl_absolute = entry_price - current_price
        else:
            logger.warning(f"Unknown position type: {position_type}")
            return {
                'pnl_percentage': 0.0,
                'pnl_absolute': 0.0,
                'is_profit': False,
                'distance_from_entry': 0.0
            }
            
        # Calculate absolute distance from entry (useful for trailing stops)
        distance_from_entry = abs(((current_price - entry_price) / entry_price) * 100)
        
        return {
            'pnl_percentage': round(pnl_percentage, 2),
            'pnl_absolute': round(pnl_absolute, 8),  # More decimals for crypto
            'is_profit': pnl_percentage > 0,
            'distance_from_entry': round(distance_from_entry, 2)
        }
        
    except Exception as e:
        logger.error(f"Error calculating current P/L: {e}")
        return {
            'pnl_percentage': 0.0,
            'pnl_absolute': 0.0,
            'is_profit': False,
            'distance_from_entry': 0.0
        }

def update_position_pnl(position_id: str, current_price: float, db: firestore.Client) -> bool:
    """
    Update the current P/L for an open position.
    
    Args:
        position_id: Firestore document ID of the position
        current_price: Current market price
        db: Firestore client
        
    Returns:
        Boolean indicating success
    """
    try:
        position_ref = db.collection(f'crypto_positions_{config.MODE.lower()}').document(position_id)
        position_doc = position_ref.get()
        
        if not position_doc.exists:
            logger.warning(f"Position {position_id} not found, cannot update P/L")
            return False
            
        position_data = position_doc.to_dict()
        pnl_data = calculate_current_pnl(position_data, current_price)
        
        # Update position with new P/L data
        position_ref.update({
            'current_price': float(current_price),
            'pnl_percentage': pnl_data['pnl_percentage'],
            'pnl_absolute': pnl_data['pnl_absolute'],
            'distance_from_entry': pnl_data['distance_from_entry'],
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"Updated P/L for position {position_id}: {pnl_data['pnl_percentage']}%")
        return True
        
    except Exception as e:
        logger.error(f"Error updating P/L for position {position_id}: {e}")
        return False

# Keep calculate_profit_percentage as a helper if needed elsewhere, or remove if only used in close_position
# def calculate_profit_percentage(position_type, entry_price, exit_price): ...

# Remove get_open_positions if get_open_position(symbol, db) is sufficient
# def get_open_positions(db): ...
