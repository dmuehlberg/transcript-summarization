#!/bin/bash

# Skript zum Einrichten der Transkriptions-Tabellen in der bestehenden Datenbank

echo "🗄️  Richte Transkriptions-Tabellen in der bestehenden Datenbank ein..."

# Prüfe ob PostgreSQL-Container läuft
if ! docker ps | grep -q postgres; then
    echo "❌ PostgreSQL-Container läuft nicht. Starte zuerst das System mit docker-compose up -d"
    exit 1
fi

# Lade Umgebungsvariablen
if [ -f ../.env ]; then
    source ../.env
    # Stelle sicher, dass die richtige Datenbank verwendet wird
    POSTGRES_DB=${POSTGRES_DB:-n8n}
else
    echo "⚠️  .env Datei nicht gefunden. Verwende Standardwerte."
    POSTGRES_USER=${POSTGRES_USER:-postgres}
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
    POSTGRES_DB=${POSTGRES_DB:-n8n}
fi

echo "📊 Verwende Datenbank: $POSTGRES_DB"
echo "👤 Benutzer: $POSTGRES_USER"

# Führe SQL-Skript aus
echo "🔧 Erstelle Tabellen und Beispieldaten..."
docker exec -i postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < init_transcript_tables.sql

if [ $? -eq 0 ]; then
    echo "✅ Tabellen erfolgreich erstellt!"
    echo ""
    echo "📋 Verfügbare Services:"
    echo "   React Frontend: http://localhost:8401"
    echo "   Express Backend: http://localhost:3002"
    echo "   Streamlit Frontend: http://localhost:8400"
    echo "   n8n: http://localhost:5678"
    echo "   PostgreSQL: localhost:5432"
else
    echo "❌ Fehler beim Erstellen der Tabellen"
    exit 1
fi 