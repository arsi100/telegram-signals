# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size and improve build time
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Cloud Run requires the container to listen on the port defined by the $PORT environment variable.
# The default is 8080.
ENV PORT 8080

# The GCP_PROJECT_ID will be set as an environment variable in the Cloud Run service configuration.
# The service account attached to the Cloud Run service will handle authentication.
ENV GCP_PROJECT_ID=""
ENV BYBIT_TICK_TOPIC_ID="raw-tick-data-bybit"

# Run main.py when the container launches.
# This script starts both the health check server and the WebSocket client.
CMD ["python", "main.py"] 