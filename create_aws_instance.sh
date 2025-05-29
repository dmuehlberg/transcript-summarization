#!/bin/bash
# Angepasstes Skript zum Deployment von WhisperX auf AWS mit GPU-Unterstützung
# Verwendet das AWS Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.4 (Ubuntu 22.04)

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
if aws ec2 describe-key-pairs --region $REGION --key-names $KEY_NAME &> /dev/null; then
    log "Schlüsselpaar '$KEY_NAME' existiert bereits."
    
    # Prüfen, ob die Datei lokal existiert
    if [[ ! -f "$KEY_NAME.pem" ]]; then
        warn "Die lokale Schlüsseldatei '$KEY_NAME.pem' fehlt!"
        warn "Lösche das vorhandene Schlüsselpaar und erstelle ein neues..."
        aws ec2 delete-key-pair --region $REGION --key-name $KEY_NAME
        
        # Neues Schlüsselpaar erstellen
        log "Erstelle neues Schlüsselpaar '$KEY_NAME'..."
        aws ec2 create-key-pair --region $REGION --key-name $KEY_NAME --query 'KeyMaterial' --output text > $KEY_NAME.pem
        chmod 400 $KEY_NAME.pem
        log "Schlüsselpaar erstellt und in '$KEY_NAME.pem' gespeichert."
    fi
else
    log "Erstelle neues Schlüsselpaar '$KEY_NAME'..."
    aws ec2 create-key-pair --region $REGION --key-name $KEY_NAME --query 'KeyMaterial' --output text > $KEY_NAME.pem
    chmod 400 $KEY_NAME.pem
    log "Schlüsselpaar erstellt und in '$KEY_NAME.pem' gespeichert."
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

# 3. Deep Learning AMI finden
log "Suche nach dem Ubuntu Server 22.04 LTS (HVM), SSD Volume Type AMI..."

# AWS Deep Learning AMI suchen
AMI_ID=$(aws ec2 describe-images --region $REGION \
    --owners amazon \
    --filters "Name=name,Values=*Ubuntu Server 22.04 LTS*HVM*SSD Volume Type*" \
    "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)

if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
    warn "Konnte Ubuntu Server 22.04 LTS (HVM), SSD Volume Type AMI nicht finden. Versuche allgemeine Suche nach Deep Learning AMI..."
    
    AMI_ID=$(aws ec2 describe-images --region $REGION \
        --owners amazon \
        --filters "Name=name,Values=*Deep Learning OSS Nvidia Driver AMI*Ubuntu*" \
        "Name=state,Values=available" \
        --query "sort_by(Images, &CreationDate)[-1].ImageId" \
        --output text)
    
    if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
        error "Konnte kein passendes Deep Learning AMI finden. Bitte überprüfe, ob die AMIs in der Region $REGION verfügbar sind."
        exit 1
    fi
fi

log "Verwende Deep Learning AMI: $AMI_ID"

# AMI-Details anzeigen
AMI_NAME=$(aws ec2 describe-images --region $REGION \
    --image-ids $AMI_ID \
    --query "Images[0].Name" \
    --output text)
log "AMI Name: $AMI_NAME"

# 4. User-Data-Skript für die automatische Installation erstellen
log "Erstelle User-Data-Skript..."
USER_DATA=$(cat <<'EOF'
#!/bin/bash
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starte WhisperX-Installation auf Deep Learning AMI..."

# System-Updates
# apt-get update && apt-get upgrade -y

# Grundlegende Tools installieren (falls noch nicht vorhanden)
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git jq wget

# CUDA-Version überprüfen
echo "Verfügbare CUDA-Versionen:"
ls -l /usr/local | grep cuda

# NVIDIA-Status prüfen
echo "NVIDIA-Status:"
nvidia-smi

# CUDA 12.1 als Standard setzen (falls verfügbar)
if [ -d "/usr/local/cuda-12.1" ]; then
    echo "Setze CUDA 12.1 als Standard..."
    if [ -L "/usr/local/cuda" ]; then
        sudo rm /usr/local/cuda
    fi
    sudo ln -s /usr/local/cuda-12.1 /usr/local/cuda
    echo 'export PATH=/usr/local/cuda/bin${PATH:+:${PATH}}' | sudo tee /etc/profile.d/cuda.sh
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' | sudo tee -a /etc/profile.d/cuda.sh
    source /etc/profile.d/cuda.sh
    echo "CUDA-Version nach Umstellung:"
    nvcc --version
fi

# Docker sollte bereits installiert sein, aber stellen wir sicher, dass es läuft
systemctl status docker || {
  echo "Docker ist nicht installiert oder läuft nicht, installiere es..."
  apt-get install -y docker.io
  systemctl enable docker
  systemctl start docker
}

# Docker-Socket-Berechtigungen prüfen
chmod 666 /var/run/docker.sock
usermod -aG docker ubuntu

# Das Setup-Skript herunterladen
cd /home/ubuntu
wget https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh
chmod +x container-setup.sh
chown ubuntu:ubuntu container-setup.sh

# Erstelle ein Wrapper-Skript für das Container-Setup
cat > /home/ubuntu/run_setup.sh << 'SETUPSCRIPT'
#!/bin/bash
set -e

cd /home/ubuntu

# Docker-Diagnose
echo "Docker-Diagnose ausführen..."
docker --version
docker info || sudo docker info
docker ps || sudo docker ps

# Docker-Socket-Berechtigungen anpassen, falls nötig
if [ ! -w /var/run/docker.sock ]; then
  echo "Berechtigungen für Docker-Socket anpassen..."
  sudo chmod 666 /var/run/docker.sock
fi

# Container-Setup ausführen
# echo "Führe container-setup.sh aus..."
# ./container-setup.sh

echo "Setup abgeschlossen!"
SETUPSCRIPT

chmod +x /home/ubuntu/run_setup.sh
chown ubuntu:ubuntu /home/ubuntu/run_setup.sh

# Setup als ubuntu-Benutzer ausführen
echo "Führe Setup-Skript als ubuntu-Benutzer aus..."
sudo -i -u ubuntu bash -c "cd /home/ubuntu && ./run_setup.sh" || {
  echo "Setup als ubuntu-Benutzer fehlgeschlagen, versuche als root..."
  cd /home/ubuntu && ./run_setup.sh
}

echo "WhisperX-Installation abgeschlossen."
echo "API sollte unter http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000 verfügbar sein."
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
log "SSH-Zugriff: ssh -i $KEY_NAME.pem ubuntu@$PUBLIC_IP"
log "WhisperX API wird unter http://$PUBLIC_IP:8000 verfügbar sein."
log "Die Installation läuft im Hintergrund und kann einige Minuten dauern."
log "Um den Fortschritt zu prüfen, verbinde dich per SSH und führe aus:"
log "  tail -f /var/log/user-data.log"