#!/bin/bash

# Transkriptions-Steuerung Start-Skript

echo "🚀 Starte Transkriptions-Steuerung..."

# Prüfe ob Docker installiert ist
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ist nicht installiert. Bitte installiere Docker zuerst."
    exit 1
fi

# Prüfe ob Docker Compose installiert ist
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose ist nicht installiert. Bitte installiere Docker Compose zuerst."
    exit 1
fi

# Prüfe ob .env Datei existiert
if [ ! -f .env ]; then
    echo "📝 .env Datei nicht gefunden. Erstelle aus env.example..."
    cp env.example .env
    echo "⚠️  Bitte bearbeite die .env Datei mit deinen Konfigurationswerten."
fi

# Baue und starte die Container
echo "🔨 Baue Docker Container..."
docker-compose build

echo "🚀 Starte Services..."
docker-compose up -d

# Warte kurz und zeige Status
sleep 5

echo "📊 Container Status:"
docker-compose ps

echo ""
echo "✅ Transkriptions-Steuerung ist gestartet!"
echo ""
echo "🌐 Zugriff:"
echo "   Frontend: http://localhost:8400"
echo "   Backend API: http://localhost:3001"
echo "   PostgreSQL: localhost:5432"
echo ""
echo "📋 Nützliche Befehle:"
echo "   Logs anzeigen: docker-compose logs -f"
echo "   Stoppen: docker-compose down"
echo "   Neustart: docker-compose restart"
echo "   Status: docker-compose ps"
echo ""
echo "🔧 Mit n8n starten: docker-compose --profile n8n up -d" 