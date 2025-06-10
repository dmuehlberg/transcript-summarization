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
KEY_NAME="whisperx-key"
MAX_RETRIES=30  # Maximale Anzahl von Versuchen
RETRY_INTERVAL=10  # Wartezeit zwischen Versuchen in Sekunden

# Parameter verarbeiten
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGIONS=("$2"); shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -k|--key) KEY_NAME="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# Funktion zum Warten auf SSH-Verfügbarkeit
wait_for_ssh() {
    local ip=$1
    local key_file=$2
    local retries=0
    
    log "Warte auf SSH-Verfügbarkeit der Instanz..."
    while [[ $retries -lt $MAX_RETRIES ]]; do
        if ssh -i "$key_file" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ec2-user@$ip "echo 'SSH-Verbindung erfolgreich'" &>/dev/null; then
            log "SSH-Verbindung erfolgreich hergestellt!"
            return 0
        fi
        
        retries=$((retries + 1))
        if [[ $retries -lt $MAX_RETRIES ]]; then
            log "Warte noch ${RETRY_INTERVAL} Sekunden... (Versuch $retries/$MAX_RETRIES)"
            sleep $RETRY_INTERVAL
        fi
    done
    
    error "Timeout: SSH-Verbindung konnte nicht hergestellt werden."
    return 1
}

# Funktion zum Starten der Instanz in einer bestimmten Region
start_instance_in_region() {
    local region=$1
    log "Suche nach gestoppter Instanz '$INSTANCE_NAME' in Region: $region..."

    # Instanz-ID finden
    INSTANCE_ID=$(aws ec2 describe-instances --region $region \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=stopped" \
        --query "Reservations[0].Instances[0].InstanceId" \
        --output text)

    if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
        warn "Keine gestoppte Instanz mit Namen '$INSTANCE_NAME' in Region $region gefunden."
        return 1
    fi

    log "Gefundene Instanz ID: $INSTANCE_ID"
    
    # Prüfe ob die Instanz im Hibernate-Modus war
    HIBERNATE_STATUS=$(aws ec2 describe-instances --region $region \
        --instance-ids $INSTANCE_ID \
        --query "Reservations[0].Instances[0].StateTransitionReason" \
        --output text)
    
    if [[ "$HIBERNATE_STATUS" == *"Hibernation"* ]]; then
        log "Instanz war im Ruhezustand - Start wird schneller sein"
    else
        log "Instanz war vollständig heruntergefahren"
    fi
    
    # Instanz starten
    log "Starte Instanz..."
    aws ec2 start-instances --region $region --instance-ids $INSTANCE_ID

    if [[ $? -eq 0 ]]; then
        log "Instanz wird gestartet..."
        
        # Warten bis die Instanz läuft
        aws ec2 wait instance-running --region $region --instance-ids $INSTANCE_ID
        
        # Public IP-Adresse abrufen
        PUBLIC_IP=$(aws ec2 describe-instances --region $region \
            --instance-ids $INSTANCE_ID \
            --query "Reservations[0].Instances[0].PublicIpAddress" \
            --output text)

        log "Instanz erfolgreich gestartet!"
        log "Instance ID: $INSTANCE_ID"
        log "Public IP: $PUBLIC_IP"
        
        # Schlüsseldatei finden
        KEY_FILE="$KEY_NAME.pem"
        if [[ ! -f "$KEY_FILE" ]]; then
            KEY_FILE="/tmp/$KEY_NAME-$(ls -t /tmp/$KEY_NAME-* 2>/dev/null | head -n1 | grep -o '[0-9]*$')"
        fi
        
        if [[ -f "$KEY_FILE" ]]; then
            log "SSH-Zugriff: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP"
            
            # Warten auf SSH-Verfügbarkeit
            if wait_for_ssh "$PUBLIC_IP" "$KEY_FILE"; then
                # Docker Container starten
                log "Starte Docker Container..."
                ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "cd /home/ec2-user/transcript-summarization && docker-compose up -d whisperx_cuda"
                
                if [[ $? -eq 0 ]]; then
                    log "Docker Container erfolgreich gestartet!"
                else
                    error "Fehler beim Starten des Docker Containers."
                fi
            else
                error "Konnte keine SSH-Verbindung herstellen. Docker Container wurde nicht gestartet."
                return 1
            fi
        else
            warn "Schlüsseldatei nicht gefunden. Bitte überprüfen Sie den Pfad zur .pem-Datei."
        fi
        
        info "📋 NÄCHSTE SCHRITTE:"
        info "1. WhisperX API testen: http://$PUBLIC_IP:8000/docs"
        info "2. Health Check: curl http://$PUBLIC_IP:8000/health"
        return 0
    else
        error "Fehler beim Starten der Instanz."
        return 1
    fi
}

# Versuche die Instanz in verschiedenen Regionen zu starten
for region in "${REGIONS[@]}"; do
    if start_instance_in_region "$region"; then
        exit 0
    fi
done

error "Konnte die Instanz in keiner der verfügbaren Regionen finden oder starten."
exit 1 