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
DEFAULT_REGION="eu-central-1"
DEFAULT_NAME="whisperx-server"
SSH_KEY="whisperx-key.pem"

# Hilfefunktion
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Dieses Skript überwacht die Installation von WhisperX auf einer EC2-Instanz."
    echo ""
    echo "Optionen:"
    echo "  -h, --help                      Zeigt diese Hilfe an"
    echo "  -n, --name NAME                 Name der EC2-Instanz (default: $DEFAULT_NAME)"
    echo "  -r, --region REGION             AWS-Region (default: $DEFAULT_REGION)"
    echo "  -k, --key KEY                   Pfad zum SSH-Schlüssel (default: $SSH_KEY)"
    echo "  -i, --ip IP                     IP-Adresse der Instanz (optional)"
    exit 0
}

# Parameter verarbeiten
INSTANCE_NAME=$DEFAULT_NAME
REGION=$DEFAULT_REGION
IP_ADDRESS=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) show_help ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -r|--region) REGION="$2"; shift ;;
        -k|--key) SSH_KEY="$2"; shift ;;
        -i|--ip) IP_ADDRESS="$2"; shift ;;
        *) error "Unbekannte Option: $1"; show_help ;;
    esac
    shift
done

# Prüfen ob AWS CLI installiert ist
if ! command -v aws &> /dev/null; then
    error "AWS CLI ist nicht installiert. Bitte installiere es zuerst."
    error "Installationsanleitung: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Prüfen ob SSH-Schlüssel existiert
if [[ ! -f "$SSH_KEY" ]]; then
    error "SSH-Schlüssel '$SSH_KEY' nicht gefunden."
    exit 1
fi

# IP-Adresse abrufen, wenn nicht angegeben
if [[ -z "$IP_ADDRESS" ]]; then
    log "Suche nach EC2-Instanz mit Namen '$INSTANCE_NAME'..."
    
    # Instanz-Details anhand des Namens abrufen
    IP_ADDRESS=$(aws ec2 describe-instances --region $REGION \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running" \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text)
    
    if [[ -z "$IP_ADDRESS" || "$IP_ADDRESS" == "None" ]]; then
        error "Keine laufende EC2-Instanz mit Namen '$INSTANCE_NAME' gefunden oder Instanz hat keine öffentliche IP-Adresse."
        exit 1
    fi
    
    log "EC2-Instanz gefunden mit IP: $IP_ADDRESS"
fi

# SSH-Verbindung testen
log "Teste SSH-Verbindung zu $IP_ADDRESS..."

# Warte auf SSH-Verfügbarkeit (max. 3 Minuten)
for i in {1..36}; do
    if ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=5 -i "$SSH_KEY" ubuntu@$IP_ADDRESS exit &>/dev/null; then
        log "SSH-Verbindung hergestellt."
        break
    fi
    
    if [[ $i -eq 36 ]]; then
        warn "Konnte keine SSH-Verbindung herstellen nach 3 Minuten."
        warn "Die Instanz startet möglicherweise noch. Bitte versuche es später erneut."
        exit 1
    fi
    
    echo -n "."
    sleep 5
done

# Installation überwachen
log "Überwache WhisperX-Installation..."

# Mit SSH verbinden und Installation überwachen
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ubuntu@$IP_ADDRESS "sudo tail -f /var/log/user-data.log"

# Statusprüfung
status_check() {
    log "Prüfe WhisperX-Dienststatus..."
    
    # Container-Status überprüfen
    container_status=$(ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ubuntu@$IP_ADDRESS "sudo docker ps -a --format '{{.Names}}: {{.Status}}' | grep -i whisperx" 2>/dev/null)
    
    if [[ -z "$container_status" ]]; then
        warn "Keine WhisperX-Container gefunden."
    else
        log "Container-Status:"
        echo "$container_status"
    fi
    
    # GPU-Status überprüfen
    log "GPU-Status:"
    gpu_status=$(ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ubuntu@$IP_ADDRESS "nvidia-smi --query-gpu=gpu_name,memory.used,memory.total,temperature.gpu --format=csv,noheader" 2>/dev/null)
    
    if [[ -z "$gpu_status" ]]; then
        warn "Konnte GPU-Status nicht abrufen."
    else
        echo "$gpu_status"
    fi
    
    # API-Erreichbarkeit testen
    log "Teste WhisperX API-Erreichbarkeit..."
    api_status=$(curl -s -o /dev/null -w "%{http_code}" http://$IP_ADDRESS:8000/health 2>/dev/null)
    
    if [[ "$api_status" == "200" ]]; then
        log "WhisperX API ist erreichbar unter http://$IP_ADDRESS:8000"
    else
        warn "WhisperX API ist noch nicht erreichbar (Status: $api_status)"
        warn "Die Installation könnte noch laufen oder es gibt ein Problem."
    fi
}

# Status nach der Installation prüfen
status_check

log "Monitoring abgeschlossen."
log "Du kannst dich jederzeit mit folgendem Befehl verbinden:"
log "  ssh -i $SSH_KEY ubuntu@$IP_ADDRESS"
log "WhisperX API URL: http://$IP_ADDRESS:8000"
log "WhisperX API Dokumentation: http://$IP_ADDRESS:8000/docs"