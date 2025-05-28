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

# Zeige Menü
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

# Erstelle neue Instanz mit GPU-Auswahl
create_new_instance() {
  choose_gpu_type
  local instance_name="whisperx-$(date +%Y%m%d-%H%M%S)"

  info "📦 Erstelle Instanz: $instance_name"
  info "   - GPU: $CHOSEN_GPU"
  info "   - Speicher: ${STORAGE_SIZE}GB"

  # Setup-Skript lokal vorbereiten
  local temp_dir="/tmp/brev-whisperx-$instance_name"
  mkdir -p "$temp_dir"
  echo "$SETUP_SCRIPT" | sed "s|GIT_REPO_PLACEHOLDER|$GIT_REPO|g" > "$temp_dir/setup.sh"
  chmod +x "$temp_dir/setup.sh"

  # Instanz erstellen
  if brev create "$instance_name" --gpu "$CHOSEN_GPU"; then
    log "✅ Instanz erfolgreich erstellt!"
    log "⏳ Warte bis Instanz startet..."
    # Warten bis der Status RUNNING angezeigt wird
    until brev ls | grep -q "${instance_name}.*RUNNING"; do
      sleep 5
    done
    log "🚀 Führe Setup-Skript auf Instanz aus..."
    cat "$temp_dir/setup.sh" | brev shell "$instance_name" -- bash -s
    rm -rf "$temp_dir"

    # Status anzeigen
    show_instance_status "$instance_name"

    # Optional SSH-Verbindung
    read -p "SSH-Verbindung zur Instanz? (y/N): " -n1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] && ssh_to_instance "$instance_name"
  else
    error "Instanz-Erstellung fehlgeschlagen!"
    warning "Ungültiger GPU-Typ oder Quota-Probleme"
    rm -rf "$temp_dir"
  fi
}GB"

  # Setup-Script vorbereiten
  local temp_dir="/tmp/brev-whisperx-$instance_name"
  mkdir -p "$temp_dir"
  echo "$SETUP_SCRIPT" | sed "s|GIT_REPO_PLACEHOLDER|$GIT_REPO|g" > "$temp_dir/setup.sh"
  chmod +x "$temp_dir/setup.sh"

  # Instanz erstellen
  if brev create "$instance_name" \
      --gpu "$CHOSEN_GPU" \
      --setup-script "$temp_dir/setup.sh" 2>&1; then
    log "✅ Instanz erfolgreich erstellt!"
    rm -rf "$temp_dir"
    log "⏳ Warte auf Instanz-Start..."
    sleep 30
    show_instance_status "$instance_name"
    read -p "SSH-Verbindung zur Instanz? (y/N): " -n1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] && ssh_to_instance "$instance_name"
  else
    error "Instanz-Erstellung fehlgeschlagen!"
    warning "Ungültiger GPU-Typ oder Quota-Probleme"
    rm -rf "$temp_dir"
  fi
}

# Liste Instanzen
list_instances() {
  log "Alle Instanzen:"; brev ls
}

# Hostname abrufen
get_hostname_for_n8n() {
  brief=$(brev ls --format table)
  echo "$brief"
  read -p "Instanzname: " inst
  hostname=$(brev describe "$inst" | grep -o '[a-zA-Z0-9.-]*\.brev\.sh')
  info "Hostname: $hostname"
}

# SSH in Instanz
ssh_to_instance() {
  read -p "Instanzname für SSH: " inst
  log "SSH zu $inst..."; brev ssh "$inst"
}

# Instanz stoppen
stop_instance() {
  read -p "Instanzname zum Stoppen: " inst
  log "Stoppe $inst..."; brev stop "$inst"
}

# Instanz löschen
delete_instance() {
  read -p "Instanzname zum Löschen: " inst
  read -p "Bestätige DELETE: " conf
  [[ $conf == "DELETE" ]] && brev delete "$inst"
}

# Konfiguration anzeigen
show_config_info() {
  info "Konfiguration:"
  info "  STORAGE_SIZE=$STORAGE_SIZE"
  info "  GIT_REPO=$GIT_REPO"
  info "  REGION=$REGION"
}

# Status anzeigen
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

# Start
main
