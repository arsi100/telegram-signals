FROM python:3.9
RUN apt-get update && apt-get install -y wget build-essential \
    && wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && ldconfig \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

ENV TA_INCLUDE_PATH=/usr/include
ENV TA_LIBRARY_PATH=/usr/lib

RUN pip install --no-cache-dir "Cython>=0.29.36" "numpy==1.26.4"
RUN pip install --no-cache-dir "TA-Lib==0.4.30"
WORKDIR /app
COPY ./functions /app
RUN pip install --no-cache-dir -r /app/requirements.txt
CMD ["functions-framework", "--target", "run_signal_generation", "--source", "/app/main.py", "--port", "8080"] 