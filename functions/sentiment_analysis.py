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

def get_sentiment_score(symbol: str) -> Dict:
    """
    Get sentiment score and metrics for a trading symbol.
    Adapting to LunarCrush API v4 which may not directly provide 'average_sentiment_score'.
    Handles API errors by returning a dictionary with a neutral score and status if configured.
    NOW ALWAYS RETURNS A DICTIONARY.
    """
    if not config.SENTIMENT_ANALYSIS_ENABLED:
        return {
            'sentiment_score_raw': 0.0, 
            'status': 'SENTIMENT_DISABLED', 
            'galaxy_score_used': None,
            'sentiment_confidence_final_RULE_WEIGHTED': 0.0,
            'sentiment_confidence_final': 0.0
        }
        
    try:
        lunarcrush_symbol = config.LUNARCRUSH_SYMBOL_MAP.get(symbol)
        if not lunarcrush_symbol:
            logger.warning(f"No LunarCrush symbol mapping for {symbol}")
            result_dict = {
                'sentiment_score_raw': config.NEUTRAL_SENTIMENT_SCORE_ON_ERROR if config.USE_NEUTRAL_SENTIMENT_ON_ERROR else 0.0,
                'status': 'NO_MAPPING', 
                'galaxy_score_used': None,
                'sentiment_confidence_final_RULE_WEIGHTED': 0.0,
                'sentiment_confidence_final': 0.0
            }
            if config.USE_NEUTRAL_SENTIMENT_ON_ERROR:
                 logger.warning(f"Defaulting to neutral sentiment score {result_dict['sentiment_score_raw']} for {symbol} due to missing mapping.")
            return result_dict
            
        api = LunarCrushAPI(config.LUNARCRUSH_API_KEY)
        metrics = api.get_coin_metrics(lunarcrush_symbol) # This is a dict or None
        
        # Initialize result_dict with a base structure, including keys expected by signal_generator
        result_dict = {
            'sentiment_score_raw': config.NEUTRAL_SENTIMENT_SCORE_ON_ERROR if config.USE_NEUTRAL_SENTIMENT_ON_ERROR else 0.0,
            'status': 'INIT',
            'galaxy_score_used': None,
            'sentiment_confidence_final_RULE_WEIGHTED': 0.0,
            'sentiment_confidence_final': 0.0
        }
        
        if metrics: # If api.get_coin_metrics returned a dictionary
            result_dict.update(metrics) # Add all metrics from LC (galaxy_score, alt_rank etc.)
            result_dict['status'] = 'METRICS_RECEIVED'
        else:
            logger.warning(f"Failed to fetch metrics for {lunarcrush_symbol} from LunarCrush.")
            result_dict['status'] = 'API_ERROR'
            if config.USE_NEUTRAL_SENTIMENT_ON_ERROR:
                logger.warning(f"Defaulting to neutral sentiment score {result_dict['sentiment_score_raw']} for {symbol} due to API error.")
            # result_dict already has neutral score from initialization
            return result_dict 
            
        galaxy_score = result_dict.get('galaxy_score') # Use .get() from result_dict after potential update
        sentiment_score_calculated = result_dict['sentiment_score_raw'] # Keep current default or override below

        if galaxy_score is not None:
            # Normalize galaxy_score (0-100) to sentiment_score (-1 to 1)
            if galaxy_score < 40:
                sentiment_score_calculated = -1.0 + ((galaxy_score / 40.0) * 0.8)
            elif galaxy_score > 60:
                sentiment_score_calculated = 0.2 + (((galaxy_score - 60) / 40.0) * 0.8)
            else: # Between 40 and 60 (inclusive)
                sentiment_score_calculated = -0.2 + (((galaxy_score - 40) / 20.0) * 0.4)
            sentiment_score_calculated = round(max(-1.0, min(1.0, sentiment_score_calculated)), 4)
            logger.info(f"Using Galaxy Score {galaxy_score} to derive sentiment_score: {sentiment_score_calculated} for {lunarcrush_symbol}")
            result_dict['status'] = 'GS_PROCESSED'
        else:
            logger.warning(f"Galaxy Score is None for {lunarcrush_symbol} from metrics: {metrics}. Defaulting sentiment to current raw score: {sentiment_score_calculated}.")
            result_dict['status'] = 'GS_MISSING'
        
        result_dict['sentiment_score_raw'] = sentiment_score_calculated # Update with calculated score
        result_dict['galaxy_score_used'] = galaxy_score # Ensure this is explicitly set from the var used

        sentiment_overall_weight_from_config = config.CONFIDENCE_WEIGHTS.get('sentiment_overall_contribution', 0.05)
        logger.debug(f"[SENTIMENT_DEBUG] For {lunarcrush_symbol}: Value of config.CONFIDENCE_WEIGHTS['sentiment_overall_contribution'] being used for rule-weighted conf: {sentiment_overall_weight_from_config}")
        result_dict['sentiment_confidence_final_RULE_WEIGHTED'] = result_dict['sentiment_score_raw'] * sentiment_overall_weight_from_config
        result_dict['sentiment_confidence_final'] = result_dict['sentiment_score_raw'] * config.SENTIMENT_WEIGHT_FOR_RULES

        logger.info(f"[{lunarcrush_symbol}] Sentiment analysis: Status={result_dict['status']}, Raw score={result_dict['sentiment_score_raw']:.3f} (GS {result_dict.get('galaxy_score_used', 'N/A')}), RuleConf={result_dict['sentiment_confidence_final_RULE_WEIGHTED']:.3f}")
        return result_dict
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis for {symbol}: {e}", exc_info=True)
        final_error_result_dict = {
            'sentiment_score_raw': config.NEUTRAL_SENTIMENT_SCORE_ON_ERROR if config.USE_NEUTRAL_SENTIMENT_ON_ERROR else 0.0,
            'status': 'EXCEPTION_IN_GET_SENTIMENT_SCORE', 
            'galaxy_score_used': None,
            'error_message': str(e),
            'sentiment_confidence_final_RULE_WEIGHTED': 0.0,
            'sentiment_confidence_final': 0.0
        }
        if config.USE_NEUTRAL_SENTIMENT_ON_ERROR:
            logger.warning(f"Defaulting to neutral sentiment score {final_error_result_dict['sentiment_score_raw']} for {symbol} due to unexpected exception.")
        return final_error_result_dict

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
        # Placeholder logic
        return 0.0 # Neutral
    except Exception as e:
        logger.error(f"Error getting social sentiment for {symbol}: {e}")
        return None

def calculate_directional_sentiment_adjustment(
    raw_score: float, 
    signal_direction: str, 
    multiplier: float = 1.0, 
    cap: Optional[float] = None
) -> float:
    """
    Adjusts a raw sentiment score based on the intended signal direction,
    applying a multiplier and a cap.

    Args:
        raw_score: The initial sentiment score.
        signal_direction: "LONG" or "SHORT".
        multiplier: Factor to multiply the score by.
        cap: Absolute maximum/minimum value for the adjusted score based on direction.
             For LONG, it's a positive cap. For SHORT, it's a negative cap.

    Returns:
        The adjusted sentiment score.
    """
    if raw_score is None: # Should not happen if called correctly, but as a safeguard
        return 0.0

    adjusted_score = raw_score * multiplier

    if cap is not None:
        if signal_direction == "LONG":
            adjusted_score = min(adjusted_score, cap)
        elif signal_direction == "SHORT":
            # Assuming cap for SHORT is a negative value (e.g., -1.0)
            # and raw_score * multiplier would be negative.
            adjusted_score = max(adjusted_score, cap) # max of two negative numbers is the one closer to zero
    
    # Further clamping to ensure score remains within a logical global range if necessary (e.g. -1 to 1)
    # This depends on overall system design for sentiment scores.
    # For now, the directional cap is primary.
    # Example global clamp: adjusted_score = max(-1.0, min(1.0, adjusted_score))
    
    return round(adjusted_score, 4)

# Ensure any old test/example blocks for this module are updated or removed if they call old signatures
# Example usage (illustrative):
# adjusted_long = calculate_directional_sentiment_adjustment(0.6, "LONG", 1.1, 1.0) -> 0.66
# adjusted_short = calculate_directional_sentiment_adjustment(-0.5, "SHORT", 1.2, -1.0) -> -0.6 