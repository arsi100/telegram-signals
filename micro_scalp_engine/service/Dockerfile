# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire micro_scalp_engine directory into the container
# This makes all modules (level_finder, entry_logic, etc.) available
COPY ../. .

# The CMD instruction tells the container to run the logic_engine.
# This is the main entry point for the service.
CMD ["python", "-m", "micro_scalp_engine.logic_engine"] 