import logging
import json
import google.generativeai as genai
from . import config

logger = logging.getLogger(__name__)

# Configure the Gemini API key at the module level
try:
    if config.GEMINI_API_KEY:
        genai.configure(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini API key configured.")
    else:
        logger.warning("GEMINI_API_KEY is not set in config. Gemini analysis will be skipped.")
except Exception as e:
    logger.error(f"Error configuring Gemini API key: {e}", exc_info=True)

def get_gemini_analysis(market_data_json: str, symbol: str):
    print(f"***** ENTERING get_gemini_analysis for {symbol} *****") # FORCED PRINT DEBUG
    """
    Sends market data to Gemini for analysis and gets a trading signal.

    Args:
        market_data_json: JSON string containing OHLCV, TAs, sentiment, etc.
        symbol: The trading symbol being analyzed (for logging).

    Returns:
        A dictionary with the analysis result (signal_type, confidence, rationale, etc.)
        or None if an error occurs or Gemini provides no actionable signal.
    """
    # Log the state of critical config values AT THE MOMENT OF THE CALL
    api_key_is_set = bool(config.GEMINI_API_KEY)
    analysis_is_enabled = config.ENABLE_GEMINI_ANALYSIS
    logger.debug(f"[{symbol}] Inside get_gemini_analysis. API Key Set: {api_key_is_set}, Analysis Enabled: {analysis_is_enabled}")

    if not api_key_is_set: # Use the locally captured variable
        logger.warning(f"[{symbol}] Skipping Gemini analysis as API key is not configured (checked at call time).")
        return None
    if not analysis_is_enabled: # Use the locally captured variable
        logger.info(f"[{symbol}] Gemini analysis is disabled in config (checked at call time). Skipping.")
        return None

    logger.debug(f"[{symbol}] Attempting to initialize Gemini model. Configured API Key: {'SET' if api_key_is_set else 'NOT SET'}")
    try:
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL_NAME,
            generation_config={"temperature": config.GEMINI_TEMPERATURE},
            # safety_settings=[ # Consider adding safety settings if needed
            #     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            #     {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            # ]
        )
        
        # Constructing a more detailed prompt
        prompt = f"""
Analyze the following cryptocurrency market data for {symbol} to determine a trading signal (LONG, SHORT, EXIT_LONG, EXIT_SHORT, or NEUTRAL).
The data includes OHLCV candles (5-minute interval, latest candle is last in list), technical indicators, sentiment scores, and current open position context (if any).

Market Data:
{market_data_json}

Based on your analysis of all provided data (technicals, sentiment, volume, patterns, context):
1.  Determine a signal_type: "LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", or "NEUTRAL".
    - If an open position exists, "EXIT_LONG" or "EXIT_SHORT" should be considered if conditions warrant closing.
    - If no position, "LONG" or "SHORT" for new entries, or "NEUTRAL".
    - If "NEUTRAL", it means no strong conviction for a trade or exit at this moment.
2.  Provide a confidence score (0.0 to 1.0) for this signal_type. Higher means more confident.
3.  Provide a brief rationale (array of strings, max 3 points) explaining the key factors for your decision.
4.  If it's an entry signal (LONG/SHORT), suggest price_targets (dictionary with "take_profit" and "stop_loss" as floats, optional if too uncertain).
5.  If it's an entry signal, suggest a position_size_pct (float, 0 to 100) of typical capital allocation for such a trade.

Respond ONLY with a valid JSON object adhering to this structure:
{{
  "signal_type": "...",
  "confidence": 0.0,
  "rationale": ["string1", "string2"],
  "price_targets": {{ "take_profit": null, "stop_loss": null }},
  "position_size_pct": null
}}
If you recommend NEUTRAL, confidence can be low, and other fields can be null or defaults.
If an EXIT signal, price_targets and position_size_pct can be null.
Ensure all float values are numbers, not strings.
"""
        
        logger.debug(f"[{symbol}] Sending prompt to Gemini. Model: {config.GEMINI_MODEL_NAME}. Market data length: {len(market_data_json)}")
        logger.debug(f"[{symbol}] Gemini Prompt (first 500 chars): {prompt[:500]}...")
        
        response = model.generate_content(prompt)
        
        logger.debug(f"[{symbol}] Gemini raw response object: {response}")
        
        if response and response.candidates:
            # Assuming the first candidate is the one we want and response_mime_type="application/json" worked
            # The content should be in response.text if it's JSON, or access parts if structured
            try:
                # If response_mime_type="application/json" is correctly handled by the SDK,
                # response.text should be the JSON string.
                # Some SDK versions/models might put it in response.parts[0].text
                json_response_text = None
                if hasattr(response, 'text') and response.text:
                    json_response_text = response.text
                elif response.parts and hasattr(response.parts[0], 'text') and response.parts[0].text:
                     json_response_text = response.parts[0].text
                else:
                    logger.warning(f"[{symbol}] Could not find JSON text in Gemini response. Response.parts: {response.parts if hasattr(response, 'parts') else 'N/A'}")
                    return None

                logger.info(f"[{symbol}] Gemini response raw text received: {json_response_text}")
                
                # Strip Markdown backticks and optional 'json' language specifier
                if json_response_text.startswith("```json"):
                    json_response_text = json_response_text[7:] # Remove ```json\\n
                elif json_response_text.startswith("```"):
                    json_response_text = json_response_text[3:] # Remove ```\\n
                
                # Strip leading/trailing whitespace first to make endswith more reliable
                json_response_text = json_response_text.strip()
                
                if json_response_text.endswith("```"):
                    json_response_text = json_response_text[:-3] # Remove \`\`\`
                    # Strip again in case there was whitespace before the closing backticks that's now exposed
                    json_response_text = json_response_text.strip() 

                logger.info(f"[{symbol}] Gemini response JSON text (cleaned): {json_response_text}")
                analysis_result = json.loads(json_response_text)
                
                # Basic validation of the received structure
                if not all(k in analysis_result for k in ["signal_type", "confidence", "rationale"]):
                    logger.warning(f"[{symbol}] Gemini response missing one or more key fields (signal_type, confidence, rationale). Result: {analysis_result}")
                    return None
                if not isinstance(analysis_result["confidence"], (int, float)):
                    logger.warning(f"[{symbol}] Gemini confidence is not a number: {analysis_result['confidence']}. Result: {analysis_result}")
                    analysis_result["confidence"] = 0.0 # Default to 0 if invalid

                logger.info(f"[{symbol}] Gemini analysis successful: {analysis_result.get('signal_type')} with confidence {analysis_result.get('confidence')}")
                return analysis_result
                
            except json.JSONDecodeError as jde:
                logger.error(f"[{symbol}] Failed to decode JSON from Gemini response. Error: {jde}. Response text: {json_response_text}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"[{symbol}] Error processing Gemini response content. Error: {e}. Response object: {response}", exc_info=True)
                return None
        else:
            logger.warning(f"[{symbol}] Gemini returned no response or no candidates. Response: {response}")
            if response and response.prompt_feedback:
                 logger.warning(f"[{symbol}] Gemini prompt feedback: {response.prompt_feedback}")
            return None

    except Exception as e:
        logger.error(f"[{symbol}] Error during Gemini API call: {e}", exc_info=True)
        # Check for specific API errors if the SDK provides them
        # The 'e' object itself (google.api_core.exceptions.InvalidArgument) contains useful details.
        # No need to probe for e.response.status_code if it's not consistently there.
        # logger.error(f"[{symbol}] Gemini API error details: {str(e)}") # This is covered by exc_info=True
        return None

# Example Test Block (optional, for direct testing of this module if needed)
if __name__ == '__main__':
    # This block will only run if you execute this file directly (e.g., python functions/gemini_analyzer.py)
    # For this to work, you'd need to ensure config is loaded (e.g. by .env in parent dir or setting env vars)
    # and provide some mock market_data_json.
    
    # Ensure config is loaded if testing directly
    from dotenv import load_dotenv
    import os
    # Assuming .env is in the parent directory of 'functions'
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(dotenv_path)
    
    # Re-initialize config for the test if it wasn't fully loaded before
    # This is a bit hacky for standalone module testing; normally config is imported once.
    class MockConfig:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # or your preferred model
        GEMINI_TEMPERATURE = 0.2
        ENABLE_GEMINI_ANALYSIS = True # To allow the function to run
    
    config = MockConfig() # Override the imported config for this test
    
    # Re-configure Gemini API key if testing standalone
    if config.GEMINI_API_KEY:
        genai.configure(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini API key configured for __main__ test.")
    else:
        logger.warning("GEMINI_API_KEY not found in .env for __main__ test.")

    logging.basicConfig(level=logging.DEBUG) # Enable debug logging for this test
    
    mock_market_data = {
        "pair": "TEST_COIN",
        "timestamp_utc_latest_candle": 1678886400,
        "ohlcv_5min_last_n_candles": [[1678886100, 100, 105, 99, 102, 1000]],
        "technical_indicators": {"rsi": 55, "ema_20": 101},
        "sentiment_analysis_data": {"calculated_sentiment_score_raw": 0.1},
        "current_position_context": {"current_position_type": None}
    }
    mock_market_data_json = json.dumps(mock_market_data)
    
    if config.GEMINI_API_KEY:
        logger.info("Attempting test call to get_gemini_analysis...")
        analysis = get_gemini_analysis(mock_market_data_json, "TEST_COIN")
        if analysis:
            logger.info(f"Test analysis result: {analysis}")
        else:
            logger.error("Test analysis failed or returned None.")
    else:
        logger.warning("Cannot run __main__ test for Gemini as API key is missing.") 