#!/bin/bash

# WhisperX FastAPI Container Setup Script
# Automatisierte Installation und Start des WhisperX Services
# Autor: Automatisch generiert für brev.nvidia.com Instanzen

set -e  # Exit on any error

# Farbige Ausgabe für bessere Lesbarkeit
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging-Funktion
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Überprüfung der Voraussetzungen
check_prerequisites() {
    log "Überprüfe Voraussetzungen..."
    
    # Git prüfen
    if ! command -v git &> /dev/null; then
        error "Git ist nicht installiert. Bitte installiere Git zuerst."
        exit 1
    fi
    
    # Docker prüfen
    if ! command -v docker &> /dev/null; then
        error "Docker ist nicht installiert. Bitte installiere Docker zuerst."
        exit 1
    fi
    
    # Docker Compose prüfen
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose ist nicht installiert. Bitte installiere Docker Compose zuerst."
        exit 1
    fi
    
    # NVIDIA Docker prüfen (für GPU Support)
    if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        warning "NVIDIA Docker Runtime scheint nicht korrekt konfiguriert zu sein."
        warning "GPU Support könnte nicht funktionieren."
    fi
    
    log "Alle Voraussetzungen erfüllt ✓"
}

# Repository klonen oder aktualisieren
clone_or_update_repo() {
    local repo_url="https://github.com/dmuehlberg/transcript-summarization.git"
    local repo_dir="transcript-summarization"
    
    if [ -d "$repo_dir" ]; then
        warning "Repository Verzeichnis existiert bereits."
        read -p "Möchtest du das Repository aktualisieren? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Aktualisiere Repository..."
            cd "$repo_dir"
            git pull origin main || git pull origin master
            cd ..
        else
            log "Verwende existierendes Repository."
        fi
    else
        log "Klone Repository von $repo_url..."
        git clone "$repo_url"
    fi
}

# .env Datei überprüfen/erstellen
setup_env_file() {
    local repo_dir="transcript-summarization"
    cd "$repo_dir"
    
    if [ ! -f ".env" ]; then
        warning ".env Datei nicht gefunden. Erstelle Standard .env Datei..."
        
        # Überprüfe ob .env.example existiert
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log ".env Datei aus .env.example erstellt."
        else
            # Erstelle minimale .env Datei basierend auf der README
            cat > .env << EOF
# WhisperX Configuration
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=tiny
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
DEV=false
FILTER_WARNING=true
DB_URL=sqlite:///records.db
EOF
            log "Standard .env Datei erstellt."
        fi
        
        warning "WICHTIG: Bitte bearbeite die .env Datei und setze deinen HuggingFace Token:"
        warning "HF_TOKEN=dein_echter_huggingface_token"
        warning ""
        warning "Du kannst das Skript mit 'nano .env' bearbeiten."
        read -p "Drücke Enter um fortzufahren, nachdem du die .env Datei bearbeitet hast..." -r
    else
        log ".env Datei gefunden ✓"
    fi
    
    cd ..
}

# Docker Container bauen und starten
build_and_start_container() {
    local repo_dir="transcript-summarization"
    cd "$repo_dir"
    
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    
    # Überprüfe welche docker-compose Datei verwendet werden soll
    local compose_file="docker-compose.yml"
    if [ ! -f "$compose_file" ]; then
        error "docker-compose.yml nicht gefunden!"
        exit 1
    fi
    
    log "Stoppe eventuell laufende Container..."
    docker compose down || docker-compose down || true
    
    log "Baue Docker Image (dies kann einige Minuten dauern)..."
    # Versuche zuerst 'docker compose', dann 'docker-compose'
    if docker compose version &> /dev/null; then
        docker compose build whisperx_cuda || docker compose build
    else
        docker-compose build whisperx_cuda || docker-compose build
    fi
    
    log "Starte Container im Hintergrund..."
    if docker compose version &> /dev/null; then
        docker compose up -d whisperx_cuda || docker compose up -d
    else
        docker-compose up -d whisperx_cuda || docker-compose up -d
    fi
    
    # Kurz warten bis Container gestartet ist
    sleep 5
    
    log "Container erfolgreich gestartet! ✓"
    
    # Container-Status anzeigen
    info "Container Status:"
    if docker compose version &> /dev/null; then
        docker compose ps
    else
        docker-compose ps
    fi
    
    cd ..
}

# Container-Logs anzeigen
show_logs() {
    local repo_dir="transcript-summarization"
    cd "$repo_dir"
    
    log "Zeige Container-Logs an (Ctrl+C zum Beenden)..."
    sleep 2
    
    # Finde den Container-Namen
    local container_name
    if docker ps --format "table {{.Names}}" | grep -q "whisperx"; then
        container_name=$(docker ps --format "{{.Names}}" | grep whisperx | head -1)
        log "Verwende Container: $container_name"
        docker logs -f "$container_name"
    else
        # Fallback: versuche häufige Namen
        for name in "whisperx-cuda" "whisperx-container" "whisperx_cuda" "transcript-summarization-whisperx_cuda-1"; do
            if docker ps --format "{{.Names}}" | grep -q "$name"; then
                log "Verwende Container: $name"
                docker logs -f "$name"
                break
            fi
        done
        
        # Wenn nichts gefunden, zeige alle Container
        warning "Kein WhisperX Container gefunden. Verfügbare Container:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    fi
    
    cd ..
}

# Service-Informationen anzeigen
show_service_info() {
    log "=== WhisperX Service Information ==="
    info "API Dokumentation: http://localhost:8000/docs"
    info "Health Check: http://localhost:8000/health"
    info "API Base URL: http://localhost:8000"
    info ""
    info "Nützliche Docker Befehle:"
    info "  - Logs anzeigen: docker logs -f <container_name>"
    info "  - Container stoppen: docker compose down"
    info "  - Container neustarten: docker compose restart"
    info "  - Container Status: docker compose ps"
    log "======================================="
}

# Hauptfunktion
main() {
    log "🚀 WhisperX FastAPI Container Setup gestartet"
    log "============================================="
    
    # Voraussetzungen prüfen
    check_prerequisites
    
    # Repository klonen/aktualisieren
    clone_or_update_repo
    
    # .env Datei setup
    setup_env_file
    
    # Container bauen und starten
    build_and_start_container
    
    # Service-Informationen anzeigen
    show_service_info
    
    log "✅ Setup erfolgreich abgeschlossen!"
    info ""
    info "Der WhisperX Service läuft jetzt auf Port 8000."
    info "Möchtest du die Container-Logs anzeigen? (y/N)"
    read -p "> " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_logs
    else
        log "Setup beendet. Du kannst die Logs jederzeit mit 'docker logs -f <container_name>' anzeigen."
    fi
}

# Fehlerbehandlung
trap 'error "Script wurde unterbrochen."; exit 1' INT TERM

# Script ausführen
main "$@"