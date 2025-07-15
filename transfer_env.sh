#!/bin/bash

# Skript zum Übertragen der .env-Datei mit HF_TOKEN auf bestehende AWS-Instanzen
# Verwendung: ./transfer_env.sh [REGION] [INSTANCE_NAME]

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
REGION=${1:-"eu-central-1"}
INSTANCE_NAME=${2:-"whisperx-server"}
KEY_FILE="whisperx-key.pem"

# Prüfen ob .env-Datei existiert
if [[ ! -f ".env" ]]; then
    error ".env-Datei nicht gefunden!"
    error "Bitte erstellen Sie eine .env-Datei mit HF_TOKEN=your_token"
    exit 1
fi

# Prüfen ob HF_TOKEN in .env definiert ist
if ! grep -q "^HF_TOKEN=" .env; then
    warn "HF_TOKEN nicht in .env-Datei gefunden!"
    warn "Bitte fügen Sie HF_TOKEN=your_token zur .env-Datei hinzu"
fi

# Prüfen ob Schlüsseldatei existiert
if [[ ! -f "$KEY_FILE" ]]; then
    error "Schlüsseldatei '$KEY_FILE' nicht gefunden!"
    exit 1
fi

log "Suche nach WhisperX-Instanz in Region $REGION..."

# Instanz-ID und IP-Adresse abrufen
INSTANCE_ID=$(aws ec2 describe-instances --region $REGION \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text)

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
    error "Keine laufende WhisperX-Instanz mit Namen '$INSTANCE_NAME' in Region $REGION gefunden."
    exit 1
fi

PUBLIC_IP=$(aws ec2 describe-instances --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

log "Gefunden: Instance $INSTANCE_ID mit IP $PUBLIC_IP"

# SSH-Verbindung testen
log "Teste SSH-Verbindung..."
if ! ssh -i "$KEY_FILE" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP 'echo "SSH-Verbindung OK"' 2>/dev/null; then
    error "SSH-Verbindung zur Instanz fehlgeschlagen!"
    exit 1
fi

# Prüfen ob Repository-Verzeichnis existiert
log "Prüfe Repository-Verzeichnis..."
if ! ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP '[ -d "/home/ec2-user/transcript-summarization" ]' 2>/dev/null; then
    error "Repository-Verzeichnis nicht gefunden!"
    error "Bitte warten Sie, bis die Installation abgeschlossen ist."
    exit 1
fi

# .env-Datei übertragen
log "Übertrage .env-Datei..."
if scp -i "$KEY_FILE" -o StrictHostKeyChecking=no .env ec2-user@$PUBLIC_IP:/home/ec2-user/transcript-summarization/ 2>/dev/null; then
    log "✅ .env-Datei erfolgreich übertragen"
    
    # Container Status prüfen und neu starten
    log "Prüfe Container-Status..."
    CONTAINER_STATUS=$(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
        cd /home/ec2-user/transcript-summarization
        docker-compose ps whisperx_cuda --format json 2>/dev/null | grep -o '\"State\":\"[^\"]*\"' | cut -d'\"' -f4 || echo 'not_found'
    " 2>/dev/null)
    
    if [[ "$CONTAINER_STATUS" == "Up" ]]; then
        log "Container läuft, starte neu mit HF_TOKEN..."
        ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
            cd /home/ec2-user/transcript-summarization
            docker-compose restart whisperx_cuda
            echo 'Container neu gestartet'
        " 2>/dev/null
        log "✅ Container mit HF_TOKEN neu gestartet"
    elif [[ "$CONTAINER_STATUS" == "not_found" ]]; then
        warn "Container nicht gefunden. Möglicherweise läuft die Installation noch."
        info "Sie können den Container später manuell starten:"
        info "ssh -i $KEY_FILE ec2-user@$PUBLIC_IP"
        info "cd transcript-summarization && docker-compose up -d whisperx_cuda"
    else
        log "Container Status: $CONTAINER_STATUS"
        log "Container wird mit HF_TOKEN gestartet..."
        ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
            cd /home/ec2-user/transcript-summarization
            docker-compose up -d whisperx_cuda
            echo 'Container gestartet'
        " 2>/dev/null
        log "✅ Container mit HF_TOKEN gestartet"
    fi
    
    # Verifizierung
    log "Verifiziere HF_TOKEN..."
    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
        cd /home/ec2-user/transcript-summarization
        if grep -q '^HF_TOKEN=' .env; then
            echo '✅ HF_TOKEN in .env gefunden'
            echo 'Token (erste 10 Zeichen): ' \$(grep '^HF_TOKEN=' .env | cut -d'=' -f2 | cut -c1-10)'...'
        else
            echo '❌ HF_TOKEN nicht in .env gefunden'
        fi
    " 2>/dev/null
    
    log ""
    info "🎉 HF_TOKEN erfolgreich übertragen!"
    info "API URL: http://$PUBLIC_IP:8000/docs"
    info "Health Check: curl http://$PUBLIC_IP:8000/health"
    
else
    error "❌ Fehler beim Übertragen der .env-Datei!"
    exit 1
fi 