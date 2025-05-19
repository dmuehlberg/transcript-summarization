FROM mcr.microsoft.com/dotnet/core/runtime:2.1 AS runtime



# Python Installation hinzufügen
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# XstPortableExport installieren
WORKDIR /app
COPY XstPortableExport.dll /app/
COPY XstReader.Base/ /app/XstReader.Base/

# Python-Abhängigkeiten installieren
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt



COPY ./app /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]