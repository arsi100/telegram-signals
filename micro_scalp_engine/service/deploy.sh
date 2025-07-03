#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Google Cloud settings - replace with your actual values or ensure they are set in your environment
GCP_PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
GCP_REGION="${GCP_REGION:-us-central1}"
ARTIFACT_REGISTRY_NAME="crypto-signal-tracker-repo"
SERVICE_NAME="micro-scalp-engine"
IMAGE_NAME="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_NAME}/${SERVICE_NAME}:latest"

# --- Pre-flight Checks ---
if [[ "$GCP_PROJECT_ID" == "your-gcp-project-id" ]]; then
    echo "🚨 Error: Please set your GCP_PROJECT_ID in this script or as an environment variable."
    exit 1
fi

echo "--- Configuration ---"
echo "Project ID:           ${GCP_PROJECT_ID}"
echo "Region:               ${GCP_REGION}"
echo "Service Name:         ${SERVICE_NAME}"
echo "Image Name:           ${IMAGE_NAME}"
echo "---------------------"

# --- 1. Configure gcloud ---
echo "🔑 Configuring gcloud to use project ${GCP_PROJECT_ID}..."
gcloud config set project "${GCP_PROJECT_ID}"
gcloud config set run/region "${GCP_REGION}"

# --- 2. Build the Docker image ---
echo "🏗️ Building Docker image..."
# We run this from the parent directory to have the correct context for the COPY command
cd .. 
docker build -t "${IMAGE_NAME}" -f service/Dockerfile .
cd service # Return to the service directory

# --- 3. Push the image to Artifact Registry ---
echo "⬆️  Pushing image to Artifact Registry..."
# Configure Docker to use gcloud as a credential helper.
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
docker push "${IMAGE_NAME}"

# --- 4. Deploy to Cloud Run ---
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}" \
    --platform="managed" \
    --region="${GCP_REGION}" \
    --allow-unauthenticated \
    --min-instances=1 \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
    # TODO: Add secrets for BYBIT_API_KEY and BYBIT_API_SECRET
    # --set-secrets="BYBIT_API_KEY=bybit-api-key:latest,BYBIT_API_SECRET=bybit-api-secret:latest"
    --quiet

echo "✅ Deployment complete."
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --format 'value(status.url)')" 