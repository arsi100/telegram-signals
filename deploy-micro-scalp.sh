#!/bin/bash
# Deploy all MICRO-SCALP services

PROJECT_ID="telegram-signals-205cc"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/micro-scalp:latest"

echo "Deploying MICRO-SCALP services..."

# Deploy Data Ingestion Service
echo "1. Deploying Data Ingestion Service..."
gcloud run deploy micro-scalp-ingestion \
  --image=$IMAGE \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --set-env-vars="SERVICE_TYPE=ingestion,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600

# Deploy Data Processor Service
echo "2. Deploying Data Processor Service..."
gcloud run deploy micro-scalp-processor \
  --image=$IMAGE \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --set-env-vars="SERVICE_TYPE=processor,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=5 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=3600

# Deploy Logic Engine
echo "3. Deploying Logic Engine..."
gcloud run deploy micro-scalp-logic \
  --image=$IMAGE \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --set-env-vars="SERVICE_TYPE=logic,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=3600

# Deploy Telegram Notifier
echo "4. Deploying Telegram Notifier..."
gcloud run deploy micro-scalp-notifier \
  --image=$IMAGE \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --set-env-vars="SERVICE_TYPE=notifier,GCP_PROJECT_ID=$PROJECT_ID,TELEGRAM_CHAT_ID=-1001925184608" \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600

echo "Deployment complete!"
echo ""
echo "Services deployed:"
echo "- micro-scalp-ingestion"
echo "- micro-scalp-processor"
echo "- micro-scalp-logic"
echo "- micro-scalp-notifier" 