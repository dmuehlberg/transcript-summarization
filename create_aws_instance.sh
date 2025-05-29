#!/bin/bash
# Optimiertes Skript zum Deployment von WhisperX auf AWS mit GPU-Unterstützung
# Verwendet Ubuntu Server 22.04 LTS mit manueller CUDA 12.1.1 und Docker-Installation

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

# 3. Direkte Verwendung der bekannten AMI-ID
log "Verwende die angegebene AMI-ID für Ubuntu Server 22.04 LTS..."
AMI_ID="ami-04a5bacc58328233d"
log "Verwende Ubuntu Server 22.04 LTS AMI: $AMI_ID"

# Optional: AMI-Details anzeigen (wenn gewünscht)
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
echo "Starte WhisperX-Installation auf Ubuntu 22.04..."

# System aktualisieren
echo "System wird aktualisiert..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Grundlegende Tools installieren
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git jq wget python3-pip

# Docker-Repository hinzufügen und Docker installieren
echo "Docker wird installiert..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker-Socket-Berechtigungen setzen
chmod 666 /var/run/docker.sock
usermod -aG docker ubuntu

# NVIDIA-Treiber für GPU installieren
echo "NVIDIA-Treiber werden installiert..."
apt-get install -y linux-headers-$(uname -r)
apt-get install -y build-essential

# NVIDIA CUDA Repository hinzufügen
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt-get update

# CUDA 12.1 und NVIDIA-Treiber installieren
apt-get install -y cuda-12-1 cuda-drivers

# NVIDIA Container Toolkit installieren
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update
apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# CUDA-Umgebungsvariablen setzen
echo 'export PATH=/usr/local/cuda-12.1/bin${PATH:+:${PATH}}' > /etc/profile.d/cuda.sh
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> /etc/profile.d/cuda.sh
chmod +x /etc/profile.d/cuda.sh
source /etc/profile.d/cuda.sh

# Python und weitere Abhängigkeiten für WhisperX
apt-get install -y python3.11 python3.11-venv python3-pip python3.11-dev ffmpeg libsndfile1

# Python-Alternative setzen
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --set python3 /usr/bin/python3.11

# Docker-Compose installieren
pip3 install docker-compose

# Das WhisperX Repository klonen
cd /home/ubuntu
git clone https://github.com/dmuehlberg/transcript-summarization.git
chown -R ubuntu:ubuntu transcript-summarization

# Das Setup-Skript herunterladen (falls es nicht im Repository ist)
cd /home/ubuntu
if [ ! -f "/home/ubuntu/transcript-summarization/container-setup.sh" ]; then
  wget https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh -O /home/ubuntu/container-setup.sh
  chmod +x /home/ubuntu/container-setup.sh
  chown ubuntu:ubuntu /home/ubuntu/container-setup.sh
fi

# Standard-ENV-Datei erstellen, falls nicht vorhanden
if [ ! -f "/home/ubuntu/transcript-summarization/.env" ]; then
  cat > /home/ubuntu/transcript-summarization/.env << 'ENVFILE'
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
ENVFILE
  chown ubuntu:ubuntu /home/ubuntu/transcript-summarization/.env
fi

# NVIDIA-Status überprüfen
echo "NVIDIA-Treiber-Status überprüfen..."
nvidia-smi || echo "NVIDIA-Treiber sind noch nicht geladen, was normal ist. Nach einem Neustart sollten sie verfügbar sein."

# Start-Skript erstellen, das nach dem Neustart ausgeführt werden soll
cat > /home/ubuntu/start_whisperx.sh << 'STARTSCRIPT'
#!/bin/bash
set -e

# Logfile
LOG_FILE="/home/ubuntu/whisperx_startup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "$(date): Starte WhisperX Setup nach Reboot..."

# Prüfe, ob NVIDIA-Treiber geladen sind
if ! nvidia-smi &>/dev/null; then
  echo "FEHLER: NVIDIA-Treiber sind nicht geladen. Bitte überprüfen!"
  exit 1
fi

# In das Repository-Verzeichnis wechseln
cd /home/ubuntu/transcript-summarization

# Docker-Socket-Berechtigungen prüfen
if [ ! -w /var/run/docker.sock ]; then
  echo "Berechtigungen für Docker-Socket anpassen..."
  sudo chmod 666 /var/run/docker.sock
fi

# NVIDIA Docker-Test ausführen
echo "Teste NVIDIA Docker..."
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi || {
  echo "FEHLER: NVIDIA Docker-Test fehlgeschlagen!"
  exit 1
}

# Container bauen und starten
echo "Stoppe alte Container, falls vorhanden..."
docker compose down 2>/dev/null || true

echo "Baue Container (kann 5-10 Minuten dauern)..."
docker compose build whisperx_cuda

echo "Starte Container..."
docker compose up -d whisperx_cuda

echo "WhisperX-Setup abgeschlossen um $(date)"
echo "API sollte unter http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/docs verfügbar sein"
STARTSCRIPT

chmod +x /home/ubuntu/start_whisperx.sh
chown ubuntu:ubuntu /home/ubuntu/start_whisperx.sh

# Crontab-Eintrag für den Neustart hinzufügen
(crontab -l 2>/dev/null || echo "") | { cat; echo "@reboot /home/ubuntu/start_whisperx.sh"; } | crontab -

# Reboot nach der Installation, um die Treiber zu laden
echo "Installation abgeschlossen. System wird in 10 Sekunden neu gestartet..."
echo "Nach dem Neustart wird WhisperX automatisch gestartet."
echo "Verbinde dich nach dem Neustart per SSH und überprüfe: tail -f /home/ubuntu/whisperx_startup.log"

# Reboot planen
nohup bash -c "sleep 10 && reboot" &

echo "Setup-Skript beendet. Warte auf Neustart..."
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
log "WhisperX API wird nach dem Neustart unter http://$PUBLIC_IP:8000 verfügbar sein."
log "Die Installation läuft im Hintergrund und kann bis zu 15 Minuten dauern, gefolgt von einem Neustart."
log "Verbinde dich nach ca. 20 Minuten per SSH und überprüfe:"
log "  tail -f /home/ubuntu/whisperx_startup.log"
log "  docker ps    # Um zu sehen, ob der Container läuft"