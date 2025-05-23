# Trading Strategy and Analysis Approach

## 1. Overall Philosophy & Goal

*   **Objective:** To generate high-probability, short-term trading signals for leveraged cryptocurrency perpetual contracts, aiming for 1-3% price movements (10-30% returns with 10x leverage).
*   **Edge:** To identify and capitalize on increased market activity/volatility, potentially correlated with the opening/closing of traditional market sessions in key global financial centers.
*   **Methodology:** Combine specific technical analysis conditions, candlestick pattern recognition, and AI-driven confidence scoring to produce actionable signals for manual execution.
*   **Aspiration:** Develop a system with refined intelligence capable of competing with sophisticated trading algorithms, continuously improved through analysis and backtesting.

## 2. Data Inputs

*   **Primary Data Source:** Kraken API.
*   **Asset Type:** Cryptocurrency perpetual contracts/futures.
*   **Candlestick Interval:** 5-minute charts.
*   **Monitored Assets:** User-defined list of high-liquidity pairs (e.g., BTCUSDT, ETHUSDT) stored in `config.py` or Firestore.

## 3. Core Technical Indicators & Patterns (`pandas-ta`)

*   **A. Candlestick Patterns (Forms 40% of local confidence score weighting):**
    *   **Bullish Patterns:**
        *   Hammer
        *   Bullish Engulfing
    *   **Bearish Patterns:**
        *   Shooting Star
        *   Bearish Engulfing
    *   **Confirmation Logic:** *[User to detail: How is a pattern considered "confirmed"? E.g., by the close of the next candle, specific price action on the next candle, etc.?]*
    *   **Scoring Contribution:** *[User to detail: How does a confirmed pattern translate to its portion of the confidence score? Is it binary (pattern confirmed = full 40 points for this component) or graded?]*

*   **B. Relative Strength Index (RSI) (Forms 30% of local confidence score weighting):**
    *   **Period:** 14-period.
    *   **Signal Conditions:**
        *   For Long: RSI < 30 (oversold).
        *   For Short: RSI > 70 (overbought).
    *   **Scoring Contribution:** *[User to detail: How does the RSI value translate to its portion of the confidence score? E.g., linearly scaled within the oversold/overbought zone?]*

*   **C. Trading Volume (Forms 20% of local confidence score weighting):**
    *   **Condition for "High Volume":** Current 5-minute candle's volume > 50-period simple moving average of volume.
    *   **Scoring Contribution:** *[User to detail: Is this binary (high volume = full 20 points for this component)? Or does the degree of volume increase matter?]*

*   **D. Trend Confirmation via Simple Moving Average (SMA) (Forms 10% of local confidence score weighting):**
    *   **Period:** 50-period SMA of closing prices.
    *   **Signal Conditions (in conjunction with patterns/RSI):**
        *   For Long: Price < 50-period SMA.
        *   For Short: Price > 50-period SMA.
    *   **Scoring Contribution:** *[User to detail: Is this binary (price alignment = full 10 points for this component)?]*

## 4. Strategic Market Activity Windows (Formerly "Market Hours")

*   **Concept:** These are UTC time windows identified by the client as periods of potentially increased market activity and opportunity, likely due to overlapping global trading sessions.
    *   00:00 – 02:30 UTC
    *   05:30 – 07:00 UTC
    *   07:45 – 10:00 UTC
    *   20:00 – 23:00 UTC
    *   Potential: ~04:00 UTC.
*   **Application in Strategy:** *[User to detail: How is an active window factored into the signal generation? Examples:*
    *   *Does it act as a primary filter (no signals generated outside these times, as currently in `signal_generator.py`)?*
    *   *Does it increase the confidence score or a weighting factor if a signal occurs within these windows?*
    *   *Is it a prerequisite for considering certain types of weaker signals?*
    *   *Or, is the current `is_market_hours` check in `signal_generator.py` sufficient?]*

## 5. Confidence Scoring (Target > 80 for action)

*   **A. Local Confidence Score Calculation (Fallback & Component):**
    *   **Purpose:** Provides a baseline score if the Gemini API fails or as an input to Gemini.
    *   **Methodology:** Weighted sum of scores from Section 3 (Patterns 40%, RSI 30%, Volume 20%, SMA 10%).
    *   **Detailed Sub-Scoring:** *[User to fill in based on their answers in Section 3 on how each component (Pattern, RSI, Volume, SMA) generates its individual score before weighting and summing].*

*   **B. Google Gemini API Integration (`gemini-1.5-flash` or similar):**
    *   **Objective:** To provide a more nuanced, AI-driven confidence score (0-100) for the potential signal.
    *   **Prompt Engineering:** *[User to detail or provide example: What information is included in the prompt to Gemini? E.g., current price, confirmed pattern type, RSI value, SMA relationship, volume status, market activity window status, type of signal being considered (Long/Short/Exit), etc. How are these weighted or emphasized in the prompt?]*
    *   **Interpretation of Gemini's Score:** How is Gemini's output (expected to be 0-100) used? Does it replace the local score if available, or is it combined?
    *   **Error Handling & Fallback:** If Gemini API call fails or returns an unexpected response, the system defaults to using the Local Confidence Score.

*   **C. Final Confidence Score & Threshold:**
    *   The signal is only considered actionable if the final confidence score (either from Gemini or the local fallback) is **> 80**.

## 6. Signal Generation Logic (Decision Rules)

This section details how all the above elements combine to generate specific signals.

*   **A. Pre-Checks (For any given coin pair):**
    1.  **Market Activity Window Check:** (As per user's definition in Section 4). If this is a hard filter, processing stops if outside active windows.
    2.  **Cooldown Period:** No new Long/Short signal for the same coin within 15 minutes of a *previous successfully generated and acted-upon Long/Short signal* (tracked in Firestore). Exit/Average Down signals are exempt from this cooldown.

*   **B. New Entry Signals (No Open Position for the Coin):**
    *   **Strict Conditions for a LONG Signal:**
        1.  Confirmed Bullish Candlestick Pattern (Section 3A).
        2.  RSI < 30 (Section 3B).
        3.  High Trading Volume (Section 3C).
        4.  Price < 50-period SMA (Section 3D).
        5.  Final Confidence Score > 80 (Section 5C).
        6.  (No open position - implicit by being in this section).
        7.  (Cooldown check passed - Section 6A).
        8.  (Market Activity Window check passed, if a hard filter - Section 6A).
    *   **Strict Conditions for a SHORT Signal:**
        1.  Confirmed Bearish Candlestick Pattern (Section 3A).
        2.  RSI > 70 (Section 3B).
        3.  High Trading Volume (Section 3C).
        4.  Price > 50-period SMA (Section 3D).
        5.  Final Confidence Score > 80 (Section 5C).
        6.  (No open position - implicit).
        7.  (Cooldown check passed).
        8.  (Market Activity Window check passed, if a hard filter).

*   **C. Existing Position Management Signals (Open Position Exists):**
    *   **1. EXIT LONG Signal Conditions:**
        *   Condition A (Profit Target): Current Price shows +1% to +3% profit from entry_price. *[User to specify exact % or range, e.g., >=2%]*
        *   OR Condition B (Reversal Indicated): Confirmed Bearish Candlestick Pattern AND RSI > 70.
        *   AND Final Confidence Score for Exit > 80. *[User to clarify: Does exit also use Gemini score, or a different logic?]*
    *   **2. EXIT SHORT Signal Conditions:**
        *   Condition A (Profit Target): Current Price shows +1% to +3% profit (price has dropped) from entry_price. *[User to specify exact % or range, e.g., >=2%]*
        *   OR Condition B (Reversal Indicated): Confirmed Bullish Candlestick Pattern AND RSI < 30.
        *   AND Final Confidence Score for Exit > 80. *[User to clarify for exit confidence logic]*
    *   **3. AVERAGE DOWN LONG Signal Conditions:**
        *   Current Price shows -2% loss from entry_price.
        *   AND High Trading Volume.
        *   AND Final Confidence Score for Averaging Down > 80. *[User to clarify for avg down confidence logic]*
        *   AND Average Down Count < Max Allowed (e.g., 2 attempts).
    *   **4. AVERAGE DOWN SHORT Signal Conditions:**
        *   Current Price shows +2% loss (price has risen) from entry_price.
        *   AND High Trading Volume.
        *   AND Final Confidence Score for Averaging Down > 80. *[User to clarify for avg down confidence logic]*
        *   AND Average Down Count < Max Allowed (e.g., 2 attempts).
    *   **5. AVERAGE UP Signals (Optional - Currently in `signal_generator.py`):**
        *   *[User to detail if this is desired and under what conditions, e.g., profit target met, high volume, high confidence, no prior average downs.]*

## 7. Risk Management (Considerations for Manual Trading)

*   While the application does not execute trades, signals should ideally provide information to support manual risk management.
*   **Take Profit / Stop Loss:** The Telegram message aims to include calculated TP/SL. *[User to detail: How should these be calculated based on the entry signal? E.g., fixed percentage, based on volatility, support/resistance levels?]*
*   **Leverage:** The system assumes 10x leverage for context; this should be clear in notifications.

## 8. Backtesting and Strategy Refinement

*   **Objective:** To validate the effectiveness of this strategy and fine-tune parameters (e.g., RSI thresholds, confidence score, P/L targets for exits/averaging) before risking real capital.
*   **Methodology:**
    *   [ ] Develop a separate Python script to run the core signal generation logic (`technical_analysis.py`, `signal_generator.py`, `confidence_calculator.py` with mocked/simulated Gemini if necessary) against historical 5-minute kline data from Kraken.
    *   [ ] Simulate trade execution based on generated signals.
    *   [ ] Track performance metrics (win rate, P/L ratio, drawdown, signal frequency).
*   **Refinement:** Use backtesting results to adjust strategy parameters and rules.

---

This document provides a detailed framework. Please fill in the `[User to detail: ...]` sections with your specific strategic logic.

## 9. Technical Implementation Notes

### Logging Optimization (December 2024)
- **Issue:** Cloud Function logs were excessively verbose (~12,000 lines per 5-minute execution) due to detailed technical analysis logging
- **Solution:** Optimized `technical_analysis.py` logging verbosity:
  - Pattern detection logging reduced from 15 rows per pattern to concise summaries 
  - DataFrame logging reduced from 15 rows to single summary lines
  - Maintains essential debugging information while reducing logs to <100 lines per execution
- **Benefits:** Dramatically reduced Cloud Functions logging costs and improved log readability for production monitoring
- **Commit:** `60410dd` - Optimize logging verbosity in technical analysis 