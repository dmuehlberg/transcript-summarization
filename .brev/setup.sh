#!/bin/bash

# Brev Setup Script für WhisperX FastAPI
# Wird automatisch beim Erstellen der Instanz ausgeführt

set -e

log() { echo "[$(date +'%H:%M:%S')] $1"; }
error() { echo "[ERROR] $1" >&2; }

log "🚀 Starte automatische WhisperX Setup..."

# In das Projektverzeichnis wechseln
cd /home/ubuntu

# System Updates
log "Aktualisiere System..."
sudo apt-get update -y

# Docker sicherstellen
if ! command -v docker &> /dev/null; then
    log "Installiere Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
fi

# NVIDIA Container Toolkit
if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
    log "Konfiguriere NVIDIA Docker Support..."
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt-get update && sudo apt-get install -y nvidia-docker2
    sudo systemctl restart docker
fi

# Repository-Verzeichnis
REPO_DIR="/home/ubuntu/transcript-summarization"
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
else
    log "Repository nicht gefunden, klone es..."
    git clone https://github.com/dmuehlberg/transcript-summarization.git
    cd transcript-summarization
fi

# .env Datei erstellen
log "Erstelle .env Konfiguration..."
cat > .env << 'EOF'
HF_TOKEN=your_huggingface_token_here
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
DEV=false
FILTER_WARNING=true
DB_URL=sqlite:///records.db
EOF

# Docker Container vorbereiten
log "Bereite Docker Container vor..."
export DOCKER_CLIENT_TIMEOUT=120
export COMPOSE_HTTP_TIMEOUT=120

# Docker Build im Hintergrund
log "Starte Docker Build im Hintergrund..."
nohup bash -c "
    cd $REPO_DIR && \
    docker compose build && \
    echo '✅ Docker Build abgeschlossen - $(date)' >> /home/ubuntu/build.log
" > /home/ubuntu/docker-build.log 2>&1 &

# Start-Skript erstellen
cat > /home/ubuntu/start-whisperx.sh << 'STARTEOF'
#!/bin/bash
cd /home/ubuntu/transcript-summarization

if docker images | grep -q transcript-summarization; then
    echo "✅ Docker Image gefunden, starte Container..."
    export DOCKER_CLIENT_TIMEOUT=120
    export COMPOSE_HTTP_TIMEOUT=120
    docker compose up -d
    echo "🚀 WhisperX läuft auf Port 8000!"
    echo "📖 API Docs: http://localhost:8000/docs"
    docker compose logs -f
else
    echo "⏳ Docker Build läuft noch. Status prüfen:"
    tail -f /home/ubuntu/docker-build.log
fi
STARTEOF

chmod +x /home/ubuntu/start-whisperx.sh

# README erstellen
cat > /home/ubuntu/README-WHISPERX.md << 'READMEEOF'
# 🚀 WhisperX FastAPI Setup

## Schnellstart:

1. **HuggingFace Token setzen:**
   ```bash
   cd transcript-summarization
   nano .env  # HF_TOKEN=dein_token_hier
   ```

2. **Container starten:**
   ```bash
   ~/start-whisperx.sh
   ```

3. **API verwenden:**
   - Dokumentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Nützliche Befehle:

```bash
# Status prüfen
cd transcript-summarization && docker compose ps

# Logs anzeigen  
cd transcript-summarization && docker compose logs -f

# Container stoppen
cd transcript-summarization && docker compose down

# Container neustarten
cd transcript-summarization && docker compose restart
```

## Build Status prüfen:
```bash
tail -f ~/docker-build.log
```
READMEEOF

log "✅ Setup abgeschlossen!"
log "📝 Siehe ~/README-WHISPERX.md für Anweisungen"
log "🔧 Setze HF_TOKEN in transcript-summarization/.env"
log "🚀 Starte mit: ~/start-whisperx.sh"

log "Setup-Script beendet. Instanz ist bereit! 🎉"