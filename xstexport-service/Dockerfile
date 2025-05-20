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
    # Sicherstellen, dass Ausgabeverzeichnis existiert
    mkdir -p /download/output && \
    # Versuch XstPortableExport.dll zu finden und zu kopieren
    if [ -n "$(find . -name "XstPortableExport.dll" | head -1)" ]; then \
      # Den Verzeichnispfad zur DLL ermitteln
      EXPORT_DIR=$(dirname $(find . -name "XstPortableExport.dll" | head -1)) && \
      # Alle Dateien aus diesem Verzeichnis kopieren
      cp -r $EXPORT_DIR/* /download/output/ && \
      echo "XstPortableExport.dll and associated files found and copied from $EXPORT_DIR" ; \
    else \
      echo "XstPortableExport.dll NOT found" ; \
      touch /download/output/XstPortableExport.dll.missing ; \
    fi && \
    # Versuche XstReader.Base als Verzeichnis zu finden
    if [ -n "$(find . -type d -name "XstReader.Base" | head -1)" ]; then \
      mkdir -p /download/output/XstReader.Base && \
      cp -r $(find . -type d -name "XstReader.Base" | head -1)/* /download/output/XstReader.Base/ ; \
      echo "XstReader.Base directory found and copied" ; \
      ls -la /download/output/XstReader.Base/ > /download/base_structure.txt ; \
    else \
      echo "XstReader.Base directory NOT found" ; \
      # Erstelle ein leeres Verzeichnis als Fallback
      mkdir -p /download/output/XstReader.Base && \
      touch /download/output/XstReader.Base/directory.missing ; \
      echo "Created empty directory with indicator file" > /download/base_structure.txt ; \
    fi && \
    # Debug: Ausgabe zeigen
    ls -la /download/output/ > /download/output_structure.txt