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
  
  # Aktiviere die Nutzung von Proxy-Servern (wie deb-cache)
  echo 'Acquire::http::Proxy-Auto-Detect "/usr/bin/apt-proxy-detect";' > /etc/apt/apt.conf.d/99proxy-auto-detect
}

# Repository-URL aktualisieren mit fix für sed-Fehler
update_repository_url() {
  local repo="$1"
  log "Aktualisiere APT-Repository-URL auf $repo..."
  
  # Sichere die originale sources.list
  cp /etc/apt/sources.list /etc/apt/sources.list.original || true
  
  # Direkter String-Ersatz ohne sed
  if [ -f /etc/apt/sources.list ]; then
    # Schreibe neue sources.list mit dem Repository
    cat > /etc/apt/sources.list.new << EOF
deb $repo jammy main restricted universe multiverse
deb $repo jammy-updates main restricted universe multiverse
deb $repo jammy-backports main restricted universe multiverse
deb $repo jammy-security main restricted universe multiverse
EOF
    
    # Ersetze die alte Datei
    mv /etc/apt/sources.list.new /etc/apt/sources.list
  else
    warn "sources.list nicht gefunden, erstelle neue..."
    cat > /etc/apt/sources.list << EOF
deb $repo jammy main restricted universe multiverse
deb $repo jammy-updates main restricted universe multiverse
deb $repo jammy-backports main restricted universe multiverse
deb $repo jammy-security main restricted universe multiverse
EOF
  fi
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
    
    # Zwischen verschiedenen Repositories wechseln
    if [ $((retry_count % 3)) -eq 0 ]; then
      if [ $((retry_count % 6)) -eq 0 ]; then
        update_repository_url "http://de.archive.ubuntu.com/ubuntu"
      else
        update_repository_url "http://us.archive.ubuntu.com/ubuntu"
      fi
      apt-get update || true
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
  
  # Setze Standard-Repository
  update_repository_url "http://de.archive.ubuntu.com/ubuntu"
  
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
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 || true
  }
  
  apt-get update || true
  
  # Installiere Python und weitere Abhängigkeiten
  log "Installiere Python ${PYTHON_VERSION} und Abhängigkeiten..."
  install_packages_with_retry python${PYTHON_VERSION} python3-pip python${PYTHON_VERSION}-venv
  
  # Installiere Git ohne GUI
  log "Installiere Git..."
  install_packages_with_retry git-core || install_packages_with_retry git
  
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
  ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 || true
  ln -s -f /usr/bin/python${PYTHON_VERSION} /usr/bin/python || true
  
  # Installiere UV für Python-Paketinstallation
  log "Installiere UV für Python-Paketinstallation..."
  TEMPDIR=$(mktemp -d)
  cd "$TEMPDIR"
  wget -q https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
  tar -xzf uv-x86_64-unknown-linux-gnu.tar.gz
  mv uv /usr/local/bin/uv
  chmod +x /usr/local/bin/uv
  cd -
  rm -rf "$TEMPDIR"
  
  # Installiere PyTorch und andere Python-Pakete direkt mit pip
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