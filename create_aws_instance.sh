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

# Im Rest des Skripts KEY_FILE anstelle von $KEY_NAME.pem verwenden

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
apt-get install -y build-essential dkms

# NVIDIA CUDA Repository hinzufügen
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt-get update

# Installiere zuerst den AWS-spezifischen NVIDIA-Treiber
apt-get install -y linux-modules-nvidia-535-aws nvidia-driver-535-server

# Versuche bei Bedarf einen zusätzlichen Ansatz
if ! nvidia-smi &>/dev/null; then
  echo "AWS-Treiber scheinen nicht zu funktionieren, versuche Metapaket..."
  apt-get install -y nvidia-driver-535
fi

# Installiere CUDA Toolkit separat (ohne nochmal Treiber zu installieren)
apt-get install -y cuda-toolkit-12-1

# Konfigurieren der Modprobe-Optionen für NVIDIA
echo "options nvidia NVreg_EnableGpuFirmware=0" > /etc/modprobe.d/nvidia.conf

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
  wget https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh -O /home/ubuntu/transcript-summarization/container-setup.sh
  chmod +x /home/ubuntu/transcript-summarization/container-setup.sh
  chown ubuntu:ubuntu /home/ubuntu/transcript-summarization/container-setup.sh
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
  echo "WARNUNG: NVIDIA-Treiber sind nicht geladen, versuche Module zu laden..."
  sudo modprobe nvidia || true
  sudo modprobe nvidia_uvm || true
  
  # Nochmal prüfen
  if ! nvidia-smi &>/dev/null; then
    echo "FEHLER: NVIDIA-Treiber konnten nicht geladen werden."
    echo "Prüfe installierte Pakete..."
    dpkg -l | grep -i nvidia
    echo "Versuche manuelle Treiberinstallation..."
    sudo apt-get update
    sudo apt-get install -y linux-modules-nvidia-535-aws
    sudo modprobe nvidia
    
    # Letzte Prüfung
    if ! nvidia-smi &>/dev/null; then
      echo "FEHLER: NVIDIA-Treiber konnten nicht initialisiert werden!"
      echo "Diese Instanz benötigt zwingend GPU-Unterstützung."
      echo "Bitte überprüfen Sie die Treiberinstallation manuell."
      exit 1
    fi
  fi
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
if ! docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi; then
  echo "FEHLER: NVIDIA Docker-Test fehlgeschlagen!"
  echo "Prüfe, ob nvidia-container-toolkit installiert ist..."
  dpkg -l | grep -q nvidia-container-toolkit
  echo "Konfiguriere nvidia-container-toolkit neu..."
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
  
  # Erneuter Test
  if ! docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi; then
    echo "FEHLER: NVIDIA Docker-Test ist endgültig fehlgeschlagen."
    echo "GPU-Durchreichung an Docker funktioniert nicht."
    exit 1
  fi
fi

# Führe das container-setup.sh Skript aus
echo "Führe container-setup.sh aus..."
cd /home/ubuntu/transcript-summarization
if [ -f "./container-setup.sh" ]; then
  chmod +x ./container-setup.sh
  bash -c "echo -e '\n\nn\n' | ./container-setup.sh"
else
  echo "FEHLER: container-setup.sh konnte nicht gefunden werden!"
  exit 1
fi

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
log "SSH-Zugriff: ssh -i $KEY_FILE ubuntu@$PUBLIC_IP"
log "WhisperX API wird nach dem Neustart unter http://$PUBLIC_IP:8000 verfügbar sein."
log "Die Installation läuft im Hintergrund und kann bis zu 15 Minuten dauern, gefolgt von einem Neustart."
log "Verbinde dich nach ca. 20 Minuten per SSH und überprüfe:"
log "  tail -f /home/ubuntu/whisperx_startup.log"
log "  docker ps    # Um zu sehen, ob der Container läuft"