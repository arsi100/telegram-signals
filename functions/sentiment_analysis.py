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
    
    BASE_URL = "https://lunarcrush.com/api4/public" # Confirmed working base
    
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
            url = f"{self.BASE_URL}/coins/{symbol}/v1" # Confirmed working path
            params = {'key': self.api_key} 
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            response_data = response.json()
            
            if not response_data or 'data' not in response_data or not isinstance(response_data['data'], dict):
                logger.warning(f"No 'data' object or unexpected structure in response from {url} for {symbol}")
                return None
            
            coin_data = response_data['data'] # This is now the object with metrics
            
            # Extract available metrics, provide defaults and warnings for missing ones
            metrics = {
                'galaxy_score': coin_data.get('galaxy_score'),
                'alt_rank': coin_data.get('alt_rank'),
                'price': coin_data.get('price'),
                'volume_24h': coin_data.get('volume_24h'), # Trading volume
                'percent_change_24h': coin_data.get('percent_change_24h'),
                # Fields from old v3 that are MISSING in this v4 /v1 endpoint:
                'average_sentiment_score': 3.0, # Default, MISSING
                'social_impact_score': 3.0,   # Default, MISSING
                'social_volume': 0.0,           # Default, MISSING
                'social_volume_change_24h': 0.0,# Default, MISSING
                'timestamp': response_data.get('config', {}).get('generated', int(time.time())) # Use 'generated' from config as timestamp
            }

            if metrics['galaxy_score'] is None: logger.warning(f"galaxy_score missing for {symbol} in v4 response")
            if coin_data.get('average_sentiment_score') is None: logger.warning(f"average_sentiment_score IS MISSING for {symbol} in v4 response. Using default.")
            if coin_data.get('social_impact_score') is None: logger.warning(f"social_impact_score IS MISSING for {symbol} in v4 response. Using default.")
            if coin_data.get('social_volume') is None: logger.warning(f"social_volume IS MISSING for {symbol} in v4 response. Using default.")
            
            logger.info(f"LunarCrush v4 metrics from {url} for {symbol}: GalaxyScore={metrics['galaxy_score']}, AltRank={metrics['alt_rank']}")
            return metrics
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching LunarCrush data for {symbol} from {url}: {e}")
            if e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LunarCrush API call for {symbol} to {url}: {e}")
            return None

def get_sentiment_score(symbol: str) -> Tuple[float, Dict]:
    """
    Get sentiment score and metrics for a trading symbol.
    Adapting to LunarCrush API v4 which may not directly provide 'average_sentiment_score'.
    """
    if not config.SENTIMENT_ANALYSIS_ENABLED:
        return 0.0, {}
        
    try:
        # Map trading symbol to LunarCrush symbol
        lunarcrush_symbol = config.LUNARCRUSH_SYMBOL_MAP.get(symbol)
        if not lunarcrush_symbol:
            logger.warning(f"No LunarCrush symbol mapping for {symbol}")
            return 0.0, {}
            
        # Initialize API client (will use the updated BASE_URL)
        api = LunarCrushAPI(config.LUNARCRUSH_API_KEY)
        
        # Get metrics (raw JSON from api4/.../v1 if successful)
        metrics = api.get_coin_metrics(lunarcrush_symbol)
        
        if not metrics:
            return 0.0, {}
            
        # --- Sentiment Calculation Adjustment for v4 ---
        # 'average_sentiment_score' is missing from the current v4 endpoint.
        # We will use 'galaxy_score' as a proxy for now. Galaxy Score is 0-100.
        # Let's normalize Galaxy Score to a -1 to 1 range.
        # Assuming 50 is neutral, <50 bearish, >50 bullish.
        # (This is a guess and might need refinement based on Galaxy Score behavior)
        
        galaxy_score = metrics.get('galaxy_score')
        sentiment_score = 0.0 # Default to neutral

        if galaxy_score is not None:
            # Normalize galaxy_score (0-100) to sentiment_score (-1 to 1)
            # Treat 0-40 as bearish (-1 to -0.2), 40-60 as neutral (-0.2 to 0.2), 60-100 as bullish (0.2 to 1)
            if galaxy_score < 40:
                sentiment_score = -1.0 + ((galaxy_score / 40.0) * 0.8) # Scales 0-39 to -1.0 to -0.2
            elif galaxy_score > 60:
                sentiment_score = 0.2 + (((galaxy_score - 60) / 40.0) * 0.8) # Scales 61-100 to 0.2 to 1.0
            else: # Between 40 and 60 (inclusive)
                sentiment_score = -0.2 + (((galaxy_score - 40) / 20.0) * 0.4) # Scales 40-60 to -0.2 to 0.2
            sentiment_score = round(max(-1.0, min(1.0, sentiment_score)), 4) # Ensure it's clamped and rounded
            logger.info(f"Using Galaxy Score {galaxy_score} to derive sentiment_score: {sentiment_score} for {lunarcrush_symbol}")
        else:
            logger.warning(f"Galaxy Score is None for {lunarcrush_symbol}. Defaulting sentiment to neutral (0.0).")
            # Fallback to old ASS if by some miracle it was populated (it won't be with current parsing)
            # ass = metrics['average_sentiment_score'] # This will be the default 3.0
            # if ass >= config.SENTIMENT_THRESHOLD_BULLISH: sentiment_score = 1.0
            # elif ass <= config.SENTIMENT_THRESHOLD_BEARISH: sentiment_score = -1.0
            # else: sentiment_score = (ass - 3.0) / (config.SENTIMENT_THRESHOLD_BULLISH - 3.0)

        # 'social_volume_change_24h' is missing. Social volume bonus cannot be applied.
        if metrics.get('social_volume_change_24h', 0) == 0 and metrics.get('social_volume', 0) == 0:
             logger.info(f"Social volume data missing for {lunarcrush_symbol}, skipping social volume bonus.")
        # else:
        #    if metrics['social_volume_change_24h'] > config.SOCIAL_VOLUME_MULTIPLIER:
        #        sentiment_score *= 1.1 
            
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

def calculate_directional_sentiment_adjustment(symbol, signal_direction):
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