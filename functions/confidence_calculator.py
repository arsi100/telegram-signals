import os
import logging
import re # Import regex for parsing
import google.generativeai as genai

# Use absolute imports
from functions import config

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
        
        # --- Construct the Prompt --- 
        price = tech_results.get('latest_close', 'N/A')
        rsi = tech_results.get('rsi', 50.0)
        sma = tech_results.get('sma', price)
        patterns = tech_results.get('patterns', {})
        volume_info = tech_results.get('volume', {})
        volume_status = "High" if volume_info.get('high_volume') else "Normal/Low"
        volume_ratio = volume_info.get('volume_ratio', 1.0)
        
        # Determine primary pattern
        primary_pattern = "None"
        if signal_intent == "LONG":
            if patterns.get('confirmed_hammer'): primary_pattern = "Hammer (confirmed, bullish)"
            elif patterns.get('confirmed_bullish_engulfing'): primary_pattern = "Bullish Engulfing (confirmed)"
        elif signal_intent == "SHORT":
            if patterns.get('confirmed_shooting_star'): primary_pattern = "Shooting Star (confirmed, bearish)"
            elif patterns.get('confirmed_bearish_engulfing'): primary_pattern = "Bearish Engulfing (confirmed)"
        
        # Interpret RSI
        rsi_interp = "neutral"
        if rsi < 30: rsi_interp = "oversold (< 30)"
        elif rsi > 70: rsi_interp = "overbought (> 70)"
        
        # Interpret Price vs SMA
        sma_interp = "N/A"
        if isinstance(price, (int, float)) and isinstance(sma, (int, float)) and sma != 0:
             if price < sma: sma_interp = f"Price below 50-period SMA ({sma:.2f})"
             elif price > sma: sma_interp = f"Price above 50-period SMA ({sma:.2f})"
             else: sma_interp = f"Price at 50-period SMA ({sma:.2f})"

        # Directional target
        target_move = "1-3% price increase" if signal_intent == "LONG" else "1-3% price decrease"

        prompt = f"""
        Analyze the likelihood of a successful crypto trade based on the following technical indicators for a potential {signal_intent} signal on {symbol} at ${price:.2f}:
        - Primary Candlestick Pattern: {primary_pattern}
        - RSI (14): {rsi:.2f} ({rsi_interp})
        - Volume: {volume_status} ({volume_ratio:.2f}x average)
        - SMA (50): {sma_interp}

        Based *only* on these indicators, what is the confidence score (an integer from 0 to 100) that this signal will achieve a {target_move} within the next few hours?
        
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

# Remove the old formula-based calculation, as fallback logic is now in signal_generator
# def calculate_score_formula(...): ... 