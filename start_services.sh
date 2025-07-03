#!/bin/bash
# A master script to ensure a clean start for all services.

echo "🚀 Starting CryptoSignalTracker Services..."
echo "---"

# Step 1: Aggressively stop any old services and clear python cache.
echo "1. Forcefully stopping any old python processes and clearing cache..."
find . -type d -name "__pycache__" -exec rm -r {} +
SERVICES=(
    "micro_scalp_engine.data_ingestion"
    "micro_scalp_engine.data_processor"
    "micro_scalp_engine.logic_engine"
    "micro_scalp_engine.async_telegram_notifier.main"
)

for service in "${SERVICES[@]}"; do
    pid=$(pgrep -f "python -m $service")
    if [ -n "$pid" ]; then
        echo "   - Killing $service (PID: $pid)..."
        kill -9 "$pid"
    else
        echo "   - $service is not running."
    fi
done
sleep 2

# Step 2: Ensure all dependencies are installed.
echo "2. Verifying and installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "---"

# Step 3: Set all environment variables
export GCP_PROJECT_ID="telegram-signals-205cc"
export GCP_PUBSUB_TOPIC_ID="trade-signals-micro"
export TELEGRAM_SIGNAL_SUB="trade-signals-micro-sub"
export TELEGRAM_BOT_TOKEN="7572425494:AAGQWx_7RIerMy3jXJq9wK2JLnKE0G5LZe8"
export TELEGRAM_CHAT_ID="-1001925184608"

# Step 4: Start background services with logging
echo "3. Starting background data services..."

echo "   - Starting Data Ingestion Service..."
nohup /Users/arsisiddiqi/Downloads/CryptoSignalTracker/venv/bin/python -m micro_scalp_engine.data_ingestion > data_ingestion.log 2>&1 &

echo "   - Starting Data Processing Service..."
nohup /Users/arsisiddiqi/Downloads/CryptoSignalTracker/venv/bin/python -m micro_scalp_engine.data_processor > data_processor.log 2>&1 &

echo "   - Starting Logic Engine..."
nohup /Users/arsisiddiqi/Downloads/CryptoSignalTracker/venv/bin/python -m micro_scalp_engine.logic_engine > logic_engine.log 2>&1 &

sleep 5 # Give services time to initialize

# Step 5: Start Telegram Notifier in the foreground
echo "4. Starting Telegram Notifier..."
echo "---"
echo "The script will now 'hang' while it listens for signals. This is correct."
echo "---"
/Users/arsisiddiqi/Downloads/CryptoSignalTracker/venv/bin/python -m micro_scalp_engine.async_telegram_notifier.main

echo "Notifier stopped."