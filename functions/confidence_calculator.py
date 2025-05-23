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

def get_confidence_score(symbol: str, signal_intent: str, tech_results: dict):
    """
    Calculate a confidence score using the Google Gemini API based on technical analysis.
    
    Args:
        symbol: The trading symbol (e.g., 'PF_XBTUSD').
        signal_intent: The potential signal type ("LONG" or "SHORT").
        tech_results: Dictionary containing technical analysis results 
                      (output from analyze_technicals).
    
    Returns:
        Confidence score (float 0-100) or None if API call/parsing fails.
    """
    api_key = config.GEMINI_API_KEY
    
    if not api_key:
        logger.warning("Gemini API key not found in config. Cannot calculate Gemini confidence score.")
        return None # Indicate failure to caller
    
    try:
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        
        # Set up the model
        generation_config = genai.GenerationConfig(
            temperature=0.2, # Lower temperature for more deterministic score
            top_p=1.0,
            top_k=1,
            max_output_tokens=50 # Expecting just a number
        )
        model = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME, generation_config=generation_config)
        
        # --- Construct the Enhanced Prompt with Multi-timeframe and Sentiment --- 
        price = tech_results.get('latest_close', 'N/A')
        rsi = tech_results.get('rsi', 50.0)
        ema = tech_results.get('ema', price)  # Changed from sma to ema
        patterns = tech_results.get('raw_patterns_result', {})
        volume_info = tech_results.get('raw_volume_analysis', {})
        volume_status = "High" if tech_results.get('volume_increase', False) else "Normal/Low"
        volume_ratio = volume_info.get('volume_ratio', 1.0)
        atr_filter = tech_results.get('atr_filter_passed', False)
        
        # Get multi-timeframe analysis
        try:
            from .multi_timeframe_analysis import analyze_higher_timeframes
            mtf_result = analyze_higher_timeframes(symbol)
            mtf_trend = mtf_result.get('trend_direction', 'neutral')
            mtf_confirmed = mtf_result.get('trend_confirmed', False)
        except Exception as e:
            logger.warning(f"Could not get multi-timeframe data: {e}")
            mtf_trend = 'neutral'
            mtf_confirmed = False
        
        # Get sentiment analysis - DISABLED
        sentiment_label = 'neutral'
        sentiment_score = 0.0
        
        # Determine primary pattern
        primary_pattern = "None"
        if signal_intent == "LONG":
            if patterns.get('pattern_name') and 'bullish' in patterns.get('pattern_type', '').lower():
                primary_pattern = f"{patterns.get('pattern_name')} (bullish)"
        elif signal_intent == "SHORT":
            if patterns.get('pattern_name') and 'bearish' in patterns.get('pattern_type', '').lower():
                primary_pattern = f"{patterns.get('pattern_name')} (bearish)"
        
        # Interpret RSI
        rsi_interp = "neutral"
        if rsi < config.RSI_OVERSOLD_THRESHOLD: rsi_interp = f"oversold (< {config.RSI_OVERSOLD_THRESHOLD})"
        elif rsi > config.RSI_OVERBOUGHT_THRESHOLD: rsi_interp = f"overbought (> {config.RSI_OVERBOUGHT_THRESHOLD})"
        
        # Interpret Price vs EMA
        ema_interp = "N/A"
        if isinstance(price, (int, float)) and isinstance(ema, (int, float)) and ema != 0:
             if price < ema: ema_interp = f"Price below 20-period EMA ({ema:.2f})"
             elif price > ema: ema_interp = f"Price above 20-period EMA ({ema:.2f})"
             else: ema_interp = f"Price at 20-period EMA ({ema:.2f})"

        # Directional target
        target_move = "1-3% price increase" if signal_intent == "LONG" else "1-3% price decrease"

        prompt = f"""
        Analyze the likelihood of a successful crypto trade based on the following technical indicators for a potential {signal_intent} signal on {symbol} at ${price:.2f}:
        
        PRIMARY INDICATORS:
        - Candlestick Pattern: {primary_pattern}
        - RSI (7-period): {rsi:.2f} ({rsi_interp})
        - Volume: {volume_status} ({volume_ratio:.2f}x average)
        - EMA (20-period): {ema_interp}
        - ATR Volatility Filter: {'Passed' if atr_filter else 'Failed'}
        
        MULTI-TIMEFRAME ANALYSIS:
        - Higher Timeframe Trend: {mtf_trend} ({'confirmed' if mtf_confirmed else 'not confirmed'})
        
        Based on these technical indicators, what is the confidence score (an integer from 0 to 100) that this {signal_intent} signal will achieve a {target_move} within the next few hours?
        
        Consider:
        - Pattern strength and confirmation
        - RSI alignment with signal direction
        - Volume confirmation
        - Trend alignment across timeframes
        - Volatility conditions
        
        Return ONLY the integer confidence score, without any explanation or other text.
        Confidence Score: 
        """
        # --- End Prompt Construction ---
        
        logger.debug(f"Generated Gemini prompt for {symbol} {signal_intent}:\n{prompt}")
        
        # Generate the response
        response = model.generate_content(prompt)
        
        # --- Parse the Confidence Score --- 
        score_text = response.text.strip()
        logger.debug(f"Received Gemini response: '{score_text}'")
        
        # Try to extract a number (integer or float) between 0 and 100
        match = re.search(r'\b([0-9]{1,2}|100)\b', score_text) # Find 1-3 digit numbers up to 100
        
        if match:
            confidence = float(match.group(1))
            logger.info(f"Extracted confidence score {confidence} from Gemini response for {symbol} {signal_intent}.")
            return confidence
        else:
            logger.warning(f"Failed to extract a valid confidence score (0-100) from Gemini response for {symbol} {signal_intent}. Response: '{score_text}'")
            return None # Indicate failure to caller
            
    except Exception as e:
        logger.error(f"Error calling Gemini API for {symbol} {signal_intent}: {e}", exc_info=True)
        return None # Indicate failure to caller

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