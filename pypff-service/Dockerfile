FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# System-Abhängigkeiten
RUN apt-get update && apt-get install -y \
    build-essential \
    autoconf \
    automake \
    autopoint \
    libtool \
    pkg-config \
    git \
    python3 \
    python3-dev \
    python3-pip \
    libfuse-dev \
    libbz2-dev \
    libz-dev \
    libssl-dev \
    wget \
    gettext \
    gettext-base \
    && apt-get clean

# libpff bauen
RUN git clone https://github.com/libyal/libpff.git && \
    cd libpff && \
    ./synclibs.sh && \
    ./autogen.sh && \
    PYTHON=python3 ./configure --disable-dependency-tracking --enable-python && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    cd bindings/python && \
    python3 setup.py build && \
    python3 setup.py install

# Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY ./app /app
WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]