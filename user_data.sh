#!/bin/bash
# Script zur automatischen Installation und Konfiguration von WhisperX auf einer AWS-Instanz

# Log-Setup
exec > >(tee /var/log/user-data.log) 2>&1
echo "Start der WhisperX-Installationsroutine..."

# System-Updates
echo "Aktualisiere Systempakete..."
apt-get update && apt-get upgrade -y

# Grundlegende Tools installieren
echo "Installiere benötigte Tools..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    jq

# Docker-Installation
echo "Installiere Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker ohne sudo nutzen können
usermod -aG docker ubuntu

# NVIDIA-Treiber und Container-Runtime
echo "Installiere NVIDIA-Treiber und Container-Runtime..."
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update
apt-get install -y nvidia-docker2
systemctl restart docker

# Repository klonen
echo "Klone WhisperX-Repository..."
cd /home/ubuntu
git clone https://github.com/pavelzbornik/whisperX-FastAPI-cuda.git
chown -R ubuntu:ubuntu whisperX-FastAPI-cuda

# Umgebungsvariablen-Datei erstellen
echo "Erstelle .env-Datei..."
cat > /home/ubuntu/whisperX-FastAPI-cuda/.env <<EOF
# WhisperX Konfiguration
HF_TOKEN=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
WHISPER_MODEL=base
DEFAULT_LANG=de
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
EOF

# Verzeichnisse für persistente Daten
echo "Erstelle Verzeichnisse für persistente Daten..."
mkdir -p /data/whisperx/cache /data/whisperx/tmp
chmod -R 777 /data/whisperx

# Installation abschließen und Container starten
echo "Starte Docker-Container..."
cd /home/ubuntu/whisperX-FastAPI-cuda
docker compose up -d

# NVIDIA-Status überprüfen
echo "NVIDIA Status:"
nvidia-smi

echo "WhisperX-Installation abgeschlossen."
echo "API sollte unter http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000 verfügbar sein."