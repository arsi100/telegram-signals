#!/usr/bin/env python3
"""
Simple local testing script for debugging the crypto signal generation function
"""

import os
import sys
import logging
from datetime import datetime
import unittest
from unittest.mock import MagicMock, patch
import firebase_admin
from firebase_admin import credentials, firestore

# Ensure the functions directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'functions')))

# Import the target function AFTER sys.path modification
from main import run_signal_generation 
from functions import config # To access config values if needed for mocks

# Configure logging for the test script
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class TestLocalRunSignalGeneration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up shared resources if any (e.g., initializing Firebase once)."""
        # Check if Firebase app is already initialized to prevent re-initialization errors
        if not firebase_admin._apps:
            try:
                # Try to initialize with default credentials (e.g., for local dev with gcloud auth)
                # For this test, we are primarily mocking Firestore, so real creds might not be strictly
                # necessary if all db interactions are perfectly mocked.
                # However, other parts of the code might implicitly try to use Firebase.
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': config.FIREBASE_PROJECT_ID or "test-project-id", # Use actual or a fallback
                })
                logger.info("Firebase Admin SDK initialized for testing.")
            except Exception as e:
                logger.warning(f"Could not initialize Firebase Admin SDK with ApplicationDefault: {e}. Firestore will be mocked.")
        else:
            logger.info("Firebase Admin SDK already initialized.")

    def setUp(self):
        """Set up mocks for each test method."""
        # Mock Firestore client and its methods
        self.mock_db = MagicMock(spec=firestore.Client)
        
        # Mock collection().document().get()
        self.mock_doc_ref = MagicMock()
        self.mock_doc_snapshot = MagicMock()
        self.mock_doc_ref.get.return_value = self.mock_doc_snapshot
        
        # Mock collection().where().stream()
        self.mock_collection_ref = MagicMock()
        self.mock_query = MagicMock()
        self.mock_collection_ref.where.return_value = self.mock_query
        self.mock_query.stream.return_value = [] # Default to no open positions

        self.mock_db.collection.return_value = self.mock_collection_ref
        
        # Specific mock for document creation/update paths (e.g., for cooldown or position recording)
        self.mock_db.collection.return_value.document.return_value.set.return_value = None # Mock .set()
        self.mock_db.collection.return_value.document.return_value.update.return_value = None # Mock .update()


        # Patch the firestore.client() to return our mock_db
        # This targets where `db = firestore.client()` would be called.
        # Assuming it's called within the modules under test, e.g. position_manager.py
        # We need to find the correct place to patch it. 
        # Let's assume it's imported as `from firebase_admin import firestore` and then `firestore.client()` is called.
        self.firestore_client_patcher = patch('firebase_admin.firestore.client', return_value=self.mock_db)
        self.mock_firestore_client = self.firestore_client_patcher.start()
        
        # Also patch direct instantiation if it happens like `firestore.Client()`
        self.firestore_Client_patcher_direct = patch('firebase_admin.firestore.Client', return_value=self.mock_db) # Note capital C
        self.mock_firestore_Client_direct = self.firestore_Client_patcher_direct.start()


        # Mock the request object for the HTTP-triggered function
        self.mock_request = MagicMock()
        self.mock_request.method = 'GET'
        self.mock_request.args = {}
        # Add a get_json method in case the function tries to parse a body (though GET usually doesn't have one)
        self.mock_request.get_json.return_value = {} 

    def tearDown(self):
        self.firestore_client_patcher.stop()
        self.firestore_Client_patcher_direct.stop()

    def test_run_signal_generation_live_apis(self):
        logger.info("Starting test_run_signal_generation_live_apis...")
        logger.info("This test uses LIVE Kraken and LunarCrush APIs. Ensure .env is configured.")

        # --- Configure mock Firestore responses ---
        # Default: No open positions, no cooldown
        self.mock_doc_snapshot.exists = False # For cooldown check (document does not exist)
        self.mock_query.stream.return_value = [] # For get_open_position (no documents found)

        # --- Call the function ---
        response_content, status_code = run_signal_generation(self.mock_request)

        # --- Assertions ---
        self.assertIsNotNone(response_content)
        self.assertIn(status_code, [200, 202]) # 200 for sync, 202 if it becomes async later
        
        logger.info(f"run_signal_generation responded with status {status_code}")
        logger.info(f"Response content: {response_content}")

        # Check if Firestore was interacted with (at least collections were accessed)
        self.mock_db.collection.assert_called() 
        
        # Add more specific assertions based on expected behavior with live data:
        # For example, check parts of the response_content string.
        # This is tricky with live data as signals may or may not generate.
        # The main purpose here is to ensure the pipeline runs end-to-end without crashing.
        self.assertTrue("Signal generation finished." in response_content)


if __name__ == '__main__':
    unittest.main() 