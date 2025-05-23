import logging
import requests
import datetime
import pytz
import time
from typing import Dict, Optional, Tuple
from . import config

# Configure logging
logger = logging.getLogger(__name__)

class LunarCrushAPI:
    """LunarCrush API integration for sentiment analysis."""
    
    BASE_URL = "https://api.lunarcrush.com/v3"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        })
        
    def get_coin_metrics(self, symbol: str) -> Optional[Dict]:
        """
        Fetch sentiment metrics for a specific coin from LunarCrush.
        
        Args:
            symbol: The coin symbol (e.g., 'bitcoin', 'ethereum')
            
        Returns:
            Dict containing sentiment metrics or None if request fails
        """
        try:
            url = f"{self.BASE_URL}/coins/{symbol}"
            params = {
                'data_points': 1,  # We only need the latest data point
                'interval': '1h',  # 1-hour interval for latest data
                'key': self.api_key
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('data'):
                logger.warning(f"No data returned for {symbol}")
                return None
                
            coin_data = data['data'][0]
            
            # Extract relevant metrics
            metrics = {
                'average_sentiment_score': coin_data.get('average_sentiment_score', 3.0),
                'social_impact_score': coin_data.get('social_impact_score', 3.0),
                'galaxy_score': coin_data.get('galaxy_score', 50.0),
                'social_volume': coin_data.get('social_volume', 0.0),
                'social_volume_change_24h': coin_data.get('social_volume_change_24h', 0.0),
                'timestamp': coin_data.get('timestamp', int(time.time()))
            }
            
            logger.info(f"LunarCrush metrics for {symbol}: ASS={metrics['average_sentiment_score']:.2f}, "
                       f"SIS={metrics['social_impact_score']:.2f}, Galaxy={metrics['galaxy_score']:.2f}")
            
            return metrics
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching LunarCrush data for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LunarCrush API call for {symbol}: {e}")
            return None

def get_sentiment_score(symbol: str) -> Tuple[float, Dict]:
    """
    Get sentiment score and metrics for a trading symbol.
    
    Args:
        symbol: The trading symbol (e.g., 'PF_XBTUSD')
        
    Returns:
        Tuple of (sentiment_score, metrics_dict)
        sentiment_score: Float between -1 and 1 (-1 = bearish, 1 = bullish)
        metrics_dict: Dictionary containing raw metrics
    """
    if not config.SENTIMENT_ANALYSIS_ENABLED:
        return 0.0, {}
        
    try:
        # Map trading symbol to LunarCrush symbol
        lunarcrush_symbol = config.LUNARCRUSH_SYMBOL_MAP.get(symbol)
        if not lunarcrush_symbol:
            logger.warning(f"No LunarCrush symbol mapping for {symbol}")
            return 0.0, {}
            
        # Initialize API client
        api = LunarCrushAPI(config.LUNARCRUSH_API_KEY)
        
        # Get metrics
        metrics = api.get_coin_metrics(lunarcrush_symbol)
        if not metrics:
            return 0.0, {}
            
        # Calculate sentiment score based on ASS
        ass = metrics['average_sentiment_score']
        if ass >= config.SENTIMENT_THRESHOLD_BULLISH:
            sentiment_score = 1.0  # Very bullish
        elif ass <= config.SENTIMENT_THRESHOLD_BEARISH:
            sentiment_score = -1.0  # Very bearish
        else:
            # Linear interpolation between thresholds
            sentiment_score = (ass - 3.0) / (config.SENTIMENT_THRESHOLD_BULLISH - 3.0)
            
        # Add social volume bonus
        if metrics['social_volume_change_24h'] > config.SOCIAL_VOLUME_MULTIPLIER:
            sentiment_score *= 1.1  # 10% boost for high social volume
            
        return sentiment_score, metrics
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis for {symbol}: {e}")
        return 0.0, {}

def get_sentiment_confidence(sentiment_score: float, metrics: Dict) -> float:
    """
    Calculate confidence contribution from sentiment analysis.
    
    Args:
        sentiment_score: Float between -1 and 1
        metrics: Dictionary of sentiment metrics
        
    Returns:
        Float between 0 and 1 representing confidence contribution
    """
    if not config.SENTIMENT_ANALYSIS_ENABLED:
        return 0.0
        
    try:
        # Base confidence from sentiment score
        confidence = abs(sentiment_score) * config.SENTIMENT_WEIGHT
        
        # Add bonus for high social volume
        if metrics.get('social_volume_change_24h', 0) > config.SOCIAL_VOLUME_MULTIPLIER:
            confidence += config.CONFIDENCE_WEIGHTS['social_volume']
            
        return min(confidence, 1.0)  # Cap at 1.0
        
    except Exception as e:
        logger.error(f"Error calculating sentiment confidence: {e}")
        return 0.0

def get_crypto_sentiment(symbol):
    """
    Get sentiment analysis for a cryptocurrency symbol.
    Returns sentiment score between -1 (very bearish) and +1 (very bullish).
    """
    if not config.SENTIMENT_ANALYSIS_ENABLED:
        logger.info("Sentiment analysis disabled")
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
    
    try:
        # Clean symbol for API calls (remove PF_ prefix if present)
        clean_symbol = symbol.replace("PF_", "").replace("USD", "")
        
        # For Phase 1, implement a basic sentiment aggregator
        # In production, this would integrate with real sentiment APIs
        sentiment_scores = []
        
        # Placeholder for news sentiment (would integrate with news APIs)
        news_sentiment = _get_news_sentiment(clean_symbol)
        if news_sentiment is not None:
            sentiment_scores.append(news_sentiment)
        
        # Placeholder for social sentiment (would integrate with social APIs)
        social_sentiment = _get_social_sentiment(clean_symbol)
        if social_sentiment is not None:
            sentiment_scores.append(social_sentiment)
        
        # Calculate aggregate sentiment
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        else:
            avg_sentiment = 0.0  # Neutral if no data
        
        # Determine sentiment label
        if avg_sentiment >= config.SENTIMENT_THRESHOLD_BULLISH:
            sentiment_label = "bullish"
        elif avg_sentiment <= config.SENTIMENT_THRESHOLD_BEARISH:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"
        
        result = {
            "sentiment_score": avg_sentiment,
            "sentiment_label": sentiment_label,
            "sources_count": len(sentiment_scores)
        }
        
        logger.info(f"{symbol} sentiment: {sentiment_label} (score: {avg_sentiment:.2f})")
        return result
        
    except Exception as e:
        logger.error(f"Error getting sentiment for {symbol}: {e}", exc_info=True)
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}

def _get_news_sentiment(symbol):
    """
    Get news sentiment for a symbol.
    Placeholder implementation - would integrate with news sentiment APIs.
    """
    try:
        # Placeholder logic - in production would call news sentiment APIs
        # For now, return a neutral to slightly positive bias for major cryptos
        major_cryptos = ["BTC", "ETH", "XRP", "SOL", "ADA", "DOGE", "BNB", "TRX", "LINK", "LTC"]
        
        if symbol.upper() in major_cryptos:
            # Simulate slight positive bias for major cryptos
            return 0.1
        else:
            # Neutral for other cryptos
            return 0.0
            
    except Exception as e:
        logger.error(f"Error getting news sentiment for {symbol}: {e}")
        return None

def _get_social_sentiment(symbol):
    """
    Get social media sentiment for a symbol.
    Placeholder implementation - would integrate with social sentiment APIs.
    """
    try:
        # Placeholder logic - in production would call social sentiment APIs
        # For now, return neutral sentiment
        return 0.0
        
    except Exception as e:
        logger.error(f"Error getting social sentiment for {symbol}: {e}")
        return None

def get_sentiment_score(symbol, signal_direction):
    """
    Get sentiment score for signal direction.
    Returns score between 0-15 based on sentiment alignment.
    """
    try:
        sentiment_result = get_crypto_sentiment(symbol)
        sentiment_score = sentiment_result["sentiment_score"]
        sentiment_label = sentiment_result["sentiment_label"]
        
        # Calculate score based on alignment with signal direction
        if signal_direction.upper() == "LONG":
            if sentiment_label == "bullish":
                return 15  # Full score for bullish sentiment on long signal
            elif sentiment_label == "neutral":
                return 8   # Partial score for neutral sentiment
            else:  # bearish
                return 0   # No score for bearish sentiment on long signal
        elif signal_direction.upper() == "SHORT":
            if sentiment_label == "bearish":
                return 15  # Full score for bearish sentiment on short signal
            elif sentiment_label == "neutral":
                return 8   # Partial score for neutral sentiment
            else:  # bullish
                return 0   # No score for bullish sentiment on short signal
        else:
            return 5  # Default neutral score
            
    except Exception as e:
        logger.error(f"Error getting sentiment score for {symbol}: {e}")
        return 5  # Default neutral score 