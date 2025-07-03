"""Publishes a burst of fake trade signals to the trade-signals topic.

This is a developer utility to test the async_telegram_notifier's batching
and formatting logic without running the full micro-scalp engine.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=./path/to/key.json
    export GCP_PROJECT_ID=my-gcp-project-id
    python dev/send_fake_signals.py
"""
import json
import os
import time

from google.cloud import pubsub_v1

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = "trade-signals"

# Create a dummy chart file for testing media groups
if not os.path.exists("charts"):
    os.makedirs("charts")
DUMMY_CHART_PATH = "charts/DUMMY_BTCUSDT.png"
if not os.path.exists(DUMMY_CHART_PATH):
    with open(DUMMY_CHART_PATH, "w") as f:
        f.write("not a real png")

FAKE_SIGNALS = [
    {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 68500.1,
        "take_profit": 69000.0,
        "stop_loss": 68200.0,
        "confidence": 0.85,
        "long_term_trend": "BULLISH",
        "chart": DUMMY_CHART_PATH,  # Include a chart for media group test
    },
    {
        "symbol": "ETHUSDT",
        "side": "SELL",
        "entry_price": 3800.5,
        "take_profit": 3750.0,
        "stop_loss": 3825.0,
        "confidence": 0.72,
        "long_term_trend": "BEARISH",
        "chart": None, # No chart
    },
    {
        "symbol": "SOLUSDT",
        "side": "BUY",
        "entry_price": 165.22,
        "take_profit": 168.0,
        "stop_loss": 164.5,
        "confidence": 0.91,
        "long_term_trend": "BULLISH",
        "chart": None, # No chart
    },
]

def main():
    if not PROJECT_ID:
        print("Error: GCP_PROJECT_ID environment variable not set.")
        return

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

    print(f"Publishing {len(FAKE_SIGNALS)} fake signals to {topic_path}...")

    for signal in FAKE_SIGNALS:
        data = json.dumps(signal).encode("utf-8")
        future = publisher.publish(topic_path, data)
        print(f"Published message ID: {future.result()}")
        time.sleep(0.1)  # Stagger slightly to ensure they arrive in a burst

    print("Done.")

if __name__ == "__main__":
    main() 