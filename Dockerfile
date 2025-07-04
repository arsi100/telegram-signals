# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container to the functions folder
WORKDIR /app

# Copy the requirements file from the functions directory
COPY functions/requirements.txt .

# Install any needed packages specified in requirements.txt
# This layer is only rebuilt when requirements.txt changes.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the functions directory into the container
COPY functions/ .

# Set the command to run when the container starts
CMD ["functions-framework", "--target", "run_signal_generation", "--source", "main.py", "--port", "8080"] 