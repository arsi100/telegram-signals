FROM python:3.9

RUN apt-get update && apt-get install -y wget build-essential

WORKDIR /app
COPY ./functions /app

# Install other dependencies from requirements.txt
# Ensure Cython and specific NumPy are installed before TA-Lib wheel attempt.
RUN pip install --no-cache-dir "Cython>=0.29.36" "numpy==1.26.4" -r /app/requirements.txt

# Download and install the TA-Lib wheel manually
RUN wget https://files.pythonhosted.org/packages/e3/69/982817f8e812742805b3a282888d736236c79893493e4688d72039533f17/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -O /tmp/TA_Lib.whl && \
    pip install --no-cache-dir /tmp/TA_Lib.whl && \
    rm /tmp/TA_Lib.whl

CMD ["functions-framework", "--target", "run_signal_generation", "--source", "/app/main.py", "--port", "8080"] 