import pandas as pd
from pathlib import Path
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RULE_HITS_FILE = Path("analysis_results/sol_rule_hits.csv")
ALL_FILE = Path("analysis_results/sol_90d_opportunities.csv")

TP_PCT = 0.5   # 0.5%% spot move = 5%% on 10x margin
USE_STOP = False
SL_PCT = -0.75  # ignored if USE_STOP=False

if not RULE_HITS_FILE.exists():
    logger.error("Run pattern_recognition_and_backtest.py first to generate rule hits.")
    exit()

hits = pd.read_csv(RULE_HITS_FILE, parse_dates=["timestamp"])
all_rows = pd.read_csv(ALL_FILE, parse_dates=["timestamp"])

# Function to classify outcome: win if max_gain_4h_pct >= TP, else loss if drawdown <= SL

def classify(row):
    if row["max_gain_4h_pct"] >= TP_PCT:
        return "win"
    elif USE_STOP and row["drawdown_pct"] <= SL_PCT:
        return "loss"
    else:
        # neither target nor stop in first 4h – treat as breakeven for now
        return "open"

hits["outcome"] = hits.apply(classify, axis=1)

wins = hits[hits["outcome"] == "win"]
losses = hits[hits["outcome"] == "loss"]
opens = hits[hits["outcome"] == "open"]

logger.info("TP %.2f%% / SL %.2f%% => %d wins, %d losses, %d open out of %d signals", TP_PCT, SL_PCT, len(wins), len(losses), len(opens), len(hits))

print("Performance summary saved to console above.") 