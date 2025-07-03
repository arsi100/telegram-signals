#!/usr/bin/env python3
"""
Test runner for macro-micro integration tests.
"""

import os
import sys
import logging
import unittest
from test_macro_integration import TestMacroIntegration

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Ensure GCP credentials are set
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        raise EnvironmentError(
            "GOOGLE_APPLICATION_CREDENTIALS environment variable not set. "
            "Please set it to point to your GCP service account key file."
        )
    
    logger.info("Starting macro-micro integration tests...")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMacroIntegration)
    
    # Run tests
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Exit with appropriate code
    sys.exit(not result.wasSuccessful()) 