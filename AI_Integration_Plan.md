# CryptoSignalTracker: AI Integration and Optimization Plan

**Overall Goal:** Evolve `CryptoSignalTracker` into an AI-driven system using Google's Gemini model for primary market analysis and trading signal generation. This plan outlines the steps to first optimize the existing rule-based system for better signal frequency and then integrate Gemini for advanced meta-analysis.

## Phase 1: Rule-Based System Optimization (Based on Grok's "DeepSearch Recommendations")

This phase focuses on applying targeted changes to the existing codebase to address low signal frequency, particularly for SHORT signals, by refining thresholds and logic.

1.  **Update `functions/config.py`:**
    *   **Action:** Replace the content of `functions/config.py` with the comprehensive settings provided by Grok's analysis. This includes updated sentiment thresholds, volume tier definitions, candlestick pattern parameters, confidence weights, and technical analysis parameters.
    *   **Key Changes:**
        *   `SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN = 0.2`
        *   `SENTIMENT_THRESHOLD_FOR_RSI_SHORT = 0.0`
        *   Relaxed `VOLUME_TIER_THRESHOLDS`
        *   `ATR_CONFIRMATION_WINDOW = 2`, `MIN_BODY_TO_ATR_RATIO = 0.2`
        *   `CONFIDENCE_WEIGHTS = {'pattern': 0.2, 'rsi': 0.3, 'volume': 0.4, 'sentiment': 0.1}`
        *   `MIN_CONFIDENCE_ENTRY = 10` (remains low for now)
    *   **Commit Message:** "Apply DeepSearch config updates for signal optimization"

2.  **Update `functions/signal_generator.py` (`process_crypto_data` function):**
    *   **Action:** Modify signal intent logic.
    *   **Key Changes:**
        *   Pattern-based SHORT: `sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN`
        *   RSI-based SHORT: `sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_RSI_SHORT`
        *   Refine `sentiment_aligned` check for SHORTs: `sentiment_aligned = sentiment_score < config.SENTIMENT_THRESHOLD_FOR_BEARISH_PATTERN` (ensure this matches the intent, possibly `sentiment_score <= config.SENTIMENT_THRESHOLD_FOR_RSI_SHORT` if for RSI based, or the pattern one if for pattern based).
        *   Allow new entry signals if `current_volume_tier` is 'LOW' or higher (i.e., not 'VERY_LOW' or 'UNKNOWN').
    *   **Commit Message:** "Optimize signal intent logic and volume rules for new entries"

3.  **Update `functions/sentiment_analysis.py` (Clarification Needed):**
    *   **Action:** Grok suggested `sentiment_score = calculate_directional_sentiment_adjustment(symbol, signal_direction, sentiment_score)` directly within `get_sentiment_score` (previously `get_market_sentiment`).
    *   **Current Approach:** `calculate_directional_sentiment_adjustment` is called in `signal_generator.py` *after* `signal_intent` is determined. This seems more logical as `signal_intent` is not known at the time `get_sentiment_score` is called.
    *   **Resolution:** We will maintain the current structure where `get_sentiment_score` returns the base score, and `signal_generator.py` handles the directional adjustment. No changes to `sentiment_analysis.py` under this specific point unless a direct improvement to `get_sentiment_score` itself is identified. The primary sentiment threshold changes are in `config.py` and logic changes in `signal_generator.py`.
    *   **Commit Message (if any changes were made here):** "Refine sentiment score calculation" (Potentially no commit for this sub-step if current logic for adjustment location is kept).

4.  **Update `functions/technical_analysis.py`:**
    *   **Action:** Adjust parameters used in `detect_candlestick_patterns` and `analyze_volume_advanced`.
    *   **Key Changes:**
        *   Ensure `ATR_CONFIRMATION_WINDOW` (from `config.py`) is used effectively in pattern filtering.
        *   Ensure `MIN_BODY_TO_ATR_RATIO` (from `config.py`) is used effectively.
        *   Ensure `analyze_volume_advanced` uses `VOLUME_EWMA_SHORT_PERIOD` from `config.py` and correctly applies the new `VOLUME_TIER_THRESHOLDS`.
    *   **Commit Message:** "Update technical analysis with DeepSearch settings for patterns and volume"

5.  **Update `functions/kraken_api.py`:**
    *   **Action:** Add logging for kline data retrieval.
    *   **Key Change:** `logging.info(f"Kline data for {symbol}: {len(data)} candles")` in `get_kline_data_futures`.
    *   **Commit Message:** "Add logging to Kraken API for data validation"

## Phase 2: Gemini AI Integration for Meta-Analysis

This phase focuses on integrating Gemini to provide a higher-level analysis of the pre-processed data from Phase 1.

1.  **Create `functions/gemini_analyzer.py` (or similar name):**
    *   **Action:** Develop a new module to encapsulate all interactions with the Gemini API.
    *   **Functionality:**
        *   Function to initialize the Gemini client (e.g., `genai.configure(api_key=os.getenv("GEMINI_API_KEY"))`).
        *   Function `analyze_with_gemini(input_data)`:
            *   Takes a dictionary `input_data` (structured as per DeepSeek/Grok, e.g., containing RSI, EMA status, pattern, volume, sentiment, open position, BTC trend).
            *   Constructs an appropriate prompt for the Gemini model.
            *   Calls the Gemini API (e.g., `model.generate_content(prompt)`).
            *   Parses Gemini's response (expected to be JSON with `signal_type`, `confidence`, `reasoning`).
            *   Includes error handling, retries (as suggested by DeepSeek).

2.  **Update `functions/signal_generator.py`:**
    *   **Action:** Integrate calls to `gemini_analyzer.py`.
    *   **Key Changes:**
        *   After the rule-based system has processed data and potentially identified a preliminary `signal_intent` or `final_signal`:
            *   Prepare the `input_data` payload for Gemini (RSI, EMA relationship, pattern name/type, volume tier, sentiment score, open position details, etc.).
            *   Call `gemini_analyzer.analyze_with_gemini(input_data)`.
            *   **Decision Logic:**
                *   If Gemini returns a high-confidence signal (e.g., `gemini_result['confidence'] > 0.5` or a configurable threshold), use Gemini's proposed `signal_type` and `confidence`.
                *   Optionally, allow Gemini to provide `price_targets` (take_profit, stop_loss) as suggested by DeepSeek.
                *   If Gemini's confidence is low or the API call fails, decide on a fallback:
                    *   Use the refined rule-based signal from Phase 1.
                    *   Generate no signal.
        *   Ensure Gemini's output (`signal_type`, `confidence`, etc.) is mapped correctly to the structure expected by the rest of the system (e.g., for Firestore logging and Telegram alerts).
    *   **Commit Message:** "Integrate Gemini AI for meta-analysis of trading signals"

## Phase 3: Testing and Iteration

1.  **Local Testing (`test_local.py`):**
    *   **Action:** Enhance/create `test_local.py` to simulate various market scenarios using mock data for Kraken OHLCV and LunarCrush.
    *   **Focus:**
        *   Verify increased signal frequency (especially SHORTs) after Phase 1 changes.
        *   Test the Gemini integration (Phase 2), mocking Gemini API responses initially, then with live calls (carefully, in a controlled manner).
        *   Log key decision parameters: sentiment scores, volume tiers, patterns detected, RSI, rule-based confidence, Gemini's input & output.
    *   **Commit Message:** "Enhance local testing script for rule-based and Gemini analysis"

2.  **Backtesting (Future Consideration):**
    *   Explore strategies for backtesting the Gemini-enhanced system using historical data. This is complex but crucial for long-term validation.

## Phase 4: Documentation Consolidation

1.  **Update Technical Analysis Documentation:**
    *   **Action:** Create `Technical_Analysis_Documentation_v2.md`.
    *   **Content:** Consolidate all technical analysis logic, parameters from `config.py`, candlestick pattern definitions, volume analysis details, and how these feed into the rule-based system and the Gemini analysis. Reflect the changes made in Phase 1.
    *   **Commit Message:** "Consolidate and update Technical Analysis Documentation (v2)"

## General Notes:

*   All changes to be kept local until explicit approval for a push.
*   Development to occur in the `/Users/arsisiddiqi/Downloads/CryptoSignalTracker/` workspace.
*   Target deployment: `telegram-signals-205cc`, `us-central1`, `run_signal_generation`.
*   Ensure `pandas-ta==0.3.14b0` is used.

---
This plan will be our roadmap. 