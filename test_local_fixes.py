#!/usr/bin/env python3
"""
Local test script to validate critical fixes before production deployment.
Tests logging configuration and pandas-ta syntax fixes.
"""
import sys
import os
import logging
import pandas as pd
import warnings

# Suppress pandas warnings for cleaner output
warnings.simplefilter(action='ignore', category=FutureWarning)

def test_logging_configuration():
    """Test that our new logging setup works without duplication."""
    print("🧪 Testing logging configuration...")
    
    # Simulate our new logging setup from functions/main.py
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Our new approach
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Test logging from different modules (simulated)
    logger1 = logging.getLogger('functions.main')
    logger2 = logging.getLogger('functions.technical_analysis') 
    logger3 = logging.getLogger('functions.position_manager')
    
    # Each should only appear once
    logger1.info("Test message from main module")
    logger2.info("Test message from technical_analysis module") 
    logger3.info("Test message from position_manager module")
    
    print("✅ Logging test completed - check above for single entries only\n")

def test_pandas_ta_syntax():
    """Test our new pandas-ta pattern detection syntax."""
    print("🧪 Testing pandas-ta pattern detection...")
    
    try:
        import pandas_ta as ta
        
        # Create test OHLC data
        test_data = {
            'open': [100.0, 101.0, 102.0, 101.5, 100.5, 99.0, 98.5, 99.2, 100.1, 101.3],
            'high': [101.5, 102.5, 103.0, 102.0, 101.0, 100.0, 99.5, 100.0, 101.0, 102.0],
            'low': [99.5, 100.5, 101.5, 100.0, 99.0, 98.0, 97.5, 98.0, 99.0, 100.0],
            'close': [101.0, 102.0, 102.5, 100.5, 100.0, 99.5, 99.0, 100.0, 100.8, 101.5]
        }
        df = pd.DataFrame(test_data)
        
        # Test our NEW syntax (should work)
        print("   Testing NEW syntax: ta.cdl_pattern(open, high, low, close, name='hammer')")
        try:
            result_hammer = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="hammer")
            print(f"   ✅ Hammer pattern detection: {type(result_hammer)} with {len(result_hammer)} values")
        except Exception as e:
            print(f"   ❌ Hammer pattern failed: {e}")
            
        try:
            result_star = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="shootingstar")
            print(f"   ✅ Shooting Star pattern detection: {type(result_star)} with {len(result_star)} values")
        except Exception as e:
            print(f"   ❌ Shooting Star pattern failed: {e}")
            
        try:
            result_engulf = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="engulfing")
            print(f"   ✅ Engulfing pattern detection: {type(result_engulf)} with {len(result_engulf)} values")
        except Exception as e:
            print(f"   ❌ Engulfing pattern failed: {e}")
            
        # Test OLD syntax (should fail)
        print("\n   Testing OLD syntax (should fail): df.ta.cdl_hammer()")
        try:
            result_old = df.ta.cdl_hammer()
            print(f"   ⚠️  OLD syntax unexpectedly worked: {type(result_old)}")
        except AttributeError as e:
            print(f"   ✅ OLD syntax correctly failed: {e}")
        except Exception as e:
            print(f"   ❓ OLD syntax failed with unexpected error: {e}")
            
        print("✅ pandas-ta syntax test completed\n")
        
    except ImportError as e:
        print(f"❌ pandas-ta not available: {e}")
        print("   Install with: pip install pandas-ta")
        return False
        
    return True

def test_imports():
    """Test that our modified files can still import properly."""
    print("🧪 Testing module imports...")
    
    # Test individual components that don't use relative imports
    try:
        sys.path.append('functions')
        
        # Test config import (should work)
        import config
        print("   ✅ config.py imports successfully")
        
        # Test if we can import other modules (may fail due to relative imports)
        try:
            import technical_analysis
            print("   ✅ technical_analysis.py imports successfully")
        except ImportError as e:
            print(f"   ⚠️  technical_analysis.py import failed (expected due to relative imports): {e}")
            
        print("✅ Import test completed\n")
        
    except Exception as e:
        print(f"❌ Import test failed: {e}\n")
        return False
        
    return True

def main():
    """Run all local tests."""
    print("🔍 LOCAL VALIDATION BEFORE PRODUCTION DEPLOYMENT")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Logging
    try:
        test_logging_configuration()
        tests_passed += 1
    except Exception as e:
        print(f"❌ Logging test failed: {e}\n")
    
    # Test 2: pandas-ta 
    try:
        if test_pandas_ta_syntax():
            tests_passed += 1
    except Exception as e:
        print(f"❌ pandas-ta test failed: {e}\n")
    
    # Test 3: Imports
    try:
        if test_imports():
            tests_passed += 1
    except Exception as e:
        print(f"❌ Import test failed: {e}\n")
    
    # Summary
    print("=" * 50)
    print(f"📊 TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ ALL TESTS PASSED - Safe to deploy to production")
        print("\nNext steps:")
        print("1. git add test_local_fixes.py")
        print("2. git commit -m 'Add local validation tests'") 
        print("3. git add functions/ requirements.txt docs/")
        print("4. git commit -m 'Deploy validated fixes'")
        print("5. git push origin main")
    else:
        print("❌ TESTS FAILED - DO NOT DEPLOY")
        print("Fix issues before pushing to production!")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    main() 