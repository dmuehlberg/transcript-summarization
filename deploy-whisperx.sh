#!/bin/bash

# WhisperX Deployment mit deinem existierenden Launchable
# Launchable ID: env-2xSQrQlnEqxgNMeSl10Vpqel29v

set -e

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

# Dein Launchable
LAUNCHABLE_ID="env-2xSQrQlnEqxgNMeSl10Vpqel29v"
LAUNCHABLE_URL="https://brev.nvidia.com/launchable/deploy?launchableID=$LAUNCHABLE_ID"

check_prerequisites() {
    log "Überprüfe Voraussetzungen..."
    
    if ! command -v brev &> /dev/null; then
        error "Brev CLI ist nicht installiert!"
        info "Installiere mit: curl -o- https://raw.githubusercontent.com/brevdev/brev-cli/main/install.sh | bash"
        exit 1
    fi
    
    if ! brev whoami &> /dev/null; then
        error "Du bist nicht bei Brev eingeloggt!"
        info "Logge dich ein mit: brev login"
        exit 1
    fi
    
    log "Alle Voraussetzungen erfüllt ✓"
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

show_menu() {
    echo
    log "🚀 WhisperX Launchable Deployment"
    echo "=================================="
    info "Launchable ID: $LAUNCHABLE_ID"
    echo
    info "1. Neue Instanz erstellen"
    info "2. Bestehende Instanzen anzeigen"
    info "3. Hostname für n8n abrufen"
    info "4. SSH zu Instanz"
    info "5. Instanz stoppen"
    info "6. Instanz löschen"
    info "7. Beenden"
    echo
    read -p "Wähle eine Option (1-7): " choice
}

launch_from_launchable() {
    log "Starte neue Instanz aus deinem Launchable..."
    
    local instance_name="whisperx-$(date +%Y%m%d-%H%M%S)"
    
    info "Instanz-Name: $instance_name"
    info "Launchable-ID: $LAUNCHABLE_ID"
    
    # Instanz erstellen
    if brev launch $LAUNCHABLE_ID --name $instance_name 2>/dev/null || \
       brev create $instance_name --template $LAUNCHABLE_ID 2>/dev/null; then
        log "✅ Instanz erfolgreich erstellt!"
        
        sleep 10
        show_instance_status $instance_name
        
        read -p "Möchtest du dich zur Instanz verbinden? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ssh_to_instance $instance_name
        fi
    else
        warning "Automatische Erstellung fehlgeschlagen."
        info "🌐 Öffne diesen Link in deinem Browser:"
        info "$LAUNCHABLE_URL"
        info "Verwende diesen Namen: $instance_name"
    fi
}

show_instance_status() {
    local instance_name=$1
    
    log "📊 Instanz-Status: $instance_name"
    echo "=================================="
    
    if brev describe $instance_name 2>/dev/null; then
        echo
        info "✅ Instanz läuft!"
        
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
    log "WhisperX Launchable Deployment Tool"
    
    check_prerequisites
    
    while true; do
        show_menu
        
        case $choice in
            1) launch_from_launchable ;;
            2) list_instances ;;
            3) get_hostname_for_n8n ;;
            4) ssh_to_instance ;;
            5) stop_instance ;;
            6) delete_instance ;;
            7) log "Auf Wiedersehen! 👋"; exit 0 ;;
            *) warning "Ungültige Auswahl. Bitte wähle 1-7." ;;
        esac
        
        echo
        read -p "Drücke Enter um fortzufahren..." -r
    done
}

trap 'error "Script wurde unterbrochen"; exit 1' INT TERM
main "$@"