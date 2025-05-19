# Erster Stage zum Herunterladen und Extrahieren von XstReader
FROM debian:bullseye AS downloader

# Installieren benötigter Tools für Download und Extraktion
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    wget \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /download

# XstReader von GitHub herunterladen und extrahieren
RUN mkdir -p xstreader && \
    cd xstreader && \
    # Neueste Release-URL ermitteln
    DOWNLOAD_URL=$(curl -s https://api.github.com/repos/Dijji/XstReader/releases/latest | \
                  jq -r '.assets[] | select(.name | endswith(".zip")) | .browser_download_url') && \
    echo "Downloading from $DOWNLOAD_URL" && \
    # Download durchführen
    wget -q "$DOWNLOAD_URL" -O xstreader.zip && \
    # Entpacken
    unzip -q xstreader.zip

# Zweiter Stage mit .NET Runtime
FROM mcr.microsoft.com/dotnet/runtime:6.0 AS runtime

# Installieren von Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /app

# XstReader-Dateien vom ersten Stage kopieren
COPY --from=downloader /download/xstreader/XstPortableExport.dll /app/
COPY --from=downloader /download/xstreader/XstReader.Base /app/XstReader.Base/

# Python-Abhängigkeiten installieren
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

# FastAPI-Anwendung kopieren
COPY app/ /app/

# Port öffnen
EXPOSE 8000

# FastAPI starten
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]