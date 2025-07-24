FROM python:3.9-slim

# Setze Arbeitsverzeichnis
WORKDIR /app

# Installiere System-Abhängigkeiten
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Kopiere requirements.txt und installiere Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere Anwendungscode
COPY . .

# Exponiere Port 8400
EXPOSE 8400

# Setze Umgebungsvariablen
ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_PORT=8400
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Starte Streamlit-App
CMD ["streamlit", "run", "app.py", "--server.port=8400", "--server.address=0.0.0.0"] 