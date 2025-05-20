# Neueres .NET Runtime als Basis (6.0 statt 2.1)
FROM mcr.microsoft.com/dotnet/runtime:6.0

# Benötigte Pakete installieren
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis einrichten
WORKDIR /app

# Lokale XstReader-Dateien kopieren statt herunterladen
COPY XstReader/ /app/

# Debug-Info erstellen
RUN find . -type f -o -type d | sort > /app/file_structure.txt && \
    ls -la /app/ > /app/app_contents.txt

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