#!/bin/bash

# Manuelles WhisperX Container Setup
# Für den Fall, dass du direkt auf einem Server arbeitest

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }

main() {
    log "🚀 WhisperX Container Setup gestartet"
    
    # Repository klonen/aktualisieren
    if [ -d "transcript-summarization" ]; then
        warning "Repository existiert bereits"
        cd transcript-summarization
        git pull origin main || git pull origin master || true
        cd ..
    else
        log "Klone Repository..."
        git clone https://github.com/dmuehlberg/transcript-summarization.git
    fi
    
    cd transcript-summarization
    
    # Docker Compose installieren falls nicht vorhanden
    if ! command -v docker-compose &> /dev/null; then
        log "Installiere Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        log "Docker Compose installiert"
    else
        info "Docker Compose bereits installiert"
    fi
    
    # Docker Setup
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    
    log "Stoppe alte Container..."
    docker-compose down 2>/dev/null || true
    
    log "Baue Container whisperx_cuda (kann 5-10 Minuten dauern)..."
    docker-compose build whisperx_cuda
    
    log "Starte Container..."
    docker-compose up -d whisperx_cuda
    
    sleep 10
    
    # Container Status prüfen
    log "Prüfe Container Status..."
    CONTAINER_STATUS=$(docker-compose ps whisperx_cuda --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    
    if [[ "$CONTAINER_STATUS" == "running" ]]; then
        log "✅ Setup erfolgreich abgeschlossen!"
        info "Container Status: $CONTAINER_STATUS"
        info "API: http://localhost:8000/docs"
        info "Health Check: curl http://localhost:8000/health"
        info "Status prüfen: docker-compose ps"
        info "Logs anzeigen: docker-compose logs -f whisperx_cuda"
    else
        warning "Container Status: $CONTAINER_STATUS"
        warning "Bitte Logs prüfen: docker-compose logs whisperx_cuda"
    fi
    
    # Logs anzeigen?
    read -p "Logs anzeigen? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose logs -f whisperx_cuda
    fi
}

main "$@"