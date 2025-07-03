import os
import json
import time
import logging
from typing import Callable

from google.cloud import pubsub_v1

# Re-use the existing formatter/sender that lives in the Cloud-Functions package
from functions.telegram_bot import send_telegram_message

# -------- Config --------
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
SIGNAL_TOPIC = "trade-signals"
RESULT_TOPIC = "trade-results"

# Optional env-vars to mute either stream
MUTE_SIGNALS = os.environ.get("MUTE_SIGNAL_ALERTS", "false").lower() == "true"
MUTE_RESULTS = os.environ.get("MUTE_RESULT_ALERTS", "false").lower() == "true"

# -------- Logging --------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


# -------- Pub/Sub helpers --------
Subscriber = pubsub_v1.SubscriberClient()


def _make_callback(mute: bool, stream_name: str) -> Callable[[pubsub_v1.subscriber.message.Message], None]:
    """Factory that returns a callback which decodes JSON and forwards to Telegram."""

    def _callback(msg: pubsub_v1.subscriber.message.Message):
        if mute:
            logging.debug(f"{stream_name} alert muted – acking message id {msg.message_id}")
            msg.ack()
            return

        try:
            payload = json.loads(msg.data.decode("utf-8"))
            ok = send_telegram_message(payload)
            if ok:
                logging.info(f"Forwarded {stream_name} message to Telegram (id={msg.message_id})")
            else:
                logging.error(f"send_telegram_message returned False for {stream_name} (id={msg.message_id})")
            msg.ack()
        except Exception as err:
            logging.error(f"Error processing {stream_name} message id {msg.message_id}: {err}", exc_info=True)
            # Nack so Pub/Sub can redeliver (avoid silent loss)
            msg.nack()

    return _callback


def _ensure_subscription(topic_name: str, sub_suffix: str) -> str:
    """Create an ephemeral subscription and return its full path."""
    topic_path = Subscriber.topic_path(PROJECT_ID, topic_name)
    subscription_path = Subscriber.subscription_path(
        PROJECT_ID, f"{sub_suffix}-{int(time.time())}")

    try:
        Subscriber.create_subscription(name=subscription_path, topic=topic_path, ack_deadline_seconds=20)
        logging.info(f"Created subscription {subscription_path} → {topic_path}")
    except Exception:
        # Already exists or race – it's fine for these throw-away subs
        pass

    return subscription_path


def main():
    if not PROJECT_ID:
        logging.critical("GCP_PROJECT_ID environment variable not set – exiting.")
        return

    # Use pre-created subscriptions if env-vars set (helps when perms block creation)
    signal_sub = os.environ.get("TELEGRAM_SIGNAL_SUB") or _ensure_subscription(SIGNAL_TOPIC, "telegram-signal-sub")
    result_sub = os.environ.get("TELEGRAM_RESULT_SUB") or _ensure_subscription(RESULT_TOPIC, "telegram-result-sub")

    # Register streaming pulls
    Subscriber.subscribe(signal_sub, callback=_make_callback(MUTE_SIGNALS, "SIGNAL"))
    Subscriber.subscribe(result_sub, callback=_make_callback(MUTE_RESULTS, "RESULT"))

    logging.info("Telegram notifier started. Listening for signals and results…")

    # Keep main thread alive indefinitely
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main() 