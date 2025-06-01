FROM python:3.9

RUN apt-get update && apt-get install -y wget build-essential curl

WORKDIR /app
COPY ./functions /app

# Install other dependencies from requirements.txt
# Ensure Cython and specific NumPy are installed before TA-Lib wheel attempt.
RUN pip install --no-cache-dir "Cython>=0.29.36" "numpy==1.26.4" -r /app/requirements.txt

# Download and install the TA-Lib wheel manually
RUN apt-get update && apt-get install -y curl && \\\
    (wget -v https://files.pythonhosted.org/packages/1c/95/53756306870979c2f98c0a0564e656c3922f74bf6d5a4392c3e787da170d/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -O /tmp/TA_Lib.whl || \\\
     curl -fvL https://files.pythonhosted.org/packages/1c/95/53756306870979c2f98c0a0564e656c3922f74bf6d5a4392c3e787da170d/TA_Lib-0.4.31-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -o /tmp/TA_Lib.whl) && \\\
    pip install --no-cache-dir /tmp/TA_Lib.whl && \\\
    rm /tmp/TA_Lib.whl

CMD ["functions-framework", "--target", "run_signal_generation", "--source", "/app/main.py", "--port", "8080"] 