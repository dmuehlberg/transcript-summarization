ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# 1) System-Pakete und Basis-Tools installieren
# ---------------------------------------------------------------------------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential autoconf automake autopoint libtool pkg-config \
      git python3-dev gettext gettext-base zlib1g-dev libssl-dev \
      python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2) libpff direkt von GitHub klonen und manuell bauen
# ---------------------------------------------------------------------------
RUN git clone --depth 1 https://github.com/libyal/libpff.git \          
 && cd libpff \                                                         
 && ./synclibs.sh \                                                     
 && ./autogen.sh \                                                      
 && PYTHON=python3 ./configure --disable-dependency-tracking --enable-python \ 
 && make \                                                              
 && make install \                                                      
 && ldconfig \
 # Sicherstellen, dass der Python-Pfad korrekt ist und das pypff Modul gefunden wird
 && ln -s /usr/local/lib/python3.10/site-packages/pypff /usr/local/lib/python3.10/dist-packages/ || true \
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

# Prüfen, ob das Modul gefunden wird, bevor wir starten
RUN python -c "import sys; print(sys.path); import pypff; print('pypff erfolgreich geladen')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]