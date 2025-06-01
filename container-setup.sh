#!/bin/bash

# WhisperX Container Setup
# Für den Fall, dass du direkt auf einem Server arbeitest

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }

fix_package_mirrors() {
    log "Optimiere APT-Repository-Einstellungen..."
    
    # Erstelle ein Backup der sources.list
    sudo cp /etc/apt/sources.list /etc/apt/sources.list.backup
    
    # Ersetze archive.ubuntu.com mit dem Mirror-Service
    sudo sed -i 's|http://archive.ubuntu.com/ubuntu|mirror://mirrors.ubuntu.com/mirrors.txt|g' /etc/apt/sources.list
    sudo sed -i 's|http://security.ubuntu.com/ubuntu|mirror://mirrors.ubuntu.com/mirrors.txt|g' /etc/apt/sources.list
    
    # Konfiguriere mehr Retries für apt
    echo 'APT::Acquire::Retries "5";' | sudo tee /etc/apt/apt.conf.d/80-retries > /dev/null
    
    sudo apt-get update
}

main() {
    log "WhisperX Container Setup gestartet"
    
    # Optimiere apt-Repository-Einstellungen
    fix_package_mirrors
    
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
    
    # Docker Setup
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    
    log "Stoppe alte Container..."
    docker compose down 2>/dev/null || true
    
    # Überprüfe Dockerfile und patche es bei Bedarf
    log "Überprüfe und optimiere Dockerfile..."
    DOCKERFILE="whisperX-FastAPI-cuda/dockerfile"
    
    if [ -f "$DOCKERFILE" ]; then
        # Überprüfe, ob die Mirror-Änderung bereits vorhanden ist
        if ! grep -q "mirrors.ubuntu.com" "$DOCKERFILE"; then
            log "Optimiere Dockerfile für bessere Package-Downloads..."
            # Sichern des Originals
            cp "$DOCKERFILE" "${DOCKERFILE}.backup"
            
            # Patche Dockerfile für bessere APT-Mirror-Konfiguration
            sed -i 's|apt-get -y update|echo \x27APT::Acquire::Retries "5";\x27 > /etc/apt/apt.conf.d/80-retries \\\n    \&\& sed -i \x27s|http://archive.ubuntu.com/ubuntu|mirror://mirrors.ubuntu.com/mirrors.txt|g\x27 /etc/apt/sources.list \\\n    \&\& apt-get -y update|g' "$DOCKERFILE"
            
            log "Dockerfile wurde optimiert."
        else
            log "Dockerfile bereits optimiert."
        fi
    else
        warning "Dockerfile nicht gefunden unter $DOCKERFILE"
    fi
    
    log "Baue Container whisperx_cuda (kann 5-10 Minuten dauern)..."
    # Verwende erhöhte Timeouts und Retry-Mechanismen
    DOCKER_BUILDKIT=1 docker compose build --progress=plain --no-cache whisperx_cuda || {
        warning "Erster Build-Versuch fehlgeschlagen, versuche mit alternativen Einstellungen..."
        DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain docker compose build --build-arg BUILDKIT_INLINE_CACHE=1 whisperx_cuda
    }
    
    log "Starte Container..."
    docker compose up -d whisperx_cuda
    
    sleep 5
    
    log "Setup abgeschlossen!"
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