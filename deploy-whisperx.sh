#!/bin/bash

# WhisperX Deployment Script - Erstellt neue Brev Instanzen
# Angepasst für Brev CLI v0.6.310 mit GPU-Auswahl

set -e

# ==================== KONFIGURATION ====================
# Diese Parameter kannst du anpassen:

# Speicherplatz in GB
STORAGE_SIZE="50"

# Git Repository für WhisperX
GIT_REPO="https://github.com/dmuehlberg/transcript-summarization.git"

# Region (optional, Standard ist us-east-1)
REGION="us-east-1"

# ==================== ENDE KONFIGURATION ====================

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}" >&2; }
warning(){ echo -e "${YELLOW}[WARNING] $1${NC}"; }
info()  { echo -e "${BLUE}[INFO] $1${NC}"; }

# Setup-Script als String (wird auf der Instanz ausgeführt)
SETUP_SCRIPT='#!/bin/bash

set -e

log() { echo "[$(date +"%H:%M:%S")] $1"; }

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
cat > /home/ubuntu/start-whisperx.sh << 'STARTSCRIPT'
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
STARTSCRIPT
chmod +x /home/ubuntu/start-whisperx.sh

log "✅ Setup abgeschlossen!"
log "📝 Siehe ~/start-whisperx.sh und README für Details"
'

# Liste unterstützter GPU-Typen
SUPPORTED_GPUS=("T4" "A10G" "A100" "L40S")

# GPU-Auswahl über Benutzerabfrage
choose_gpu_type() {
  echo
  log "Wähle einen GPU-Typ für die neue Instanz:"
  local i=1
  for gpu in "${SUPPORTED_GPUS[@]}"; do
    echo "  $i) $gpu"
    ((i++))
  done
  echo
  read -p "Nummer eingeben (1-${#SUPPORTED_GPUS[@]}): " gpu_choice
  CHOSEN_GPU="${SUPPORTED_GPUS[$((gpu_choice-1))]}"
  echo
  log "Du hast ausgewählt: $CHOSEN_GPU"
}

# Prüfe Voraussetzungen für Brev CLI
check_prerequisites() {
  log "Überprüfe Voraussetzungen..."
  if ! command -v brev &> /dev/null; then
    error "Brev CLI ist nicht installiert!"
    info "Installiere mit: curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/install.sh | bash"
    exit 1
  fi
  if ! brev ls &> /dev/null; then
    error "Nicht eingeloggt bei Brev CLI. Führe 'brev login' aus."
    exit 1
  fi
  log "Alle Voraussetzungen erfüllt ✓"
}

# Hauptmenü anzeigen
show_menu() {
  echo
  log "🚀 WhisperX Deployment Tool"
  echo "=================================="
  info "Brev CLI Version: $(brev --version 2>/dev/null || echo 'unbekannt')"
  echo
  info "1) Neue Instanz erstellen"
  info "2) Bestehende Instanzen anzeigen"
  info "3) Hostname für n8n abrufen"
  info "4) SSH zu Instanz"
  info "5) Instanz stoppen"
  info "6) Instanz löschen"
  info "7) Konfiguration anzeigen"
  info "8) Beenden"
  echo
  read -p "Wähle eine Option (1-8): " choice
}

# Erstelle neue Instanz mit GPU-Auswahl und Setup-Skript
create_new_instance() {
  choose_gpu_type
  local instance_name="whisperx-$(date +%Y%m%d-%H%M%S)"

  info "📦 Erstelle Instanz: $instance_name"
  info "   - GPU: $CHOSEN_GPU"
  info "   - Speicher: ${STORAGE_SIZE}GB"

  # Instanz erstellen
  if brev create "$instance_name" --gpu "$CHOSEN_GPU"; then
    log "✅ Instanz erfolgreich erstellt!"
    log "⏳ Warte bis RUNNING..."
    until brev ls | grep -q "${instance_name}.*RUNNING"; do sleep 5; done
    log "🚀 Starte Setup-Skript auf Instanz..."
    cat <(echo "$SETUP_SCRIPT") | brev shell "$instance_name" -- bash -s
    log "✅ Setup abgeschlossen auf Instanz"
  else
    error "Instanz-Erstellung fehlgeschlagen!"
    warning "Ungültiger GPU-Typ oder Quota-Probleme"
  fi
}

# Liste Instanzenlist_instances() {
  log "Alle Instanzen:"; brev ls
}

# Hostname abrufen
get_hostname_for_n8n() {
  log "Hostname für n8n abfragen..."
  brev ls --format table
  read -p "Instanzname: " inst
  hostname=$(brev describe "$inst" | grep -o '[a-zA-Z0-9.-]*\.brev\.sh')
  info "Hostname: $hostname"
}

# SSH zur Instanz
ssh_to_instance() {
  read -p "Instanzname: " inst
  log "SSH zu $inst..."; brev ssh "$inst"
}

# Stoppe Instanz
stop_instance() {
  read -p "Instanzname zum Stoppen: " inst
  log "Stoppe $inst..."; brev stop "$inst"
}

# Lösche Instanz
delete_instance() {
  read -p "Instanzname zum Löschen: " inst
  read -p "Bestätige mit DELETE: " conf
  [[ $conf == "DELETE" ]] && brev delete "$inst"
}

# Konfigurations-Info anzeigen
show_config_info() {
  info "Konfiguration:"
  info " STORAGE_SIZE=$STORAGE_SIZE"
  info " GIT_REPO=$GIT_REPO"
  info " REGION=$REGION"
}

# Show Instance Status
show_instance_status() {
  brev describe "$1"
}

# Main Loop
main() {
  check_prerequisites
  while true; do
    show_menu
    case $choice in
      1) create_new_instance ;; 2) list_instances ;; 3) get_hostname_for_n8n ;; 4) ssh_to_instance ;;
      5) stop_instance ;; 6) delete_instance ;; 7) show_config_info ;; 8) exit 0 ;;
      *) warning "Ungültige Auswahl." ;;
    esac
  done
}

trap 'error "Script wurde unterbrochen"; exit 1' INT TERM
main
