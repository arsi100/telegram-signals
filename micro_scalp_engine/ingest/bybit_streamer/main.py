import os
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
from pybit.unified_trading import WebSocket
from aiohttp import web
from google.cloud import monitoring_v3

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# GCP Project and Pub/Sub Topic from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("BYBIT_TICK_TOPIC_ID", "raw-tick-data-bybit")
PORT = int(os.getenv("PORT", 8080))

# Rate limiting configuration
MAX_MESSAGES_PER_SECOND = 100
RATE_LIMIT_WINDOW = 1.0  # seconds

# Monitoring metrics
@dataclass
class Metrics:
    messages_received: int = 0
    messages_published: int = 0
    errors: int = 0
    last_message_time: Optional[float] = None
    rate_limited_count: int = 0
    reconnect_count: int = 0

metrics = Metrics()

# Initialize monitoring client if in GCP
monitoring_client = None
if PROJECT_ID:
    try:
        monitoring_client = monitoring_v3.MetricServiceClient()
    except Exception as e:
        logging.error(f"Failed to initialize monitoring client: {e}")

def update_metric(metric_name: str, value: int):
    """Update a Cloud Monitoring metric."""
    if not monitoring_client:
        return
        
    try:
        project_path = f"projects/{PROJECT_ID}"
        series = monitoring_v3.TimeSeries()
        series.metric.type = f"custom.googleapis.com/bybit_streamer/{metric_name}"
        point = series.points.add()
        point.value.int64_value = value
        point.interval.end_time.seconds = int(time.time())
        
        monitoring_client.create_time_series(
            request={
                "name": project_path,
                "time_series": [series]
            }
        )
    except Exception as e:
        logging.error(f"Failed to update metric {metric_name}: {e}")

class RateLimiter:
    def __init__(self, max_messages: int, window: float):
        self.max_messages = max_messages
        self.window = window
        self.messages = []
    
    def can_process(self) -> bool:
        now = time.time()
        # Remove old messages
        self.messages = [ts for ts in self.messages if now - ts < self.window]
        if len(self.messages) >= self.max_messages:
            metrics.rate_limited_count += 1
            return False
        self.messages.append(now)
        return True

rate_limiter = RateLimiter(MAX_MESSAGES_PER_SECOND, RATE_LIMIT_WINDOW)

def validate_trade_message(trade: Dict) -> bool:
    """Validate required fields in trade message."""
    required_fields = ['symbol', 'price', 'size', 'side', 'timestamp']
    return all(field in trade for field in required_fields)

# Bybit WebSocket symbols - Top 25 by recent volume (example list)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "MATICUSDT", "DOTUSDT", "TRXUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
    "BNBUSDT", "SHIB1000USDT", "ATOMUSDT", "ETCUSDT", "BCHUSDT", "NEARUSDT",
    "UNIUSDT", "FTMUSDT", "AAVEUSDT", "ALGOUSDT", "XLMUSDT", "MANAUSDT", "SANDUSDT"
]

# --- Pub/Sub Publisher ---
publisher = None
topic_path = None
if PROJECT_ID:
    try:
        from google.cloud import pubsub_v1
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        logging.info(f"Pub/Sub publisher initialized for topic: {topic_path}")
    except Exception as e:
        logging.error(f"Failed to initialize Google Cloud Pub/Sub client. Error: {e}")
        exit(1)
else:
    logging.warning("GCP_PROJECT_ID not set. Publisher will be in DRY_RUN mode.")

def handle_message(message: dict):
    """Callback function to process messages from Bybit WebSocket."""
    if "topic" in message and "trade" in message["topic"]:
        metrics.messages_received += 1
        metrics.last_message_time = time.time()
        
        for trade in message.get('data', []):
            try:
                # Rate limiting check
                if not rate_limiter.can_process():
                    logging.warning("Rate limit exceeded, skipping message")
                    continue
                
                # Validate message
                if not validate_trade_message(trade):
                    logging.error(f"Invalid trade message format: {trade}")
                    metrics.errors += 1
                    continue
                
                # Add metadata
                trade['received_at_ts'] = metrics.last_message_time
                trade['processing_latency_ms'] = (time.time() - trade['received_at_ts']) * 1000
                
                payload = json.dumps(trade).encode("utf-8")

                if publisher and topic_path:
                    future = publisher.publish(topic_path, payload)
                    future.add_done_callback(lambda f: metrics.messages_published += 1)
                else:
                    logging.info(f"[DRY_RUN] Would publish: {payload.decode()}")
                    metrics.messages_published += 1

            except Exception as e:
                logging.error(f"Failed to process trade message: {trade}. Error: {e}")
                metrics.errors += 1

async def update_metrics():
    """Periodically update Cloud Monitoring metrics."""
    while True:
        try:
            update_metric("messages_received", metrics.messages_received)
            update_metric("messages_published", metrics.messages_published)
            update_metric("errors", metrics.errors)
            update_metric("rate_limited_count", metrics.rate_limited_count)
            update_metric("reconnect_count", metrics.reconnect_count)
        except Exception as e:
            logging.error(f"Failed to update metrics: {e}")
        await asyncio.sleep(60)  # Update every minute

async def bybit_worker():
    """Connects to Bybit WebSocket and streams data indefinitely."""
    while True:
        try:
            logging.info(f"Connecting to Bybit WebSocket...")
            ws = WebSocket(
                testnet=False,
                channel_type="linear",
                ping_interval=20,  # More frequent ping
                ping_timeout=10
            )
            
            # Subscribe to trades
            for symbol in SYMBOLS:
                ws.subscribe_public(symbol, "trade", handle_message)
            
            logging.info("WebSocket subscriptions active")
            
            # Keep connection alive
            while True:
                await asyncio.sleep(30)
                if not ws.ws.sock or not ws.ws.sock.connected:
                    raise Exception("WebSocket disconnected")
                
        except Exception as e:
            metrics.reconnect_count += 1
            logging.error(f"WebSocket error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def health_check(request):
    """Enhanced health check with basic metrics."""
    if metrics.last_message_time and time.time() - metrics.last_message_time > 60:
        return web.Response(text="No recent messages", status=503)
    return web.Response(
        text=json.dumps({
            "status": "OK",
            "metrics": {
                "messages_received": metrics.messages_received,
                "messages_published": metrics.messages_published,
                "errors": metrics.errors,
                "rate_limited": metrics.rate_limited_count
            }
        }),
        content_type="application/json"
    )

async def start_health_check_server():
    """Starts the aiohttp server for health checks."""
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Health check server started on http://0.0.0.0:{PORT}")
    while True:
        await asyncio.sleep(3600)

async def main():
    """Runs all components concurrently."""
    if not PROJECT_ID:
        logging.warning("Running without GCP_PROJECT_ID. No data will be published.")

    tasks = [
        asyncio.create_task(bybit_worker()),
        asyncio.create_task(start_health_check_server()),
        asyncio.create_task(update_metrics())
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutdown signal received. Exiting.") 