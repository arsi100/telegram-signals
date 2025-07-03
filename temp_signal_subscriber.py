import os
from google.cloud import pubsub_v1
import time
import json

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
TOPIC_NAME = "trade-signals"
# Create a unique subscription name to avoid conflicts
SUBSCRIPTION_NAME = "trade-signals-test-sub" 

def receive_signals(project_id, subscription_name):
    """Receives messages from the trade-signals Pub/Sub subscription."""
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = subscriber.topic_path(project_id, TOPIC_NAME)
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    # Create the subscription if it doesn't exist.
    try:
        subscriber.create_subscription(name=subscription_path, topic=topic_path)
        print(f"Subscription '{subscription_name}' created for topic '{TOPIC_NAME}'.")
    except Exception as e:
        # If the subscription already exists, the API will return an error.
        # We can safely ignore it and proceed.
        if 'already exists' in str(e):
            print(f"Subscription '{subscription_name}' already exists.")
            pass
        else:
            print(f"Failed to create subscription: {e}")
            return

    def callback(message):
        print("\\n" + "="*20 + " NEW TRADE SIGNAL " + "="*20)
        try:
            # Decode the message and pretty-print the JSON
            signal_data = json.loads(message.data.decode('utf-8'))
            print(json.dumps(signal_data, indent=2))
        except json.JSONDecodeError:
            print(f"Received raw message: {message.data.decode('utf-8')}")
        
        print("="*58)
        message.ack()

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    print(f"\\nListening for trade signals on {subscription_path}...")
    print("Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive to receive messages.
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        print("Subscriber stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        streaming_pull_future.cancel()


if __name__ == "__main__":
    if not PROJECT_ID:
        print("GCP_PROJECT_ID environment variable not set.")
    else:
        receive_signals(PROJECT_ID, SUBSCRIPTION_NAME) 