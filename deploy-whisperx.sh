#!/bin/bash

# WhisperX Deployment Script - Erstellt neue Brev Instanzen
# Angepasst für Brev CLI v0.6.310 ohne Launchable Support

set -e

# ==================== KONFIGURATION ====================
# Diese Parameter kannst du anpassen:

# Instanz-Typ (GPU Instanzen)
# - g4dn.xlarge: ~$0.50/h, T4 GPU, 16GB VRAM, 4 vCPUs, 16GB RAM
# - g4dn.2xlarge: ~$0.75/h, T4 GPU, 16GB VRAM, 8 vCPUs, 32GB RAM
# - g4dn.4xlarge: ~$1.20/h, T4 GPU, 16GB VRAM, 16 vCPUs, 64GB RAM
# - g5.xlarge: ~$1.00/h, A10G GPU, 24GB VRAM, 4 vCPUs, 16GB RAM
# - p3.2xlarge: ~$3.00/h, V100 GPU, 16GB VRAM, 8 vCPUs, 61GB RAM
INSTANCE_TYPE="g4dn.xlarge"

# Speicherplatz in GB
STORAGE_SIZE="50"

# Git Repository für WhisperX
GIT_REPO="https://github.com/dmuehlberg/transcript-summarization.git"

# Region (optional, Standard ist us-east-1)
REGION="us-east-1"

# Base Image (Ubuntu 22.04 mit CUDA)
BASE_IMAGE="ubuntu:22.04"

# ==================== ENDE KONFIGURATION ====================

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}" >&2; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }

# Setup-Script als String (wird auf der Instanz ausgeführt)
SETUP_SCRIPT='#!/bin/bash

set -e

log() { echo "[$(date +\"%H:%M:%S\")] $1"; }

log "🚀 Starte WhisperX Setup..."

# System Updates
log "Aktualisiere System..."
sudo apt-get update -y
sudo apt-get install -y git curl wget jq

# Docker installieren
if ! command -v docker &> /dev/null; then
    log "Installiere Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Docker Compose installieren
if ! command -v docker-compose &> /dev/null; then
    log "Installiere Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# NVIDIA Container Toolkit
log "Installiere NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Repository klonen
log "Klone WhisperX Repository..."
cd /home/ubuntu
if [ ! -d "transcript-summarization" ]; then
    git clone GIT_REPO_PLACEHOLDER
fi
cd transcript-summarization

# .env Datei erstellen
log "Erstelle .env Konfiguration..."
cat > .env << EOF
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
DEV=false
FILTER_WARNING=true
DB_URL=sqlite:///records.db
EOF

# Docker Build starten
log "Starte Docker Build..."
export DOCKER_CLIENT_TIMEOUT=120
export COMPOSE_HTTP_TIMEOUT=120

nohup bash -c "docker compose build && echo \"✅ Docker Build abgeschlossen - $(date)\" >> /home/ubuntu/build.log" > /home/ubuntu/docker-build.log 2>&1 &

# Start-Script erstellen
cat > /home/ubuntu/start-whisperx.sh << "STARTEOF"
#!/bin/bash
cd /home/ubuntu/transcript-summarization

if docker images | grep -q transcript-summarization; then
    echo "✅ Docker Image gefunden, starte Container..."
    docker compose up -d
    echo "🚀 WhisperX läuft auf Port 8000!"
    echo "📖 API Docs: http://localhost:8000/docs"
    docker compose logs -f
else
    echo "⏳ Docker Build läuft noch. Status prüfen:"
    tail -f /home/ubuntu/docker-build.log
fi
STARTEOF

chmod +x /home/ubuntu/start-whisperx.sh

# README erstellen
cat > /home/ubuntu/README-WHISPERX.md << "READMEEOF"
# 🚀 WhisperX FastAPI Setup

## Schnellstart:

1. **HuggingFace Token setzen:**
   ```bash
   cd transcript-summarization
   nano .env  # HF_TOKEN=dein_token_hier
   ```

2. **Container starten:**
   ```bash
   ~/start-whisperx.sh
   ```

3. **API verwenden:**
   - Dokumentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## GPU Status prüfen:
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```
READMEEOF

log "✅ Setup abgeschlossen!"
log "📝 Siehe ~/README-WHISPERX.md für Anweisungen"
'

check_prerequisites() {
    log "Überprüfe Voraussetzungen..."
    
    if ! command -v brev &> /dev/null; then
        error "Brev CLI ist nicht installiert!"
        info "Installiere mit: curl -o- https://raw.githubusercontent.com/brevdev/brev-cli/main/install.sh | bash"
        exit 1
    fi
    
    # Login Check
    if ! brev ls &> /dev/null; then
        error "Du bist nicht bei Brev eingeloggt!"
        info "Führe aus: brev login"
        exit 1
    fi
    
    log "Alle Voraussetzungen erfüllt ✓"
    
    # Zeige aktuelle Konfiguration
    echo
    info "📋 Aktuelle Konfiguration:"
    info "  - Instanz-Typ: $INSTANCE_TYPE"
    info "  - Speicher: ${STORAGE_SIZE}GB"
    info "  - Region: $REGION"
    info "  - Git Repo: $GIT_REPO"
    echo
}

create_new_instance() {
    log "Erstelle neue WhisperX Instanz..."
    
    local instance_name="whisperx-$(date +%Y%m%d-%H%M%S)"
    
    info "📦 Erstelle Instanz: $instance_name"
    info "  - Typ: $INSTANCE_TYPE"
    info "  - Speicher: ${STORAGE_SIZE}GB"
    
    # Temporäres Verzeichnis für Setup
    local temp_dir="/tmp/brev-whisperx-$instance_name"
    mkdir -p "$temp_dir"
    
    # Setup-Script mit Git Repo ersetzen und speichern
    echo "$SETUP_SCRIPT" | sed "s|GIT_REPO_PLACEHOLDER|$GIT_REPO|g" > "$temp_dir/setup.sh"
    chmod +x "$temp_dir/setup.sh"
    
    # Versuche Instanz zu erstellen
    if brev create "$instance_name" \
        --instance-type "$INSTANCE_TYPE" \
        --storage "${STORAGE_SIZE}Gi" \
        --setup-script "$temp_dir/setup.sh" 2>&1; then
        
        log "✅ Instanz erfolgreich erstellt!"
        
        # Aufräumen
        rm -rf "$temp_dir"
        
        # Warte bis Instanz bereit ist
        log "⏳ Warte auf Instanz-Start (kann 2-3 Minuten dauern)..."
        sleep 30
        
        # Status zeigen
        show_instance_status "$instance_name"
        
        echo
        read -p "Möchtest du dich zur Instanz verbinden? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ssh_to_instance "$instance_name"
        fi
        
    else
        error "Instanz-Erstellung fehlgeschlagen!"
        
        # Debug-Infos
        warning "Mögliche Gründe:"
        warning "- Ungültiger Instanz-Typ: $INSTANCE_TYPE"
        warning "- Nicht genügend Quota in Region: $REGION"
        warning "- Syntaxfehler im Befehl"
        
        echo
        info "💡 Verfügbare Instanz-Typen anzeigen:"
        info "brev instance-types"
        
        echo
        info "💡 Manuelle Erstellung versuchen:"
        info "brev create $instance_name --instance-type g4dn.xlarge"
        
        # Aufräumen
        rm -rf "$temp_dir"
        
        return 1
    fi
}

get_instance_hostname() {
    local instance_name=$1
    local max_attempts=12
    local attempt=1
    
    log "🔍 Ermittle Hostname für: $instance_name"
    
    while [ $attempt -le $max_attempts ]; do
        local hostname=""
        
        # Hostname aus brev describe ermitteln
        hostname=$(brev describe $instance_name 2>/dev/null | grep -E "(Host|URL|Endpoint)" | head -1 | egrep -o '[a-zA-Z0-9.-]+\.brev\.sh' | head -1)
        
        # Fallback: SSH dry-run
        if [ -z "$hostname" ]; then
            hostname=$(brev ssh $instance_name --dry-run 2>/dev/null | grep -o '[a-zA-Z0-9.-]*\.brev\.sh' | head -1)
        fi
        
        if [ -n "$hostname" ] && [[ "$hostname" =~ \.brev\.sh$ ]]; then
            echo "$hostname"
            return 0
        fi
        
        warning "Versuch $attempt/$max_attempts: Hostname noch nicht verfügbar, warte 10s..."
        sleep 10
        ((attempt++))
    done
    
    error "Hostname konnte nicht ermittelt werden"
    return 1
}

show_instance_status() {
    local instance_name=$1
    
    log "📊 Instanz-Status: $instance_name"
    echo "=================================="
    
    if brev describe $instance_name 2>/dev/null; then
        echo
        info "✅ Instanz läuft!"
        
        # GPU Info
        info "🎮 GPU: $INSTANCE_TYPE"
        
        # Hostname ermitteln
        if hostname=$(get_instance_hostname $instance_name); then
            echo
            log "🌐 HOSTNAME FÜR N8N:"
            echo "=================================="
            info "Hostname: $hostname"
            info "API Base URL: https://$hostname:8000"
            info "API Docs: https://$hostname:8000/docs"
            info "Health Check: https://$hostname:8000/health"
            echo "=================================="
            
            # Dateien speichern
            echo "$hostname" > "/tmp/whisperx-hostname-$instance_name.txt"
            echo "https://$hostname:8000" > "/tmp/whisperx-api-url-$instance_name.txt"
            
            info "💾 Hostname gespeichert in: /tmp/whisperx-hostname-$instance_name.txt"
            
            # Clipboard
            if command -v pbcopy &> /dev/null; then
                echo "https://$hostname:8000" | pbcopy
                info "📋 API URL in Zwischenablage kopiert!"
            fi
        else
            warning "Hostname noch nicht verfügbar. Instanz startet noch..."
        fi
    else
        warning "Instanz nicht gefunden oder noch nicht bereit"
    fi
    
    echo
    info "📱 Nach SSH-Verbindung auf der Instanz:"
    info "  ~/start-whisperx.sh - WhisperX Container starten"
    info "  nano transcript-summarization/.env - HF Token setzen"
    info "  tail -f ~/docker-build.log - Setup-Status prüfen"
    info "  nvidia-smi - GPU Status prüfen"
}

show_config_info() {
    log "⚙️  Konfiguration anzeigen/ändern"
    echo "=================================="
    info "Aktuelle Einstellungen:"
    info "  - Instanz-Typ: $INSTANCE_TYPE"
    info "  - Speicher: ${STORAGE_SIZE}GB"
    info "  - Region: $REGION"
    info "  - Git Repo: $GIT_REPO"
    echo
    info "📝 Zum Ändern, editiere die Variablen am Anfang dieses Scripts:"
    info "  nano $0"
    echo
    info "💰 Kosten-Übersicht GPU-Instanzen:"
    info "  - g4dn.xlarge: ~\$0.50/h (T4, 16GB VRAM)"
    info "  - g4dn.2xlarge: ~\$0.75/h (T4, 32GB RAM)"
    info "  - g5.xlarge: ~\$1.00/h (A10G, 24GB VRAM)"
    info "  - p3.2xlarge: ~\$3.00/h (V100, 16GB VRAM)"
}

show_menu() {
    echo
    log "🚀 WhisperX Deployment Tool"
    echo "=================================="
    info "Brev CLI Version: $(brev --version 2>/dev/null || echo 'unbekannt')"
    echo
    info "1. Neue Instanz erstellen"
    info "2. Bestehende Instanzen anzeigen"
    info "3. Hostname für n8n abrufen"
    info "4. SSH zu Instanz"
    info "5. Instanz stoppen"
    info "6. Instanz löschen"
    info "7. Konfiguration anzeigen"
    info "8. Beenden"
    echo
    read -p "Wähle eine Option (1-8): " choice
}

get_hostname_for_n8n() {
    log "🔍 Hostname für n8n abrufen"
    brev ls --format table
    echo
    read -p "Für welche Instanz soll der Hostname abgerufen werden? " instance_name
    
    if [ -n "$instance_name" ]; then
        if hostname=$(get_instance_hostname $instance_name); then
            echo
            log "🎯 N8N INTEGRATION INFO:"
            echo "========================================="
            info "Instanz: $instance_name"
            info "Hostname: $hostname"
            info "API Base URL: https://$hostname:8000"
            info "FastAPI Docs: https://$hostname:8000/docs"
            info "Health Endpoint: https://$hostname:8000/health"
            echo "========================================="
            
            # Clipboard
            if command -v pbcopy &> /dev/null; then
                echo "https://$hostname:8000" | pbcopy
                info "📋 API Base URL in Zwischenablage kopiert!"
            fi
            
            echo
            warning "🔧 N8N SETUP SCHRITTE:"
            warning "1. HTTP Request Node in n8n erstellen"
            warning "2. Base URL: https://$hostname:8000"
            warning "3. Endpoint: /transcribe"
            warning "4. Method: POST"
            warning "5. Content-Type: multipart/form-data"
            
        else
            error "Hostname konnte nicht ermittelt werden!"
        fi
    fi
}

list_instances() {
    log "Alle deine Instanzen:"
    brev ls
}

ssh_to_instance() {
    local instance_name=$1
    
    if [ -z "$instance_name" ]; then
        log "Verfügbare Instanzen:"
        brev ls --format table
        echo
        read -p "Zu welcher Instanz möchtest du dich verbinden? " instance_name
    fi
    
    if [ -n "$instance_name" ]; then
        log "Verbinde zu: $instance_name"
        brev ssh $instance_name
    fi
}

stop_instance() {
    log "Verfügbare Instanzen:"
    brev ls --format table
    echo
    read -p "Welche Instanz möchtest du stoppen? " instance_name
    
    if [ -n "$instance_name" ]; then
        log "Stoppe Instanz: $instance_name"
        brev stop $instance_name
        log "✅ Instanz gestoppt"
    fi
}

delete_instance() {
    log "Verfügbare Instanzen:"
    brev ls --format table
    echo
    warning "⚠️ ACHTUNG: Löschen ist permanent!"
    read -p "Welche Instanz möchtest du LÖSCHEN? " instance_name
    
    if [ -n "$instance_name" ]; then
        read -p "Bist du sicher? Gib 'DELETE' ein: " confirmation
        if [ "$confirmation" = "DELETE" ]; then
            log "Lösche Instanz: $instance_name"
            brev delete $instance_name
            log "✅ Instanz gelöscht"
        else
            info "Löschung abgebrochen"
        fi
    fi
}

main() {
    log "WhisperX Deployment Tool"
    
    check_prerequisites
    
    while true; do
        show_menu
        
        case $choice in
            1) create_new_instance ;;
            2) list_instances ;;
            3) get_hostname_for_n8n ;;
            4) ssh_to_instance ;;
            5) stop_instance ;;
            6) delete_instance ;;
            7) show_config_info ;;
            8) log "Auf Wiedersehen! 👋"; exit 0 ;;
            *) warning "Ungültige Auswahl. Bitte wähle 1-8." ;;
        esac
        
        echo
        read -p "Drücke Enter um fortzufahren..." -r
    done
}

trap 'error "Script wurde unterbrochen"; exit 1' INT TERM
main "$@"