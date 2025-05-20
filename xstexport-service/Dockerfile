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
    # Nicht die Architektur erkennen, sondern direkt ARM64 Build verwenden, da wir wissen, dass wir auf ARM64 sind
    && mkdir -p /usr/share/dotnet \
    && wget -q https://dotnetcli.blob.core.windows.net/dotnet/Runtime/2.1.30/dotnet-runtime-2.1.30-linux-arm64.tar.gz -O dotnet-runtime-2.1.30-linux.tar.gz \
    && tar -zxf dotnet-runtime-2.1.30-linux.tar.gz -C /usr/share/dotnet \
    && rm dotnet-runtime-2.1.30-linux.tar.gz \
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