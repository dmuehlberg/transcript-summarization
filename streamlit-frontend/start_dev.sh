#!/bin/bash

# Streamlit Dashboard Development Start Script

echo "🚀 Starting Streamlit Dashboard in Development Mode..."

# Prüfe ob Python 3.9+ verfügbar ist
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python $python_version gefunden"
else
    echo "❌ Python 3.9+ erforderlich, gefunden: $python_version"
    exit 1
fi

# Prüfe ob .env Datei existiert
if [ ! -f "../.env" ]; then
    echo "❌ .env Datei nicht gefunden. Bitte erstellen Sie eine .env Datei im Projektroot."
    exit 1
fi

# Installiere Dependencies
echo "📦 Installiere Dependencies..."
pip install -r requirements.txt

# Führe Tests aus
echo "🧪 Führe Tests aus..."
python -m pytest tests/ -v

# Starte Streamlit App
echo "🎯 Starte Streamlit Dashboard..."
echo "📍 Verfügbar unter: http://localhost:8400"
echo "🛑 Beenden mit: Ctrl+C"

streamlit run app.py --server.port=8400 --server.address=0.0.0.0 