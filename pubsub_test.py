from google.cloud import pubsub_v1
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SUBSCRIPTION_NAME = "telegram-signal-sub"

def receive_messages(project_id, subscription_name):
    """Receives messages from a Pub/Sub subscription."""
    if not project_id:
        print("🔴 GCP_PROJECT_ID is not set. Please check your .env file.")
        return

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    def callback(message):
        print(f"✅ Message Received! Data: {message.data.decode('utf-8')}")
        message.ack()

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    print(f"🎧 Listening for messages on {subscription_path}...")

    # Keep the main thread alive to allow the subscriber to work in the background.
    try:
        # Wait for 30 seconds to see if a message comes in.
        print("\n⏳ Waiting for a test signal... (30s timeout)")
        time.sleep(30)
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
    finally:
        streaming_pull_future.cancel()
        subscriber.close()
        print("\n🛑 Listener stopped.")


if __name__ == "__main__":
    receive_messages(PROJECT_ID, SUBSCRIPTION_NAME) 