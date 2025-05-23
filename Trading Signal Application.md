    # Project: Cryptocurrency Trading Signal Application

    ## Objective
    Build a Python-based application deployed on Firebase's free tier that monitors 5-minute candlestick charts for user-defined cryptocurrencies (futures/perpetual contracts) on Kraken. The application generates leveraged long, short, exit, or average down signals with confidence scores and sends them via a Telegram bot. The focus is on identifying 1-3% price movements (~10-30% returns with 10x leverage) based on strict technical analysis conditions, ideally during specific windows of heightened market activity. The application tracks open positions in Firestore but does not execute trades automatically.

    ## Context & Background
    - **Target User:** Client using a margin account for leveraged (10x) futures trading.
    - **Trading Strategy:** Manually executed trades based on high-probability signals, aiming for small, frequent gains during volatile periods. Relies on technical indicators and pattern recognition, cross-referenced with an existing external AI for long-term trend validation.
    - **Technical Constraints:** Must run on Firebase free tier (Cloud Functions, Firestore). Utilizes Kraken API, Telegram Bot API, Google Gemini (free tier) for scoring, and potentially CryptoCompare as a data backup. Requires `pandas-ta` for technical analysis.
    - **Developer:** Skilled in Python, Telegram bots, Firebase; limited margin trading knowledge. Prefers cost-free solutions.

    ## Core Requirements & Features
    1.  **Deployment:** Firebase Cloud Functions & Firestore (Free Tier).
    2.  **Data Source:** Kraken API (Kline endpoint for 5-min candles). CryptoCompare as backup.
    3.  **AI Integration:** Google Gemini for confidence scoring (0-100). Grok 3 as alternative. External AI for long-term trend (via API call).
    4.  **Signal Delivery:** Telegram Bot.
    5.  **Monitored Assets:** User-defined list (initially 5-10 high-liquidity pairs like BTCUSDT, ETHUSDT) stored in Firestore/config.
    6.  **Market Activity Windows (Strategic Consideration):** Signals are ideally identified during specific UTC windows believed to have higher market activity and potential for short-term opportunities. These are not necessarily hard gates for function execution but inform the strategic timing of analysis:
        - 00:00 – 02:30
        - 05:30 – 07:00
        - 07:45 – 10:00
        - 20:00 – 23:00
        - Potential short windows around 04:00 UTC.
    7.  **Position Tracking:** Firestore to track open positions (symbol, type, entry price, status, avg_down_count). No automatic trade execution.
    8.  **Signal Types:** Long, Short, Exit Long, Exit Short, Average Down Long, Average Down Short.

    ## Strict Conditions for Signal Generation (Confidence Score > 80)
    Signals are generated based on a weighted combination of factors, calculated every 5 minutes during market hours, but only sent if **all** applicable conditions are met:
    1.  **Candlestick Pattern (40%):** Reliable bullish (Hammer, Bullish Engulfing) or bearish (Shooting Star, Bearish Engulfing) pattern detected using `pandas-ta`, confirmed by follow-up candle.
    2.  **RSI Alignment (30%):** 14-period RSI < 30 (oversold) for Long, > 70 (overbought) for Short.
    3.  **High Trading Volume (20%):** Current 5-min volume > 50-period average volume.
    4.  **Trend Confirmation via SMA (10%):** Price relative to 50-period SMA must align (Price < SMA for Long, Price > SMA for Short).
    5.  **Confidence Score Threshold (>80):** Gemini-calculated score must exceed 80.
    6.  **Position Status:**
        - No open position for the coin allows Long/Short signals.
        - Open position allows Exit or Average Down signals based on profit/loss targets and secondary indicator confirmations (e.g., counter-pattern + RSI).
            - Exit Long: +1-3% profit OR Bearish Pattern + RSI > 70.
            - Exit Short: +1-3% profit (price drop) OR Bullish Pattern + RSI < 30.
            - Average Down Long: -2% loss, high volume, confidence > 80.
            - Average Down Short: +2% loss (price rise), high volume, confidence > 80.
    7.  **Cooldown Period (15 Min):** No new Long/Short signal for the same coin within 15 minutes of a previous signal (tracked in Firestore). Exit/Avg Down exempt.
    8.  **Market Hours:** Function execution restricted to specified high-volume UTC times.

    ## Action Plan / Implementation Steps
    1.  **Setup Environment:**
        - [ ] Initialize Firebase project (`firebase init functions`).
        - [x] Create `requirements.txt` (Manual).
        - [x] Create `.gitignore` (Manual).
        - [x] Create `project_doc.md` (Manual).
        - [ ] Create `main.py`.
        - [ ] Create `README.md`.
        - [ ] Obtain API Keys (Kraken, CryptoCompare, Gemini, Telegram Bot Token, Existing AI API). Store securely (e.g., Firebase environment variables or Secret Manager).
        - [ ] Set up Firebase project (Firestore database, Cloud Functions).
        - [ ] Install dependencies (`pip install -r requirements.txt`). Ensure `pandas-ta` is the primary TA library.
    2.  **Configuration Management:**
        - [ ] Implement a way to manage tracked coins (e.g., Firestore collection or config file).
        - [ ] Store API keys and sensitive data securely.
    3.  **Data Fetching Module:**
        - [ ] Implement `fetch_kraken_kline` using Kraken REST API.
        - [ ] (Optional) Implement WebSocket connection for real-time data (`wss://stream.bybit.com/v5/public/linear`).
        - [ ] Implement `fetch_cryptocompare_kline` as a backup.
        - [ ] Add error handling for API requests (timeouts, rate limits, invalid responses).
    4.  **Technical Analysis Module:**
        - [ ] Implement `detect_patterns` using `pandas-ta` (Hammer, Shooting Star, Engulfing). Handle pattern confirmation logic (next candle).
        - [ ] Implement `calculate_indicators` using `pandas-ta` (RSI, SMA).
        - [ ] Calculate average volume.
        - [ ] Ensure data is pre-processed correctly for TA-Lib (numpy arrays).
    5.  **Confidence Scoring Module:**
        - [ ] Implement `get_confidence` using Google Gemini API (`gemini-1.5-flash`).
        - [ ] Format prompt clearly with weighted factors.
        - [ ] Handle potential API errors or unexpected responses from Gemini.
    6.  **Firestore Management:**
        - [ ] Define Firestore schemas for `positions` and `signals` collections.
        - [ ] Implement functions: `save_position`, `update_position` (for averaging down), `close_position`.
        - [ ] Implement query to check for recent signals (cooldown).
        - [ ] Implement query to check current open position status.
        - [ ] Initialize `firebase_admin` SDK.
    7.  **Signal Generation Logic (`generate_signal`):**
        - [ ] Combine data fetching, technical analysis, and Firestore checks.
        - [ ] Implement all 8 strict conditions precisely.
        - [ ] Calculate profit/loss targets for exit/average down signals.
    8.  **Telegram Notification Module:**
        - [ ] Implement `send_telegram_signal`.
        - [ ] Fetch long-term trend from the existing AI API.
        - [ ] Format message clearly with all required details (type, symbol, price, confidence, target, stop loss, leverage, long-term trend).
        - [ ] Handle Telegram API errors.
    9.  **Cloud Function Orchestration (`main.py`):**
        - [ ] Define the main scheduled Cloud Function (`analyze_candles`) using `firebase_functions.scheduler_fn`.
        - [ ] Set the correct cron schedule string for market hours.
        - [ ] Loop through tracked coins.
        - [ ] Call `fetch_kraken_kline`, `generate_signal`.
        - [ ] If a signal is generated:
            - Call `send_telegram_signal`.
            - Log the signal in Firestore (`signals` collection).
            - Update position status in Firestore (`positions` collection) using helper functions.
        - [ ] Add robust logging throughout the process.
    10. **Testing & Validation:**
        - [ ] Unit tests for TA module, signal condition logic.
        - [ ] Integration tests for data fetching and Firestore interactions.
        - [ ] Backtesting using historical Bybit data (consider fetching larger datasets).
        - [ ] Live testing with demo signals (or small real amounts if client agrees) during market hours. Monitor Firestore and Telegram.
    11. **Deployment:**
        - [ ] Configure `firebase.json` for function deployment (runtime, memory, timeout, environment variables/secrets).
        - [ ] Deploy using `firebase deploy --only functions`.
        - [ ] Monitor logs and quotas in Firebase Console.

    ## Notes & Considerations
    - **`pandas-ta` Usage:** `pandas-ta` is used for technical analysis, simplifying dependencies compared to TA-Lib.
    - **Rate Limits:** Monitor Bybit API usage. WebSocket is preferred for frequent polling but adds complexity. REST polling every 5 minutes should be acceptable for ~10 coins.
    - **Error Handling:** Implement retries, exponential backoff for API calls. Log errors clearly.
    - **Timezones:** Be explicit with timezones, especially for market hours and Firestore timestamps (use UTC).
    - **Backtesting:** Crucial for validating the strategy and refining the confidence threshold (80 is a starting point).
    - **Firebase Costs:** Monitor free tier usage (invocations, Firestore reads/writes/storage). Optimize Firestore queries.
    - **Gemini Costs/Limits:** Be aware of free tier limits for the Gemini API.

