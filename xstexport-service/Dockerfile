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

# XstReader von GitHub herunterladen und extrahieren mit Debug-Ausgabe
RUN mkdir -p xstreader && \
    cd xstreader && \
    # Neueste Release-URL ermitteln
    DOWNLOAD_URL=$(curl -s https://api.github.com/repos/Dijji/XstReader/releases/latest | \
                  jq -r '.assets[] | select(.name | endswith(".zip")) | .browser_download_url') && \
    echo "Downloading from $DOWNLOAD_URL" && \
    # Download durchführen
    wget -q "$DOWNLOAD_URL" -O xstreader.zip && \
    # Entpacken
    unzip -q xstreader.zip && \
    # Debug: Dateistruktur anzeigen
    find . -type f -o -type d | sort > /download/file_structure.txt && \
    # Dateien in ein standardisiertes Verzeichnis kopieren
    mkdir -p /download/output && \
    find . -name "XstPortableExport.dll" -exec cp {} /download/output/ \; && \
    # finde XstReader.Base entweder als Datei oder Verzeichnis
    if [ -d "$(find . -type d -name "XstReader.Base" | head -1)" ]; then \
      mkdir -p /download/output/XstReader.Base && \
      cp -r $(find . -type d -name "XstReader.Base" | head -1)/* /download/output/XstReader.Base/ ; \
    else \
      # Falls es eine einzelne Datei ist (unwahrscheinlich, aber zur Sicherheit)
      find . -name "XstReader.Base.*" -exec cp {} /download/output/ \; ; \
    fi && \
    # Debug: Ausgabe zeigen
    ls -la /download/output/ > /download/output_structure.txt && \
    if [ -d "/download/output/XstReader.Base" ]; then \
      ls -la /download/output/XstReader.Base/ > /download/base_structure.txt; \
    fi

# Zweiter Stage mit .NET Runtime
FROM mcr.microsoft.com/dotnet/runtime:6.0 AS runtime

# Installieren von Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /app

# Debug-Infos kopieren
COPY --from=downloader /download/file_structure.txt /app/
COPY --from=downloader /download/output_structure.txt /app/
COPY --from=downloader /download/base_structure.txt /app/ 2>/dev/null || :

# XstReader-Dateien vom ersten Stage kopieren
COPY --from=downloader /download/output/XstPortableExport.dll /app/

# Sicherstellen, dass das Zielverzeichnis existiert
RUN mkdir -p /app/XstReader.Base/

# XstReader.Base kopieren (wenn es existiert)
COPY --from=downloader /download/output/XstReader.Base/ /app/XstReader.Base/ 2>/dev/null || :

# Python-Abhängigkeiten installieren
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

# FastAPI-Anwendung kopieren
COPY app/ /app/

# Port öffnen
EXPOSE 8000

# FastAPI starten
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]