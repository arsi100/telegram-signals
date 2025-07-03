import os
import json
import time
import logging
from uuid import uuid4
from datetime import datetime, timezone
from typing import Dict

from google.cloud import pubsub_v1
from google.cloud import bigquery

# -------- Config --------
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
SIGNAL_TOPIC = "trade-signals"          # already created
RESULT_TOPIC = "trade-results"          # new topic; create via infra script
TICK_TOPIC   = "raw-tick-data-bybit"    # ingestion service publishes ticks here
BQ_DATASET   = "cryptotracker"
BQ_TABLE     = "paper_trades"

# -------- Logging --------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# -------- BigQuery Client --------
try:
    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = bq_client.dataset(BQ_DATASET).table(BQ_TABLE)
    logging.info("BigQuery client initialised for paper_trades.")
except Exception as e:
    bq_client = None
    logging.error(f"BigQuery init failed: {e}")

# -------- Pub/Sub Clients --------
subscriber = pubsub_v1.SubscriberClient()
publisher  = pubsub_v1.PublisherClient()

signal_sub_path = subscriber.subscription_path(
    PROJECT_ID, f"position-tracker-signal-sub-{int(time.time())}")
result_topic_path = publisher.topic_path(PROJECT_ID, RESULT_TOPIC)

tick_sub_path = subscriber.subscription_path(
    PROJECT_ID, f"position-tracker-tick-sub-{int(time.time())}")

# Create ephemeral subscriptions (auto-delete TTL in config) ------------------
try:
    subscriber.create_subscription(name=signal_sub_path,
                                   topic=subscriber.topic_path(PROJECT_ID, SIGNAL_TOPIC),
                                   ack_deadline_seconds=20)
except Exception:
    pass

try:
    subscriber.create_subscription(name=tick_sub_path,
                                   topic=subscriber.topic_path(PROJECT_ID, TICK_TOPIC),
                                   ack_deadline_seconds=20)
except Exception:
    pass

# -------- Position store --------
class Position:
    def __init__(self, payload: dict):
        self.id = str(uuid4())
        self.symbol = payload["symbol"]
        self.side = payload["side"]  # BUY or SELL
        self.entry = payload["entry_price"]
        self.tp = payload["take_profit"]
        self.sl = payload["stop_loss"]
        self.opened_at = datetime.now(timezone.utc)
        self.extra = payload  # store full signal for reference

    def check_close(self, price: float):
        if self.side == "BUY":
            if price >= self.tp:
                return "WIN", self.tp
            if price <= self.sl:
                return "LOSS", self.sl
        else:  # SELL
            if price <= self.tp:
                return "WIN", self.tp
            if price >= self.sl:
                return "LOSS", self.sl
        return None, None

# key: symbol -> list[Position]
open_positions: Dict[str, list] = {}

# -------- Helpers --------

def publish_result(pos: Position, result: str, exit_price: float):
    payload = {
        "id": pos.id,
        "symbol": pos.symbol,
        "side": pos.side,
        "entry": pos.entry,
        "exit": exit_price,
        "pnl_pct": round(((exit_price - pos.entry)/pos.entry)*100 * (1 if pos.side=="BUY" else -1), 4),
        "result": result,
        "opened_at": pos.opened_at.isoformat(),
        "closed_at": datetime.now(timezone.utc).isoformat()
    }
    # publish
    publisher.publish(result_topic_path, json.dumps(payload).encode("utf-8"))
    logging.critical(f"TRADE RESULT PUBLISHED: {payload}")

    # write to BigQuery
    if bq_client:
        rows_to_insert = [
            {**payload,
             "opened_at": pos.opened_at,
             "closed_at": datetime.now(timezone.utc)}
        ]
        errors = bq_client.insert_rows_json(table_ref, rows_to_insert)
        if errors:
            logging.error(f"BQ insert errors: {errors}")


def handle_signal(message: pubsub_v1.subscriber.message.Message):
    try:
        data = json.loads(message.data.decode("utf-8"))
        pos = Position(data)
        open_positions.setdefault(pos.symbol, []).append(pos)
        logging.warning(f"OPENED paper trade {pos.id} {pos.side} {pos.symbol} @ {pos.entry}")
        message.ack()
    except Exception as e:
        logging.error(f"Signal handling error: {e}")
        message.nack()


def handle_tick(message: pubsub_v1.subscriber.message.Message):
    try:
        tick = json.loads(message.data.decode("utf-8"))
        symbol = tick.get("symbol") or tick.get("s")  # depending on WS schema
        # Some exchange heartbeat messages may not carry a price – ignore those safely
        raw_price = tick.get("price") or tick.get("p")
        if raw_price is None:
            logging.debug("Skipping tick without price field")
            message.ack()
            return
        price = float(raw_price)
        positions = open_positions.get(symbol)
        if not positions:
            message.ack()
            return
        remaining = []
        for pos in positions:
            result, exit_price = pos.check_close(price)
            if result:
                publish_result(pos, result, exit_price)
            else:
                remaining.append(pos)
        if remaining:
            open_positions[symbol] = remaining
        else:
            del open_positions[symbol]
        message.ack()
    except Exception as e:
        logging.error(f"Tick handling error: {e}")
        message.nack()


def main():
    logging.info("Starting Position Tracker…")
    # start streaming pulls
    subscriber.subscribe(signal_sub_path, callback=handle_signal)
    subscriber.subscribe(tick_sub_path,   callback=handle_tick)

    # Keep process alive
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main() 