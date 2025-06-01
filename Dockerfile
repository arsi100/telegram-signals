FROM python:3.9

RUN apt-get update && apt-get install -y build-essential

WORKDIR /app
COPY ./functions /app

# Install other dependencies from requirements.txt
# Ensure Cython and specific NumPy are installed before TA-Lib wheel attempt.
RUN pip install --no-cache-dir "Cython>=0.29.36" "numpy==1.26.4" -r /app/requirements.txt

# Copy and install TA-Lib wheel from local vendor directory
COPY vendor/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl /tmp/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
RUN ls -l /tmp/ && \
    pip install --no-cache-dir /tmp/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl && \
    rm /tmp/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

CMD ["functions-framework", "--target", "run_signal_generation", "--source", "/app/main.py", "--port", "8080"] 