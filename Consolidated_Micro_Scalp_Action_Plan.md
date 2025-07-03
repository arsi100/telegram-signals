# CryptoSignalTracker: Unified Action Plan for MICRO-SCALP Engine

This document outlines a consolidated action plan to develop and integrate the "MICRO-SCALP" engine into the existing CryptoSignalTracker application. It synthesizes the best recommendations from analyses provided by Gemini, Claude, DeepSeek, and Grok.

---

## PHASE 1: Data Infrastructure & Foundation (1 Week)

**Objective:** Build a robust, low-latency data pipeline and storage foundation. Get this right before any logic is written.

**Key Actions:**

1.  **GCP Service Setup:**
    *   **Cloud Run:** Provision a new service for the MICRO-SCALP engine. Configure it with `min-instances = 1` to ensure it's "always-on" and avoids cold-start latency (per Gemini's recommendation).
    *   **Cloud Pub/Sub:** Create topics for:
        *   `raw-tick-data-bybit` (for incoming WebSocket data)
        *   `ohlc-data-kraken` (for incoming REST data)
        *   `macro-bias-updates` (for communication from the MACRO engine)
        *   `trade-signals-micro` (for publishing scalp signals)
    *   **Cloud Bigtable:** (Per Gemini's advice for high-throughput state) Provision an instance to store real-time, rapidly changing data:
        *   `live-positions` table (single source of truth for both engines)
        *   `order-book-snapshots` table
    *   **BigQuery:** Set up datasets for long-term storage, analysis, and backtesting:
        *   `historical_ohlcv`
        *   `historical_ticks`
        *   `trade_signal_logs`
    *   **Secret Manager:** Store all exchange API keys and bot tokens.

2.  **Data Ingestion Pipeline:**
    *   Develop a Python service (to be deployed on Cloud Run) that connects to the **Bybit WebSocket** to stream tick data for the top 25 USDT perpetual pairs. It will immediately publish this raw data to the `raw-tick-data-bybit` Pub/Sub topic.
    *   Develop a separate Cloud Function triggered on a schedule (e.g., every minute) to fetch **Kraken OHLC** data and publish it to the `ohlc-data-kraken` topic.

---

## PHASE 2: Core Scalping Logic & Development (2 Weeks)

**Objective:** Build the core intelligence of the MICRO-SCALP engine.

**Key Actions:**

1.  **Level-Finder Module:**
    *   Implement a robust module to identify S/R levels and trend lines.
    *   **Horizontal S/R:** Use 15-minute candles (`last 120 candles` lookback). A level is valid if `price touched ≥ 3x within 0.25%`. A "touch" must be quantitatively defined (e.g., candle low/high is within 0.1% of the level).
    *   **Diagonal Trend Line:** Use linear regression on 1-hour swing highs/lows (`last 200 swings`). Add a **guard for quality**: the R² value of the regression must be `> 0.7` to be considered a valid trend (per DeepSeek's suggestion).

2.  **Exhaustion & Entry Logic Module:**
    *   Develop the logic for the entry trigger, which requires `≥ 2` exhaustion checks.
    *   **Quantify Checks:**
        *   `RSI-7`: `> 80` (overbought) or `< 20` (oversold).
        *   `Low Volume`: Define as volume `< 0.75x` of the 20-period EMA of volume.
        *   `Double Wick`: Define with precise criteria (e.g., wicks are >60% of candle range and their highs/lows are within 0.1% of each other).
        *   `Order-Book Flip`: Implement a listener for Level 2 data from the WebSocket. A valid flip requires a significant shift in liquidity, not just a simple bid/ask change.

3.  **Risk & Execution Module:**
    *   **Order Placement:** Integrate with Bybit's API to place trades. **Use Limit Orders exclusively** for both entry (TP) and exit (SL) to control slippage.
    *   **Dynamic Position Sizing:** (Per Gemini's critical risk insight) Do NOT use a fixed `10% of equity`. Instead, calculate position size based on a **total portfolio risk model**. For example, cap the total risk across ALL open scalp trades to a maximum of 2% of total account equity at any given time.
    *   **Telegram Integration:** Create a module that, upon a signal, generates a PNG chart plot (using `mplfinance` or `plotly`) with the S/R lines, trend line, and entry/TP/SL levels, and sends it to Telegram.

---

## PHASE 3: Integration & Coexistence (1 Week)

**Objective:** Ensure the MACRO and MICRO engines work together seamlessly.

**Key Actions:**

1.  **Modify MACRO Engine:**
    *   Add functionality to publish its confidence score and directional bias (`LONG`/`SHORT`) to the `macro-bias-updates` Pub/Sub topic whenever a new SWING signal is generated or updated. Include a 4-hour TTL for the bias.

2.  **Implement Integration Rules in MICRO Engine:**
    *   **Position Conflict Rule:** Before placing a trade, the MICRO engine **must** query the `live-positions` table in Bigtable. If a `SWING` position exists for the same pair, it will halve its calculated trade size.
    *   **Macro Bias Filter:** The MICRO engine will subscribe to the `macro-bias-updates` topic.
        *   If `macro_confidence ≥ 80` for `LONG`, the engine is **only allowed to take LONG scalps**.
        *   If `macro_confidence ≥ 80` for `SHORT`, the engine is **only allowed to take SHORT scalps**.
        *   **Hysteresis Buffer:** (Per DeepSeek's insight) The filter is only *removed* when confidence drops below `70%`. This prevents the engine from rapidly toggling on and off if confidence hovers around 80%.

---

## PHASE 4: Backtesting & Strategy Optimization (2 Weeks)

**Objective:** Rigorously validate and optimize the trading strategy's profitability and robustness before risking real capital. This phase is iterative and data-driven.

**Key Actions:**

1.  **Establish Backtesting Framework:**
    *   Utilize the `backtester.py` script to run simulations against historical data stored in BigQuery/Bigtable.
    *   **Crucially, incorporate realistic transaction costs (e.g., 0.06% per trade) and potential slippage into all performance calculations.** A strategy that looks good on paper can be a loser once fees are included.

2.  **Execute Multi-Variable Parameter Optimization:**
    *   Instead of testing one variable at a time, systematically test combinations of key parameters to find the most profitable configuration.
    *   **EMA Period:** Test a range of short-term trend lengths (e.g., `10`, `15`, `20`, `30`).
    *   **RSI Period:** Test different sensitivity levels for the momentum oscillator (e.g., `6`, `10`, `14`).
    *   **RSI Thresholds:** Adjust the overbought/oversold levels (e.g., `80/20`, `75/25`, `70/30`).
    *   Log the performance (Total PnL, Win Rate, Max Drawdown, Profit Factor) for each combination to identify the optimal set.

3.  **Optimize Exit Strategy:**
    *   **Fixed vs. Dynamic Exits:** Backtest the current fixed TP/SL (0.5%/0.3%) against a dynamic approach.
    *   **ATR-Based Exits:** Implement and test an exit strategy based on the Average True Range (ATR). For example:
        *   `Take Profit = Entry Price + (1.5 * ATR)`
        *   `Stop Loss = Entry Price - (1.0 * ATR)`
    *   This allows the strategy to adapt to changing market volatility.

4.  **Analyze & Validate:**
    *   **Identify Best Strategy:** From the tests above, select the parameter set and exit strategy with the best risk-adjusted return.
    *   **Forward-Testing (Paper Trading):** Once the optimal strategy is identified via backtesting, deploy it to the live `logic_engine` but in a paper-trading mode for at least one week. This validates its performance on unseen, live market data.
    *   **Stress Test:** Analyze performance during high-volatility events within the historical data to understand its robustness.

---

## PHASE 5: Production Deployment & Monitoring

**Objective:** Go live and ensure operational stability.

**Key Actions:**

1.  **Deploy:** Push the containerized and tested MICRO engine to the production Cloud Run service.
2.  **Monitor:**
    *   Create a Cloud Monitoring Dashboard to track key system and business metrics in real-time:
        *   System: Latency, error rates, CPU usage.
        *   Business: Live P/L, open positions, signal frequency, win rate.
    *   Set up critical alerts for API failures, service downtime, or if daily drawdown exceeds a predefined threshold (e.g., 3%).
3.  **Iterate:** The market evolves. Plan to review performance and potentially re-tune parameters on a quarterly basis.

## PHASE 5.1: Trade Analytics & User Interfaces (begins *after* Phase 5 stabilizes)

Even after the core engine is live, users need friction-free visibility into performance.  We will ship three complementary surfaces, all fed from the same `paper_trades` BigQuery table.

### 1. Telegram Bot (interactive)
•  Commands (inline buttons for quick tap):
  – `/stats 24h` → returns win-rate and net-% P for last day.
  – `/last 5`  → carousel of the five most recent trades, each message includes chart PNG + win/loss badge.
  – `/equity`  → generates an equity-curve PNG for the selected period.
  – `/config` button → shows current per-coin strategy parameters and lets the owner toggle live/paper mode.
•  Rich UI: Telegram's **InlineKeyboardMarkup** will provide buttons so the user can page forward/back, refresh stats, or request a new timeframe without typing.
•  Extensible: after this project is stable we can merge the user's existing "analysis-on-demand" bot by exposing a `/analyze SOL` command that calls the same BigQuery/LLM layer described below.

#### Access-Control & Multi-User Support
•  **Why the first prototype used a fixed chat_id** – our early PoC only needed to PUSH out alerts, so hard-coding your chat ID was the quickest way to verify pub→bot wiring.
•  **Moving to interactive, multi-user mode** – the bot will switch to Webhook polling and will process `update.message.chat.id` for every incoming command; no hard coded IDs.
•  **Allowed-users list** – we maintain a BigQuery table or a simple JSON/Firestore doc of `approved_user_ids`.  On every command the bot checks membership:
  – If the user is approved → execute.
  – If not → respond with a short "Request access @owner".
•  **Invite workflow** – owner sends `/invite` which returns a single-use 6-digit code.  New user DM's the bot `/verify 123456`; the bot cross-checks and adds their ID to the allow-list.
•  **Group support** – the bot can be added to a Telegram group; group chat ID is auto-whitelisted once the owner issues `/allowgroup` so alerts flow there.
•  **Per-user context** – for future auto-trading the bot will store each user's Bybit API key (encrypted in Secret Manager) keyed by their Telegram ID, so trades can run on a user-specific account.
•  **Re-using existing bot** – If you already have a Telegram bot token you're happy with, simply set `BOT_TOKEN` env-var to that token; no need to register a new bot.  All invite / verify / group-allow logic works the same.
•  **Sharing the invite code** – Because only an admin can generate `/invite`, you retain full control: you decide which friends/clients get a code.  Forwarding that six-digit code is all they need to self-onboard; no code or credentials have to be shared publicly.

### 1.1 Telegram UI Upgrade Roadmap (rich UX)

The notifier bot will evolve from simple push alerts to a premium, interactive trading assistant.  Work is sliced into small, shippable phases so users feel immediate progress while we keep production stable.

| Phase | Goal | Core tasks | ETA |
|-------|------|-----------|----|
| **0 – Prep** | Create `telegram-ui-upgrade` branch.  Upgrade to **python-telegram-bot v21** (async).  Add lightweight `MessageQueue` to cap ≤ 29 msgs/s. | 0.5 d |
| **1 – Polished text & batching** | Switch to `parse_mode="HTML"`; bold/italics, emoji.  Escape helper.  Combine multi-pair bursts with `sendMediaGroup`. | 0.5 d |
| **2 – Inline keyboards** | Buttons: 📊 Chart • 🎯 Move TP • 🔔 Mute.  Callback dispatcher; store `trade_id → message_id` in Redis (5 h TTL). | 0.5 d |
| **3 – Live edits & Topics** | On EXIT edit the original alert (`editMessageText`).  Route all messages to per-symbol **Topics** so the main channel remains a signal feed. | 0.5 d |
| **4 – Mini chart previews** | Attach 640 px PNG in alert, or group charts when ≥ 3 signals in same cycle. | 0.5 d |
| **5 – Mini-App dashboard** | SvelteKit Web App served via Cloud Run. Opens from "🖥 Dashboard" button (`web_app`).  Shows open paper-trades table & sliders to adjust TP/SL → publishes to `trade-commands` Pub/Sub. | 4 d |
| **6 – Slash commands & inline mode** | `/stats`, `/equity`, `/mute` commands.  Inline query `@Bot BTCUSDT` returns chart & RSI/EMA snapshot cards. | 0.5 d |
| **7 – Adaptive flow control** | Use Telegram `retry_after` for exponential back-off.  Auto-shrink chart imgs when queue > 15. | 0.25 d |
| **8 – Mobile polish** (opt.) | Dark-theme charts, user-mention links, spoiler tags for secondary stats. | 0.25 d |
| **9 – Business account extras** (post-launch) | After migrating bot to a *Business Account*:  
• **Stories** – post daily PnL infographics (`postStory`).  
• **Gift Stars** – capture `gift` updates, maintain leaderboard in BigQuery. | TBD |

**> ✅  Status: Phases 0-4 (Prep to Chart Previews) completed on 2025-06-27. The notifier is now interactive and feature-rich. Remaining phases (5+) can be built on this foundation.**

**Risks & Mitigations**

* Async refactor – keep blocking code inside `run_in_executor` wrappers.
* Message-ID mapping – daily Redis RDB snapshot or Memorystore.
* Media limits – Telegram allows ≤ 10 items/album – queue guards enforce.
* Business API limits – isolate Story upload job with separate token.

_We will start with Phase 0 right after this plan is merged.  Each phase is a pull-request tagged `telegram-ux-<phase>` so you can review and test incrementally._

### 2. BI Dashboard (Looker Studio)
•  Data source: `cryptotracker.paper_trades`

## PHASE 0.5: Bug-Fix & Stabilization (2 Days)

**Why this exists:** Before expanding infrastructure, we must ensure core plumbing (Pub/Sub ↔ Telegram, env vars, CI smoke tests) is rock-solid. This phase captures the work we just completed plus any residual fixes.

**Key Actions (all DONE unless regressions surface):**

1.  Harden `telegram_bot.py` formatter to ignore malformed payloads.
2.  Patch `async_telegram_notifier.py` to drop empty messages.
3.  Seek `telegram-signal-sub` to *now* to purge stale backlog.
4.  Validate end-to-end flow with test publishes (`PING`, `TEST`).
5.  Tag this git commit as `v0.5.0-stable`.

> ✅  Status: Completed on 2025-06-27 (see commit `stabilize-telegram-notifier`).

---

## PHASE 5.2: CI/CD Pipeline Hardening

**Objective:** Document and solidify the deployment process to ensure reliable and repeatable builds, preventing future failures.

**Context:**
Following the initial setup, two consecutive deployment failures were encountered. This phase documents the root causes and establishes a clear, go-forward deployment protocol.

**Root Cause Analysis:**

1.  **IAM Permission Failure:** The first build failed due to a permissions error: `denied: Permission "artifactregistry.repositories.uploadArtifacts"`.
    *   **Resolution:** The Cloud Build service account (`777440185914@cloudbuild.gserviceaccount.com`) was granted the `Artifact Registry Writer` (`roles/artifactregistry.writer`) IAM role, which provides the necessary permissions to push images.

2.  **Manual Build Failure:** A subsequent manual build, triggered via the `gcloud builds submit` command, failed with an `invalid reference format` error.
    *   **Resolution:** This occurred because the `cloudbuild.yaml` file relies on the `$COMMIT_SHA` substitution variable for tagging Docker images. This variable is only populated on builds triggered from a source code repository (like GitHub). Manual builds from a local directory do not have this Git context, causing the tag to be empty and the `docker build` command to fail.

**Correct Deployment Procedure:**

*   All standard deployments **must** be initiated via a `git push` to the `main` branch of the GitHub repository. This is the only way to ensure that the Cloud Build trigger has the full Git context and can correctly populate variables like `$COMMIT_SHA`.

**Emergency Manual Deployment:**

*   In a critical situation where a `git push` is not feasible, a manual build can be triggered from a clean git checkout using the following command. This command explicitly provides the current commit SHA as a substitution:
    ```bash
    gcloud builds submit --config cloudbuild.yaml --substitutions=COMMIT_SHA=$(git rev-parse HEAD) .
    ```

**Action Item:** The immediate next step is to commit any pending changes to Git and push them to the `main` branch to trigger a correct, automated deployment.

---