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

# Prüfen ob AWS CLI installiert ist
if ! command -v aws &> /dev/null; then
    error "AWS CLI ist nicht installiert. Bitte installiere es zuerst."
    error "Installationsanleitung: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Prüfen ob jq installiert ist
if ! command -v jq &> /dev/null; then
    error "jq ist nicht installiert. Bitte installiere es zuerst."
    error "Auf macOS: brew install jq"
    exit 1
fi

# Standardwerte
DEFAULT_INSTANCE_TYPE="g4dn.xlarge"  # T4 GPU
DEFAULT_REGION="eu-central-1"
DEFAULT_NAME="whisperx-server"
DEFAULT_ACTION="create"

# Hilfefunktion
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Optionen:"
    echo "  -h, --help                      Zeigt diese Hilfe an"
    echo "  -a, --action ACTION             Aktion: create, delete oder status (default: $DEFAULT_ACTION)"
    echo "  -n, --name NAME                 Name der EC2-Instanz (default: $DEFAULT_NAME)"
    echo "  -t, --instance-type TYPE        EC2-Instance-Typ (default: $DEFAULT_INSTANCE_TYPE)"
    echo "  -r, --region REGION             AWS-Region (default: $DEFAULT_REGION)"
    echo "  -g, --gpu-type TYPE             GPU-Typ: t4 oder a10g (default: t4)"
    echo ""
    echo "Beispiele:"
    echo "  $0 --action create --gpu-type t4          # Erstellt eine EC2-Instanz mit T4 GPU"
    echo "  $0 --action create --gpu-type a10g        # Erstellt eine EC2-Instanz mit A10G GPU"
    echo "  $0 --action delete                        # Löscht die EC2-Instanz"
    echo "  $0 --action status                        # Zeigt den Status der EC2-Instanz"
    exit 0
}

# Parameter verarbeiten
INSTANCE_NAME=$DEFAULT_NAME
INSTANCE_TYPE=$DEFAULT_INSTANCE_TYPE
REGION=$DEFAULT_REGION
ACTION=$DEFAULT_ACTION
GPU_TYPE="t4"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) show_help ;;
        -a|--action) ACTION="$2"; shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -t|--instance-type) INSTANCE_TYPE="$2"; shift ;;
        -r|--region) REGION="$2"; shift ;;
        -g|--gpu-type) GPU_TYPE="$2"; shift ;;
        *) error "Unbekannte Option: $1"; show_help ;;
    esac
    shift
done

# GPU-Typ überprüfen und Instance-Typ setzen
if [[ "$GPU_TYPE" == "t4" ]]; then
    INSTANCE_TYPE="g4dn.xlarge"  # T4 GPU
    log "GPU-Typ: T4 (g4dn.xlarge)"
elif [[ "$GPU_TYPE" == "a10g" ]]; then
    INSTANCE_TYPE="g5.xlarge"  # A10G GPU
    log "GPU-Typ: A10G (g5.xlarge)"
else
    error "Unbekannter GPU-Typ: $GPU_TYPE. Unterstützte Typen: t4, a10g"
    exit 1
fi

# Prüfen, ob ein EC2-Schlüsselpaar existiert oder erstellt werden muss
check_or_create_keypair() {
    local keypair_name="whisperx-key"
    local key_file="$keypair_name.pem"
    
    # Prüfen, ob das Schlüsselpaar bereits existiert
    if aws ec2 describe-key-pairs --region $REGION --key-names $keypair_name &> /dev/null; then
        # Das Schlüsselpaar existiert bereits
        info "Schlüsselpaar '$keypair_name' existiert bereits."
        
        # Prüfen, ob die lokale Schlüsseldatei existiert
        if [[ ! -f "$key_file" ]]; then
            warn "Die lokale Schlüsseldatei '$key_file' fehlt."
            warn "Du kannst entweder:"
            warn "1. Die lokale Schlüsseldatei beschaffen, oder"
            warn "2. Das vorhandene Schlüsselpaar in AWS löschen und ein neues erstellen mit:"
            warn "   aws ec2 delete-key-pair --region $REGION --key-name $keypair_name"
            exit 1
        fi
    else
        # Das Schlüsselpaar existiert nicht, also erstellen wir es
        log "Erstelle neues Schlüsselpaar '$keypair_name'..."
        aws ec2 create-key-pair --region $REGION --key-name $keypair_name --query 'KeyMaterial' --output text > $key_file
        
        if [[ $? -ne 0 ]]; then
            error "Fehler beim Erstellen des Schlüsselpaars."
            exit 1
        fi
        
        # Berechtigungen ändern
        chmod 400 $key_file
        log "Schlüsselpaar erstellt und in '$key_file' gespeichert."
    fi
    
    # Rückgabe des Namens des Schlüsselpaars
    echo $keypair_name
}

# Funktion zum Erstellen einer Sicherheitsgruppe oder Wiederverwenden einer vorhandenen
check_or_create_security_group() {
    local sg_name="whisperx-sg"
    local sg_id=""
    
    # Prüfen, ob die Sicherheitsgruppe bereits existiert
    sg_check=$(aws ec2 describe-security-groups --region $REGION --filters "Name=group-name,Values=$sg_name" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)
    
    if [[ "$sg_check" != "None" && "$sg_check" != "" ]]; then
        # Die Sicherheitsgruppe existiert bereits
        sg_id=$sg_check
        info "Sicherheitsgruppe '$sg_name' existiert bereits mit ID: $sg_id"
    else
        # Die Sicherheitsgruppe existiert nicht, also erstellen wir sie
        log "Erstelle neue Sicherheitsgruppe '$sg_name'..."
        
        # Erstellen der Sicherheitsgruppe
        sg_id=$(aws ec2 create-security-group --region $REGION \
            --group-name $sg_name \
            --description "Sicherheitsgruppe für WhisperX-Server" \
            --query "GroupId" --output text)
        
        if [[ $? -ne 0 || -z "$sg_id" ]]; then
            error "Fehler beim Erstellen der Sicherheitsgruppe."
            exit 1
        fi
        
        log "Sicherheitsgruppe erstellt mit ID: $sg_id"
        
        # Regeln hinzufügen
        log "Füge Sicherheitsregeln hinzu..."
        
        # SSH-Zugriff erlauben
        aws ec2 authorize-security-group-ingress --region $REGION \
            --group-id $sg_id \
            --protocol tcp \
            --port 22 \
            --cidr 0.0.0.0/0 > /dev/null
            
        # WhisperX API auf Port 8000 erlauben
        aws ec2 authorize-security-group-ingress --region $REGION \
            --group-id $sg_id \
            --protocol tcp \
            --port 8000 \
            --cidr 0.0.0.0/0 > /dev/null
            
        log "Sicherheitsregeln hinzugefügt."
    fi
    
    # Rückgabe der ID der Sicherheitsgruppe
    echo $sg_id
}

# Funktion zum Abrufen der neuesten Ubuntu AMI-ID
get_latest_ubuntu_ami() {
    # Ubuntu 22.04 LTS (Jammy Jellyfish) für die angegebene Region abrufen
    local ami_id=$(aws ec2 describe-images --region $REGION \
        --owners 099720109477 \
        --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
        "Name=state,Values=available" \
        --query "sort_by(Images, &CreationDate)[-1].ImageId" \
        --output text)
    
    if [[ -z "$ami_id" ]]; then
        error "Konnte keine passende Ubuntu AMI finden."
        exit 1
    fi
    
    echo $ami_id
}

# Funktion zum Erstellen der EC2-Instanz
create_instance() {
    log "Erstelle EC2-Instanz '$INSTANCE_NAME' vom Typ '$INSTANCE_TYPE' in Region '$REGION'..."
    
    # Überprüfen oder Erstellen des Schlüsselpaars
    local keypair_name=$(check_or_create_keypair)
    
    # Überprüfen oder Erstellen der Sicherheitsgruppe
    local sg_id=$(check_or_create_security_group)
    
    # Abrufen der neuesten Ubuntu AMI-ID
    local ami_id=$(get_latest_ubuntu_ami)
    log "Verwende AMI: $ami_id"
    
    # User-Data-Skript zur automatischen Installation bei Instanzstart
    local user_data=$(cat <<EOF
#!/bin/bash
exec > >(tee /var/log/user-data.log) 2>&1
echo "Start der Installationsroutine..."

# System-Updates
apt-get update && apt-get upgrade -y

# Grundlegende Tools
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    jq

# Docker-Installation
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \$(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker ohne sudo nutzen können
usermod -aG docker ubuntu

# NVIDIA-Treiber und Container-Runtime
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
  apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update
apt-get install -y nvidia-docker2
systemctl restart docker

# Repository klonen
cd /home/ubuntu
git clone https://github.com/pavelzbornik/whisperX-FastAPI-cuda.git
chown -R ubuntu:ubuntu whisperX-FastAPI-cuda

# Umgebungsvariablen-Datei erstellen
cat > /home/ubuntu/whisperX-FastAPI-cuda/.env <<ENVFILE
# WhisperX Konfiguration
HF_TOKEN=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
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
ENVFILE

# Installation abschließen und Container starten
cd /home/ubuntu/whisperX-FastAPI-cuda
docker compose up -d

echo "Installation abgeschlossen."
EOF
)
    
    # Base64-Kodierung des User-Data-Skripts
    local user_data_encoded=$(echo "$user_data" | base64)
    
    # Instanz erstellen
    local instance_id=$(aws ec2 run-instances --region $REGION \
        --image-id $ami_id \
        --instance-type $INSTANCE_TYPE \
        --key-name $keypair_name \
        --security-group-ids $sg_id \
        --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":50,\"VolumeType\":\"gp3\"}}]" \
        --user-data "$user_data" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --query "Instances[0].InstanceId" \
        --output text)
    
    if [[ $? -ne 0 || -z "$instance_id" ]]; then
        error "Fehler beim Erstellen der EC2-Instanz."
        exit 1
    fi
    
    log "EC2-Instanz wird erstellt mit ID: $instance_id"
    log "Warte auf Instanzstart..."
    
    # Warten, bis die Instanz läuft
    aws ec2 wait instance-running --region $REGION --instance-ids $instance_id
    
    if [[ $? -ne 0 ]]; then
        error "Fehler beim Warten auf den Start der Instanz."
        exit 1
    fi
    
    # Public IP-Adresse abrufen
    local public_ip=$(aws ec2 describe-instances --region $REGION \
        --instance-ids $instance_id \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text)
    
    log "EC2-Instanz erfolgreich erstellt!"
    log "Instance ID: $instance_id"
    log "Public IP: $public_ip"
    log "SSH-Zugriff: ssh -i whisperx-key.pem ubuntu@$public_ip"
    log "WhisperX API wird unter http://$public_ip:8000 verfügbar sein."
    log "Die Installation läuft im Hintergrund und kann einige Minuten dauern."
    log "Um den Fortschritt zu prüfen, verbinde dich per SSH und führe aus:"
    log "  tail -f /var/log/user-data.log"
}

# Funktion zum Löschen der EC2-Instanz
delete_instance() {
    log "Suche nach EC2-Instanz mit Namen '$INSTANCE_NAME'..."
    
    # Instanz-ID anhand des Namens abrufen
    local instance_id=$(aws ec2 describe-instances --region $REGION \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped,pending,stopping" \
        --query "Reservations[0].Instances[0].InstanceId" \
        --output text)
    
    if [[ -z "$instance_id" || "$instance_id" == "None" ]]; then
        warn "Keine laufende EC2-Instanz mit Namen '$INSTANCE_NAME' gefunden."
        return
    fi
    
    log "Lösche EC2-Instanz mit ID: $instance_id"
    
    # Instanz terminieren
    aws ec2 terminate-instances --region $REGION --instance-ids $instance_id > /dev/null
    
    if [[ $? -ne 0 ]]; then
        error "Fehler beim Löschen der EC2-Instanz."
        exit 1
    fi
    
    log "EC2-Instanz wird gelöscht. Dies kann einige Minuten dauern."
}

# Funktion zum Anzeigen des Status der EC2-Instanz
show_status() {
    log "Prüfe Status der EC2-Instanz mit Namen '$INSTANCE_NAME'..."
    
    # Instanz-Details anhand des Namens abrufen
    local instance_details=$(aws ec2 describe-instances --region $REGION \
        --filters "Name=tag:Name,Values=$INSTANCE_NAME" \
        --query "Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,PublicIP:PublicIpAddress,InstanceType:InstanceType,LaunchTime:LaunchTime}" \
        --output json)
    
    if [[ -z "$instance_details" || "$instance_details" == "null" ]]; then
        warn "Keine EC2-Instanz mit Namen '$INSTANCE_NAME' gefunden."
        return
    fi
    
    # JSON-Antwort parsen
    local instance_id=$(echo $instance_details | jq -r '.InstanceId')
    local state=$(echo $instance_details | jq -r '.State')
    local public_ip=$(echo $instance_details | jq -r '.PublicIP')
    local instance_type=$(echo $instance_details | jq -r '.InstanceType')
    local launch_time=$(echo $instance_details | jq -r '.LaunchTime')
    
    if [[ -z "$instance_id" || "$instance_id" == "null" ]]; then
        warn "Keine EC2-Instanz mit Namen '$INSTANCE_NAME' gefunden."
        return
    fi
    
    log "EC2-Instanz gefunden!"
    log "Instance ID: $instance_id"
    log "Status: $state"
    log "Public IP: $public_ip"
    log "Instance Typ: $instance_type"
    log "Launch Time: $launch_time"
    
    if [[ "$state" == "running" && -n "$public_ip" ]]; then
        log "SSH-Zugriff: ssh -i whisperx-key.pem ubuntu@$public_ip"
        log "WhisperX API URL: http://$public_ip:8000"
    fi
}

# Hauptlogik basierend auf der gewählten Aktion
case "$ACTION" in
    create)
        create_instance
        ;;
    delete)
        delete_instance
        ;;
    status)
        show_status
        ;;
    *)
        error "Unbekannte Aktion: $ACTION"
        show_help
        ;;
esac

exit 0