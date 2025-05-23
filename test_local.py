#!/usr/bin/env python3
"""
Simple local testing script for debugging the crypto signal generation function
"""

import os
import sys
import logging
from datetime import datetime

def setup_logging():
    """Setup basic logging for local testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def test_imports():
    """Test if all required imports work"""
    print("=== Testing Imports ===")
    try:
        # Add functions directory to path
        functions_path = os.path.join(os.path.dirname(__file__), 'functions')
        if functions_path not in sys.path:
            sys.path.insert(0, functions_path)
        
        # Test imports
        import functions.config as config
        print(f"✓ Config loaded - LOG_LEVEL: {config.LOG_LEVEL}")
        
        from functions.kraken_api import fetch_kline_data
        print("✓ Kraken API import successful")
        
        from functions.technical_analysis import analyze_technicals
        print("✓ Technical analysis import successful")
        
        # Test a basic API call
        print("\n=== Testing Basic API Call ===")
        test_pair = "PF_XBTUSD"
        kline_data = fetch_kline_data(test_pair)
        if kline_data:
            print(f"✓ Successfully fetched {len(kline_data)} data points for {test_pair}")
            print(f"Sample data point: {kline_data[-1]}")
        else:
            print("✗ Failed to fetch kline data")
            
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_volume_analysis():
    """Test volume analysis specifically"""
    print("\n=== Testing Volume Analysis ===")
    try:
        # Add functions directory to path
        functions_path = os.path.join(os.path.dirname(__file__), 'functions')
        if functions_path not in sys.path:
            sys.path.insert(0, functions_path)
            
        from functions.kraken_api import fetch_kline_data
        from functions.technical_analysis import analyze_technicals, analyze_volume
        import pandas as pd
        
        # Get data for Bitcoin
        test_pair = "PF_XBTUSD"
        kline_data = fetch_kline_data(test_pair)
        
        if not kline_data:
            print("✗ No data to analyze")
            return
            
        # Convert to DataFrame for volume analysis
        df = pd.DataFrame(kline_data)
        if 'volume' in df.columns:
            volume_analysis = analyze_volume(df)
            print(f"Volume analysis result: {volume_analysis}")
            
            # Calculate volume statistics
            recent_volume = df['volume'].tail(20).mean()
            historical_avg = df['volume'].mean()
            volume_ratio = recent_volume / historical_avg if historical_avg > 0 else 0
            
            print(f"Recent 20-period volume avg: {recent_volume:.2f}")
            print(f"Historical average volume: {historical_avg:.2f}") 
            print(f"Volume ratio (recent/historical): {volume_ratio:.2f}")
            
            # Show volume distribution
            volume_percentiles = df['volume'].quantile([0.25, 0.5, 0.75, 0.9, 0.95]).round(2)
            print(f"Volume percentiles: {volume_percentiles.to_dict()}")
            
        else:
            print("✗ No volume data in kline data")
            
    except Exception as e:
        print(f"✗ Volume analysis failed: {e}")
        import traceback
        traceback.print_exc()

def analyze_current_volume_patterns():
    """Analyze current volume patterns across multiple coins"""
    print("\n=== Current Volume Pattern Analysis ===")
    try:
        functions_path = os.path.join(os.path.dirname(__file__), 'functions')
        if functions_path not in sys.path:
            sys.path.insert(0, functions_path)
            
        import functions.config as config
        from functions.kraken_api import fetch_kline_data
        import pandas as pd
        
        volume_stats = {}
        
        for coin in config.TRACKED_COINS[:5]:  # Test first 5 coins
            print(f"\nAnalyzing {coin}...")
            kline_data = fetch_kline_data(coin)
            
            if kline_data:
                df = pd.DataFrame(kline_data)
                if 'volume' in df.columns and len(df) > 50:
                    # Volume metrics
                    recent_20 = df['volume'].tail(20).mean()
                    recent_50 = df['volume'].tail(50).mean()
                    historical = df['volume'].mean()
                    
                    # Price change context
                    price_change_1h = ((df['close'].iloc[-1] - df['close'].iloc[-13]) / df['close'].iloc[-13]) * 100 if len(df) >= 13 else 0
                    price_change_4h = ((df['close'].iloc[-1] - df['close'].iloc[-49]) / df['close'].iloc[-49]) * 100 if len(df) >= 49 else 0
                    
                    volume_stats[coin] = {
                        'recent_20_avg': recent_20,
                        'recent_50_avg': recent_50,
                        'historical_avg': historical,
                        'ratio_20_hist': recent_20 / historical if historical > 0 else 0,
                        'ratio_50_hist': recent_50 / historical if historical > 0 else 0,
                        'price_change_1h': price_change_1h,
                        'price_change_4h': price_change_4h,
                        'current_volume': df['volume'].iloc[-1],
                        'volume_spike': df['volume'].iloc[-1] / historical if historical > 0 else 0
                    }
                    
        # Print analysis
        print("\n" + "="*80)
        print("VOLUME ANALYSIS SUMMARY")
        print("="*80)
        for coin, stats in volume_stats.items():
            print(f"\n{coin}:")
            print(f"  Current volume spike: {stats['volume_spike']:.2f}x historical")
            print(f"  Recent 20 vs historical: {stats['ratio_20_hist']:.2f}x")
            print(f"  Price change 1h: {stats['price_change_1h']:.2f}%")
            print(f"  Price change 4h: {stats['price_change_4h']:.2f}%")
            
            # Flag interesting patterns
            if stats['volume_spike'] > 2.0:
                print(f"  🔥 HIGH VOLUME SPIKE: {stats['volume_spike']:.2f}x")
            if stats['ratio_20_hist'] > 1.5:
                print(f"  📈 ELEVATED RECENT VOLUME: {stats['ratio_20_hist']:.2f}x")
            if abs(stats['price_change_1h']) > 2:
                print(f"  ⚡ SIGNIFICANT PRICE MOVE: {stats['price_change_1h']:.2f}%")
                
    except Exception as e:
        print(f"✗ Volume pattern analysis failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main test function"""
    print("🚀 CRYPTO SIGNAL TRACKER - LOCAL TESTING")
    print("=" * 50)
    
    setup_logging()
    
    # Run tests
    if test_imports():
        test_volume_analysis()
        analyze_current_volume_patterns()
    
    print("\n" + "=" * 50)
    print("✅ Local testing complete!")

if __name__ == "__main__":
    main() 