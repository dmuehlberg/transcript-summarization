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

# Hilfefunktion
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Dieses Skript bereinigt alle AWS-Ressourcen, die mit WhisperX zusammenhängen."
    echo ""
    echo "Optionen:"
    echo "  -h, --help                      Zeigt diese Hilfe an"
    echo "  -n, --name NAME                 Name der EC2-Instanz (default: $DEFAULT_NAME)"
    echo "  -r, --region REGION             AWS-Region (default: $DEFAULT_REGION)"
    echo "  -f, --force                     Keine Bestätigung abfragen"
    exit 0
}

# Parameter verarbeiten
INSTANCE_NAME=$DEFAULT_NAME
REGION=$DEFAULT_REGION
FORCE=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) show_help ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -r|--region) REGION="$2"; shift ;;
        -f|--force) FORCE=true ;;
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

# Bestätigung abfragen, wenn nicht --force
if [ "$FORCE" != true ]; then
    echo ""
    warn "ACHTUNG: Dieses Skript wird alle AWS-Ressourcen löschen, die mit WhisperX zusammenhängen:"
    echo "- EC2-Instanz(en) mit Namen: $INSTANCE_NAME"
    echo "- Sicherheitsgruppe: whisperx-sg"
    echo "- Schlüsselpaar: whisperx-key"
    echo ""
    read -p "Möchtest du fortfahren? (j/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Jj]$ ]]; then
        log "Abgebrochen."
        exit 0
    fi
fi

# 1. EC2-Instanz(en) terminieren
log "Suche nach EC2-Instanz(en) mit Namen '$INSTANCE_NAME'..."

instance_ids=$(aws ec2 describe-instances --region $REGION \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped,pending,stopping" \
    --query "Reservations[*].Instances[*].InstanceId" \
    --output text)

if [[ -z "$instance_ids" || "$instance_ids" == "None" ]]; then
    warn "Keine EC2-Instanz(en) mit Namen '$INSTANCE_NAME' gefunden."
else
    log "Gefundene EC2-Instanz(en): $instance_ids"
    log "Terminiere EC2-Instanz(en)..."
    
    aws ec2 terminate-instances --region $REGION --instance-ids $instance_ids > /dev/null
    
    if [[ $? -ne 0 ]]; then
        error "Fehler beim Terminieren der EC2-Instanz(en)."
    else
        log "EC2-Instanz(en) werden terminiert. Dies kann einige Minuten dauern."
        log "Warte auf Beendigung der Instanz(en)..."
        aws ec2 wait instance-terminated --region $REGION --instance-ids $instance_ids
        log "EC2-Instanz(en) erfolgreich terminiert."
    fi
fi

# 2. Sicherheitsgruppe löschen
log "Suche nach Sicherheitsgruppe 'whisperx-sg'..."

sg_id=$(aws ec2 describe-security-groups --region $REGION \
    --filters "Name=group-name,Values=whisperx-sg" \
    --query "SecurityGroups[0].GroupId" \
    --output text)

if [[ -z "$sg_id" || "$sg_id" == "None" ]]; then
    warn "Keine Sicherheitsgruppe 'whisperx-sg' gefunden."
else
    log "Gefundene Sicherheitsgruppe: $sg_id"
    log "Lösche Sicherheitsgruppe..."
    
    # Kurz warten, da die Sicherheitsgruppe noch an der Instanz hängen könnte
    sleep 5
    
    aws ec2 delete-security-group --region $REGION --group-id $sg_id
    
    if [[ $? -ne 0 ]]; then
        warn "Fehler beim Löschen der Sicherheitsgruppe. Möglicherweise ist sie noch mit Ressourcen verknüpft."
        warn "Versuche es später erneut oder lösche sie manuell in der AWS-Konsole."
    else
        log "Sicherheitsgruppe erfolgreich gelöscht."
    fi
fi

# 3. Schlüsselpaar löschen
log "Suche nach Schlüsselpaar 'whisperx-key'..."

key_exists=$(aws ec2 describe-key-pairs --region $REGION \
    --key-names whisperx-key \
    --query "KeyPairs[0].KeyName" \
    --output text 2>/dev/null)

if [[ -z "$key_exists" || "$key_exists" == "None" ]]; then
    warn "Kein Schlüsselpaar 'whisperx-key' gefunden."
else
    log "Gefundenes Schlüsselpaar: $key_exists"
    log "Lösche Schlüsselpaar..."
    
    aws ec2 delete-key-pair --region $REGION --key-name whisperx-key
    
    if [[ $? -ne 0 ]]; then
        error "Fehler beim Löschen des Schlüsselpaars."
    else
        log "Schlüsselpaar erfolgreich gelöscht."
        
        # Lokale Schlüsseldatei löschen
        if [[ -f "whisperx-key.pem" ]]; then
            log "Lösche lokale Schlüsseldatei 'whisperx-key.pem'..."
            rm whisperx-key.pem
            log "Lokale Schlüsseldatei erfolgreich gelöscht."
        fi
    fi
fi

log "Bereinigung abgeschlossen."