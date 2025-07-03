# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy just the requirements file to leverage Docker layer caching
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# This layer is only rebuilt when requirements.txt changes.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Set the command to run when the container starts
# The main.py file needs to be in the root of what's copied to /app
CMD ["functions-framework", "--target", "run_signal_generation", "--source", "main.py", "--port", "8080"] 