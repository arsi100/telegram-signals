import pandas as pd
import logging
from pattern_success_analyzer import PatternSuccessAnalyzer
from datetime import datetime, timedelta
import sys
sys.path.append('..')
from functions.kraken_api import get_kline_data_futures

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_analysis(symbol: str, days: int = 90):
    """Run pattern analysis for a given symbol over specified days."""
    
    # Get historical data
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    try:
        # Get 5-minute candles for the period
        kline_data = get_kline_data_futures(
            symbol=symbol,
            interval=5,
            start_time=int(start_time.timestamp()),
            end_time=int(end_time.timestamp())
        )
        
        if not kline_data:
            logger.error(f"Failed to get kline data for {symbol}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(kline_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Convert string values to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # Initialize analyzer
        analyzer = PatternSuccessAnalyzer(lookback_window_minutes=60)  # 60-minute window
        
        # Run analysis
        results = analyzer.analyze_pattern_success(df, target_move_percent=0.5)
        
        # Print results
        print(f"\nPattern Analysis Results for {symbol} over {days} days:")
        print("=" * 80)
        print(f"{'Pattern':<20} {'Total':<10} {'Success':<10} {'Rate %':<10} {'Fail %':<10}")
        print("-" * 80)
        
        for pattern, stats in results.items():
            print(f"{pattern:<20} {stats['total_occurrences']:<10} "
                  f"{stats['successful_predictions']:<10} "
                  f"{stats['success_rate_percent']:.2f}%     "
                  f"{stats['failure_rate_percent']:.2f}%")
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        return None

if __name__ == "__main__":
    # List of symbols to analyze
    symbols = ["PF_SOLUSD"]  # Add more symbols as needed
    
    for symbol in symbols:
        run_analysis(symbol) 