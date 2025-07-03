import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import joblib

logger = logging.getLogger(__name__)

@dataclass
class PatternFeatures:
    # Price action features
    body_ratio: float  # Candle body to range ratio
    upper_wick_ratio: float
    lower_wick_ratio: float
    close_position: float  # Position of close within the range
    
    # Volume features
    volume_ratio: float  # Current volume vs MA
    volume_trend: float  # Volume trend direction
    
    # Momentum features
    rsi: float
    macd_hist: float
    momentum_score: float
    
    # Multi-timeframe features
    h1_trend: float
    m5_momentum: float
    m1_signal: float
    
    # Outcome
    future_return: float  # Forward-looking return
    success: bool  # Whether pattern led to profitable trade

class PatternAnalyzer:
    def __init__(self, min_profit_threshold=0.004):
        self.min_profit_threshold = min_profit_threshold
        self.timeframes = ['1m', '5m', '1h']
        self.pattern_clusters = None
        self.feature_scaler = None
        
    def extract_features(self, df_dict: Dict[str, pd.DataFrame], idx: int) -> PatternFeatures:
        """Extract pattern features from multiple timeframes."""
        m1_data = df_dict['1m']
        m5_data = df_dict['5m']
        h1_data = df_dict['1h']
        
        # Current candle data
        current = m1_data.iloc[idx]
        
        # Price action features
        body = abs(current['close'] - current['open'])
        total_range = current['high'] - current['low']
        body_ratio = body / total_range if total_range != 0 else 0
        
        upper_wick = current['high'] - max(current['open'], current['close'])
        lower_wick = min(current['open'], current['close']) - current['low']
        
        close_position = (current['close'] - current['low']) / total_range if total_range != 0 else 0.5
        
        # Volume features
        volume_ma = m1_data['volume'].rolling(20).mean()
        volume_ratio = current['volume'] / volume_ma.iloc[idx] if volume_ma.iloc[idx] != 0 else 1
        volume_trend = np.sign(m1_data['volume'].iloc[idx-5:idx].diff().mean())
        
        # Momentum features
        rsi = self._calculate_rsi(m1_data['close'])
        macd_hist = self._calculate_macd_histogram(m1_data['close'])
        momentum_score = self._calculate_momentum_score(m1_data, idx)
        
        # Multi-timeframe features
        h1_trend = self._calculate_trend(h1_data['close'])
        m5_momentum = self._calculate_momentum_score(m5_data, -1)  # Latest 5m candle
        m1_signal = self._calculate_signal_strength(m1_data, idx)
        
        # Calculate forward-looking return (next 60 minutes)
        future_return = self._calculate_future_return(m1_data, idx)
        success = future_return >= self.min_profit_threshold
        
        return PatternFeatures(
            body_ratio=body_ratio,
            upper_wick_ratio=upper_wick/body if body != 0 else 0,
            lower_wick_ratio=lower_wick/body if body != 0 else 0,
            close_position=close_position,
            volume_ratio=volume_ratio,
            volume_trend=volume_trend,
            rsi=rsi.iloc[idx],
            macd_hist=macd_hist.iloc[idx],
            momentum_score=momentum_score,
            h1_trend=h1_trend,
            m5_momentum=m5_momentum,
            m1_signal=m1_signal,
            future_return=future_return,
            success=success
        )
        
    def _calculate_rsi(self, prices: pd.Series, period=14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def _calculate_macd_histogram(self, prices: pd.Series) -> pd.Series:
        """Calculate MACD histogram."""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd - signal
        
    def _calculate_momentum_score(self, df: pd.DataFrame, idx: int) -> float:
        """Calculate combined momentum score."""
        close = df['close']
        
        # Price momentum
        returns = close.pct_change()
        mom_1 = returns.iloc[idx]
        mom_5 = returns.iloc[idx-5:idx].mean()
        
        # Volume momentum
        vol_ratio = df['volume'].iloc[idx] / df['volume'].iloc[idx-5:idx].mean()
        
        # Combine scores
        return 0.4 * np.sign(mom_1) + 0.4 * np.sign(mom_5) + 0.2 * np.sign(vol_ratio - 1)
        
    def _calculate_trend(self, prices: pd.Series) -> float:
        """Calculate trend strength using EMA slope."""
        ema = prices.ewm(span=20).mean()
        slope = (ema.iloc[-1] - ema.iloc[-2]) / ema.iloc[-2]
        return slope
        
    def _calculate_signal_strength(self, df: pd.DataFrame, idx: int) -> float:
        """Calculate entry signal strength."""
        # Combine multiple factors
        momentum = self._calculate_momentum_score(df, idx)
        volume_impact = np.log(df['volume'].iloc[idx] / df['volume'].iloc[idx-20:idx].mean())
        price_impact = abs(df['close'].iloc[idx] - df['open'].iloc[idx]) / df['close'].iloc[idx]
        
        return (0.4 * momentum + 0.3 * volume_impact + 0.3 * price_impact)
        
    def _calculate_future_return(self, df: pd.DataFrame, idx: int) -> float:
        """Calculate maximum return in next 60 minutes."""
        if idx + 60 >= len(df):
            return 0
            
        entry_price = df['close'].iloc[idx]
        future_prices = df['close'].iloc[idx+1:idx+61]
        
        max_price = future_prices.max()
        min_price = future_prices.min()
        
        long_return = (max_price - entry_price) / entry_price
        short_return = (entry_price - min_price) / entry_price
        
        return max(long_return, short_return)
        
    def analyze_patterns(self, df_dict: Dict[str, pd.DataFrame]) -> List[Dict]:
        """Analyze and cluster patterns in the data."""
        logger.info("Starting pattern analysis...")
        features_list = []
        trade_durations = []
        pattern_timestamps = []
        
        # Extract features for each potential entry point
        for i in range(60, len(df_dict['1m']) - 60):  # Need history and future data
            try:
                features = self.extract_features(df_dict, i)
                if features is not None:
                    features_list.append(features)
                    
                    # Calculate trade duration
                    if features.success:
                        entry_time = df_dict['1m'].index[i]
                        exit_idx = self._find_exit_point(df_dict['1m'], i)
                        exit_time = df_dict['1m'].index[exit_idx]
                        duration = (exit_time - entry_time).total_seconds() / 60  # in minutes
                        trade_durations.append(duration)
                        pattern_timestamps.append(entry_time)
                        
            except Exception as e:
                logger.error(f"Error extracting features at index {i}: {e}")
                continue
                
        if not features_list:
            logger.warning("No features extracted!")
            return []
            
        logger.info(f"Extracted {len(features_list)} feature sets")
        
        # Convert to numpy array for clustering
        feature_array = np.array([[
            f.body_ratio, f.upper_wick_ratio, f.lower_wick_ratio,
            f.close_position, f.volume_ratio, f.volume_trend,
            f.rsi, f.macd_hist, f.momentum_score,
            f.h1_trend, f.m5_momentum, f.m1_signal
        ] for f in features_list])
        
        # Scale features
        if self.feature_scaler is None:
            self.feature_scaler = StandardScaler()
            scaled_features = self.feature_scaler.fit_transform(feature_array)
        else:
            scaled_features = self.feature_scaler.transform(feature_array)
            
        # Cluster patterns - more lenient parameters
        if self.pattern_clusters is None:
            self.pattern_clusters = DBSCAN(
                eps=0.5,  # Increased from 0.3
                min_samples=3  # Reduced from 5
            )
            
        clusters = self.pattern_clusters.fit_predict(scaled_features)
        unique_clusters = set(clusters)
        logger.info(f"Found {len(unique_clusters) - 1} clusters")  # -1 for noise
        
        # Analyze success rate for each cluster
        pattern_stats = {}
        for cluster_id in unique_clusters:
            if cluster_id == -1:  # Noise points
                continue
                
            cluster_indices = [i for i, c in enumerate(clusters) if c == cluster_id]
            cluster_features = [features_list[i] for i in cluster_indices]
            
            # Calculate success metrics
            successes = [f for f in cluster_features if f.success]
            success_rate = len(successes) / len(cluster_features)
            avg_return = np.mean([f.future_return for f in cluster_features])
            
            # Calculate trade durations for successful trades
            cluster_durations = [trade_durations[i] for i in cluster_indices 
                               if features_list[i].success]
            
            # Time of day analysis
            trade_times = [pattern_timestamps[i].hour for i in cluster_indices 
                          if features_list[i].success]
            
            # Calculate feature correlations with success
            feature_names = [
                'Body Ratio', 'Upper Wick', 'Lower Wick', 'Close Position',
                'Volume Ratio', 'Volume Trend', 'RSI', 'MACD Hist',
                'Momentum Score', '1H Trend', '5M Momentum', '1M Signal'
            ]
            
            # Calculate average feature values for successful vs failed trades
            success_features = np.mean([
                [f.body_ratio, f.upper_wick_ratio, f.lower_wick_ratio,
                 f.close_position, f.volume_ratio, f.volume_trend,
                 f.rsi, f.macd_hist, f.momentum_score,
                 f.h1_trend, f.m5_momentum, f.m1_signal]
                for f in cluster_features if f.success
            ], axis=0)
            
            failed_features = np.mean([
                [f.body_ratio, f.upper_wick_ratio, f.lower_wick_ratio,
                 f.close_position, f.volume_ratio, f.volume_trend,
                 f.rsi, f.macd_hist, f.momentum_score,
                 f.h1_trend, f.m5_momentum, f.m1_signal]
                for f in cluster_features if not f.success
            ], axis=0) if len(cluster_features) > len(successes) else None
            
            logger.info(f"Cluster {cluster_id}: {len(cluster_features)} patterns, "
                       f"{success_rate:.1%} success rate, {avg_return:.2%} avg return")
            
            # More lenient success criteria
            if success_rate >= 0.7 and avg_return >= self.min_profit_threshold:  # Reduced from 0.8
                pattern_stats[cluster_id] = {
                    'success_rate': success_rate,
                    'avg_return': avg_return,
                    'count': len(cluster_features),
                    'features': np.mean(feature_array[clusters == cluster_id], axis=0),
                    'avg_duration': np.mean(cluster_durations) if cluster_durations else 0,
                    'min_duration': np.min(cluster_durations) if cluster_durations else 0,
                    'max_duration': np.max(cluster_durations) if cluster_durations else 0,
                    'time_distribution': {h: trade_times.count(h) for h in range(24)},
                    'feature_importance': dict(zip(feature_names, success_features)),
                    'failed_features': dict(zip(feature_names, failed_features)) if failed_features is not None else None,
                    'entry_timestamps': [pattern_timestamps[i] for i in cluster_indices if features_list[i].success],
                    'returns_distribution': {
                        'min': np.min([f.future_return for f in successes]),
                        'max': np.max([f.future_return for f in successes]),
                        'std': np.std([f.future_return for f in successes]),
                        'quartiles': np.percentile([f.future_return for f in successes], [25, 50, 75])
                    }
                }
                
        logger.info(f"Found {len(pattern_stats)} successful pattern clusters")
        return pattern_stats
        
    def _find_exit_point(self, df: pd.DataFrame, entry_idx: int) -> int:
        """Find the exit point for a trade."""
        entry_price = df['close'].iloc[entry_idx]
        max_return = 0
        exit_idx = entry_idx
        
        for i in range(entry_idx + 1, min(entry_idx + 61, len(df))):
            current_return = (df['close'].iloc[i] - entry_price) / entry_price
            if current_return > max_return:
                max_return = current_return
                exit_idx = i
                
        return exit_idx
        
    def save_model(self, filepath: str):
        """Save the trained pattern recognition model."""
        model_data = {
            'feature_scaler': self.feature_scaler,
            'pattern_clusters': self.pattern_clusters
        }
        joblib.dump(model_data, filepath)
        
    def load_model(self, filepath: str):
        """Load a trained pattern recognition model."""
        model_data = joblib.load(filepath)
        self.feature_scaler = model_data['feature_scaler']
        self.pattern_clusters = model_data['pattern_clusters']
        
    def match_current_pattern(self, df_dict: Dict[str, pd.DataFrame]) -> Tuple[bool, float, str]:
        """Check if current market conditions match any successful pattern."""
        if self.pattern_clusters is None or self.feature_scaler is None:
            return False, 0, "Model not trained"
            
        try:
            current_features = self.extract_features(df_dict, -1)
            feature_vector = np.array([[
                current_features.body_ratio, current_features.upper_wick_ratio,
                current_features.lower_wick_ratio, current_features.close_position,
                current_features.volume_ratio, current_features.volume_trend,
                current_features.rsi, current_features.macd_hist,
                current_features.momentum_score, current_features.h1_trend,
                current_features.m5_momentum, current_features.m1_signal
            ]])
            
            scaled_features = self.feature_scaler.transform(feature_vector)
            cluster = self.pattern_clusters.predict(scaled_features)[0]
            
            if cluster != -1:  # If pattern matches a known cluster
                confidence = self._calculate_pattern_confidence(scaled_features, cluster)
                return True, confidence, f"Pattern {cluster} matched with {confidence:.1%} confidence"
                
            return False, 0, "No matching pattern found"
            
        except Exception as e:
            logger.error(f"Error matching pattern: {e}")
            return False, 0, str(e)
            
    def _calculate_pattern_confidence(self, features: np.ndarray, cluster_id: int) -> float:
        """Calculate confidence score for pattern match."""
        # Get cluster center
        cluster_center = np.mean(
            self.feature_scaler.transform(self.pattern_clusters.components_[cluster_id].reshape(1, -1)),
            axis=0
        )
        
        # Calculate distance to cluster center
        distance = np.linalg.norm(features - cluster_center)
        
        # Convert distance to confidence score (1.0 = perfect match, 0.0 = poor match)
        confidence = np.exp(-distance)
        
        return min(0.98, max(0.0, confidence))  # Cap at 98% confidence 