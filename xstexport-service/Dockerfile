# .NET Core Runtime als Basis
FROM mcr.microsoft.com/dotnet/core/runtime:2.1 AS runtime

# Installieren benötigter Tools für Download und Extraktion
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    unzip \
    wget \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /app

# XstReader von GitHub herunterladen und extrahieren
RUN mkdir -p /tmp/xstreader && \
    cd /tmp/xstreader && \
    # Neueste Release-URL ermitteln
    DOWNLOAD_URL=$(curl -s https://api.github.com/repos/Dijji/XstReader/releases/latest | \
                  jq -r '.assets[] | select(.name | endswith(".zip")) | .browser_download_url') && \
    echo "Downloading from $DOWNLOAD_URL" && \
    # Download durchführen
    wget -q "$DOWNLOAD_URL" -O xstreader.zip && \
    # Entpacken
    unzip -q xstreader.zip && \
    # Dateien in das App-Verzeichnis kopieren
    cp XstPortableExport.dll /app/ && \
    cp -r XstReader.Base /app/ && \
    # Aufräumen
    cd /app && \
    rm -rf /tmp/xstreader

# Python-Abhängigkeiten installieren
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

# FastAPI-Anwendung kopieren
COPY app/ /app/

# Port öffnen
EXPOSE 8000

# FastAPI starten
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]