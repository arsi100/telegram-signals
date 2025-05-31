FROM python:3.9-slim
RUN apt-get update && apt-get install -y wget build-essential
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && make && make install
RUN pip install TA-Lib==0.4.29
WORKDIR /app
COPY ./functions /app
RUN pip install -r /app/requirements.txt
CMD ["functions-framework", "--target", "run_signal_generation", "--source", "/app/main.py", "--port", "8080"] 