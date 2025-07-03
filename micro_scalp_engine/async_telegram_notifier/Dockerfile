# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
# This includes the main.py and allows the path hack to find the `functions` module
COPY ../../. /app/

# The CMD instruction tells the container to run the notifier.
CMD ["python", "micro_scalp_engine/async_telegram_notifier/main.py"] 