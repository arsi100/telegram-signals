import logging
import datetime
import pytz
# Use absolute import for config
from functions import config

# Set up logging
# Remove basicConfig, assume it's handled by the entry point (e.g., main.py or local_test_runner.py)
# logging.basicConfig(level=logging.DEBUG)
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
    
    # Extract hour and day of the week
    hour = current_time.hour
    # weekday = current_time.weekday() # Monday is 0, Sunday is 6
    
    # Use config directly
    start_hour = config.MARKET_HOURS['start_hour']
    end_hour = config.MARKET_HOURS['end_hour']
    # active_days = config.MARKET_HOURS['active_days']

    # Check day of week (Removed for now as market is 24/7 in config)
    # if weekday not in active_days:
    #     return False
        
    # Check hour (simple check assuming end_hour is within the same day or next day midnight)
    if start_hour <= end_hour:
        # Market hours are within a single day (e.g., 9 to 17)
        is_within_hours = start_hour <= hour <= end_hour
    else:
        # Market hours cross midnight (e.g., 22 to 6)
        is_within_hours = hour >= start_hour or hour <= end_hour

    # Simplified 24/7 check based on current config (0-23)
    if config.MARKET_HOURS['start_hour'] == 0 and config.MARKET_HOURS['end_hour'] == 23:
        return True # Always market hours

    # Fallback to previous logic if config changes
    # This logic needs refinement if MARKET_HOURS includes minutes or complex ranges
    return is_within_hours 

# --- Removed is_in_cooldown_period as it's now in position_manager.py ---
# def is_in_cooldown_period(symbol, db, cooldown_minutes=15):
#     ...

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
