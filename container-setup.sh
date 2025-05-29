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
    
    # .env Datei erstellen falls nicht vorhanden
    if [ ! -f ".env" ]; then
        warning "Erstelle .env Datei..."
        cat > .env << 'EOF'
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
EOF
        warning "WICHTIG: Bearbeite .env und setze deinen HuggingFace Token!"
        info "Verwende: nano .env"
        read -p "Drücke Enter nach Bearbeitung der .env Datei..." -r
    fi
    
    # Docker Setup
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    
    log "Stoppe alte Container..."
    docker compose down 2>/dev/null || true
    
    log "Baue Container whisperx_cuda (kann 5-10 Minuten dauern)..."
    docker compose build whisperx_cuda
    
    log "Starte Container..."
    docker compose up -d whisperx_cuda
    
    sleep 5
    
    log "✅ Setup abgeschlossen!"
    info "API: http://localhost:8000/docs"
    info "Status: docker compose ps"
    info "Logs: docker compose logs -f"
    
    # Logs anzeigen?
    read -p "Logs anzeigen? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose logs -f
    fi
}

main "$@"