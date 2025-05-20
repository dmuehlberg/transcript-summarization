# Neueres Debian als Basis verwenden
FROM debian:bullseye

# .NET Core 2.1 herunterladen und installieren
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    python3 \
    python3-pip \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q https://download.visualstudio.microsoft.com/download/pr/e9fec778-d087-4c89-b13e-71a6dda8c1d3/a717e6dcd6421c972afe8671ede0213a/dotnet-runtime-2.1.30-linux-x64.tar.gz \
    && mkdir -p /usr/share/dotnet \
    && tar -zxf dotnet-runtime-2.1.30-linux-x64.tar.gz -C /usr/share/dotnet \
    && rm dotnet-runtime-2.1.30-linux-x64.tar.gz \
    && ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

# Arbeitsverzeichnis einrichten
WORKDIR /app

# Lokale XstReader-Dateien kopieren statt herunterladen
COPY XstReader/ /app/

# Debug-Info erstellen
RUN find . -type f -o -type d | sort > /app/file_structure.txt && \
    ls -la /app/ > /app/app_contents.txt && \
    # Zeige .NET-Informationen
    dotnet --info > /app/dotnet_info.txt

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