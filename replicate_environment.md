# Anleitung zur Replikation der WhisperX-GPU-Umgebung auf AWS

Diese Anleitung beschreibt, wie du die lauffähige WhisperX-Umgebung auf einer eigenen AWS-Instanz replizieren kannst.

## 1. Skripte zur Systemanalyse ausführen

Führe zunächst die bereitgestellten Skripte auf der funktionierenden Brev-Instanz aus, um die Umgebung zu analysieren:

```bash
# Systemanalyse (Hardware, Software, Bibliotheken)
bash system_analyzer.sh

# Docker-Analyse (Container, Images, Konfiguration)
bash docker_analyzer.sh
```

Diese Skripte erzeugen detaillierte Berichte, die du als Referenz für die Einrichtung deiner AWS-Instanz verwenden kannst.

## 2. AWS-Instanz mit passender Hardware erstellen

1. Wähle einen Instance-Typ mit NVIDIA T4 GPU (z.B. g4dn.xlarge)
2. Starte mit Ubuntu Server 22.04 LTS (ami-04a5bacc58328233d)
3. Stelle sicher, dass die Instanz mindestens 16 GB RAM und 100 GB Speicher hat

Du kannst dein vorhandenes Skript `create_aws_instance.sh` verwenden, aber stelle sicher, dass du den richtigen Instance-Typ wählst:

```bash
./create_aws_instance.sh --type t4 --region eu-central-1
```

## 3. NVIDIA-Treiber und CUDA installieren

Nach dem Verbinden mit der AWS-Instanz:

```bash
# System aktualisieren
sudo apt-get update
sudo apt-get upgrade -y

# Notwendige Pakete installieren
sudo apt-get install -y build-essential git curl wget

# NVIDIA-Treiber installieren
sudo apt-get install -y linux-headers-$(uname -r)
sudo apt-get install -y nvidia-driver-535-server

# CUDA 12.1 installieren
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-1

# NVIDIA Container Toolkit installieren
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sudo sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Umgebungsvariablen setzen
echo 'export PATH=/usr/local/cuda-12.1/bin${PATH:+:${PATH}}' | sudo tee /etc/profile.d/cuda.sh
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' | sudo tee -a /etc/profile.d/cuda.sh
source /etc/profile.d/cuda.sh
```

## 4. Docker und Docker Compose installieren

```bash
# Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Benutzer zur Docker-Gruppe hinzufügen
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose installieren
sudo apt-get install -y docker-compose
```

## 5. Methode 1: WhisperX-Image von Brev übertragen (empfohlen)

### 5.1 Auf der Brev-Instanz: Image exportieren

```bash
# Image identifizieren
docker images

# Image speichern
docker save whisperx_cuda -o whisperx_cuda.tar

# Komprimieren
gzip whisperx_cuda.tar
```

### 5.2 Das Image zur AWS-Instanz übertragen

```bash
# Von deinem lokalen Computer
scp -i whisperx-key.pem whisperx_cuda.tar.gz ubuntu@DEINE_AWS_IP:/home/ubuntu/
```

### 5.3 Auf der AWS-Instanz: Image importieren

```bash
# Entpacken
gunzip whisperx_cuda.tar.gz

# Docker-Image importieren
docker load -i whisperx_cuda.tar

# Aufräumen
rm whisperx_cuda.tar
```

## 6. Methode 2: Repository klonen und Container bauen (Alternative)

Falls die erste Methode nicht funktioniert:

```bash
# Repository klonen
git clone https://github.com/dmuehlberg/transcript-summarization.git
cd transcript-summarization

# .env-Datei erstellen
cat > .env << EOF
POSTGRES_USER=root
POSTGRES_PASSWORD=postgres
POSTGRES_DB=n8n
HF_TOKEN=dein_huggingface_token
EOF

# Aktualisierte Version des Dockerfiles für whisperX-FastAPI-cuda erstellen
# (Verwende das aktualisierte Dockerfile aus dem ersten Artefakt)

# Container bauen (kann lange dauern)
docker compose build whisperx_cuda
```

## 7. Docker Compose-Konfiguration anpassen

```bash
cd transcript-summarization
```

Bearbeite die `docker-compose.yml`-Datei, um sicherzustellen, dass sie das korrekte Image verwendet:

```yaml
# Für importiertes Image:
whisperx_cuda:
  image: whisperx_cuda
  container_name: whisperx-cuda
  networks: ['demo']
  ports:
    - "8000:8000"
  environment:
    - DEVICE=cuda
    - HF_TOKEN=${HF_TOKEN}
    # Weitere Umgebungsvariablen...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## 8. Container starten

```bash
# Container starten
docker compose up -d whisperx_cuda

# Logs überprüfen
docker compose logs -f whisperx_cuda
```

## 9. GPU-Unterstützung verifizieren

```bash
# Nvidia-SMI im Container ausführen
docker exec whisperx-cuda nvidia-smi

# Teste, ob Python CUDA erkennt
docker exec whisperx-cuda python -c "import torch; print('CUDA verfügbar:', torch.cuda.is_available()); print('CUDA-Version:', torch.version.cuda if torch.cuda.is_available() else 'N/A')"
```

## 10. API-Zugriff testen

```bash
# API-Status prüfen
curl http://localhost:8000/health

# API-Dokumentation aufrufen
# Öffne in deinem Browser: http://DEINE_AWS_IP:8000/docs
```

## Fehlerbehebung

### Falls GPU nicht erkannt wird:

```bash
# NVIDIA-Treiber prüfen
nvidia-smi

# Docker-GPU-Unterstützung prüfen
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Test mit CUDA-Container
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

### Falls Container nicht startet:

```bash
# Container-Logs prüfen
docker logs whisperx-cuda

# Container neu starten
docker compose down
docker compose up -d whisperx_cuda
```

### Zeitüberschreitung beim Build:

Falls der Build zu lange dauert oder fehlschlägt, ist die Übertragung des fertigen Images von Brev (Methode 1) die bevorzugte Lösung.

## Zusätzliche Hinweise

- Setze einen gültigen Hugging Face-Token in der `.env`-Datei
- Stelle sicher, dass die Sicherheitsgruppe der AWS-Instanz Port 8000 für eingehenden Verkehr öffnet
- Die erste Transkription kann etwas länger dauern, da die Modelle heruntergeladen werden müssen