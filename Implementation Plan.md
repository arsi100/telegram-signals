# Implementation Plan: Cryptocurrency Trading Signal Application

This document outlines the remaining tasks to complete the Cryptocurrency Trading Signal Application.

## Phase 1: Core Logic Implementation & Refinement

1.  **API Key Configuration:**
    *   [ ] Store API keys securely (Telegram Bot Token/Chat ID, Gemini API Key, CryptoCompare API Key) using environment variables or Google Secret Manager.
    *   [ ] Ensure `.env` file is used for local development and added to `.gitignore`.
    *   [ ] Document how to set up environment variables for Cloud Function deployment.

2.  **Technical Analysis Module (`functions/technical_analysis.py`):**
    *   [ ] Finalize TA-Lib pattern detection (`detect_patterns`) for Hammer, Shooting Star, Engulfing patterns.
    *   [ ] Implement pattern confirmation logic (based on the follow-up candle).
    *   [ ] Ensure `calculate_indicators` (RSI, SMA) and average volume calculation are robust.
    *   [ ] Verify data preprocessing for TA-Lib functions.

3.  **Confidence Scoring Module (`functions/confidence_calculator.py`):**
    *   [ ] Fully integrate the `get_confidence` call using the Gemini API (`gemini-1.5-flash` or similar).
    *   [ ] Develop and refine the prompt sent to Gemini, clearly outlining the weighted factors (Pattern 40%, RSI 30%, Volume 20%, SMA 10%) and current market data.
    *   [ ] Implement robust error handling for the Gemini API calls.
    *   [ ] Implement the fallback algorithm mentioned in the status report (if Gemini fails).

4.  **Signal Generation Logic (`functions/signal_generator.py` - `process_crypto_data`):**
    *   [ ] Integrate results from `technical_analysis.py` and `confidence_calculator.py`.
    *   [ ] Implement the check for all 8 strict conditions defined in `Trading Signal Application.md` for generating Long/Short signals:
        *   [ ] Candlestick Pattern Confirmed
        *   [ ] RSI Alignment (<30 Long / >70 Short)
        *   [ ] High Trading Volume (> 50-period Avg)
        *   [ ] Trend Confirmation via SMA (Price < SMA Long / Price > SMA Short)
        *   [ ] Confidence Score > 80 (from Gemini)
        *   [ ] No conflicting open position
        *   [ ] Cooldown Period (15 min since last Long/Short for the same coin) - Requires Firestore check.
        *   ~~[ ] Market Hours (Removed)~~ 
    *   [ ] Implement logic for Exit and Average Down signals based on P/L targets and secondary confirmations, using data from `position_manager.py`.

5.  **Position Management Module (`functions/position_manager.py`):**
    *   [ ] Finalize Firestore schema for the `positions` collection.
    *   [ ] Complete functions for `save_position`, `update_position` (tracking average down count), `close_position`.
    *   [ ] Implement queries to reliably get the current open position status for a given coin.
    *   [ ] Implement logic to calculate current P/L for open positions to inform Exit/Avg Down signals.
    *   [ ] Implement Firestore query to check for recent signals (for the 15-min cooldown).

6.  **Telegram Notification Module (`functions/telegram_bot.py`):**
    *   [ ] Refine `format_signal_message` to include all required details: type, symbol, entry price, confidence score, calculated take profit/stop loss, leverage (mention 10x), potentially long-term trend indicator (if an external AI API call is added).
    *   [ ] Implement error handling for Telegram API calls.

7.  **Main Cloud Function (`functions/main.py`):**
    *   [ ] Ensure `process_crypto_data` returns comprehensive signal data (including confidence score, type, etc.).
    *   [ ] Ensure the generated signal and position updates are correctly saved to Firestore.
    *   [ ] Add robust logging for each step (fetching, analysis, signal decision, notification, DB write).
    *   [ ] Verify `setup_cloud_scheduler` function correctly configures the job (check project ID, region, target URI).

## Phase 2: Testing & Validation

*   [ ] **Unit Tests:** Write unit tests for critical logic, especially in `technical_analysis.py` and `signal_generator.py` (condition checking).
*   [ ] **Integration Tests:**
    *   [ ] Test API interactions (Bybit, Gemini, Telegram) with mock data or sandbox environments if possible.
    *   [ ] Test Firestore read/write operations for signals and positions.
*   [ ] **End-to-End Testing:**
    *   [ ] Run the `run_signal_generation` function locally (using `service-account.json` and `.env` file) or deploy to a test Firebase environment.
    *   [ ] Trigger the function and monitor logs, Firestore data, and Telegram messages.
    *   [ ] Validate signal generation against known historical data scenarios.
*   [ ] **Backtesting (Optional but Recommended):**
    *   [ ] Develop a separate script to run the signal generation logic against a larger historical dataset from Bybit to evaluate strategy performance and fine-tune parameters (e.g., confidence threshold, P/L targets).

## Phase 3: Deployment & Documentation

*   [ ] **Firebase Configuration (`firebase.json`):**
    *   [ ] Configure function settings: runtime (Python 3.10+), memory, timeout.
    *   [ ] Set up environment variables/secrets for API keys in the deployed environment.
*   [ ] **Firestore Rules (`firestore.rules`):**
    *   [ ] Define appropriate security rules to protect Firestore data (e.g., only allow authenticated function service account to write).
*   [ ] **Deployment:**
    *   [ ] Deploy the function using `firebase deploy --only functions`.
    *   [ ] Deploy Firestore rules and indexes (`firebase deploy --only firestore`).
*   [ ] **Monitoring:**
    *   [ ] Monitor function logs, execution times, and error rates in Google Cloud Console / Firebase Console.
    *   [ ] Monitor Firestore usage against free tier quotas.
*   [ ] **Documentation:**
    *   [ ] Update `README.md` with final setup, configuration, and deployment instructions.
    *   [ ] Add comments to complex code sections.
*   [ ] **Firestore Database Setup:**
    *   [ ] Create a Firestore database in the Firebase Console. For initial development and testing, start in **Test Mode** to allow open access for your backend and local testing.
    *   [ ] **Important:** Before adding real users or going live, switch to **Production Mode** and update Firestore security rules to restrict access (only allow authenticated Cloud Functions or service accounts to read/write as needed).
    *   [ ] Choose a Firestore location/region closest to your main user base (e.g., `me-central1` for Dubai, or the nearest available region).

## Dependencies/External Factors

*   [ ] Ensure TA-Lib C library installation is handled correctly for Cloud Functions environment (may require specifying packages in `functions/requirements.txt` or configuring the build environment).
*   [ ] Monitor API rate limits (Bybit, Gemini, Telegram).
*   [ ] Manage Firebase free tier quotas. 