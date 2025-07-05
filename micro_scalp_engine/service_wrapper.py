"""
Service wrapper that provides HTTP health check endpoint while running background services
"""
import os
import sys
import threading
import logging
from flask import Flask, jsonify
import signal

# Configure logging immediately
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*50)
logger.info("Service wrapper starting...")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path}")
logger.info(f"Environment variables:")
for key, value in os.environ.items():
    if key.startswith(('SERVICE_', 'GCP_', 'PORT')):
        logger.info(f"  {key}={value}")
logger.info("="*50)

app = Flask(__name__)
service_healthy = True

@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    if service_healthy:
        return jsonify({"status": "healthy"}), 200
    return jsonify({"status": "unhealthy"}), 503

@app.route('/')
def index():
    """Root endpoint"""
    return jsonify({"service": os.environ.get("SERVICE_TYPE", "unknown"), "status": "running"}), 200

def run_service():
    """Run the actual service based on SERVICE_TYPE"""
    service_type = os.environ.get("SERVICE_TYPE")
    
    try:
        if service_type == "ingestion":
            logger.info("Starting data ingestion service...")
            from .data_ingestion import start_data_ingestion
            start_data_ingestion()
        elif service_type == "processor":
            logger.info("Starting data processor service...")
            from .data_processor import start_data_processor
            start_data_processor()
        elif service_type == "logic":
            logger.info("Starting logic engine...")
            from .logic_engine import start_logic_engine
            start_logic_engine()
        elif service_type == "notifier":
            logger.info("Starting telegram notifier...")
            from .async_telegram_notifier.main import main
            import asyncio
            asyncio.run(main())
        else:
            logger.error(f"Unknown SERVICE_TYPE: {service_type}")
            global service_healthy
            service_healthy = False
    except Exception as e:
        logger.error(f"Service failed to start: {e}", exc_info=True)
        service_healthy = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the background service in a separate thread
    service_thread = threading.Thread(target=run_service, daemon=True)
    service_thread.start()
    
    # Start the Flask app for health checks
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting HTTP server on port {port}")
    app.run(host="0.0.0.0", port=port) 