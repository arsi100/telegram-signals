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


Updated Trading Strategy for CryptoSignalTracker
1. Overall Philosophy & Goal

Objective: Generate high-probability signals for 1-3% price movements in leveraged crypto perpetual contracts (10x leverage) across a diverse 11-coin portfolio.
Edge: Combine technical analysis, AI-driven sentiment scoring, dynamic market timing, and rigorous backtesting to outperform quant traders, leveraging volatility and market psychology.
Methodology: Use candlestick patterns, optimized indicators, sentiment analysis, and Gemini API scoring, validated through extensive backtesting.

2. Data Inputs

Source: Kraken API (e.g., /0/public/OHLC?pair=PF_XBTUSD&interval=5) for 5-minute OHLC data; Santiment API (/social-trends) for sentiment scores.
Assets: 
Major Coins: PF_XBTUSD (Bitcoin), PF_ETHUSD (Ethereum), PF_SOLUSD (Solana), PF_BNBUSD (Binance Coin), PF_LTCUSD (Litecoin)
Altcoins: PF_XRPUSD (Ripple), PF_ADAUSD (Cardano), PF_DOGEUSD (Dogecoin), PF_TRXUSD (Tron), PF_LINKUSD (Chainlink)
Meme/Newer Coins: PF_PEPEUSD (Pepe, verify availability via /0/public/AssetPairs)
Managed in config.py or Firestore, with active processing confirmed for PF_TRXUSD and PF_LINKUSD.


Data per Coin: 2000 historical data points, fetched every 5 minutes (24/7 schedule).

3. Core Technical Indicators & Patterns

Candlestick Patterns (35% of local confidence score):
Bullish: Hammer, Bullish Engulfing, Morning Star.
Bearish: Shooting Star, Bearish Engulfing, Evening Star.
Confirmation: Next candle closes in signal direction (e.g., green for bullish).
Scoring: Binary (confirmed = 35 points; unconfirmed = 0).


RSI (25%):
Period: 7 (optimized for 5-minute charts).
Conditions: Long: RSI < 35; Short: RSI > 65.
Scoring: Linear scale (e.g., RSI 20 = 25 points, RSI 35 = 0).


Volume (20%):
Condition: Current volume > 1.5x 20-period volume SMA, adjusted per coin.
Scoring: Binary (high volume = 20 points).


EMA (10%):
Period: 20-period EMA, tailored to each coin's volatility.
Conditions: Long: Price < EMA; Short: Price > EMA.
Scoring: Binary (aligned = 10 points).


Multi-Timeframe Check (10%):
Period: 15-minute RSI and EMA alignment with 5-minute signal.
Scoring: Binary (aligned = 10 points; misaligned = 0).



4. Market Activity Windows

Dynamic Trigger: Signals generated when ATR > 1.5x 20-period average or volume spike detected, adapting to each coin's volatility.

5. Sentiment Analysis

Source: Santiment API (/social-trends) for real-time sentiment scores (0-1 scale) based on X and Telegram data for all 11 coins.
Integration: Fetched every 5 minutes, included in Gemini API prompts (e.g., "Sentiment: 0.75 bullish for PF_XBTUSD").
Scoring Contribution: Adds 10% to local score if sentiment aligns with signal direction (e.g., bullish sentiment for long).

6. Confidence Scoring

Local Score: Weighted sum (35% patterns, 25% RSI, 20% volume, 10% EMA, 10% multi-timeframe), with +10% from sentiment if aligned. Total possible = 110, actionable if > 80.
Gemini API:
Prompt: Includes pattern type, RSI, volume ratio, EMA position, multi-timeframe alignment, sentiment score, and coin-specific volatility.
Output: 0-100 score, replaces local score if >80 and available.
Fallback: Use local score if Gemini fails, ensuring reliability for real-money trading.


Threshold: Signal actionable if score > 80.

7. Signal Generation

Pre-Checks: 15-minute cooldown for new signals (except exits/average downs) per coin.
Long Signal:
Confirmed bullish pattern, RSI < 35, high volume, price < EMA, 15-minute alignment, sentiment bullish, score > 80.


Short Signal:
Confirmed bearish pattern, RSI > 65, high volume, price > EMA, 15-minute alignment, sentiment bearish, score > 80.


Exit Long:
Profit > 2% or bearish pattern with RSI > 65, score > 80.


Exit Short:
Profit > 2% or bullish pattern with RSI < 35, score > 80.


Average Down:
Loss > 2%, high volume, score > 80, <2 attempts per coin.



8. Risk Management

TP/SL: TP at 2%, SL at 1.5x ATR below entry (longs) or above (shorts), adjusted per coin.
Position Sizing: Risk 1% of capital per trade with 10x leverage, diversified across 11 coins.
Order Book Check: Use Kraken /0/public/Depth to confirm buy/sell imbalances (e.g., >60% buy orders) before signaling.

9. Backtesting

Script: Use pandas with 2000-point historical Kraken data for all 11 coins to simulate trades, incorporating sentiment and multi-timeframe data.
Metrics: Win rate, profit factor, drawdown per coin.
Optimization: Test RSI (5-14), EMA (10-30), ATR thresholds, sentiment impact for each asset.
Execution Plan: Run backtests post-deployment to validate strategy before scaling capital.

10. Deployment and Monitoring

Deployment: Commit changes to main.py, technical_analysis.py, and signal_generator.py, push to GitHub (e.g., git add ., git commit -m "Add sentiment, multi-timeframe, order book", git push), triggering Cloud Build for telegram-signals-205cc (us-central1, run_signal_generation).
Monitoring: Check Cloud Function logs for signal success across all 11 coins, verify Telegram messages (@Amer_crypto_bot, chat ID 6379641204), and monitor Cloud Scheduler (crypto-signal-generation-job, next run May 23, 2025, ~04:45 AM EDT).

## 11. DETAILED IMPLEMENTATION PLAN

### PHASE 1: IMMEDIATE SIGNAL GENERATION (Deploy Today)
**Goal:** Get signals flowing within 24 hours by fixing overly conservative parameters

**Root Cause Analysis (Per Grok):**
- Current PF_TRXUSD score: 10/80 (RSI: 0, Patterns: 0, Volume: 0, SMA: 10)
- RSI 68.06 missed by 30/70 thresholds, would trigger with 35/65
- Volume 0.0 vs 2082.8 avg (50-period too broad for crypto spikes)
- Only 4 basic patterns detected vs expanded set needed

**Specific Changes:**

**A. Technical Analysis Updates (`functions/technical_analysis.py`):**
1. **RSI Thresholds:**
   - CHANGE: `RSI < 30` → `RSI < 35` (Long)
   - CHANGE: `RSI > 70` → `RSI > 65` (Short)
   - IMPACT: PF_TRXUSD (68.06) would now contribute 25 points vs 0

2. **Volume Analysis:**
   - CHANGE: `50-period SMA` → `20-period SMA`
   - CHANGE: `>1.0x threshold` → `>1.5x threshold`
   - IMPACT: More adaptive to recent crypto volume spikes

3. **Add Candlestick Patterns:**
   - ADD: `Morning Star` (3-candle bullish reversal)
   - ADD: `Evening Star` (3-candle bearish reversal)
   - IMPACT: 6 total patterns vs current 4, higher detection probability

4. **Add ATR Volatility Filter:**
   - ADD: ATR > 1.5x 20-period average requirement
   - IMPACT: Only trade during high-volatility periods

**B. Signal Generator Updates (`functions/signal_generator.py`):**
1. **Confidence Threshold (Temporary):**
   - CHANGE: `>80` → `>70` for testing
   - IMPACT: PF_TRXUSD would score 75+ (10 SMA + 25 RSI + 40 patterns) = SIGNAL

**C. Config Updates (`functions/config.py`):**
1. **RSI Period (Optional):**
   - CONSIDER: `RSI_PERIOD = 14` → `RSI_PERIOD = 10` (more responsive)

**Expected Outcome:**
- PF_TRXUSD example: 10 (SMA) + 25 (RSI 68.06>65) + potential 35 (patterns) = 70+ points = SIGNAL
- Multiple coins likely to trigger within next few runs
- Signal frequency increase from 0 to potentially 2-5 per day across 11 coins

**Deployment Commands:**
```bash
git add functions/technical_analysis.py functions/signal_generator.py functions/config.py
git commit -m "Phase 1: Adjust parameters for immediate signal generation - RSI 35/65, 20-period volume, add patterns, confidence 70"
git push origin main
```

**Monitoring:**
- Next Cloud Scheduler run: ~04:45 AM EDT May 23, 2025
- Watch Cloud Function logs for signal generation
- Verify Telegram messages (@Amer_crypto_bot, chat ID 6379641204)
- If signals generated, proceed to Phase 2

### PHASE 2: FULL STRATEGY IMPLEMENTATION (After Signals Confirmed)
**Goal:** Implement comprehensive system with sentiment, multi-timeframe, and advanced features

**A. Sentiment Analysis Integration:**
1. **Create `functions/sentiment_analysis.py`:**
   - Santiment API integration for all 11 coins
   - Social volume trend-based scoring (0-1 scale)
   - Symbol mapping (PF_XBTUSD → bitcoin)
   - Fallback handling for API failures

2. **Update `functions/main.py`:**
   - Add sentiment import and bulk fetching
   - Pass sentiment data to signal generation

3. **Update Signal Scoring:**
   - Add 10% sentiment bonus if aligned with signal direction
   - Total possible: 110 points (100 + 10 sentiment)

**B. Multi-Timeframe Analysis:**
1. **15-Minute Data Fetching:**
   - Modify `kraken_api.py` to support multiple timeframes
   - Fetch both 5-min and 15-min data

2. **Alignment Validation:**
   - 15-min RSI must agree with 5-min signal direction
   - 15-min EMA trend must align
   - Add 10% multi-timeframe bonus

**C. Advanced Technical Indicators:**
1. **Switch to EMA:**
   - Replace 50-period SMA with 20-period EMA
   - More responsive to price changes

2. **Optimize RSI:**
   - Change to 7-period RSI (from 14)
   - More sensitive to 5-minute chart movements

**D. Order Book Analysis:**
1. **Kraken Depth API:**
   - Fetch order book data via `/0/public/Depth`
   - Calculate buy/sell pressure ratio
   - Require >60% buy orders for long signals

**E. Dynamic Market Timing:**
1. **ATR-Based Triggers:**
   - Only generate signals when ATR > 1.5x 20-period average
   - Adaptive to each coin's volatility profile

**Deployment Timeline:**
- Phase 1: Deploy today (May 22, 2025)
- Monitor: May 23-24, 2025 (confirm signals)
- Phase 2: Deploy May 25-26, 2025 (full upgrade)
- Backtest: May 27+, 2025 (validate with historical data)

**Success Metrics:**
- Phase 1: 2-5 signals per day across 11 coins
- Phase 2: 5-10 signals per day with 70%+ win rate
- Target: 2-3% profit per signal with 1-2% max loss

