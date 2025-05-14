FROM python:3.10-slim

# Installiere notwendige Abhängigkeiten
RUN apt-get update && apt-get install -y \
    libpff-dev gcc python3-dev

# Kopiere Anforderungen und installiere sie
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installiere eine Alternative wie python-libpff
RUN pip install python-libpff

# Kopiere Anwendungscode
COPY ./app /app
WORKDIR /app

# Starte die Anwendung
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]