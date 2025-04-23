import logging
import datetime
import pytz
from config import MARKET_HOURS

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def is_market_hours(current_time=None):
    """
    Check if the current time is within the defined market hours.
    
    Args:
        current_time: Current datetime object (UTC)
        
    Returns:
        Boolean indicating if we're in market hours
    """
    if current_time is None:
        current_time = datetime.datetime.now(pytz.UTC)
    
    # Extract hour and minute
    hour = current_time.hour
    minute = current_time.minute
    current_minutes = hour * 60 + minute
    
    # Check each market hour window
    for start, end in MARKET_HOURS:
        start_hour, start_minute = start
        end_hour, end_minute = end
        
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        if start_minutes <= current_minutes <= end_minutes:
            return True
    
    return False

def is_in_cooldown_period(symbol, db, cooldown_minutes=15):
    """
    Check if a symbol is in cooldown period after a recent signal.
    
    Args:
        symbol: Trading pair symbol
        db: Firestore database instance
        cooldown_minutes: Cooldown period in minutes (default: 15)
        
    Returns:
        Boolean indicating if symbol is in cooldown period
    """
    try:
        # Calculate cooldown timestamp
        cooldown_timestamp = datetime.datetime.now(pytz.UTC) - datetime.timedelta(minutes=cooldown_minutes)
        
        # Query for recent signals
        signals_query = (
            db.collection("signals")
            .where("symbol", "==", symbol)
            .where("timestamp", ">=", cooldown_timestamp)
            .limit(1)
            .get()
        )
        
        # If we have any signals within the cooldown period, return True
        return len(signals_query) > 0
        
    except Exception as e:
        logger.error(f"Error checking cooldown period for {symbol}: {str(e)}")
        return False  # Default to allowing signals if we can't check

def format_number(number, decimals=2):
    """
    Format a number with the specified number of decimal places.
    
    Args:
        number: Number to format
        decimals: Number of decimal places (default: 2)
        
    Returns:
        Formatted number string
    """
    return f"{number:.{decimals}f}"
