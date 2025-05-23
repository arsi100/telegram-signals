import logging
import requests
import datetime
import pytz
from . import config

# Configure logging
logger = logging.getLogger(__name__)

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