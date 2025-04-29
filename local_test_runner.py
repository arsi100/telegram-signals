print("--- Script Start ---")
import os
import sys
import logging
import firebase_admin
from firebase_admin import firestore, credentials

print("--- Basic imports done ---")

# Add the 'functions' directory to the Python path
# This allows us to import modules from the functions directory
# when running this script from the project root.
functions_path = os.path.join(os.path.dirname(__file__), 'functions')
if functions_path not in sys.path:
    sys.path.insert(0, functions_path)
print(f"--- functions path added: {functions_path} ---")
print(f"--- sys.path: {sys.path} ---")


# Now we can import from 'functions'
# Important: Make sure config loads .env before other modules use it
# Explicitly import config from the functions package
print("--- Importing functions.config --- ")
from functions import config 
print("--- Importing functions.main --- ")
from functions.main import run_signal_generation
print("--- Importing firebase_admin --- ")
import firebase_admin # Need this to check initialization
print("--- All Imports Done ---")


# --- Initialize Firebase Explicitly Here ---
print("--- Initializing Firebase Admin SDK --- ")
_db_client = None # Use temporary name to avoid conflict
try:
    if not firebase_admin._apps:
        # Assumes GOOGLE_APPLICATION_CREDENTIALS is set in environment
        firebase_admin.initialize_app() 
        print("--- firebase_admin.initialize_app() called --- ")
    else:
        print("--- firebase_admin already initialized --- ")
        
    # Explicitly pass project ID when getting client
    project_id = config.FIREBASE_PROJECT_ID
    if not project_id:
        raise ValueError("FIREBASE_PROJECT_ID not found in config/.env")
    print(f"--- Attempting to get Firestore client for database: signals-db ---")
    # Explicitly specify the database ID using the correct argument name
    _db_client = firestore.client(database_id='signals-db')
    
    print(f"--- Firestore client obtained: {_db_client} --- ")
    # Inject the db client into the main module
    # This relies on functions.main being imported already
    import functions.main 
    functions.main.db = _db_client 
    print(f"--- Injected db_client into functions.main.db --- ")
    logger = logging.getLogger(__name__) # Get logger after basicConfig potentially runs
    logger.info("Firebase initialized successfully in test runner.")
except Exception as e:
    logger = logging.getLogger(__name__) # Get logger to log error
    logger.error(f"Failed to initialize Firebase in test runner: {e}", exc_info=True)
    print(f"--- Firebase Initialization FAILED in test runner: {e} --- ")
    sys.exit(1) # Exit if Firebase fails
# --- End Firebase Initialization ---


# Configure logging EXPLICITLY for local testing
# (Moved after Firebase init attempt to capture init logs better)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)
logger = logging.getLogger(__name__) # Re-get logger for this module if needed
print("--- Logging Configured ---")

def run_local_test():
    """
    Simulates the Cloud Function trigger for local testing.
    """
    print("--- Entering run_local_test() --- ")
    logger.info("--- Starting Local Test Run ---")

    # Check if Firebase was initialized successfully above
    # Access the injected db from the main module to check
    import functions.main 
    if functions.main.db is None:
        logger.error("Firebase db client is None after initialization attempt. Cannot proceed.")
        print("--- Exiting run_local_test() due to DB initialization failure --- ")
        return 
    else:
        print("--- Firebase App Check OK (db injected) --- ")

    # Simulate the request object
    mock_request = None 

    try:
        # Call the main function logic (it will use its own global db)
        print("--- Calling run_signal_generation --- ")
        result = functions.main.run_signal_generation(mock_request)
        print("--- run_signal_generation Finished --- ")
        logger.info(f"--- Local Test Run Finished ---")
        logger.info(f"Result: {result}")
        
    except Exception as e:
        logger.error(f"An error occurred during the local test run: {e}", exc_info=True)
        print(f"--- run_signal_generation FAILED: {e} --- ")
        logger.info(f"--- Local Test Run Failed ---")

if __name__ == "__main__":
    print("--- Running main block --- ")
    run_local_test()
    print("--- Script End ---") 