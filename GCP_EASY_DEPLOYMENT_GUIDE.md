# CryptoSignalTracker - Easy GCP Deployment Guide

## Overview

This guide provides the simplest path to deploy CryptoSignalTracker on Google Cloud Platform. We'll use Cloud Run for all services to maintain consistency and ease of management.

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **Google Cloud CLI** (`gcloud`) installed and configured
3. **Docker** installed locally
4. **Python 3.9+** installed
5. **Git** for version control

## Step 1: Initial Setup

### 1.1 Set Project Variables
```bash
export PROJECT_ID="telegram-signals-205cc"
export REGION="us-central1"
export REPO_NAME="crypto-signal-tracker"

# Set default project
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

### 1.2 Enable Required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  pubsub.googleapis.com \
  bigtable.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com
```

### 1.3 Create Artifact Registry Repository
```bash
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker images for CryptoSignalTracker"
```

## Step 2: Set Up Infrastructure

### 2.1 Create Pub/Sub Topics
```bash
# Create topics
gcloud pubsub topics create raw-tick-data-bybit
gcloud pubsub topics create trade-signals-micro
gcloud pubsub topics create macro-bias-updates

# Create subscriptions
gcloud pubsub subscriptions create raw-tick-data-bybit-sub \
  --topic=raw-tick-data-bybit

gcloud pubsub subscriptions create trade-signals-micro-sub \
  --topic=trade-signals-micro

gcloud pubsub subscriptions create macro-bias-sub \
  --topic=macro-bias-updates
```

### 2.2 Create Bigtable Instance
```bash
gcloud bigtable instances create cryptotracker-bigtable \
  --cluster=cryptotracker-cluster \
  --cluster-zone=us-central1-a \
  --display-name="CryptoTracker Bigtable" \
  --cluster-storage-type=SSD \
  --cluster-num-nodes=1

# Create table
echo "Create table 'market-data-1m' with column family 'data'" | \
  cbt -instance=cryptotracker-bigtable createtable market-data-1m
  
cbt -instance=cryptotracker-bigtable createfamily market-data-1m data
```

### 2.3 Set Up Firestore
```bash
# Create Firestore database (if not exists)
gcloud firestore databases create --location=$REGION
```

### 2.4 Store Secrets
```bash
# Store API keys and tokens
gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=-
# Paste your token and press Ctrl+D

gcloud secrets create TELEGRAM_CHAT_ID --data-file=-
# Paste your chat ID and press Ctrl+D

gcloud secrets create GEMINI_API_KEY --data-file=-
# Paste your API key and press Ctrl+D

# Add more secrets as needed
```

## Step 3: Prepare Services for Deployment

### 3.1 Create Service Account
```bash
gcloud iam service-accounts create crypto-signal-tracker \
  --display-name="CryptoSignalTracker Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigtable.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3.2 Update Dockerfiles

Create a unified Dockerfile for micro-scalp services:

```dockerfile
# micro_scalp_engine/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY micro_scalp_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY micro_scalp_engine/ ./micro_scalp_engine/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Create entry point script
RUN echo '#!/bin/bash\n\
if [ "$SERVICE_TYPE" = "ingestion" ]; then\n\
    python -m micro_scalp_engine.data_ingestion\n\
elif [ "$SERVICE_TYPE" = "processor" ]; then\n\
    python -m micro_scalp_engine.data_processor\n\
elif [ "$SERVICE_TYPE" = "logic" ]; then\n\
    python -m micro_scalp_engine.logic_engine\n\
elif [ "$SERVICE_TYPE" = "notifier" ]; then\n\
    python -m micro_scalp_engine.async_telegram_notifier.main\n\
else\n\
    echo "Unknown SERVICE_TYPE: $SERVICE_TYPE"\n\
    exit 1\n\
fi' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
```

## Step 4: Deploy Services

### 4.1 Build and Push Docker Images
```bash
# Configure Docker
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build micro-scalp engine image
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest \
  -f micro_scalp_engine/Dockerfile .

docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest

# Build macro engine image (convert Cloud Function to Cloud Run)
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/macro-engine:latest \
  -f Dockerfile .

docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/macro-engine:latest
```

### 4.2 Deploy Micro-Scalp Services
```bash
# Deploy Data Ingestion
gcloud run deploy micro-scalp-ingestion \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --service-account=crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="SERVICE_TYPE=ingestion,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=512Mi

# Deploy Data Processor
gcloud run deploy micro-scalp-processor \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --service-account=crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="SERVICE_TYPE=processor,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=5 \
  --memory=1Gi

# Deploy Logic Engine
gcloud run deploy micro-scalp-logic \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --service-account=crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="SERVICE_TYPE=logic,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=1Gi

# Deploy Telegram Notifier
gcloud run deploy micro-scalp-notifier \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/micro-scalp:latest \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --service-account=crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="SERVICE_TYPE=notifier,GCP_PROJECT_ID=$PROJECT_ID" \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest" \
  --min-instances=1 \
  --max-instances=3 \
  --memory=512Mi
```

### 4.3 Deploy Macro Engine
```bash
# Deploy as Cloud Run service
gcloud run deploy macro-engine \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/macro-engine:latest \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --service-account=crypto-signal-tracker@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --min-instances=0 \
  --max-instances=10 \
  --memory=1Gi
```

### 4.4 Set Up Cloud Scheduler
```bash
# Get the Macro Engine URL
MACRO_URL=$(gcloud run services describe macro-engine --format='value(status.url)')

# Create scheduler job for market hours
gcloud scheduler jobs create http macro-engine-scheduler \
  --location=$REGION \
  --schedule="*/5 0-2,5-7,8-10,20-23 * * *" \
  --uri="$MACRO_URL/run" \
  --http-method=POST \
  --time-zone="UTC"
```

## Step 5: Verify Deployment

### 5.1 Check Service Status
```bash
# List all Cloud Run services
gcloud run services list

# Check logs for each service
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=micro-scalp-ingestion" --limit=50
```

### 5.2 Monitor Pub/Sub
```bash
# Check message flow
gcloud pubsub topics list
gcloud pubsub subscriptions list
```

### 5.3 Test the System
```bash
# Send a test message to trigger the system
# You can create a simple test script or use the existing dev/send_test_signal.py
```

## Step 6: Set Up Monitoring

### 6.1 Create Monitoring Dashboard
```bash
# Use Cloud Console to create a custom dashboard with:
# - Cloud Run service metrics
# - Pub/Sub topic/subscription metrics
# - Bigtable performance metrics
# - Error logs
```

### 6.2 Set Up Alerts
```bash
# Create alert for service failures
gcloud alpha monitoring policies create \
  --notification-channels=[YOUR_CHANNEL_ID] \
  --display-name="Service Down Alert" \
  --condition-display-name="Cloud Run Service Down" \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count"'
```

## Troubleshooting

### Common Issues and Solutions

1. **Port Configuration Errors**
   - Ensure all services listen on PORT environment variable
   - Check Dockerfile CMD uses correct port

2. **Permission Denied Errors**
   - Verify service account has all required roles
   - Check Secret Manager permissions

3. **Pub/Sub Message Not Flowing**
   - Verify topics and subscriptions exist
   - Check service logs for connection errors

4. **Bigtable Connection Issues**
   - Ensure Bigtable instance is in same region
   - Verify service account has bigtable.user role

## Cost Optimization Tips

1. **Use minimum instances wisely**
   - Only critical services need min-instances=1
   - Macro engine can scale to zero

2. **Right-size memory allocation**
   - Monitor actual usage and adjust
   - Data processor might need more memory

3. **Set up budget alerts**
   ```bash
   gcloud billing budgets create \
     --billing-account=[YOUR_BILLING_ACCOUNT] \
     --display-name="CryptoSignalTracker Budget" \
     --budget-amount=100 \
     --threshold-rule=percent=90
   ```

## Next Steps

1. **Production Hardening**
   - Implement proper error handling
   - Add retry logic for API calls
   - Set up dead letter queues

2. **Performance Optimization**
   - Profile services for bottlenecks
   - Optimize Bigtable queries
   - Consider caching strategies

3. **Security Enhancements**
   - Enable VPC Service Controls
   - Implement API rate limiting
   - Regular security audits

## Conclusion

This deployment approach provides a simple, scalable, and maintainable setup for CryptoSignalTracker on Google Cloud Platform. All services run on Cloud Run, providing consistent management and easy scaling. 