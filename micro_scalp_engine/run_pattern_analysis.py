import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ccxt
import logging
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
import json
from pattern_analyzer import PatternAnalyzer
from trade_analyzer import TradeAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiCoinAnalyzer:
    def __init__(self):
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'LINKUSDT', 'ADAUSDT',
            'XRPUSDT', 'AVAXUSDT', 'MATICUSDT', 'DOTUSDT', 'ATOMUSDT'
        ]
        self.timeframes = ['1m', '5m', '1h']
        self.analyzer = PatternAnalyzer(min_profit_threshold=0.004)
        self.trade_analyzer = TradeAnalyzer(initial_capital=10000)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
    def load_data(self, symbol: str, days: int = 90) -> Dict[str, pd.DataFrame]:
        """Load historical data for all timeframes."""
        logger.info(f"Loading data for {symbol}")
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        data_dict = {}
        for tf in self.timeframes:
            # Calculate required number of candles
            if tf == '1m':
                limit = min(1000, days * 24 * 60)
            elif tf == '5m':
                limit = min(1000, days * 24 * 12)
            else:  # 1h
                limit = min(1000, days * 24)
                
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe=tf,
                    since=int(start.timestamp() * 1000),
                    limit=limit
                )
                
                df = pd.DataFrame(
                    candles,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                data_dict[tf] = df
                
            except Exception as e:
                logger.error(f"Error fetching {tf} data for {symbol}: {e}")
                return None
                
        return data_dict
        
    def analyze_coin(self, symbol: str) -> Dict:
        """Analyze patterns and simulate trades for a single coin."""
        data_dict = self.load_data(symbol)
        if data_dict is None:
            return None
            
        try:
            # Find patterns
            patterns = self.analyzer.analyze_patterns(data_dict)
            
            # Save the trained model
            model_dir = Path('trained_models')
            model_dir.mkdir(exist_ok=True)
            self.analyzer.save_model(model_dir / f'{symbol}_pattern_model.joblib')
            
            # Extract successful trade entry points
            entry_points = []
            pattern_features = {}
            
            for pattern_id, stats in patterns.items():
                entry_points.extend(stats['entry_timestamps'])
                pattern_features[pattern_id] = stats['feature_importance']
                
            # Analyze different exit strategies
            trade_results = self.trade_analyzer.analyze_exit_strategies(
                data_dict['1m'],
                entry_points,
                pattern_features
            )
            
            # Generate trade reports
            output_dir = Path('analysis_results') / symbol
            self.trade_analyzer.generate_trade_report(trade_results, output_dir)
            
            return {
                'symbol': symbol,
                'patterns': patterns,
                'total_patterns': sum(p['count'] for p in patterns.values()),
                'avg_success_rate': np.mean([p['success_rate'] for p in patterns.values()]),
                'avg_return': np.mean([p['avg_return'] for p in patterns.values()]),
                'total_trades': sum(p['count'] for p in patterns.values()),
                'successful_trades': sum(
                    int(p['count'] * p['success_rate']) for p in patterns.values()
                ),
                'trade_results': trade_results
            }
            
        except Exception as e:
            logger.error(f"Error analyzing patterns for {symbol}: {e}")
            return None
            
    def run_analysis(self) -> List[Dict]:
        """Run pattern analysis on all coins in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.analyze_coin, symbol): symbol 
                      for symbol in self.symbols}
            
            for future in futures:
                symbol = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    
        return results
        
    def generate_report(self, results: List[Dict]):
        """Generate detailed analysis report."""
        report_dir = Path('analysis_results')
        report_dir.mkdir(exist_ok=True)
        
        # Generate summary report
        summary = []
        summary.append("=== Pattern Analysis Summary ===\n")
        
        total_trades = sum(r['total_trades'] for r in results)
        total_successful = sum(r['successful_trades'] for r in results)
        overall_success_rate = total_successful / total_trades if total_trades > 0 else 0
        
        summary.append(f"Total Patterns Analyzed: {total_trades}")
        summary.append(f"Total Successful Trades: {total_successful}")
        summary.append(f"Overall Success Rate: {overall_success_rate:.1%}\n")
        
        # Generate detailed coin reports
        for result in results:
            symbol = result['symbol']
            patterns = result['patterns']
            
            # Create coin-specific directory
            coin_dir = report_dir / symbol
            coin_dir.mkdir(exist_ok=True)
            
            # Save raw pattern data
            with open(coin_dir / 'pattern_data.json', 'w') as f:
                json.dump(patterns, f, indent=2, default=str)
            
            summary.append(f"\n=== {symbol} Analysis ===")
            summary.append(f"Total Successful Patterns: {result['total_patterns']}")
            summary.append(f"Average Success Rate: {result['avg_success_rate']:.1%}")
            summary.append(f"Average Return: {result['avg_return']:.2%}")
            
            summary.append("\nTop Performing Patterns:")
            # Sort patterns by success rate * average return
            sorted_patterns = sorted(
                patterns.items(),
                key=lambda x: x[1]['success_rate'] * x[1]['avg_return'],
                reverse=True
            )
            
            for pattern_id, stats in sorted_patterns[:5]:  # Top 5 patterns
                summary.append(f"\nPattern {pattern_id}:")
                summary.append(f"  Success Rate: {stats['success_rate']:.1%}")
                summary.append(f"  Average Return: {stats['avg_return']:.2%}")
                summary.append(f"  Trade Count: {stats['count']}")
                summary.append(f"  Average Duration: {stats['avg_duration']:.1f} minutes")
                summary.append(f"  Return Distribution:")
                summary.append(f"    Min: {stats['returns_distribution']['min']:.2%}")
                summary.append(f"    Max: {stats['returns_distribution']['max']:.2%}")
                summary.append(f"    Std Dev: {stats['returns_distribution']['std']:.2%}")
                
                # Most important features
                summary.append("\n  Key Features (Success vs Failure):")
                feature_diff = {
                    k: stats['feature_importance'][k] - stats['failed_features'][k]
                    for k in stats['feature_importance'].keys()
                } if stats['failed_features'] is not None else stats['feature_importance']
                
                sorted_features = sorted(
                    feature_diff.items(),
                    key=lambda x: abs(x[1]),
                    reverse=True
                )
                
                for feature, value in sorted_features[:5]:
                    if stats['failed_features'] is not None:
                        summary.append(
                            f"    {feature}: {stats['feature_importance'][feature]:.3f} vs "
                            f"{stats['failed_features'][feature]:.3f}"
                        )
                    else:
                        summary.append(f"    {feature}: {value:.3f}")
                        
                # Time distribution
                peak_hours = sorted(
                    stats['time_distribution'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                
                summary.append("\n  Best Trading Hours (UTC):")
                for hour, count in peak_hours:
                    summary.append(f"    {hour:02d}:00 - {count} trades")
                    
            # Add exit strategy comparison
            summary.append("\nExit Strategy Comparison:")
            for strategy, results in result['trade_results'].items():
                trades_df = results['trades']
                summary.append(f"\n{strategy}:")
                summary.append(f"  Win Rate: {(trades_df['profit_pct'] > 0).mean():.1%}")
                summary.append(f"  Average Profit: {trades_df['profit_pct'].mean():.2%}")
                summary.append(f"  Average Duration: {trades_df['duration_minutes'].mean():.1f} minutes")
                summary.append(f"  Upside Capture: {trades_df['captured_upside_pct'].mean():.1%}")
                summary.append(f"  Total Return: {results['total_return']:.2%}")
                
        # Write summary report
        with open(report_dir / 'pattern_analysis_summary.txt', 'w') as f:
            f.write('\n'.join(summary))
            
def main():
    """Run pattern analysis across all coins."""
    analyzer = MultiCoinAnalyzer()
    results = analyzer.run_analysis()
    analyzer.generate_report(results)
    
if __name__ == '__main__':
    main() 