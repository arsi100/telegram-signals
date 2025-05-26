Detailed Breakdown of Analysis Logic and Processing Flow
The core of the signal generation happens in functions/main.py within the run_signal_generation function, which iterates through each coin in config.TRACKED_COINS and calls process_crypto_data (from functions/signal_generator.py) for each.
Here's the detailed flow within process_crypto_data(symbol, kline_data, db):
Phase 1: Initial Checks & Data Gathering
Market Hours Check (is_market_hours in utils.py):
Checks if the current UTC time is within config.MARKET_HOURS (start/end hour, active days).
If not in market hours, it logs and returns None (no signal).
Current Status: This is active and using real time. For 24/7 crypto, it should always pass.
Cooldown Period Check (is_in_cooldown_period in position_manager.py):
Queries Firestore for the last signal timestamp for the given symbol.
If a recent signal (within config.SIGNAL_COOLDOWN_MINUTES, currently 15 mins) exists, it logs and returns None.
Current Status: This is active and using real Firestore data (or mock Firestore in test_local_pipeline.py).
Technical Analysis (analyze_technicals in technical_analysis.py):
Takes a list of kline data (OHLCV).
Data Preparation: Converts to a Pandas DataFrame, calculates typical price, etc.
RSI Calculation: Calculates RSI using pandas_ta.rsi(close, length=config.RSI_PERIOD). RSI_PERIOD is currently 7.
EMA Calculation: Calculates EMA using pandas_ta.ema(close, length=config.EMA_PERIOD). EMA_PERIOD is currently 20.
SMA Calculation: Calculates SMA using pandas_ta.sma(close, length=config.SMA_PERIOD). SMA_PERIOD is currently 14.
ATR Calculation: Calculates ATR using pandas_ta.atr(high, low, close, length=config.ATR_PERIOD). ATR_PERIOD is currently 14.
Volume Analysis (analyze_volume_advanced):
Calculates average volume over config.VOLUME_PERIOD (currently 10).
Compares current volume to average to get volume_ratio.
Assigns a volume_tier (EXTREME, VERY_HIGH, HIGH, ELEVATED, NORMAL, LOW, VERY_LOW, UNKNOWN) based on the ratio.
Calculates EWMA of volume and price range, and their correlation.
Sets late_entry_warning based on conditions (e.g., extreme volume after a significant price move).
Current Status: This is active and seems to be using real calculations. No obvious mock data here.
Candlestick Pattern Detection (detect_candlestick_patterns):
Uses pandas_ta to detect a suite of candlestick patterns (e.g., df.ta.cdl_pattern(name='all')).
Iterates through known patterns (Hammer, Shooting Star, Engulfing, etc.) and checks if any were detected on the latest complete candle or the one before (raw check).
It prioritizes "confirmed" patterns (not just raw). A "raw" pattern means it was detected on the very last candle which might still be forming or very recent.
Returns a dictionary like {'pattern_name': 'Raw Hammer', 'pattern_type': 'bullish', 'pattern_detected_raw': True} or {'pattern_name': 'N/A', 'pattern_type': 'neutral', 'pattern_detected_raw': False}.
Current Status: This relies on TA-Lib via pandas-ta. We confirmed TA-Lib is working locally. The logic for "raw" vs. "confirmed" might be something to review for sensitivity. No mock data.
ATR Filter (atr_filter): This is calculated but not currently used in the signal_generator.py logic to directly influence signal decisions. It's returned in tech_results.
Returns a dictionary tech_results containing latest_close, rsi, ema, pattern (dict), volume_analysis (dict), atr_filter.
If tech_results is None (e.g., not enough data), process_crypto_data returns None.
Current Status: All calculations seem to be based on the input kline data.
Sentiment Analysis:
get_sentiment_score(symbol) in sentiment_analysis.py:
Uses LUNARCRUSH_API_KEY and LUNARCRUSH_SYMBOL_MAP to call the LunarCrush API (https://lunarcrush.com/api4/public/coins/{mapped_symbol}/v1).
Extracts galaxy_score.
Derives sentiment_score from galaxy_score:
If galaxy_score > 65 (strong positive), sentiment_score = (galaxy_score - 50) / 50 (scales 0.3 to 1.0 for GS 65-100).
If galaxy_score < 35 (strong negative), sentiment_score = (galaxy_score - 50) / 50 (scales -0.3 to -1.0 for GS 35-0).
Else (neutral GS 35-65), sentiment_score = (galaxy_score - 50) / 100 (scales -0.15 to 0.15).
If API call fails or data is missing, sentiment_score defaults to 0.0.
Returns sentiment_score and sentiment_metrics (raw data from API).
Current Status: Uses the live LunarCrush API. The mapping from Galaxy Score to our internal sentiment_score is a key piece of logic.
get_sentiment_confidence(sentiment_score, sentiment_metrics) in sentiment_analysis.py:
This function currently calculates a confidence score based on the sentiment_score itself and potentially social_volume (though social_volume is often missing from v4 API).
The main part is: abs(sentiment_score) * config.SENTIMENT_WEIGHT. SENTIMENT_WEIGHT is 0.20. So, a sentiment_score of 0.5 gives 0.5 * 0.20 = 0.10 sentiment confidence. A sentiment_score of -1.0 gives 1.0 * 0.20 = 0.20.
Current Status: This is active. The sentiment_confidence is passed to get_confidence_score.
Phase 2: Position Status & Intent Determination
Check Position Status (get_open_position in position_manager.py):
Queries Firestore to see if there's an "open" position for the symbol.
Returns current_position (dict with details like type, entry_price, ref_path, avg_down_count) or None.
Current Status: Active, uses real Firestore.
Determine Potential Signal Intent (signal_intent): This is a critical section in signal_generator.py.
Initialize signal_intent = None.
pattern_detected = pattern.get("pattern_detected_raw", False)
pattern_type = pattern.get("pattern_type", "")
Primary intent from patterns:
If pattern_detected is True:
If pattern_type == "bullish" AND sentiment_score >= config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN (currently -0.05), then signal_intent = "LONG".
If pattern_type == "bearish" AND sentiment_score <= -config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN (currently <= -(-0.05), i.e., <= 0.05), then signal_intent = "SHORT".
Logic for SHORT with pattern: The condition sentiment_score <= -config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN (which is sentiment_score <= 0.05 because SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN is -0.05) might be too permissive for a bearish pattern. A bearish pattern should ideally align with negative sentiment.
Secondary intent from RSI and Sentiment (if signal_intent is still None):
If rsi <= config.RSI_OVERSOLD_THRESHOLD (currently 35) AND sentiment_score > config.SENTIMENT_THRESHOLD_NEUTRAL (currently -0.25), then signal_intent = "LONG".
If rsi >= config.RSI_OVERBOUGHT_THRESHOLD (currently 65) AND sentiment_score < -config.SENTIMENT_THRESHOLD_NEUTRAL (currently < -(-0.25), i.e., < 0.25), then signal_intent = "SHORT".
Logic for SHORT with RSI: sentiment_score < -config.SENTIMENT_THRESHOLD_NEUTRAL (i.e., sentiment_score < 0.25) is also quite permissive. It means a significantly overbought RSI could trigger a SHORT even if sentiment is neutral or slightly positive (e.g., 0.20).
Current Status: This logic is active. We are definitely evaluating for SHORT signals. The conditions for them (bearish pattern + sentiment OR overbought RSI + sentiment) might not be met by current market data, or the sentiment alignment thresholds might be too broad.
Phase 3: Process Signals Based on Position Status
If current_position exists (Open Position Logic):
Calculates P&L.
EXIT Conditions:
Profit target reached (pnl_percent >= config.PROFIT_TARGET_PERCENT).
Reversal signal:
LONG position + bearish pattern + RSI > 65 + sentiment < 0.
SHORT position + bullish pattern + RSI < 35 + sentiment > 0.
If exit_signal is True:
confidence = get_confidence_score(tech_results, sentiment_confidence).
If should_generate_signal(confidence, "EXIT") (i.e., confidence >= config.MIN_CONFIDENCE_EXIT, currently 45), then final_signal is an EXIT signal.
AVERAGE DOWN Conditions (if no exit and avg_down_count < MAX_AVG_DOWN_COUNT):
P&L <= -config.LOSS_TARGET_PERCENT.
Volume tier is 'ELEVATED' or 'NORMAL'.
No late_entry_warning.
Sentiment aligns with position type (LONG needs positive sentiment, SHORT needs negative).
confidence = get_confidence_score(...).
If should_generate_signal(confidence, f"AVG_DOWN_{position_type}") (uses config.MIN_CONFIDENCE_AVG, currently 70), then final_signal is AVG_DOWN.
AVERAGE UP Conditions (if no exit, no avg_down, and avg_down_count == 0):
P&L >= config.PROFIT_TARGET_PERCENT * 1.5.
Similar volume, late warning, and sentiment checks as AVG_DOWN.
confidence = get_confidence_score(...).
If should_generate_signal(confidence, f"AVG_UP_{position_type}") (uses config.MIN_CONFIDENCE_AVG), then final_signal is AVG_UP.
Current Status: This logic is active but only triggers if a position is already open for that coin in Firestore.
Else (If signal_intent exists - New Position Logic):
volume_tier_ok = volume_analysis.get('volume_tier') in ['EXTREME', 'VERY_HIGH', 'HIGH', 'ELEVATED', 'NORMAL', 'LOW'].
late_warning = volume_analysis.get('late_entry_warning', False).
sentiment_aligned check (this re-checks sentiment based on how signal_intent was derived, which is a bit redundant but acts as a safeguard).
If volume_tier_ok AND NOT late_warning AND sentiment_aligned:
confidence = get_confidence_score(tech_results, sentiment_confidence) (from confidence_calculator.py). This function:
Calculates individual confidence scores for pattern, RSI, volume (EMA, multi-timeframe are currently weighted 0).
pattern_confidence: 1.0 if pattern, 0.5 if no pattern but RSI is extreme, else 0.0.
rsi_confidence: Scales based on how far RSI is into oversold/overbought.
volume_confidence: Based on volume_tier (e.g., EXTREME=1.0, NORMAL=0.4, LOW=0.2, VERY_LOW=0.0).
Combines these with config.CONFIDENCE_WEIGHTS.
Adds the sentiment_confidence (calculated earlier, which is abs(sentiment_score) * 0.20).
Multiplies by 100.
should_gen = should_generate_signal(confidence, signal_intent) (from confidence_calculator.py). This function:
Checks confidence >= config.MIN_CONFIDENCE_ENTRY (currently 10) for LONG/SHORT.
If should_gen is True, then final_signal is a new LONG or SHORT signal.
Current Status: This is the path that generated the BNBUSD signal. All calculations seem to be based on live data and defined configurations.
Phase 4: Record & Return
Record Signal Timestamp (record_signal_ts in position_manager.py):
If final_signal is a new LONG or SHORT, records the current timestamp in Firestore to manage the cooldown.
Current Status: Active.
Return final_signal:
This dictionary (or None) is returned to main.py.
main.py then saves the position to Firestore (if it's a new entry/avg_down/avg_up) and sends a Telegram notification (if it's a new entry or exit).
Summary of Concerns & Potential Issues:
No Mock Data Found in Core Logic: Based on this deep dive, the core signal_generator.py, technical_analysis.py, sentiment_analysis.py, and confidence_calculator.py do not appear to be using hardcoded dummy data or mock objects during a live run initiated by functions-framework. The test_local_pipeline.py script does use mocks, but that's separate from running the function directly.
Strictness of signal_intent Logic:
The primary bottleneck is the generation of signal_intent. If no intent is formed, confidence scores are irrelevant for new signals.
Pattern Detection: Perhaps patterns are not forming frequently on 5-min charts, or our detection criteria (detect_candlestick_patterns) isn't sensitive enough (e.g., the "raw" vs. "confirmed" logic).
RSI + Sentiment for Intent:
For LONG, needing RSI <= 35 AND sentiment_score > -0.25 is still fairly specific.
For SHORT, needing RSI >= 65 AND sentiment_score < 0.25 is also specific. The sentiment condition here sentiment_score < 0.25 for a SHORT is broad; it would allow a SHORT if sentiment is 0.20 (slightly positive) as long as RSI is overbought. This might be counter-intuitive. Perhaps it should be sentiment_score < -config.SENTIMENT_THRESHOLD_NEUTRAL (so < -(-0.25) i.e. <0.25 if SENTIMENT_THRESHOLD_NEUTRAL is negative) or even more strictly sentiment_score < some_negative_threshold_for_short.
Sentiment Score Derivation: The mapping of LunarCrush galaxy_score to our internal sentiment_score significantly impacts the logic. If galaxy_score hovers in the 35-65 "neutral" range, our sentiment_score will be small (between -0.15 and +0.15). This makes it hard to cross the SENTIMENT_THRESHOLD_NEUTRAL (even at -0.25) if it requires strongly positive/negative sentiment.
Volume Tiers: VERY_LOW volume prevents signals. This is reasonable, but some coins might often have very low volume on Kraken futures.
LunarCrush API Limitations: The rate limiting and missing data fields (average_sentiment_score, social_volume) for some coins mean we're relying heavily on galaxy_score and sometimes getting default 0.0 sentiment.
Confidence Weights: The current CONFIDENCE_WEIGHTS give 0% to EMA and Multi-timeframe analysis. This simplifies things but also means we're not using all potential inputs. Pattern (35%), RSI (15%), Volume (30%) are the main drivers if an intent is formed. Sentiment's direct impact on the final confidence score (beyond intent generation) comes from the sentiment_confidence component which is abs(sentiment_score) * 0.20.
Regarding your concern about only LONG events / lack of SHORTs:
The system is designed to detect SHORT signals.
Pattern-based SHORT: pattern_type == "bearish" AND sentiment_score <= 0.05.
RSI-based SHORT: RSI >= 65 AND sentiment_score < 0.25.
The lack of SHORT signals suggests these combined conditions haven't been met frequently with the live data. For example, in the last log, PF_TRXUSD had RSI=50.21 (not overbought) and Sentiment=0.00. PF_LTCUSD had RSI=63.24 (close to overbought but not >=65) and Sentiment=0.00.
Plan for Grok (and our own next steps):
This detailed breakdown should be a good starting point for Grok. Key areas to focus research and optimization on would be:
signal_intent Generation Logic:
Are the conditions for pattern-based and RSI-based intent too strict or misaligned (especially the sentiment components)?
Review the sentiment_score <= -config.SENTIMENT_THRESHOLD_EXTREME_OPPOSITE_PATTERN (i.e. sentiment_score <= 0.05) for bearish patterns. This should likely require negative sentiment.
Review sentiment_score < -config.SENTIMENT_THRESHOLD_NEUTRAL (i.e. sentiment_score < 0.25) for RSI-based shorts. This should also likely require negative sentiment.
Sentiment Analysis Robustness:
How to better handle missing LunarCrush data or rate limits?
Is the galaxy_score to sentiment_score mapping optimal?
Pattern Detection Sensitivity:
Is detect_candlestick_patterns effective for 5-min charts? Should "raw" patterns be given more weight?
Volume Analysis Impact:
Is the VERY_LOW volume filter too restrictive for some listed coins?
Is the late_entry_warning too aggressive?
Confidence Score Calculation:
Review CONFIDENCE_WEIGHTS. Should EMA or multi-timeframe analysis be reintroduced?
How does sentiment_confidence interact with the overall score?
Threshold Values (config.py): Systematically review all thresholds (RSI, Sentiment, Confidence entry/exit points) for appropriateness for 5-minute futures trading.
