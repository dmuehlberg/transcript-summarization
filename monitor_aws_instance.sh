#!/bin/bash
# Skript zum Überwachen der WhisperX-Installation auf einer AWS-Instanz

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
REGION="eu-central-1"
INSTANCE_NAME="whisperx-server"
KEY_FILE="whisperx-key.pem"
PUBLIC_IP=""

# Parameter verarbeiten
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGION="$2"; shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -k|--key) KEY_FILE="$2"; shift ;;
        -i|--ip) PUBLIC_IP="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# Prüfen, ob der Schlüssel existiert
if [[ ! -f "$KEY_FILE" ]]; then
    error "Schlüsseldatei '$KEY_FILE' nicht gefunden."
    exit 1
fi

# IP-Adresse abrufen, wenn nicht angegeben
if [[ -z "$PUBLIC_IP" ]]; then
    log "Suche nach EC2-Instanz mit Namen '$INSTANCE_NAME'..."
    
    PUBLIC_IP=$(aws ec2 describe-instances --region $REGION \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running" \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text)
    
    if [[ -z "$PUBLIC_IP" || "$PUBLIC_IP" == "None" ]]; then
        error "Keine laufende EC2-Instanz mit Namen '$INSTANCE_NAME' gefunden oder keine öffentliche IP-Adresse zugewiesen."
        exit 1
    fi
    
    log "EC2-Instanz gefunden mit IP: $PUBLIC_IP"
fi

# SSH-Verbindung testen
log "Teste SSH-Verbindung zu $PUBLIC_IP..."

# Warten auf SSH-Verfügbarkeit (max. 3 Minuten)
for i in {1..36}; do
    if ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=5 -i "$KEY_FILE" ubuntu@$PUBLIC_IP exit &>/dev/null; then
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
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@$PUBLIC_IP "sudo tail -f /var/log/user-data.log"

# Statusprüfung
log "Prüfe WhisperX-Dienststatus..."

# API-Erreichbarkeit testen
log "Teste WhisperX API-Erreichbarkeit..."
if curl -s -o /dev/null -w "%{http_code}" http://$PUBLIC_IP:8000/health 2>/dev/null | grep -q "200"; then
    log "✅ WhisperX API ist erreichbar unter http://$PUBLIC_IP:8000"
else
    warn "⚠️ WhisperX API ist noch nicht erreichbar."
    warn "Die Installation könnte noch laufen oder es gibt ein Problem."
    
    # Docker-Container Status prüfen
    log "Prüfe Docker-Container..."
    ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@$PUBLIC_IP "sudo docker ps -a"
    
    # Überprüfen, ob das Repository geklont wurde
    log "Prüfe Repository..."
    ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@$PUBLIC_IP "ls -la ~/transcript-summarization"
    
    # NVIDIA-Status überprüfen
    log "Prüfe NVIDIA-Status..."
    ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@$PUBLIC_IP "nvidia-smi || echo 'NVIDIA-Treiber nicht verfügbar'"
fi

log "Du kannst dich jederzeit mit folgendem Befehl verbinden:"
log "  ssh -i $KEY_FILE ubuntu@$PUBLIC_IP"
log "WhisperX API URL: http://$PUBLIC_IP:8000"
log "WhisperX API Dokumentation: http://$PUBLIC_IP:8000/docs"