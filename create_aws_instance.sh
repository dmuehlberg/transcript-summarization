#!/bin/bash
# Optimiertes Skript zum Deployment von WhisperX auf AWS mit GPU-Unterstützung
# Repliziert das funktionierende Brev-Setup mit NVIDIA 550.163.01 Treibern und CUDA 12.4

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
GPU_TYPE="t4"
KEY_NAME="whisperx-key"

# Parameter verarbeiten
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGION="$2"; shift ;;
        -t|--type) GPU_TYPE="$2"; shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -k|--key) KEY_NAME="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# GPU-Typ überprüfen und Instance-Typ setzen
if [[ "$GPU_TYPE" == "t4" ]]; then
    INSTANCE_TYPE="g4dn.xlarge"
    log "GPU-Typ: T4 (g4dn.xlarge)"
elif [[ "$GPU_TYPE" == "a10g" ]]; then
    INSTANCE_TYPE="g5.xlarge"
    log "GPU-Typ: A10G (g5.xlarge)"
else
    error "Unbekannter GPU-Typ: $GPU_TYPE. Unterstützte Typen: t4, a10g"
    exit 1
fi

log "Starte EC2-Instanz in Region: $REGION, Instance-Typ: $INSTANCE_TYPE"

# 1. Schlüsselpaar erstellen, falls es noch nicht existiert
log "Prüfe auf vorhandenes Schlüsselpaar..."
KEY_EXISTS=$(aws ec2 describe-key-pairs --region $REGION --key-names $KEY_NAME --query 'KeyPairs[0].KeyName' --output text 2>/dev/null)

# Temporäre Datei für das Schlüsselpaar
KEY_FILE="$KEY_NAME.pem"
TEMP_KEY_FILE="/tmp/$KEY_NAME-$(date +%s).pem"

if [[ "$KEY_EXISTS" == "$KEY_NAME" ]]; then
    log "Schlüsselpaar '$KEY_NAME' existiert bereits."
    
    # Prüfen, ob die Datei lokal existiert und beschreibbar ist
    if [[ ! -f "$KEY_FILE" || ! -w "$KEY_FILE" ]]; then
        warn "Die lokale Schlüsseldatei '$KEY_FILE' fehlt oder ist nicht beschreibbar!"
        warn "Lösche das vorhandene Schlüsselpaar und erstelle ein neues..."
        aws ec2 delete-key-pair --region $REGION --key-name $KEY_NAME
        
        # Neues Schlüsselpaar erstellen
        log "Erstelle neues Schlüsselpaar '$KEY_NAME'..."
        if ! aws ec2 create-key-pair --region $REGION --key-name $KEY_NAME --query 'KeyMaterial' --output text > "$TEMP_KEY_FILE"; then
            error "Fehler beim Erstellen des Schlüsselpaars."
            exit 1
        fi
        
        # Versuche, die temporäre Datei an die gewünschte Stelle zu kopieren
        if ! cp "$TEMP_KEY_FILE" "$KEY_FILE" 2>/dev/null; then
            warn "Konnte Schlüsseldatei nicht nach '$KEY_FILE' kopieren. Verwende stattdessen: $TEMP_KEY_FILE"
            KEY_FILE="$TEMP_KEY_FILE"
        fi
        
        chmod 400 "$KEY_FILE"
        log "Schlüsselpaar erstellt und in '$KEY_FILE' gespeichert."
    fi
else
    # Sicherstellen, dass kein Schlüsselpaar mit diesem Namen existiert
    aws ec2 delete-key-pair --region $REGION --key-name $KEY_NAME 2>/dev/null
    
    log "Erstelle neues Schlüsselpaar '$KEY_NAME'..."
    
    # Zuerst in temporäre Datei schreiben
    if ! aws ec2 create-key-pair --region $REGION --key-name $KEY_NAME --query 'KeyMaterial' --output text > "$TEMP_KEY_FILE"; then
        error "Fehler beim Erstellen des Schlüsselpaars. Bitte überprüfen Sie Ihre AWS-Berechtigungen."
        exit 1
    fi
    
    # Versuche, die temporäre Datei an die gewünschte Stelle zu kopieren
    if ! cp "$TEMP_KEY_FILE" "$KEY_FILE" 2>/dev/null; then
        warn "Konnte Schlüsseldatei nicht nach '$KEY_FILE' kopieren. Verwende stattdessen: $TEMP_KEY_FILE"
        KEY_FILE="$TEMP_KEY_FILE"
    fi
    
    chmod 400 "$KEY_FILE"
    log "Schlüsselpaar erstellt und in '$KEY_FILE' gespeichert."
fi

# Nochmal prüfen, ob das Schlüsselpaar jetzt existiert
if ! aws ec2 describe-key-pairs --region $REGION --key-names $KEY_NAME &> /dev/null; then
    error "Schlüsselpaar '$KEY_NAME' konnte nicht erstellt werden. Bitte überprüfen Sie Ihre AWS-Berechtigungen."
    exit 1
fi

# 2. Sicherheitsgruppe erstellen, falls sie noch nicht existiert
SG_NAME="whisperx-sg"
log "Prüfe auf vorhandene Sicherheitsgruppe..."
SG_ID=$(aws ec2 describe-security-groups --region $REGION --filters "Name=group-name,Values=$SG_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)

if [[ "$SG_ID" != "None" && "$SG_ID" != "" ]]; then
    log "Sicherheitsgruppe '$SG_NAME' existiert bereits mit ID: $SG_ID"
else
    log "Erstelle neue Sicherheitsgruppe '$SG_NAME'..."
    SG_ID=$(aws ec2 create-security-group --region $REGION \
        --group-name $SG_NAME \
        --description "Security Group for WhisperX Server" \
        --query "GroupId" --output text)
    
    log "Füge Sicherheitsregeln hinzu..."
    # SSH erlauben
    aws ec2 authorize-security-group-ingress --region $REGION \
        --group-id $SG_ID \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 > /dev/null
    
    # WhisperX API auf Port 8000 erlauben
    aws ec2 authorize-security-group-ingress --region $REGION \
        --group-id $SG_ID \
        --protocol tcp \
        --port 8000 \
        --cidr 0.0.0.0/0 > /dev/null
    
    log "Sicherheitsgruppe erstellt mit ID: $SG_ID"
fi

# 3. Direkte Verwendung der bekannten AMI-ID für Ubuntu 22.04 LTS
log "Verwende die angegebene AMI-ID für Ubuntu Server 22.04 LTS..."
# AMI_ID="ami-04a5bacc58328233d"
AMI_ID="ami-0ebbe5fd64f8315ed"

log "Verwende Ubuntu Server 22.04 LTS AMI: $AMI_ID"

# Optional: AMI-Details anzeigen
AMI_NAME=$(aws ec2 describe-images --region $REGION \
    --image-ids $AMI_ID \
    --query "Images[0].Name" \
    --output text)
if [[ -n "$AMI_NAME" && "$AMI_NAME" != "None" ]]; then
    log "AMI Name: $AMI_NAME"
else
    log "AMI Details konnten nicht abgerufen werden, fahre mit bekannter ID fort."
fi

# 4. User-Data-Skript für die automatische Installation erstellen
log "Erstelle User-Data-Skript..."
USER_DATA=$(cat <<'EOF'
#!/bin/bash
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starte WhisperX-Installation auf Ubuntu 22.04 mit NVIDIA 550.163.01 Treibern und CUDA 12.4..."

# Führe das container-setup.sh Skript aus
# echo "Führe container-setup.sh aus..."
# cd /home/ubuntu/transcript-summarization
# if [ -f "./container-setup.sh" ]; then
#   chmod +x ./container-setup.sh
#   bash -c "echo -e '\n\nn\n' | ./container-setup.sh"
# else
#   echo "FEHLER: container-setup.sh konnte nicht gefunden werden!"
  
#   # Lade das Skript herunter, falls es nicht im Repository ist
#   wget https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh -O ./container-setup.sh
#   chmod +x ./container-setup.sh
#   bash -c "echo -e '\n\nn\n' | ./container-setup.sh"
# fi

# echo "WhisperX-Setup abgeschlossen um $(date)"
# echo "API sollte unter http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/docs verfügbar sein"
STARTSCRIPT


EOF
)

# 5. EC2-Instanz erstellen
log "Erstelle EC2-Instanz..."
INSTANCE_ID=$(aws ec2 run-instances --region $REGION \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":128,\"VolumeType\":\"gp3\"}}]" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query "Instances[0].InstanceId" \
    --output text)

if [[ $? -ne 0 || -z "$INSTANCE_ID" ]]; then
    error "Fehler beim Erstellen der EC2-Instanz."
    exit 1
fi

# # 5. EC2-Instanz erstellen
# log "Erstelle EC2-Instanz..."
# INSTANCE_ID=$(aws ec2 run-instances --region $REGION \
#     --image-id $AMI_ID \
#     --instance-type $INSTANCE_TYPE \
#     --key-name $KEY_NAME \
#     --security-group-ids $SG_ID \
#     --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":128,\"VolumeType\":\"gp3\"}}]" \
#     --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
#     --query "Instances[0].InstanceId" \
#     --output text)

# if [[ $? -ne 0 || -z "$INSTANCE_ID" ]]; then
#     error "Fehler beim Erstellen der EC2-Instanz."
#     exit 1
# fi

log "EC2-Instanz wird erstellt mit ID: $INSTANCE_ID"
log "Warte auf Instanzstart..."

# 6. Warten, bis die Instanz läuft
aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID

# 7. Public IP-Adresse abrufen
PUBLIC_IP=$(aws ec2 describe-instances --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

log "EC2-Instanz erfolgreich erstellt!"
log "Instance ID: $INSTANCE_ID"
log "Public IP: $PUBLIC_IP"
log "SSH-Zugriff: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP"