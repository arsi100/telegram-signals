#!/usr/bin/env python
# Try importing core modules first and log any errors
try:
    import logging
    import datetime
    import time
    import pytz
    import firebase_admin
    from firebase_admin import firestore
    print("Successfully imported core libraries") # Use print for early feedback
except ImportError as e:
    print(f"CRITICAL: Failed to import core libraries: {e}")
    # If core libs fail, the function likely can't proceed
    raise # Re-raise the exception to ensure failure

# Try importing local/application modules
try:
    from . import config
    from .signal_generator import process_crypto_data
    from .kraken_api import fetch_kline_data
    from .telegram_bot import send_telegram_message
    from .position_manager import save_position, update_position, close_position
    print("Successfully imported application modules") # Use print
except ImportError as e:
    print(f"CRITICAL: Failed to import application modules: {e}")
    # Log the error before potentially failing
    # Get a logger instance here just in case logging *partially* works
    try:
        logger_init_fail = logging.getLogger(__name__)
        logger_init_fail.error(f"Failed to import application modules: {e}", exc_info=True)
    except Exception as log_e:
        print(f"Also failed to get logger during import error: {log_e}")
    raise # Re-raise the exception

# Set up logging *after* successful imports
logger = logging.getLogger(__name__)

# Global placeholder for db client - MUST be initialized by entry point
# This isn't ideal practice, passing db would be better, but simplifies refactoring for now
db = None

print("***** TOP LEVEL PRINT: main.py loaded *****") # ADDED FOR DEBUGGING

# Add functions directory to sys.path to allow absolute imports for deployment
# functions_dir = os.path.dirname(__file__)
# if functions_dir not in sys.path:
#     sys.path.append(functions_dir)

# Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
# logging.getLogger().setLevel(logging.DEBUG) # Ensure root logger level is set

# Explicitly configure logging - trying another way
log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=log_format, force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Attempt imports within try-except block for debugging deployment issues
try:
    print("***** TOP LEVEL: Trying imports... *****") # ADDED FOR DEBUGGING
    import firebase_admin
    from firebase_admin import credentials, firestore
    from . import config
    from .kraken_api import get_kraken_kline_data
    from .technical_analysis import analyze_technicals
    from .position_manager import get_position, save_position, check_cooldown # Added save_position back
    from .telegram_bot import send_telegram_message
    from .confidence_calculator import get_confidence_score
    print("***** TOP LEVEL: Imports successful *****") # ADDED FOR DEBUGGING
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"***** TOP LEVEL IMPORT ERROR: {e} *****") # Use print for early logging potential
    logger.error(f"Failed to import required modules at top level: {e}", exc_info=True) # Also log normally
    # Let the function execution handle the failure
except Exception as e:
    print(f"***** TOP LEVEL UNEXPECTED ERROR DURING IMPORT: {e} *****")
    logger.error(f"Unexpected error during top-level imports: {e}", exc_info=True)
    # Let the function execution handle the failure

# --- Firebase Initialization (Attempt at top level, checked in function) ---
if IMPORTS_SUCCESSFUL and not firebase_admin._apps:
    try:
        # Use Application Default Credentials provided by the Cloud Functions environment
        print("***** TOP LEVEL: Initializing Firebase Admin... *****")
        firebase_admin.initialize_app()
        db = firestore.client()
        print("***** TOP LEVEL: Firebase Admin initialized successfully. *****") # Use print
        logger.info("Firebase Admin initialized successfully at top level.")
        FIREBASE_INITIALIZED = True
    except Exception as e:
        print(f"***** TOP LEVEL: Firebase Admin initialization failed: {e} *****") # Use print
        logger.error(f"Firebase Admin initialization failed at top level: {e}", exc_info=True)
        # Let the function execution handle the failure
elif IMPORTS_SUCCESSFUL:
    # Already initialized (e.g., in a warm instance)
    db = firestore.client() # Ensure db is assigned
    print("***** TOP LEVEL: Firebase Admin already initialized. *****")
    logger.info("Firebase Admin already initialized at top level.")
    FIREBASE_INITIALIZED = True # Assume it's good if apps exist

import functions_framework
import sys

# Minimal logging setup just in case
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True)
logger = logging.getLogger(__name__)

@functions_framework.http
def run_signal_generation(request):
    """Minimal function to test logging."""
    message = "***** MINIMAL FUNCTION EXECUTING *****"
    print(message) # Try basic print
    logger.info(message) # Try logging
    return "Minimal function executed.", 200

# # Local testing entry point (optional)
# if __name__ == '__main__':
#      # Mock request object for local testing if needed
#      class MockRequest:
#          args = {}
#          def get_json(self, silent=False):
#              return {}
#
#      # Set environment variables locally if not using ADC for local runs
#      # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'path/to/your/service-account-file.json'
#      # os.environ['TELEGRAM_BOT_TOKEN'] = 'your_token'
#      # os.environ['TELEGRAM_CHAT_ID'] = 'your_chat_id'
#      # os.environ['GEMINI_API_KEY'] = 'your_gemini_key' # Needed if not hardcoding confidence
#      # os.environ['CRYPTOCOMPARE_API_KEY'] = 'your_cryptocompare_key' # If needed by Kraken API wrapper or other parts
#
#      print("Running locally...")
#      run_signal_generation(MockRequest())
