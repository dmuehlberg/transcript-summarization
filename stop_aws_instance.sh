#!/bin/bash

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log-Funktionen
log() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# Standardwerte
REGIONS=("eu-central-1" "eu-west-1" "eu-north-1" "us-east-1" "us-west-2")
INSTANCE_NAME="whisperx-server"
STOP_MODE="stop"  # Standard: vollständiges Herunterfahren

# Parameter verarbeiten
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGIONS=("$2"); shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -m|--mode) STOP_MODE="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# Überprüfe Stop-Modus
if [[ "$STOP_MODE" != "stop" && "$STOP_MODE" != "hibernate" ]]; then
    error "Ungültiger Stop-Modus: $STOP_MODE. Erlaubte Werte: stop, hibernate"
    exit 1
fi

# Funktion zum Stoppen der Instanz in einer bestimmten Region
stop_instance_in_region() {
    local region=$1
    log "Suche nach Instanz '$INSTANCE_NAME' in Region: $region..."

    # Instanz-ID finden
    INSTANCE_ID=$(aws ec2 describe-instances --region $region \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running" \
        --query "Reservations[0].Instances[0].InstanceId" \
        --output text)

    if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
        warn "Keine laufende Instanz mit Namen '$INSTANCE_NAME' in Region $region gefunden."
        return 1
    fi

    log "Gefundene Instanz ID: $INSTANCE_ID"
    
    # Prüfe ob Hibernate unterstützt wird
    if [[ "$STOP_MODE" == "hibernate" ]]; then
        HIBERNATE_SUPPORTED=$(aws ec2 describe-instances --region $region \
            --instance-ids $INSTANCE_ID \
            --query "Reservations[0].Instances[0].HibernationOptions" \
            --output text)
        
        if [[ "$HIBERNATE_SUPPORTED" == "False" ]]; then
            warn "Diese Instanz unterstützt keinen Ruhezustand. Verwende stattdessen vollständiges Herunterfahren."
            STOP_MODE="stop"
        fi
    fi
    
    # Instanz stoppen
    if [[ "$STOP_MODE" == "hibernate" ]]; then
        log "Setze Instanz in den Ruhezustand..."
        aws ec2 stop-instances --region $region --instance-ids $INSTANCE_ID --hibernate
    else
        log "Fahre Instanz herunter..."
        aws ec2 stop-instances --region $region --instance-ids $INSTANCE_ID
    fi

    if [[ $? -eq 0 ]]; then
        if [[ "$STOP_MODE" == "hibernate" ]]; then
            log "Instanz wird in den Ruhezustand versetzt..."
        else
            log "Instanz wird heruntergefahren..."
        fi
        
        # Warten bis die Instanz gestoppt ist
        aws ec2 wait instance-stopped --region $region --instance-ids $INSTANCE_ID
        
        log "Instanz erfolgreich gestoppt!"
        info "📋 NÄCHSTE SCHRITTE:"
        info "1. Um die Instanz wieder zu starten, führen Sie ./start_aws_instance.sh aus"
        info "2. Die Instanz bleibt in der AWS-Konsole sichtbar, aber im gestoppten Zustand"
        if [[ "$STOP_MODE" == "hibernate" ]]; then
            info "3. Der Start wird schneller sein, da die Instanz im Ruhezustand war"
        fi
        return 0
    else
        error "Fehler beim Stoppen der Instanz."
        return 1
    fi
}

# Versuche die Instanz in verschiedenen Regionen zu stoppen
for region in "${REGIONS[@]}"; do
    if stop_instance_in_region "$region"; then
        exit 0
    fi
done

error "Konnte die Instanz in keiner der verfügbaren Regionen finden oder stoppen."
exit 1 