import os
import logging
import json
from google.cloud import firestore
from functions.signal_generator import process_crypto_data
import google.auth

# Configure logging to be clear and informative
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

def run_live_test():
    """
    Runs a live integration test of the signal generation logic for a list of symbols.
    This simulates the action of the GCP Cloud Function.
    """
    logging.info("Starting live strategy test...")

    # --- GCP Authentication ---
    # Let's explicitly check which credentials are being used.
    try:
        credentials, project_id = google.auth.default()
        if hasattr(credentials, 'service_account_email'):
            logging.info(f"AUTHENTICATING WITH SERVICE ACCOUNT: {credentials.service_account_email}")
        else: # It's likely a user credential
            logging.info(f"AUTHENTICATING WITH USER: {credentials.account if hasattr(credentials, 'account') else 'Unknown User'}")
        logging.info(f"TARGET PROJECT ID: {project_id}")
    except Exception as e:
        logging.error(f"Could not determine authentication credentials: {e}")
        credentials = None
        project_id = None
        return

    try:
        # Explicitly pass the discovered credentials to the client.
        # This removes any ambiguity about which identity is being used.
        db = firestore.Client(project=project_id, credentials=credentials)
        logging.info(f"Firestore client created successfully for project '{db.project}'.")
    except Exception as e:
        logging.error(f"Failed to create Firestore client: {e}", exc_info=True)
        return

    # List of symbols to test
    symbols_to_test = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'ADAUSDT', 'XRPUSDT', 'CROUSDT']
    logging.info(f"Will test the following symbols: {symbols_to_test}")

    for symbol in symbols_to_test:
        print("-" * 60)
        logging.info(f"--- Testing symbol: {symbol} ---")
        try:
            signal = process_crypto_data(symbol=symbol, db=db)
            if signal:
                logging.info(f"🚀 Signal generated for {symbol}: {json.dumps(signal, indent=2)}")
            else:
                logging.info(f"☑️ No signal generated for {symbol} at this time, as per the strategy rules.")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {symbol}: {e}", exc_info=True)
        finally:
            logging.info(f"--- Finished testing symbol: {symbol} ---\n")

    print("-" * 60)
    logging.info("Live strategy test run complete.")

if __name__ == "__main__":
    run_live_test() 