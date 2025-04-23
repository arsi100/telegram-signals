import os
import logging
import google.generativeai as genai

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Gemini API
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=gemini_api_key)

def get_confidence_score(pattern_type, rsi, volume_ratio, price, sma):
    """
    Calculate a confidence score using the Google Gemini API.
    
    Args:
        pattern_type: Type of pattern detected ("bullish" or "bearish")
        rsi: Relative Strength Index value
        volume_ratio: Volume compared to average
        price: Current price
        sma: Simple Moving Average
    
    Returns:
        Confidence score (0-100)
    """
    try:
        # First try to calculate score using the formula if Gemini API fails
        score = calculate_score_formula(pattern_type, rsi, volume_ratio, price, sma)
        
        # Now try to get a more nuanced score from Gemini if available
        if gemini_api_key:
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            # Create a detailed prompt for Gemini
            prompt = f"""
            ANALYZE CRYPTO TRADING SIGNAL AND RETURN A NUMERIC CONFIDENCE SCORE (0-100).
            
            FACTORS (with weights):
            * Candlestick pattern ({pattern_type}) - 40% weight
            * RSI ({rsi:.2f}) - 30% weight
                - <30 is good for LONG
                - >70 is good for SHORT
            * Trading volume ({volume_ratio:.2f}x average) - 20% weight
                - >1.0 is good
            * SMA alignment - 10% weight
                - Price ${price:.2f}, SMA ${sma:.2f}
                - Price < SMA favors LONG
                - Price > SMA favors SHORT
            
            IMPORTANT: ONLY RETURN A SINGLE NUMBER BETWEEN 0-100.
            """
            
            try:
                response = model.generate_content(prompt)
                result = response.text.strip()
                
                # Extract the number from the response
                # Look for a number in the response
                import re
                score_match = re.search(r'\b(\d{1,3})\b', result)
                if score_match:
                    gemini_score = float(score_match.group(1))
                    # Validate score is within range
                    if 0 <= gemini_score <= 100:
                        logger.info(f"Gemini confidence score: {gemini_score}")
                        return gemini_score
                        
                logger.warning(f"Invalid Gemini score format: {result}. Using formula score.")
            except Exception as e:
                logger.error(f"Error querying Gemini API: {str(e)}")
        
        # Return the formula-based score if Gemini fails
        logger.info(f"Formula-based confidence score: {score}")
        return score
        
    except Exception as e:
        logger.error(f"Error in get_confidence_score: {str(e)}")
        return 50  # Return neutral score on error

def calculate_score_formula(pattern_type, rsi, volume_ratio, price, sma):
    """
    Calculate a confidence score using a formula.
    
    This is a fallback when the Gemini API is unavailable.
    
    Args:
        pattern_type: Type of pattern detected ("bullish" or "bearish")
        rsi: Relative Strength Index value
        volume_ratio: Volume compared to average
        price: Current price
        sma: Simple Moving Average
    
    Returns:
        Confidence score (0-100)
    """
    # Pattern score (40%)
    pattern_score = 40  # Base score if pattern detected
    
    # RSI score (30%)
    rsi_score = 0
    if pattern_type == "bullish":
        # For bullish patterns, lower RSI is better (oversold condition)
        if rsi < 30:
            rsi_score = 30
        elif rsi < 40:
            rsi_score = 20
        elif rsi < 50:
            rsi_score = 10
        else:
            rsi_score = 0
    else:  # Bearish
        # For bearish patterns, higher RSI is better (overbought condition)
        if rsi > 70:
            rsi_score = 30
        elif rsi > 60:
            rsi_score = 20
        elif rsi > 50:
            rsi_score = 10
        else:
            rsi_score = 0
    
    # Volume score (20%)
    volume_score = min(20, 20 * volume_ratio)
    
    # SMA score (10%)
    sma_score = 0
    if pattern_type == "bullish" and price < sma:
        sma_score = 10  # Price below SMA is good for long
    elif pattern_type == "bearish" and price > sma:
        sma_score = 10  # Price above SMA is good for short
    
    # Calculate total score
    total_score = pattern_score + rsi_score + volume_score + sma_score
    
    # Round to one decimal
    return round(total_score, 1)
