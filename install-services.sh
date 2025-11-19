#!/bin/bash
#
# Services-Installation für WhisperX + Ollama.
# Wird als ec2-user gestartet (nohup), schreibt Logs nach /var/log/install-services.log.

set -euo pipefail

LOG_FILE="/var/log/install-services.log"

# Prüfe ob Log-Datei beschreibbar ist, sonst Fallback auf Home-Verzeichnis
if [ ! -w "${LOG_FILE}" ] 2>/dev/null; then
    LOG_FILE="${HOME}/install-services.log"
    echo "Warnung: /var/log/install-services.log nicht beschreibbar, verwende ${LOG_FILE}" >&2
fi

exec >> "${LOG_FILE}" 2>&1

echo "=== SERVICES INSTALLATION GESTARTET ==="
echo "Datum: $(date)"

REPO_DIR="/home/ec2-user/transcript-summarization"

if [ ! -d "${REPO_DIR}" ]; then
    echo "Repository nicht gefunden, warte auf Bootstrap..."
    MAX_WAIT=300
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ] && [ ! -d "${REPO_DIR}" ]; do
        sleep 5
        WAIT_COUNT=$((WAIT_COUNT + 5))
        if [ $((WAIT_COUNT % 30)) -eq 0 ]; then
            echo "Warte auf Repository... (${WAIT_COUNT}/${MAX_WAIT} Sekunden)"
        fi
    done
fi

if [ ! -d "${REPO_DIR}" ]; then
    echo "FEHLER: Repository weiterhin nicht verfügbar, breche ab."
    exit 1
fi

cd "${REPO_DIR}"

if [ -f "./container-setup.sh" ]; then
    echo "Führe container-setup.sh aus..."
    chmod +x ./container-setup.sh
    echo "n" | timeout 1800 ./container-setup.sh 2>&1 || true
else
    echo "FEHLER: container-setup.sh nicht gefunden!"
    echo "Versuche, Skript aus dem Repository herunterzuladen..."
    curl -L https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh -o ./container-setup.sh 2>&1
    if [ -f "./container-setup.sh" ]; then
        chmod +x ./container-setup.sh
        echo "n" | timeout 1800 ./container-setup.sh 2>&1 || true
    else
        echo "FEHLER: container-setup.sh konnte nicht geladen werden."
        exit 1
    fi
fi

echo "=== OLLAMA-GPU INSTALLATION ==="
echo "Warte auf WhisperX-Container..."
WHISPERX_WAIT=600
WHISPERX_COUNT=0
WHISPERX_READY=false

while [ $WHISPERX_COUNT -lt $WHISPERX_WAIT ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ WhisperX-Container läuft"
        WHISPERX_READY=true
        break
    fi
    if [ $((WHISPERX_COUNT % 60)) -eq 0 ]; then
        echo "Warte auf WhisperX... ($WHISPERX_COUNT/$WHISPERX_WAIT Sekunden)"
    fi
    sleep 10
    WHISPERX_COUNT=$((WHISPERX_COUNT + 10))
done

if [ "$WHISPERX_READY" != "true" ]; then
    echo "⚠️ Warnung: WhisperX-Container nicht erreichbar nach $WHISPERX_WAIT Sekunden"
    echo "Ollama-Installation wird trotzdem versucht..."
fi

DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif [ -f "/usr/local/bin/docker-compose" ]; then
    DOCKER_COMPOSE_CMD="/usr/local/bin/docker-compose"
else
    echo "FEHLER: docker-compose nicht gefunden"
    exit 1
fi

echo "Starte Ollama-GPU Container..."
$DOCKER_COMPOSE_CMD --profile gpu-nvidia up -d ollama-gpu 2>&1 || true

echo "Warte auf Ollama-Container-Start..."
MAX_WAIT=120
WAIT_COUNT=0
OLLAMA_READY=false

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama-Container läuft"
        OLLAMA_READY=true
        break
    fi
    if [ $((WAIT_COUNT % 15)) -eq 0 ]; then
        echo "Warte auf Ollama... ($WAIT_COUNT/$MAX_WAIT Sekunden)"
    fi
    sleep 5
    WAIT_COUNT=$((WAIT_COUNT + 5))
done

if [ "$OLLAMA_READY" = "true" ]; then
    echo "Pulle qwen2.5:7b Modell..."
    if docker exec ollama ollama pull qwen2.5:7b 2>&1; then
        echo "✅ qwen2.5:7b Modell erfolgreich gepullt"
    else
        echo "⚠️ Warnung: Direkter Pull fehlgeschlagen, versuche alternativen Ansatz..."
        docker run --rm \
            --network transcript-summarization_demo \
            -v transcript-summarization_ollama_storage:/root/.ollama \
            ollama/ollama:latest \
            /bin/sh -c "sleep 3; OLLAMA_HOST=ollama:11434 ollama pull qwen2.5:7b" 2>&1 || true
    fi
else
    echo "⚠️ Warnung: Ollama-Container nicht erreichbar, Modell-Pull wird übersprungen"
fi

echo "=== INSTALLATION STATUS ==="
echo "Datum: $(date)"

echo "Docker Container:"
$DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "Container Status nicht verfügbar"

echo "Ollama Container:"
docker ps --filter name=ollama --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Ollama Container Status nicht verfügbar"

echo "Ollama API Check:"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama API: OK"
else
    echo "⚠️ Ollama API: Nicht verfügbar"
fi

echo "Ollama Modell Check:"
if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "✅ qwen2.5:7b Modell verfügbar"
else
    echo "⚠️ qwen2.5:7b Modell nicht gefunden"
fi

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unbekannt")
echo "Public IP: $PUBLIC_IP"
echo "API URL: http://$PUBLIC_IP:8000/docs"
echo "Ollama API: http://$PUBLIC_IP:11434/api/tags"

curl -s http://localhost:8000/health 2>/dev/null && echo "API Health Check: OK" || echo "API Health Check: Nicht verfügbar"

echo "=== SERVICES INSTALLATION ABGESCHLOSSEN ==="

