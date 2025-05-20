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

# XstReader direkt von einer spezifischen Release-Version herunterladen und extrahieren
RUN mkdir -p xstreader && \
    cd xstreader && \
    # Direkte URL zur Release-Version 1.14
    DOWNLOAD_URL="https://github.com/Dijji/XstReader/releases/download/v1.14/XstReader.zip" && \
    echo "Downloading from $DOWNLOAD_URL" && \
    # Download durchführen
    wget -q "$DOWNLOAD_URL" -O xstreader.zip && \
    # Entpacken
    unzip -q xstreader.zip && \
    # Debug: Dateistruktur anzeigen
    find . -type f -o -type d | sort > /download/file_structure.txt && \
    # Sicherstellen, dass Ausgabeverzeichnis existiert
    mkdir -p /download/output && \
    mkdir -p /download/output/XstReader.Base && \
    # Versuch XstPortableExport.dll zu finden und zu kopieren
    if [ -n "$(find . -name "XstPortableExport.dll" | head -1)" ]; then \
      # Den Verzeichnispfad zur DLL ermitteln
      EXPORT_DIR=$(dirname $(find . -name "XstPortableExport.dll" | head -1)) && \
      # Alle Dateien aus diesem Verzeichnis kopieren
      cp -r $EXPORT_DIR/* /download/output/ || true && \
      echo "XstPortableExport.dll and associated files found and copied from $EXPORT_DIR" ; \
    else \
      echo "XstPortableExport.dll NOT found" ; \
      touch /download/output/XstPortableExport.dll.missing ; \
    fi && \
    # Versuche XstReader.Base als Verzeichnis zu finden
    if [ -n "$(find . -type d -name "XstReader.Base" | head -1)" ]; then \
      cp -r $(find . -type d -name "XstReader.Base" | head -1)/* /download/output/XstReader.Base/ || true && \
      echo "XstReader.Base directory found and copied" ; \
      ls -la /download/output/XstReader.Base/ > /download/base_structure.txt || true ; \
    else \
      echo "XstReader.Base directory NOT found" ; \
      # Erstelle ein leeres Verzeichnis als Fallback
      touch /download/output/XstReader.Base/directory.missing ; \
      echo "Created empty directory with indicator file" > /download/base_structure.txt || true ; \
    fi && \
    # Debug: Ausgabe zeigen
    ls -la /download/output/ > /download/output_structure.txt || true

# Zweiter Stage mit .NET 2.1 Runtime
FROM mcr.microsoft.com/dotnet/core/runtime:2.1 AS runtime

# Installieren von Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /app

# Sicherstellen, dass die benötigten Verzeichnisse existieren
RUN mkdir -p /app/XstReader.Base

# Debug-Infos kopieren
COPY --from=downloader /download/file_structure.txt /app/ || true
COPY --from=downloader /download/output_structure.txt /app/ || true
COPY --from=downloader /download/base_structure.txt /app/ || true

# XstReader-Dateien vom ersten Stage kopieren
COPY --from=downloader /download/output/*.dll /app/ || true
COPY --from=downloader /download/output/*.json /app/ || true

# XstReader.Base kopieren
COPY --from=downloader /download/output/XstReader.Base/* /app/XstReader.Base/ || true

# Prüfen, ob die benötigten Dateien vorhanden sind oder Fehler ausgeben
RUN ls -la /app/ && \
    if [ -f "/app/XstPortableExport.dll" ]; then \
      echo "XstPortableExport.dll exists" ; \
    else \
      echo "XstPortableExport.dll NOT found after copy!" && \
      exit 1; \
    fi

# Python-Abhängigkeiten installieren
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

# FastAPI-Anwendung kopieren
COPY app/ /app/app/

# Ausgabeverzeichnis für OST-Dateien erstellen
RUN mkdir -p /data/ost && chmod 777 /data/ost

# Port öffnen
EXPOSE 8200

# FastAPI starten
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]