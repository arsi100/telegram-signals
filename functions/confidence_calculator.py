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

def get_confidence_score(tech_results: dict, sentiment_confidence: float = 0.0, signal_direction: str = "NEUTRAL") -> float:
    """
    Calculate confidence score based on technical analysis and sentiment.
    
    Args:
        tech_results: Dictionary containing technical analysis results 
        sentiment_confidence: Float between 0 and 1 representing sentiment confidence
        signal_direction: String "LONG", "SHORT", or "NEUTRAL" / "EXIT_LONG" / "EXIT_SHORT"
    
    Returns:
        Float between 0 and 100 representing overall confidence
    """
    try:
        # Initialize confidence components
        pattern_confidence = 0.0
        rsi_confidence = 0.0
        volume_confidence = 0.0
        ema_confidence = 0.0 # Not currently used with weight 0
        multi_timeframe_confidence = 0.0 # Placeholder
        
        # 1. Pattern Analysis (Weight from config)
        pattern_info = tech_results.get('pattern', {})
        if pattern_info.get('pattern_name', 'N/A') != 'N/A':
            # Simple binary: 1.0 if pattern detected, 0 otherwise.
            # Could be refined with pattern strength if available.
            if pattern_info.get('pattern_type') == 'bullish' and signal_direction in ["LONG", "EXIT_SHORT"]:
                pattern_confidence = 1.0
            elif pattern_info.get('pattern_type') == 'bearish' and signal_direction in ["SHORT", "EXIT_LONG"]:
                pattern_confidence = 1.0
            elif pattern_info.get('pattern_type') == 'neutral': # e.g. Doji
                pattern_confidence = 0.2 # Small confidence for neutral patterns if aligned

        # 2. RSI Analysis (Weight from config) - Grok's proposed logic
        rsi = tech_results.get('rsi', 50.0) # Default to 50 (neutral) if missing
        rsi_conf_raw = 0.0 # Raw confidence contribution from RSI (0.0 to 1.0 scale for this component)

        if signal_direction in ["LONG", "EXIT_SHORT"]:
            if rsi <= config.RSI_OVERSOLD_THRESHOLD:  # e.g. <= 25
                rsi_conf_raw = 1.0  # Max confidence for oversold
            elif rsi < 50:  # e.g. 25 < rsi < 50
                # Grok: scales from 0.1 (at threshold) to 0.5 (at 50)
                rsi_conf_raw = 0.1 + ((rsi - config.RSI_OVERSOLD_THRESHOLD) / (50.0 - config.RSI_OVERSOLD_THRESHOLD)) * 0.4
            elif rsi <= config.RSI_OVERBOUGHT_THRESHOLD:  # e.g. 50 <= rsi <= 75
                # Proposed: scales from 0.1 (at RSI 50) to 0.5 (at RSI 75) for bullish momentum
                rsi_conf_raw = 0.1 + ((rsi - 50.0) / (config.RSI_OVERBOUGHT_THRESHOLD - 50.0)) * 0.4
            elif rsi > config.RSI_OVERBOUGHT_THRESHOLD: # e.g. > 75
                # If intent is LONG and RSI is in overbought territory (strong bullish momentum case)
                # This case is often driven by "price > ema" in signal_generator for intent
                rsi_conf_raw = 0.8 # Strong confidence for sustained overbought momentum
            else: # Should not be reached if logic is correct
                rsi_conf_raw = 0.0
            
        elif signal_direction in ["SHORT", "EXIT_LONG"]:
            if rsi >= config.RSI_OVERBOUGHT_THRESHOLD:  # e.g. >= 75
                rsi_conf_raw = 1.0  # Max confidence for overbought (expecting reversal)
            elif rsi > 50:  # e.g. 50 < rsi < 75 (RSI is high/rising, increasing confidence for a SHORT)
                # Scales from 0.1 (near 50) up to 0.5 (near RSI_OVERBOUGHT_THRESHOLD)
                rsi_conf_raw = 0.1 + ((rsi - 50.0) / (config.RSI_OVERBOUGHT_THRESHOLD - 50.0)) * 0.4
            elif rsi >= config.RSI_OVERSOLD_THRESHOLD:  # e.g. 25 <= rsi <= 50 (RSI is mid to low/falling)
                # Scales from 0.1 (near 50) up to 0.5 (near RSI_OVERSOLD_THRESHOLD)
                rsi_conf_raw = 0.1 + ((50.0 - rsi) / (50.0 - config.RSI_OVERSOLD_THRESHOLD)) * 0.4
            elif rsi < config.RSI_OVERSOLD_THRESHOLD:  # e.g. < 25 (RSI is deeply oversold)
                # This aligns with signal_generator's rule for SHORT in an oversold downtrend
                rsi_conf_raw = 0.8  # Strong confidence for sustained oversold momentum
            else: # Should not be reached if logic is correct
                rsi_conf_raw = 0.0
            
        rsi_confidence = max(0.0, min(1.0, rsi_conf_raw)) # Ensure it's capped 0-1 before weighting
            
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
            volume_confidence * config.CONFIDENCE_WEIGHTS['volume_tier'] +
            ema_confidence * config.CONFIDENCE_WEIGHTS['ema_trend'] +
            multi_timeframe_confidence * config.CONFIDENCE_WEIGHTS.get('multi_timeframe', 0.0) +
            sentiment_confidence  # Already weighted in get_sentiment_confidence
        ) * 100  # Convert to percentage
        
        # Log confidence components
        logger.debug(f"[CC_DEBUG] Confidence components for {tech_results.get('symbol', 'unknown')}:")
        logger.debug(f"[CC_DEBUG] Pattern_raw: {pattern_confidence:.2f}, Weight: {config.CONFIDENCE_WEIGHTS['pattern']}, Result: {pattern_confidence * config.CONFIDENCE_WEIGHTS['pattern']:.2f}")
        logger.debug(f"[CC_DEBUG] RSI_raw: {rsi_confidence:.2f}, Weight: {config.CONFIDENCE_WEIGHTS['rsi']}, Result: {rsi_confidence * config.CONFIDENCE_WEIGHTS['rsi']:.2f}")
        logger.debug(f"[CC_DEBUG] Volume_raw: {volume_confidence:.2f}, Weight: {config.CONFIDENCE_WEIGHTS['volume_tier']}, Result: {volume_confidence * config.CONFIDENCE_WEIGHTS['volume_tier']:.2f}")
        logger.debug(f"[CC_DEBUG] EMA_raw: {ema_confidence:.2f}, Weight: {config.CONFIDENCE_WEIGHTS['ema_trend']}, Result: {ema_confidence * config.CONFIDENCE_WEIGHTS['ema_trend']:.2f}")
        logger.debug(f"[CC_DEBUG] MultiTF_raw: {multi_timeframe_confidence:.2f}, Weight: {config.CONFIDENCE_WEIGHTS.get('multi_timeframe', 0.0)}, Result: {multi_timeframe_confidence * config.CONFIDENCE_WEIGHTS.get('multi_timeframe', 0.0):.2f}")
        logger.debug(f"[CC_DEBUG] Sentiment_raw: {sentiment_confidence:.2f} (Note: this is post-weighting from sentiment_analysis.py)")
        logger.debug(f"[CC_DEBUG] Sum of weighted components before x100: {(pattern_confidence * config.CONFIDENCE_WEIGHTS['pattern'] + rsi_confidence * config.CONFIDENCE_WEIGHTS['rsi'] + volume_confidence * config.CONFIDENCE_WEIGHTS['volume_tier'] + ema_confidence * config.CONFIDENCE_WEIGHTS['ema_trend'] + multi_timeframe_confidence * config.CONFIDENCE_WEIGHTS.get('multi_timeframe', 0.0) + sentiment_confidence):.4f}")
        logger.debug(f"[CC_DEBUG] Final confidence (after x100, pre-cap): {confidence:.2f}%")
        
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
        logger.debug(f"[CC_DEBUG] should_generate_signal called with confidence: {confidence:.2f}, signal_type: {signal_type}")
        # For EXIT_LONG and EXIT_SHORT, use MIN_CONFIDENCE_EXIT
        if signal_type.startswith("EXIT_"):
            result = confidence >= config.MIN_CONFIDENCE_EXIT
            logger.debug(f"[CC_DEBUG] EXIT_ signal ({signal_type}): {confidence:.2f} >= {config.MIN_CONFIDENCE_EXIT} (MIN_CONFIDENCE_EXIT) = {result}")
            return result
        elif signal_type == "EXIT": # General EXIT, if ever used directly
            result = confidence >= config.MIN_CONFIDENCE_EXIT
            logger.debug(f"[CC_DEBUG] EXIT signal: {confidence:.2f} >= {config.MIN_CONFIDENCE_EXIT} (MIN_CONFIDENCE_EXIT) = {result}")
            return result
        elif signal_type.startswith("AVG_"):
            result = confidence >= config.MIN_CONFIDENCE_AVG
            logger.debug(f"[CC_DEBUG] AVG_ signal: {confidence:.2f} >= {config.MIN_CONFIDENCE_AVG} (MIN_CONFIDENCE_AVG) = {result}")
            return result
        else:  # LONG or SHORT
            result = confidence >= config.MIN_CONFIDENCE_ENTRY
            logger.debug(f"[CC_DEBUG] ENTRY signal ({signal_type}): {confidence:.2f} >= {config.MIN_CONFIDENCE_ENTRY} (MIN_CONFIDENCE_ENTRY) = {result}")
            return result
            
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