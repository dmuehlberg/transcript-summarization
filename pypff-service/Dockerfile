FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# 1) System-Pakete
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential autoconf automake autopoint libtool pkg-config \
        git python3-dev gettext gettext-base zlib1g-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2) libpff bauen
# ---------------------------------------------------------------------------
RUN git clone --depth 1 https://github.com/libyal/libpff.git \          
 && cd libpff \                                                         
 && ./synclibs.sh \                                                     
 && ./autogen.sh \                                                      
 && PYTHON=python3 ./configure --disable-dependency-tracking --enable-python \ 
 && make \                                                              
 && make install \                                                      
 && ldconfig \                                                          
 && cd / \                                                              
 && rm -rf /libpff                                                      # aufräumen

# ---------------------------------------------------------------------------
# 3) Python-Dependencies
# ---------------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# 4) Anwendungscode
# ---------------------------------------------------------------------------
COPY ./app /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
