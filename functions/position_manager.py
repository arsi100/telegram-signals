import logging
from firebase_admin import firestore

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def save_position(db, signal):
    """
    Save a new position to Firestore.
    
    Args:
        db: Firestore database instance
        signal: Signal dict with position details
        
    Returns:
        Position document reference
    """
    try:
        position_data = {
            "symbol": signal["symbol"],
            "type": signal["type"],  # long or short
            "entry_price": signal["price"],
            "avg_price": signal["price"],  # Initially the same as entry price
            "size": 0.01,  # Default size
            "avg_down_count": 0,
            "status": "open",
            "avg_volume": signal.get("volume", 0),
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        
        # Add the position to Firestore
        position_ref = db.collection("positions").add(position_data)
        logger.info(f"Saved new {signal['type']} position for {signal['symbol']} at ${signal['price']}")
        
        return position_ref[1]
        
    except Exception as e:
        logger.error(f"Error saving position: {str(e)}")
        return None

def update_position(db, signal):
    """
    Update an existing position based on a signal.
    
    Args:
        db: Firestore database instance
        signal: Signal dict with position details
        
    Returns:
        True if position was updated successfully, False otherwise
    """
    try:
        # Get position reference
        position_path = signal.get("position_ref")
        if not position_path:
            logger.error("No position reference in signal")
            return False
            
        position_ref = db.document(position_path)
        position = position_ref.get()
        
        if not position.exists:
            logger.error(f"Position {position_path} does not exist")
            return False
            
        position_data = position.to_dict()
        
        # Handle different signal types
        if signal["type"] == "exit":
            # Close the position
            position_ref.update({
                "status": "closed",
                "exit_price": signal["price"],
                "exit_timestamp": firestore.SERVER_TIMESTAMP,
                "profit_percentage": calculate_profit_percentage(
                    position_data["type"],
                    position_data["avg_price"],
                    signal["price"]
                )
            })
            logger.info(f"Closed {position_data['type']} position for {signal['symbol']} at ${signal['price']}")
            
        elif signal["type"] in ["avg_down_long", "avg_down_short"]:
            # Average down the position
            current_size = position_data.get("size", 0.01)
            current_avg_price = position_data.get("avg_price", position_data["entry_price"])
            avg_down_count = position_data.get("avg_down_count", 0)
            
            # Calculate new average price
            new_size = current_size * 0.5  # Add 50% more to position
            total_size = current_size + new_size
            
            new_avg_price = ((current_avg_price * current_size) + (signal["price"] * new_size)) / total_size
            
            # Update the position
            position_ref.update({
                "avg_price": new_avg_price,
                "size": total_size,
                "avg_down_count": avg_down_count + 1,
                "last_avg_down_price": signal["price"],
                "last_avg_down_timestamp": firestore.SERVER_TIMESTAMP
            })
            
            position_type = "long" if signal["type"] == "avg_down_long" else "short"
            logger.info(f"Averaged down {position_type} position for {signal['symbol']} at ${signal['price']}, new avg: ${new_avg_price:.2f}")
            
        return True
        
    except Exception as e:
        logger.error(f"Error updating position: {str(e)}")
        return False

def calculate_profit_percentage(position_type, entry_price, exit_price):
    """
    Calculate profit percentage for a position.
    
    Args:
        position_type: Type of position ("long" or "short")
        entry_price: Entry price
        exit_price: Exit price
        
    Returns:
        Profit percentage
    """
    if position_type == "long":
        return ((exit_price - entry_price) / entry_price) * 100
    elif position_type == "short":
        return ((entry_price - exit_price) / entry_price) * 100
    else:
        return 0.0
        
def get_open_positions(db):
    """
    Get all currently open positions.
    
    Args:
        db: Firestore database instance
        
    Returns:
        List of open positions
    """
    try:
        positions = []
        position_query = db.collection("positions").where("status", "==", "open").get()
        
        for doc in position_query:
            position = doc.to_dict()
            position["id"] = doc.id
            position["ref"] = doc.reference.path
            positions.append(position)
            
        return positions
        
    except Exception as e:
        logger.error(f"Error getting open positions: {str(e)}")
        return []
