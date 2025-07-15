FROM python:3.9-slim

# Build-Argument für die Plattform
ARG TARGETPLATFORM=linux/amd64

# Installiere libpst und andere Abhängigkeiten
RUN apt-get update && apt-get install -y \
    libpst-dev \
    wget \
    gnupg \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/*

# Installiere .NET SDK für beide Architekturen
RUN if [ "$TARGETPLATFORM" = "linux/arm64/v8" ]; then \
        wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh \
        && chmod +x dotnet-install.sh \
        && ./dotnet-install.sh --version 6.0.419 \
        && rm dotnet-install.sh \
        && ln -s /root/.dotnet/dotnet /usr/local/bin/dotnet; \
    else \
        wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh \
        && chmod +x dotnet-install.sh \
        && ./dotnet-install.sh --version 6.0.419 \
        && rm dotnet-install.sh \
        && ln -s /root/.dotnet/dotnet /usr/local/bin/dotnet; \
    fi

# Kopiere die Anwendungscode und Konfiguration
COPY app/ /app/app/
COPY app/config/ /app/app/config/
COPY XstReader/XstExporter.Portable.dll /app/XstExporter.Portable.dll
COPY XstReader/XstExporter.Portable.deps.json /app/XstExporter.Portable.deps.json
COPY XstReader/XstExporter.Portable.runtimeconfig.json /app/XstExporter.Portable.runtimeconfig.json
COPY XstReader/XstReader.Api.dll /app/XstReader.Api.dll

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Installiere Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install -r requirements.txt

# Erstelle Verzeichnis für PST/OST-Dateien
RUN mkdir -p /data/ost

# Setze .NET-Umgebungsvariablen für Globalisierung und große Dateien
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
ENV DOTNET_CLI_UI_LANGUAGE=en
ENV DOTNET_GCHeapHardLimit=0x8000000
ENV DOTNET_GCAllowVeryLargeObjects=1
ENV DOTNET_GCHeapHardLimitPercent=80

# Exponiere den Port
EXPOSE 8200

# Starte die Anwendung
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]