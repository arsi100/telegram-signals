import pandas as pd
import logging
from market_move_analyzer import MarketMoveAnalyzer
from datetime import datetime, timedelta
import sys
sys.path.append('..')
from functions.bybit_api import fetch_kline_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_analysis(symbol: str, days: int = 90):
    """Run comprehensive market analysis for a given symbol."""
    
    try:
        # Get 5-minute candles
        kline_data = fetch_kline_data(
            symbol=symbol,
            interval="5",
            limit=days * 24 * 12,  # days * hours * 12 5-min candles per hour
            category="linear"
        )
        
        if not kline_data:
            logger.error(f"Failed to get kline data for {symbol}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(kline_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Convert string values to float
        for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Initialize analyzer
        analyzer = MarketMoveAnalyzer()
        
        # Run analysis
        results = analyzer.analyze_market(df, target_move_percent=0.5, max_lookback_minutes=60)
        
        # Print Pattern Analysis Results
        print(f"\nPattern Analysis Results for {symbol} over {days} days:")
        print("=" * 80)
        print(f"{'Pattern':<20} {'Total':<10} {'Success':<10} {'Rate %':<10} {'Fail %':<10}")
        print("-" * 80)
        
        for pattern, stats in results['pattern_stats'].items():
            print(f"{pattern:<20} {stats['total_occurrences']:<10} "
                  f"{stats['successful_predictions']:<10} "
                  f"{stats['success_rate_percent']:.2f}%     "
                  f"{stats['failure_rate_percent']:.2f}%")
                  
        # Print Move Analysis Results
        print(f"\nPrice Move Analysis Results:")
        print("=" * 80)
        move_stats = results['move_stats']
        print(f"Total 0.5%+ Moves: {move_stats['total_moves']}")
        print(f"Upward Moves: {move_stats['upward_moves']} ({move_stats['upward_moves']/move_stats['total_moves']*100:.1f}%)")
        print(f"Downward Moves: {move_stats['downward_moves']} ({move_stats['downward_moves']/move_stats['total_moves']*100:.1f}%)")
        print(f"Average Move Size: {move_stats['avg_move_size']:.2f}%")
        print(f"Maximum Move Size: {move_stats['max_move_size']:.2f}%")
        print(f"Average Time to Target: {move_stats['avg_time_to_target']:.1f} minutes")
        
        print("\nPatterns Present Before Moves:")
        print("-" * 80)
        for pattern, count in move_stats['patterns_present'].items():
            if count > 0:
                presence_rate = count / move_stats['total_moves'] * 100
                print(f"{pattern:<20} Present in {count} moves ({presence_rate:.1f}% of all moves)")
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        return None

if __name__ == "__main__":
    # List of symbols to analyze
    symbols = ["SOLUSDT"]  # Add more symbols as needed
    
    for symbol in symbols:
        run_analysis(symbol) 