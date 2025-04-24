import os
import logging
import google.generativeai as genai
from . import config

# Set up logging
logger = logging.getLogger(__name__)

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
    api_key = config.GEMINI_API_KEY
    
    if not api_key:
        logger.warning("Gemini API key not found, using formula-based confidence calculation")
        return calculate_score_formula(pattern_type, rsi, volume_ratio, price, sma)
    
    try:
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        
        # Set up the model
        model = genai.GenerativeModel('gemini-pro')
        
        # Create the prompt for analysis
        prompt = f"""
        As a trading expert, analyze this technical pattern and provide a confidence score from 0-100.
        
        Pattern: {pattern_type}
        RSI: {rsi}
        Volume ratio (compared to average): {volume_ratio}
        Price: {price}
        50 SMA: {sma}
        Price to SMA ratio: {price/sma if sma else 'N/A'}
        
        Provide only a single number as the confidence score (0-100).
        """
        
        # Generate the response
        response = model.generate_content(prompt)
        
        # Parse the confidence score from the response
        score_text = response.text.strip()
        
        # Extract just the number
        score = ''.join(c for c in score_text if c.isdigit())
        if score:
            confidence = min(100, max(0, int(score)))
            logger.info(f"Calculated confidence with Gemini: {confidence}")
            return confidence
        else:
            logger.warning(f"Failed to extract confidence score from Gemini response: {score_text}")
            return calculate_score_formula(pattern_type, rsi, volume_ratio, price, sma)
            
    except Exception as e:
        logger.error(f"Error using Gemini API: {e}")
        return calculate_score_formula(pattern_type, rsi, volume_ratio, price, sma)

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
    # Base score from pattern type
    base_score = 60
    
    # RSI component (0-20 points)
    if pattern_type == "bullish":
        # For bullish patterns, lower RSI is better (oversold condition)
        rsi_score = max(0, 20 - (rsi / 5)) if rsi <= 50 else max(0, 10 - ((rsi - 50) / 5))
    else:
        # For bearish patterns, higher RSI is better (overbought condition)
        rsi_score = max(0, 20 - ((100 - rsi) / 5)) if rsi >= 50 else max(0, 10 - ((50 - rsi) / 5))
    
    # Volume component (0-15 points)
    volume_score = min(15, volume_ratio * 10) if volume_ratio > 0 else 0
    
    # Price vs SMA component (0-5 points)
    if sma and sma > 0:
        ratio = price / sma
        if pattern_type == "bullish":
            # For bullish patterns, price below SMA is good
            price_score = min(5, max(0, 5 * (1 - ratio))) if ratio < 1 else 0
        else:
            # For bearish patterns, price above SMA is good
            price_score = min(5, max(0, 5 * (ratio - 1))) if ratio > 1 else 0
    else:
        price_score = 0
    
    # Calculate final score
    confidence = min(100, int(base_score + rsi_score + volume_score + price_score))
    
    logger.info(f"Calculated confidence with formula: {confidence} (Base: {base_score}, RSI: {rsi_score}, Volume: {volume_score}, Price: {price_score})")
    return confidence