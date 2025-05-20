# .NET Core 2.1 Runtime als Basis (spezifisch für arm64)
FROM mcr.microsoft.com/dotnet/core/runtime:2.1

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
    ls -la /app/ > /app/app_contents.txt && \
    # Zeige .NET-Informationen
    dotnet --info

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