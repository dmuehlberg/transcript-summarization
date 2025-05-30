#!/bin/bash
# Docker-Container und Image-Analyzer
# Dieses Skript analysiert Docker-Container und Images, um ihre Konfiguration zu reproduzieren

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Ausgabe-Datei
OUTPUT_FILE="docker_analysis_$(hostname)_$(date +%Y%m%d_%H%M%S).txt"

# Log-Funktionen
log() { echo -e "${GREEN}[INFO] $1${NC}" | tee -a "$OUTPUT_FILE"; }
section() { echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}" | tee -a "$OUTPUT_FILE"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}" | tee -a "$OUTPUT_FILE"; }
error() { echo -e "${RED}[ERROR] $1${NC}" | tee -a "$OUTPUT_FILE"; }

# Prüfen, ob Docker installiert ist
if ! command -v docker &> /dev/null; then
    error "Docker ist nicht installiert oder nicht im PATH."
    exit 1
fi

# Einleitung
echo "Docker-Container und Image-Analyzer" | tee "$OUTPUT_FILE"
echo "Generiert am $(date)" | tee -a "$OUTPUT_FILE"
echo "Hostname: $(hostname)" | tee -a "$OUTPUT_FILE"
echo "---------------------------------------------" | tee -a "$OUTPUT_FILE"

# 1. Docker-Umgebung
section "DOCKER-UMGEBUNG"
log "Docker-Version:"
docker version | tee -a "$OUTPUT_FILE"

log "Docker-Info (System-Details):"
docker info | tee -a "$OUTPUT_FILE"

# 2. Laufende Container
section "LAUFENDE CONTAINER"
log "Aktuell laufende Container:"
docker ps | tee -a "$OUTPUT_FILE"

# 3. Alle Container (inkl. gestoppte)
section "ALLE CONTAINER"
log "Alle Container (inkl. gestoppte):"
docker ps -a | tee -a "$OUTPUT_FILE"

# 4. Docker-Images
section "DOCKER-IMAGES"
log "Verfügbare Docker-Images:"
docker images | tee -a "$OUTPUT_FILE"

# 5. Docker-Netzwerke
section "DOCKER-NETZWERKE"
log "Konfigurierte Docker-Netzwerke:"
docker network ls | tee -a "$OUTPUT_FILE"

# 6. Docker-Volumes
section "DOCKER-VOLUMES"
log "Konfigurierte Docker-Volumes:"
docker volume ls | tee -a "$OUTPUT_FILE"

# 7. Detaillierte Analyse aller WhisperX-bezogenen Container
section "WHISPERX-CONTAINER-ANALYSE"

WHISPERX_CONTAINERS=$(docker ps -a --format "{{.Names}}" | grep -i "whisper\|transcrib\|speech")

if [ -n "$WHISPERX_CONTAINERS" ]; then
    for CONTAINER in $WHISPERX_CONTAINERS; do
        log "Detaillierte Analyse für Container: $CONTAINER"
        
        log "Container-Inspect (Konfiguration):"
        docker inspect "$CONTAINER" | tee -a "$OUTPUT_FILE"
        
        log "Container-Umgebungsvariablen:"
        docker exec "$CONTAINER" env 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "Konnte Umgebungsvariablen nicht abrufen - Container nicht aktiv?" | tee -a "$OUTPUT_FILE"
        
        log "Container-Logs (letzte 20 Zeilen):"
        docker logs "$CONTAINER" --tail 20 2>&1 | tee -a "$OUTPUT_FILE"
        
        log "Installierte Python-Pakete im Container:"
        docker exec "$CONTAINER" pip list 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "Konnte pip-Pakete nicht abrufen - Container nicht aktiv oder pip nicht installiert?" | tee -a "$OUTPUT_FILE"
        
        log "NVIDIA-Sichtbarkeit im Container:"
        docker exec "$CONTAINER" nvidia-smi 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "NVIDIA-SMI nicht verfügbar im Container" | tee -a "$OUTPUT_FILE"
    done
else
    warn "Keine WhisperX-bezogenen Container gefunden."
fi

# 8. Detaillierte Analyse aller WhisperX-bezogenen Images
section "WHISPERX-IMAGE-ANALYSE"

WHISPERX_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -i "whisper\|transcrib\|speech")

if [ -n "$WHISPERX_IMAGES" ]; then
    for IMAGE in $WHISPERX_IMAGES; do
        log "Detaillierte Analyse für Image: $IMAGE"
        
        log "Image-History (Build-Schritte):"
        docker history --no-trunc "$IMAGE" | tee -a "$OUTPUT_FILE"
        
        log "Image-Inspect (Konfiguration):"
        docker inspect "$IMAGE" | tee -a "$OUTPUT_FILE"
        
        # Container temporär starten, um Informationen zu sammeln
        log "Temporärer Container für weitere Analyse:"
        TEMP_CONTAINER=$(docker run -d --entrypoint=/bin/sh "$IMAGE" -c "sleep 60" 2>/dev/null)
        
        if [ -n "$TEMP_CONTAINER" ]; then
            log "Dateisystem-Struktur (wichtige Verzeichnisse):"
            docker exec "$TEMP_CONTAINER" find /app -type f -name "*.py" 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "Kein /app-Verzeichnis gefunden" | tee -a "$OUTPUT_FILE"
            
            log "Installierte Python-Pakete:"
            docker exec "$TEMP_CONTAINER" pip list 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "pip nicht verfügbar im Image" | tee -a "$OUTPUT_FILE"
            
            log "Betriebssystem-Informationen:"
            docker exec "$TEMP_CONTAINER" cat /etc/os-release 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "Keine OS-Release-Informationen verfügbar" | tee -a "$OUTPUT_FILE"
            
            log "CUDA und GPU-Informationen:"
            docker exec "$TEMP_CONTAINER" bash -c "ldconfig -p | grep -i cuda" 2>/dev/null | tee -a "$OUTPUT_FILE" || echo "ldconfig nicht verfügbar" | tee -a "$OUTPUT_FILE"
            
            # Container aufräumen
            docker stop "$TEMP_CONTAINER" >/dev/null
            docker rm "$TEMP_CONTAINER" >/dev/null
        else
            warn "Konnte keinen temporären Container für $IMAGE starten."
        fi
    done
else
    warn "Keine WhisperX-bezogenen Images gefunden."
fi

# 9. Docker-Compose-Dateien
section "DOCKER-COMPOSE-DATEIEN"
log "Docker-Compose-Dateien im System:"
find / -name "docker-compose.yml" -o -name "docker-compose.yaml" 2>/dev/null | grep -v "/proc/" | head -10 | tee -a "$OUTPUT_FILE"

log "Inhalt der gefundenen Docker-Compose-Dateien:"
for COMPOSE_FILE in $(find / -name "docker-compose.yml" -o -name "docker-compose.yaml" 2>/dev/null | grep -v "/proc/" | head -5); do
    log "Datei: $COMPOSE_FILE"
    cat "$COMPOSE_FILE" | tee -a "$OUTPUT_FILE"
done

# 10. Dockerfile-Suche
section "DOCKERFILE-SUCHE"
log "Dockerfiles im System:"
find / -name "Dockerfile" -o -name "dockerfile" 2>/dev/null | grep -v "/proc/" | head -10 | tee -a "$OUTPUT_FILE"

log "Inhalt der gefundenen Dockerfiles:"
for DOCKERFILE in $(find / -name "Dockerfile" -o -name "dockerfile" 2>/dev/null | grep -v "/proc/" | head -5); do
    log "Datei: $DOCKERFILE"
    cat "$DOCKERFILE" | tee -a "$OUTPUT_FILE"
done

# 11. Reproduktionsanleitung generieren
section "REPRODUKTIONSANLEITUNG"
log "Basierend auf der Analyse, hier ist eine Anleitung zur Reproduktion der Docker-Umgebung:"

cat << EOF | tee -a "$OUTPUT_FILE"
# Anleitung zur Reproduktion der Docker-Umgebung

## 1. Docker installieren
# Installiere Docker (falls noch nicht geschehen):
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker \$USER

## 2. NVIDIA Docker einrichten (für GPU-Support)
# Für Ubuntu/Debian:
distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.repo | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

EOF

# Füge Docker-Compose-Anweisungen hinzu, wenn Compose-Dateien gefunden wurden
COMPOSE_FILES=$(find / -name "docker-compose.yml" -o -name "docker-compose.yaml" 2>/dev/null | grep -v "/proc/" | head -1)
if [ -n "$COMPOSE_FILES" ]; then
    cat << EOF | tee -a "$OUTPUT_FILE"
## 3. Docker Compose einrichten
# Erstelle ein Verzeichnis für das Projekt:
mkdir -p whisperx_project
cd whisperx_project

# Erstelle die docker-compose.yml Datei mit folgendem Inhalt:
cat > docker-compose.yml << 'EOFCOMPOSE'
$(cat "$COMPOSE_FILES")
EOFCOMPOSE

# Erstelle eine .env Datei mit Umgebungsvariablen:
cat > .env << 'EOFENV'
POSTGRES_USER=root
POSTGRES_PASSWORD=postgres
POSTGRES_DB=n8n
HF_TOKEN=your_huggingface_token_here
# Weitere Umgebungsvariablen je nach Bedarf
EOFENV

# Starte die Container:
docker-compose up -d
EOF
else
    # Fallback: Manuelle Docker-Anweisungen, wenn keine Compose-Datei gefunden wurde
    cat << EOF | tee -a "$OUTPUT_FILE"
## 3. Container manuell starten
# Erstelle ein Netzwerk:
docker network create whisperx-network

# Starte den WhisperX-Container:
docker run -d \\
  --name whisperx \\
  --gpus all \\
  -p 8000:8000 \\
  -e HF_TOKEN=your_huggingface_token_here \\
  -e DEVICE=cuda \\
  -e COMPUTE_TYPE=float16 \\
  whisperx_cuda
EOF
fi

section "ZUSAMMENFASSUNG"
log "Docker-Analysebericht wurde in $OUTPUT_FILE gespeichert."
log "Verwende diesen Bericht, um die Docker-Umgebung auf deiner eigenen AWS-Instanz zu reproduzieren."

# Berechtigungen für die Ausgabe-Datei setzen
chmod 644 "$OUTPUT_FILE"
echo "Die Docker-Analyse ist abgeschlossen. Der Bericht wurde in $OUTPUT_FILE gespeichert."