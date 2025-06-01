#!/bin/bash

# WhisperX Container Setup
# Für den Fall, dass du direkt auf einem Server arbeitest

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# Diese Funktion erstellt ein neues, minimales Dockerfile
create_minimal_dockerfile() {
    local dockerfile_dir="$1"
    local setup_script="$2"
    
    log "Erstelle minimales Dockerfile zur Umgehung der 403 Forbidden Fehler..."
    
    # Erstelle Verzeichnis für das Setup-Skript
    mkdir -p "$dockerfile_dir"
    
    # Erstelle das Setup-Skript
    cat > "$setup_script" << 'SCRIPT_EOF'
#!/bin/bash
# setup_container.sh - Robuster Setup-Skript für WhisperX CUDA-Container
set -e

# Error-Handling
trap 'echo "Ein Fehler ist aufgetreten. Führe Fallback-Installation durch..."' ERR

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Log-Funktionen
log() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# Variablen
PYTHON_VERSION=${PYTHON_VERSION:-3.11}
MAX_RETRIES=10
REPOSITORIES=(
  "http://nl.archive.ubuntu.com/ubuntu"
  "http://de.archive.ubuntu.com/ubuntu"
  "http://us.archive.ubuntu.com/ubuntu"
  "http://gb.archive.ubuntu.com/ubuntu"
  "http://fr.archive.ubuntu.com/ubuntu"
  "http://jp.archive.ubuntu.com/ubuntu"
  "http://sg.archive.ubuntu.com/ubuntu"
)

# Funktion zum Testen von Repositories
test_repository() {
  local repo=$1
  if curl -s --head "$repo/dists/jammy/Release" | grep -q "200 OK"; then
    return 0
  else
    return 1
  fi
}

# Finde das beste Repository
find_best_repository() {
  log "Suche nach dem besten Ubuntu-Repository..."
  
  for repo in "${REPOSITORIES[@]}"; do
    if test_repository "$repo"; then
      log "Verwende Repository: $repo"
      echo "$repo"
      return 0
    fi
  done
  
  warn "Kein funktionierendes Repository gefunden, verwende Standard-Repository"
  echo "http://archive.ubuntu.com/ubuntu"
}

# Apt-Konfiguration optimieren
configure_apt() {
  log "Konfiguriere APT für robuste Paketinstallation..."
  
  # Mehr Retries für apt
  echo 'APT::Acquire::Retries "10";' > /etc/apt/apt.conf.d/80-retries
  # Längeres Timeout
  echo 'Acquire::http::Timeout "180";' > /etc/apt/apt.conf.d/99timeout
  echo 'Acquire::ftp::Timeout "180";' >> /etc/apt/apt.conf.d/99timeout
  
  # Fix für "Temporary failure resolving"
  echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4
  
  # Fix für "403 Forbidden" durch User-Agent
  echo 'Acquire::http::User-Agent "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0";' > /etc/apt/apt.conf.d/99user-agent
}

# Repository-URL aktualisieren
update_repository_url() {
  local repo=$1
  log "Aktualisiere APT-Repository-URL auf $repo..."
  
  # Sichere die originale sources.list
  cp /etc/apt/sources.list /etc/apt/sources.list.original
  
  # Ersetze den Server in sources.list
  sed -i "s|http://archive.ubuntu.com/ubuntu|$repo|g" /etc/apt/sources.list
  sed -i "s|http://security.ubuntu.com/ubuntu|$repo|g" /etc/apt/sources.list
}

# Installiere Pakete mit Retry-Mechanismus
install_packages_with_retry() {
  local packages=("$@")
  local retry_count=0
  
  while [ $retry_count -lt $MAX_RETRIES ]; do
    log "Installiere Pakete (Versuch $((retry_count+1))/${MAX_RETRIES})..."
    
    if apt-get -y --no-install-recommends install "${packages[@]}"; then
      log "Paketinstallation erfolgreich"
      return 0
    fi
    
    retry_count=$((retry_count+1))
    warn "Paketinstallation fehlgeschlagen. Versuche es erneut in 5 Sekunden..."
    sleep 5
    
    # Repository wechseln nach einigen Versuchen
    if [ $((retry_count % 3)) -eq 0 ]; then
      local new_repo=$(find_best_repository)
      update_repository_url "$new_repo"
      apt-get update
    fi
  done
  
  error "Konnte Pakete nach ${MAX_RETRIES} Versuchen nicht installieren"
  return 1
}

# Hauptinstallationsfunktion
main_install() {
  log "Starte Installation für WhisperX CUDA-Container..."
  
  # Setze DEBIAN_FRONTEND auf noninteractive
  export DEBIAN_FRONTEND=noninteractive
  
  # Konfiguriere APT
  configure_apt
  
  # Finde das beste Repository
  local best_repo=$(find_best_repository)
  update_repository_url "$best_repo"
  
  # Update apt
  log "Aktualisiere APT-Paketlisten..."
  apt-get update || true
  
  # Installiere essentielle Pakete
  log "Installiere essentielle Pakete..."
  install_packages_with_retry software-properties-common gnupg ca-certificates apt-transport-https curl wget
  
  # PPA für Python hinzufügen
  log "Füge PPA für Python ${PYTHON_VERSION} hinzu..."
  add-apt-repository -y ppa:deadsnakes/ppa || {
    warn "Konnte PPA nicht hinzufügen, versuche alternativen Ansatz..."
    echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu jammy main" > /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-jammy.list
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776
  }
  
  apt-get update || true
  
  # Installiere Python und weitere Abhängigkeiten
  log "Installiere Python ${PYTHON_VERSION} und Abhängigkeiten..."
  install_packages_with_retry python${PYTHON_VERSION} python3-pip python${PYTHON_VERSION}-venv
  
  # Installiere Git ohne GUI
  log "Installiere Git..."
  install_packages_with_retry git-core
  
  # Installiere ffmpeg und libsndfile1 über apt-get
  log "Installiere ffmpeg und libsndfile1..."
  {
    install_packages_with_retry ffmpeg libsndfile1
  } || {
    warn "Konnte ffmpeg/libsndfile1 nicht installieren, versuche alternatives Repository..."
    add-apt-repository -y universe
    apt-get update
    install_packages_with_retry ffmpeg libsndfile1
  }
  
  # Python-Links erstellen
  log "Erstelle Python-Links..."
  ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3
  ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python
  
  # Installiere UV für Python-Paketinstallation
  log "Installiere UV für Python-Paketinstallation..."
  curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz | tar -xzf - -C /tmp
  mv /tmp/uv /usr/local/bin/uv
  chmod +x /usr/local/bin/uv
  
  # Installiere PyTorch und andere Python-Pakete
  log "Installiere PyTorch und Abhängigkeiten..."
  pip3 install --no-cache-dir torch==2.1.0+cu121 torchvision==0.16.0+cu121 torchaudio==2.1.0+cu121 -f https://download.pytorch.org/whl/cu121/torch_stable.html
  pip3 install --no-cache-dir numba==0.61.0
  pip3 install --no-cache-dir colorlog==6.9.0 fastapi==0.115.12 gunicorn==23.0.0 httpx==0.28.1 python-dotenv==1.1.0 python-multipart==0.0.20 tqdm==4.67.1 uvicorn==0.34.2 whisperx==3.3.3
  
  # Aufräumen
  log "Räume auf..."
  apt-get clean
  rm -rf /var/lib/apt/lists/*
  
  log "Installation abgeschlossen!"
}

# Führe die Hauptinstallation aus
main_install
SCRIPT_EOF

    # Erstelle das minimale Dockerfile
    cat > "$dockerfile_dir/dockerfile" << 'DOCKERFILE_EOF'
# Verwenden eines stabileren CUDA-Images mit cuDNN
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV PYTHON_VERSION=3.11
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/cuda/include:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

# Kopiere ein Skript zum Container-Setup
COPY setup_container.sh /tmp/setup_container.sh
RUN chmod +x /tmp/setup_container.sh && /tmp/setup_container.sh

WORKDIR /app

# Copy application code
COPY app app/
COPY tests tests/
COPY app/gunicorn_logging.conf .
COPY requirements requirements/

# Zeige die verfügbaren cuDNN-Bibliotheken für Diagnose 
RUN find /usr -name "libcudnn*.so*" 2>/dev/null | sort

# Verifiziere die PyTorch-Installation
RUN python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('PyTorch version:', torch.__version__); print('CUDA version:', torch.version.cuda if torch.cuda.is_available() else 'N/A')"

EXPOSE 8000

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "0", "--log-config", "gunicorn_logging.conf", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
DOCKERFILE_EOF

    chmod +x "$setup_script"
    log "Minimales Dockerfile und Setup-Skript erstellt."
}

main() {
    log "WhisperX Container Setup gestartet"
    
    # Repository klonen/aktualisieren
    if [ -d "transcript-summarization" ]; then
        warning "Repository existiert bereits"
        cd transcript-summarization
        git pull origin main || git pull origin master || true
        cd ..
    else
        log "Klone Repository..."
        git clone https://github.com/dmuehlberg/transcript-summarization.git
    fi
    
    cd transcript-summarization
    
    # Docker Setup
    log "Setze Docker Timeouts..."
    export DOCKER_CLIENT_TIMEOUT=300
    export COMPOSE_HTTP_TIMEOUT=300
    
    log "Stoppe alte Container..."
    docker compose down 2>/dev/null || true
    
    # Erstelle minimales Dockerfile
    log "Ersetze vorhandenes Dockerfile mit robusterer Alternative..."
    DOCKERFILE_DIR="whisperX-FastAPI-cuda"
    SETUP_SCRIPT="$DOCKERFILE_DIR/setup_container.sh"
    
    # Sichere das originale Dockerfile
    if [ -f "$DOCKERFILE_DIR/dockerfile" ]; then
        cp "$DOCKERFILE_DIR/dockerfile" "$DOCKERFILE_DIR/dockerfile.original"
        log "Originales Dockerfile gesichert als dockerfile.original"
    fi
    
    # Erstelle minimales Dockerfile und Setup-Skript
    create_minimal_dockerfile "$DOCKERFILE_DIR" "$SETUP_SCRIPT"
    
    log "Baue Container whisperx_cuda mit erhöhten Timeouts (kann 10-15 Minuten dauern)..."
    # Verwende BuildKit für bessere Build-Performance und Cache-Nutzung
    DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain docker compose build --no-cache whisperx_cuda
    
    log "Starte Container..."
    docker compose up -d whisperx_cuda
    
    sleep 5
    
    log "Setup abgeschlossen!"
    info "API: http://localhost:8000/docs"
    info "Status: docker compose ps"
    info "Logs: docker compose logs -f"
    
    # Logs anzeigen?
    read -p "Logs anzeigen? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose logs -f
    fi
}

main "$@"