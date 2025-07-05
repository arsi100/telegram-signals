# Fix Cloud Scheduler Error - Update to Cloud Run URL

## Problem
Your Cloud Scheduler job `crypto-signal-generation-job` is trying to reach:
```
https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation
```

But you're actually deploying to **Cloud Run**, not Cloud Functions.

## Solution 1: Update Cloud Scheduler to Point to Cloud Run

### Step 1: Get the Cloud Run Service URL
```bash
# Get the correct Cloud Run URL
gcloud run services describe run-signal-generation \
  --region=us-central1 \
  --format='value(status.url)'
```

If the service doesn't exist or isn't healthy, you'll need to fix the deployment first (see Solution 2).

### Step 2: Update the Cloud Scheduler Job
```bash
# Delete the old job
gcloud scheduler jobs delete crypto-signal-generation-job \
  --location=us-central1 \
  --quiet

# Create a new job pointing to Cloud Run
CLOUD_RUN_URL=$(gcloud run services describe run-signal-generation \
  --region=us-central1 \
  --format='value(status.url)')

gcloud scheduler jobs create http crypto-signal-generation-job \
  --location=us-central1 \
  --schedule="*/5 * * * *" \
  --uri="${CLOUD_RUN_URL}" \
  --http-method=POST \
  --attempt-deadline=30m \
  --time-zone="UTC"
```

## Solution 2: Fix the Cloud Run Deployment First

The underlying issue is that your Cloud Run deployment is failing. The container isn't listening on PORT=8080.

### Option A: Fix the Dockerfile (Recommended)
Update your `Dockerfile` to properly handle the PORT environment variable:

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements
COPY functions/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY functions/ .

# Expose port (documentation only)
EXPOSE 8080

# Use PORT environment variable
ENV PORT=8080

# For Cloud Run, you need an HTTP server
# Option 1: If using functions-framework (for Cloud Functions code)
CMD exec functions-framework --target=run_signal_generation --port=${PORT}

# Option 2: If you want a simple HTTP wrapper
# CMD exec gunicorn --bind :${PORT} --workers 1 --threads 8 --timeout 0 main:app
```

### Option B: Create a Simple HTTP Wrapper
If your code is designed for Cloud Functions, create a wrapper to make it work with Cloud Run:

```python
# functions/app.py
import os
from flask import Flask, request
from main import run_signal_generation

app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def trigger_function():
    # Call your existing function
    try:
        result = run_signal_generation(request)
        return result, 200
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
```

Then update your Dockerfile:
```dockerfile
CMD ["python", "app.py"]
```

### Step 3: Redeploy to Cloud Run
```bash
# Trigger a new build
git add .
git commit -m "Fix Cloud Run port configuration"
git push origin main

# Or manually deploy
gcloud builds submit --config cloudbuild.yaml
```

### Step 4: Verify the Deployment
```bash
# Check if the service is running
gcloud run services list --region=us-central1

# Test the endpoint
CLOUD_RUN_URL=$(gcloud run services describe run-signal-generation \
  --region=us-central1 \
  --format='value(status.url)')

curl -X POST $CLOUD_RUN_URL
```

## Alternative: Switch Back to Cloud Functions

If you prefer to use Cloud Functions instead of Cloud Run:

### Update cloudbuild.yaml
```yaml
steps:
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  args:
  - gcloud
  - functions
  - deploy
  - run-signal-generation
  - --gen2
  - --runtime=python39
  - --region=us-central1
  - --source=./functions
  - --entry-point=run_signal_generation
  - --trigger-http
  - --allow-unauthenticated
  - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID
  - --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest
```

Then your existing Cloud Scheduler configuration would work as-is.

## Recommended Approach

Given your setup, I recommend:
1. Fix the Cloud Run deployment by updating the Dockerfile to properly handle PORT
2. Update Cloud Scheduler to point to the Cloud Run URL
3. This maintains consistency with your micro-scalp engine which also uses Cloud Run

This approach gives you better debugging capabilities and a unified deployment model across all services. 