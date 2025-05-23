import os
import logging
import re # Import regex for parsing
import google.generativeai as genai

# Use relative import for config
from . import config
from .multi_timeframe_analysis import get_trend_confirmation_score
# from .sentiment_analysis import get_sentiment_score  # DISABLED - no real sentiment data

# Configure logging
logger = logging.getLogger(__name__)

# Define the Gemini model name
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

def get_confidence_score(tech_results: dict, sentiment_confidence: float = 0.0) -> float:
    """
    Calculate confidence score based on technical analysis and sentiment.
    
    Args:
        tech_results: Dictionary containing technical analysis results
        sentiment_confidence: Float between 0 and 1 representing sentiment confidence
        
    Returns:
        Float between 0 and 100 representing overall confidence
    """
    try:
        # Initialize confidence components
        pattern_confidence = 0.0
        rsi_confidence = 0.0
        volume_confidence = 0.0
        ema_confidence = 0.0
        multi_timeframe_confidence = 0.0
        
        # 1. Pattern Analysis (35%)
        pattern = tech_results.get('pattern', {})
        if pattern.get('pattern_detected_raw', False):
            pattern_confidence = 1.0  # Full confidence for confirmed patterns
            
        # 2. RSI Analysis (25%)
        rsi = tech_results.get('rsi', 50)
        if rsi < config.RSI_OVERSOLD_THRESHOLD:
            rsi_confidence = 1.0  # Strong oversold
        elif rsi > config.RSI_OVERBOUGHT_THRESHOLD:
            rsi_confidence = 1.0  # Strong overbought
        else:
            # Linear interpolation between thresholds
            if rsi < 50:
                rsi_confidence = (config.RSI_OVERSOLD_THRESHOLD - rsi) / config.RSI_OVERSOLD_THRESHOLD
            else:
                rsi_confidence = (rsi - config.RSI_OVERBOUGHT_THRESHOLD) / (100 - config.RSI_OVERBOUGHT_THRESHOLD)
                
        # 3. Volume Analysis (20%)
        volume_analysis = tech_results.get('volume_analysis', {})
        volume_tier = volume_analysis.get('volume_tier', 'UNKNOWN')
        volume_ratio = volume_analysis.get('volume_ratio', 0)
        
        if volume_tier == 'EXTREME':
            volume_confidence = 1.0
        elif volume_tier == 'HIGH':
            volume_confidence = 0.8
        elif volume_tier == 'ELEVATED':
            volume_confidence = 0.6
        elif volume_tier == 'NORMAL':
            volume_confidence = 0.4
        elif volume_tier == 'LOW':
            volume_confidence = 0.2
        else:  # VERY_LOW
            volume_confidence = 0.0
            
        # Add bonus for early trend signals
        if volume_analysis.get('early_trend_signal', False):
            volume_confidence *= 1.2  # 20% boost
            
        # 4. EMA Trend Analysis (10%)
        ema = tech_results.get('ema', 0)
        price = tech_results.get('latest_close', 0)
        if price > ema:
            ema_confidence = 1.0  # Uptrend
        else:
            ema_confidence = 0.0  # Downtrend
            
        # 5. Multi-timeframe Analysis (10%)
        if config.MULTI_TIMEFRAME_ENABLED:
            # This would be implemented when multi-timeframe data is available
            multi_timeframe_confidence = 0.5  # Placeholder
            
        # Calculate weighted confidence
        confidence = (
            pattern_confidence * config.CONFIDENCE_WEIGHTS['pattern'] +
            rsi_confidence * config.CONFIDENCE_WEIGHTS['rsi'] +
            volume_confidence * config.CONFIDENCE_WEIGHTS['volume'] +
            ema_confidence * config.CONFIDENCE_WEIGHTS['ema'] +
            multi_timeframe_confidence * config.CONFIDENCE_WEIGHTS['multi_timeframe'] +
            sentiment_confidence  # Already weighted in get_sentiment_confidence
        ) * 100  # Convert to percentage
        
        # Log confidence components
        logger.info(f"Confidence components for {tech_results.get('symbol', 'unknown')}:")
        logger.info(f"Pattern: {pattern_confidence:.2f} ({config.CONFIDENCE_WEIGHTS['pattern']*100}%)")
        logger.info(f"RSI: {rsi_confidence:.2f} ({config.CONFIDENCE_WEIGHTS['rsi']*100}%)")
        logger.info(f"Volume: {volume_confidence:.2f} ({config.CONFIDENCE_WEIGHTS['volume']*100}%)")
        logger.info(f"EMA: {ema_confidence:.2f} ({config.CONFIDENCE_WEIGHTS['ema']*100}%)")
        logger.info(f"Multi-timeframe: {multi_timeframe_confidence:.2f} ({config.CONFIDENCE_WEIGHTS['multi_timeframe']*100}%)")
        logger.info(f"Sentiment: {sentiment_confidence:.2f} ({config.SENTIMENT_WEIGHT*100}%)")
        logger.info(f"Final confidence: {confidence:.2f}%")
        
        return min(max(confidence, 0), 100)  # Ensure between 0 and 100
        
    except Exception as e:
        logger.error(f"Error calculating confidence score: {e}")
        return 0.0

def should_generate_signal(confidence: float, signal_type: str) -> bool:
    """
    Determine if a signal should be generated based on confidence and type.
    
    Args:
        confidence: Float between 0 and 100 representing confidence score
        signal_type: String indicating signal type (LONG, SHORT, EXIT, etc.)
        
    Returns:
        Boolean indicating whether to generate signal
    """
    try:
        if signal_type == "EXIT":
            return confidence >= config.MIN_CONFIDENCE_EXIT
        elif signal_type.startswith("AVG_"):
            return confidence >= config.MIN_CONFIDENCE_AVG
        else:  # LONG or SHORT
            return confidence >= config.MIN_CONFIDENCE_ENTRY
            
    except Exception as e:
        logger.error(f"Error in should_generate_signal: {e}")
        return False

def calculate_enhanced_local_confidence(symbol, signal_intent, tech_results):
    """
    Enhanced local confidence calculator with multi-timeframe analysis.
    Weights: Pattern=35, RSI=30, Volume=20, EMA=10, Multi-timeframe=5 (disabled sentiment)
    """
    try:
        score = 0
        components = {}

        patterns = tech_results['raw_patterns_result']
        rsi = tech_results['rsi']
        volume_high = tech_results['volume_increase']
        ema = tech_results['ema']
        price = tech_results['latest_close']

        # Pattern Score (Max 35) - Increased since sentiment disabled
        is_bullish_pattern = patterns.get('confirmed_hammer', False) or patterns.get('confirmed_bullish_engulfing', False) or patterns.get('confirmed_morning_star', False)
        is_bearish_pattern = patterns.get('confirmed_shooting_star', False) or patterns.get('confirmed_bearish_engulfing', False) or patterns.get('confirmed_evening_star', False)
        if is_bullish_pattern or is_bearish_pattern:
            score += 35
            components['pattern'] = 35
        else:
            components['pattern'] = 0

        # RSI Score (Max 30) - Increased since sentiment disabled
        rsi_score = 0
        if is_bullish_pattern and rsi < config.RSI_OVERSOLD_THRESHOLD:
            rsi_score = max(0, min(1, (config.RSI_OVERSOLD_THRESHOLD - rsi) / 25)) * 30
        elif is_bearish_pattern and rsi > config.RSI_OVERBOUGHT_THRESHOLD:
            rsi_score = max(0, min(1, (rsi - config.RSI_OVERBOUGHT_THRESHOLD) / 25)) * 30
        score += rsi_score
        components['rsi'] = rsi_score

        # Volume Score (Max 20) - Increased since sentiment disabled
        if volume_high:
            score += 20
            components['volume'] = 20
        else:
            components['volume'] = 0

        # EMA Score (Max 10) - Same as before
        if is_bullish_pattern and price < ema:
            score += 10
            components['ema'] = 10
        elif is_bearish_pattern and price > ema:
            score += 10
            components['ema'] = 10
        else:
            components['ema'] = 0

        # Multi-timeframe Score (Max 5) - Reduced weight for now
        mtf_score = get_trend_confirmation_score(symbol, signal_intent)
        # Scale down from 0-20 to 0-5
        scaled_mtf_score = (mtf_score / 20) * 5 if mtf_score > 0 else 0
        score += scaled_mtf_score
        components['multi_timeframe'] = scaled_mtf_score

        # Sentiment Score - DISABLED (no fake data)
        components['sentiment'] = 0

        logger.info(f"Enhanced local confidence for {symbol} {signal_intent}: {score:.1f} - {components}")
        return min(score, 100)  # Cap at 100
            
    except Exception as e:
        logger.error(f"Error calculating enhanced local confidence for {symbol}: {e}", exc_info=True)
        return 50  # Default neutral score

# Remove the old formula-based calculation, as fallback logic is now in signal_generator
# def calculate_score_formula(...): ... 