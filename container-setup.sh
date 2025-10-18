#!/bin/bash

# Manuelles WhisperX Container Setup
# Für den Fall, dass du direkt auf einem Server arbeitest

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

main() {
    log "🚀 WhisperX Container Setup gestartet"
    
    # Repository-Klon wird vom aufrufenden Skript übernommen
    # Wir sind bereits im richtigen Verzeichnis
    log "Verwende bereits geklontes Repository..."
    
    # Prüfe, ob wir im richtigen Verzeichnis sind
    if [ ! -f "docker-compose.yml" ]; then
        error "docker-compose.yml nicht gefunden. Bitte stellen Sie sicher, dass Sie im transcript-summarization Verzeichnis sind."
        exit 1
    fi
    
    # Docker Compose installieren falls nicht vorhanden
    if ! command -v docker-compose &> /dev/null; then
        log "Installiere Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        
        # Symlink für bessere Verfügbarkeit erstellen
        sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
        
        # PATH aktualisieren
        export PATH="/usr/local/bin:$PATH"
        
        log "Docker Compose installiert"
    else
        info "Docker Compose bereits installiert"
    fi
    
    # Docker Compose Version prüfen
    if command -v docker-compose &> /dev/null; then
        info "Docker Compose Version: $(docker-compose --version)"
    else
        warning "Docker Compose immer noch nicht verfügbar!"
        # Fallback: Direkten Pfad verwenden
        DOCKER_COMPOSE_CMD="/usr/local/bin/docker-compose"
        if [ -f "$DOCKER_COMPOSE_CMD" ]; then
            info "Verwende direkten Pfad: $DOCKER_COMPOSE_CMD"
            alias docker-compose="$DOCKER_COMPOSE_CMD"
        fi
    fi
    
    # Docker Setup
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    
    # Prüfe Docker Buildx Version (muss v0.18.0+ für --allow flag sein)
    log "Prüfe Docker Buildx Version..."
    if command -v docker &> /dev/null && docker buildx version &> /dev/null; then
        BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
        if [[ "$BUILDX_VERSION" < "v0.18.0" ]]; then
            warning "Docker Buildx Version $BUILDX_VERSION ist zu alt. Installiere v0.18.0+..."
            sudo mkdir -p /usr/local/lib/docker/cli-plugins
            sudo curl -L "https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
            sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
            docker buildx create --use --name mybuilder
            log "Docker Buildx v0.18.0+ installiert"
        else
            info "Docker Buildx Version $BUILDX_VERSION ist kompatibel"
        fi
    else
        warning "Docker Buildx nicht verfügbar - verwende Docker Compose v1.29.2 als Fallback"
        if ! command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
            log "Installiere Docker Compose v1.29.2 als Fallback..."
            sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-Linux-x86_64" -o /usr/local/bin/docker-compose-v1
            sudo chmod +x /usr/local/bin/docker-compose-v1
        fi
    fi
    
    log "Stoppe alte Container..."
    docker-compose down 2>/dev/null || /usr/local/bin/docker-compose down 2>/dev/null || true
    
    log "Baue Container whisperx_cuda (kann 5-10 Minuten dauern)..."
    # Verwende Docker Compose v2 wenn verfügbar, sonst v1.29.2 als Fallback
    if command -v docker-compose &> /dev/null && docker buildx version &> /dev/null; then
        info "Verwende Docker Compose v2 mit Buildx"
        docker-compose build whisperx_cuda
    elif command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
        info "Verwende Docker Compose v1.29.2 als Fallback"
        /usr/local/bin/docker-compose-v1 build whisperx_cuda
    else
        error "Keine kompatible Docker Compose Version gefunden"
        exit 1
    fi
    
    log "Starte Container..."
    if command -v docker-compose &> /dev/null && docker buildx version &> /dev/null; then
        docker-compose up -d whisperx_cuda
    elif command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
        /usr/local/bin/docker-compose-v1 up -d whisperx_cuda
    else
        error "Keine kompatible Docker Compose Version gefunden"
        exit 1
    fi
    
    sleep 10
    
    # Container Status prüfen
    log "Prüfe Container Status..."
    if command -v docker-compose &> /dev/null && docker buildx version &> /dev/null; then
        CONTAINER_STATUS=$(docker-compose ps whisperx_cuda --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    elif command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
        CONTAINER_STATUS=$(/usr/local/bin/docker-compose-v1 ps whisperx_cuda --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    else
        CONTAINER_STATUS="unknown"
    fi
    
    if [[ "$CONTAINER_STATUS" == "running" ]]; then
        log "✅ Setup erfolgreich abgeschlossen!"
        info "Container Status: $CONTAINER_STATUS"
        info "API: http://localhost:8000/docs"
        info "Health Check: curl http://localhost:8000/health"
        info "Status prüfen: docker-compose ps (oder /usr/local/bin/docker-compose ps)"
        info "Logs anzeigen: docker-compose logs -f whisperx_cuda"
    else
        warning "Container Status: $CONTAINER_STATUS"
        if command -v docker-compose &> /dev/null && docker buildx version &> /dev/null; then
            warning "Bitte Logs prüfen: docker-compose logs whisperx_cuda"
        elif command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
            warning "Bitte Logs prüfen: /usr/local/bin/docker-compose-v1 logs whisperx_cuda"
        else
            warning "Bitte Logs prüfen: docker logs whisperx-cuda"
        fi
    fi
    
    # Logs anzeigen?
    read -p "Logs anzeigen? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v docker-compose &> /dev/null && docker buildx version &> /dev/null; then
            docker-compose logs -f whisperx_cuda
        elif command -v /usr/local/bin/docker-compose-v1 &> /dev/null; then
            /usr/local/bin/docker-compose-v1 logs -f whisperx_cuda
        else
            error "Keine kompatible Docker Compose Version für Logs gefunden"
        fi
    fi
}

main "$@"