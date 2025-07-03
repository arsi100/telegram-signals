import logging
from google.cloud import pubsub_v1
import os
from dotenv import load_dotenv

# --- START OF ADDED LOGGING ---
# Enable verbose logging to see what the client is doing under the hood.
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('google.cloud.pubsub_v1').setLevel(logging.DEBUG)
# --- END OF ADDED LOGGING ---

# Load environment variables from .env file
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SUBSCRIPTION_NAME = "telegram-signal-sub"

# Check if environment variables are loaded
if not PROJECT_ID:
    print("Error: GCP_PROJECT_ID environment variable not set.")
    print("Please ensure it is defined in your .env file.")
    exit()

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)

def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    """Callback executed for each received message."""
    print(f"Received message: {message.data.decode('utf-8')}")
    message.ack()

print(f"Listening for messages on {subscription_path}...")
streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

# Wrap the result() call in a try/except block to allow for graceful shutdown
try:
    # When timeout is not set, result() will block indefinitely,
    # waiting for messages.
    streaming_pull_future.result()
except KeyboardInterrupt:
    streaming_pull_future.cancel()  # Trigger the shutdown
    streaming_pull_future.result()  # Block until the shutdown is complete
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    streaming_pull_future.cancel()
    streaming_pull_future.result() 