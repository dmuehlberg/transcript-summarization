#!/bin/bash
# Umfassender System-Analyzer für CUDA/GPU-Umgebung
# Dieses Skript sammelt detaillierte Informationen über eine CUDA/GPU-Umgebung,
# um diese auf einer anderen Maschine reproduzieren zu können.

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Ausgabe-Datei
OUTPUT_FILE="system_analysis_$(hostname)_$(date +%Y%m%d_%H%M%S).txt"

# Log-Funktionen
log() { echo -e "${GREEN}[INFO] $1${NC}" | tee -a "$OUTPUT_FILE"; }
section() { echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}" | tee -a "$OUTPUT_FILE"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}" | tee -a "$OUTPUT_FILE"; }
error() { echo -e "${RED}[ERROR] $1${NC}" | tee -a "$OUTPUT_FILE"; }

# Hilfreiche Funktionen
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Einleitung
echo "Umfassender System-Analyzer für CUDA/GPU-Umgebung" | tee "$OUTPUT_FILE"
echo "Generiert am $(date)" | tee -a "$OUTPUT_FILE"
echo "Hostname: $(hostname)" | tee -a "$OUTPUT_FILE"
echo "---------------------------------------------" | tee -a "$OUTPUT_FILE"

# 1. Systeminformationen
section "SYSTEMINFORMATIONEN"
log "Betriebssystem:"
cat /etc/os-release | tee -a "$OUTPUT_FILE"

log "Kernel-Version:"
uname -a | tee -a "$OUTPUT_FILE"

if command_exists lsb_release; then
    log "LSB Release Information:"
    lsb_release -a 2>/dev/null | tee -a "$OUTPUT_FILE"
fi

log "CPU-Informationen:"
lscpu | grep -E "Model name|Architecture|CPU\(s\)|Thread|Core|Socket|MHz" | tee -a "$OUTPUT_FILE"

log "RAM-Informationen:"
free -h | tee -a "$OUTPUT_FILE"

log "Festplattenspeicher:"
df -h | grep -v "tmpfs\|udev" | tee -a "$OUTPUT_FILE"

# 2. AWS-spezifische Informationen
section "AWS-INFORMATIONEN"
if curl -s http://169.254.169.254/latest/meta-data/ >/dev/null 2>&1; then
    log "EC2-Instance-Metadaten gefunden!"
    
    log "Instance-ID:"
    curl -s http://169.254.169.254/latest/meta-data/instance-id | tee -a "$OUTPUT_FILE"
    
    log "Instance-Typ:"
    curl -s http://169.254.169.254/latest/meta-data/instance-type | tee -a "$OUTPUT_FILE"
    
    log "AMI-ID:"
    curl -s http://169.254.169.254/latest/meta-data/ami-id | tee -a "$OUTPUT_FILE"
    
    log "Region:"
    curl -s http://169.254.169.254/latest/meta-data/placement/region | tee -a "$OUTPUT_FILE" 2>/dev/null
    if [ $? -ne 0 ]; then
        curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/[a-z]$//' | tee -a "$OUTPUT_FILE"
    fi
else
    warn "Keine EC2-Instance-Metadaten gefunden."
fi

# 3. NVIDIA-GPU und CUDA
section "NVIDIA-GPU UND CUDA"
if command_exists nvidia-smi; then
    log "NVIDIA-GPU erkannt!"
    log "GPU-Details (nvidia-smi):"
    nvidia-smi | tee -a "$OUTPUT_FILE"
    
    log "Treiber-Version und CUDA-Version:"
    nvidia-smi --query-gpu=driver_version,cuda_version --format=csv,noheader | tee -a "$OUTPUT_FILE"
    
    log "Detaillierte GPU-Informationen:"
    nvidia-smi -q | grep -E "Product Name|CUDA Version|Driver Version|GPU UUID|VBIOS|Memory|Bar1|Power|Temp" | tee -a "$OUTPUT_FILE"
else
    warn "NVIDIA-Tools nicht gefunden oder GPU nicht verfügbar."
fi

if command_exists nvcc; then
    log "CUDA Compiler (nvcc) gefunden!"
    log "NVCC-Version:"
    nvcc --version | tee -a "$OUTPUT_FILE"
else
    warn "CUDA Compiler (nvcc) nicht gefunden."
fi

# 4. Installierte Pakete
section "INSTALLIERTE PAKETE"
if command_exists apt; then
    log "Debian/Ubuntu-basiertes System erkannt."
    log "Wichtige installierte Pakete (Entwicklung, CUDA, Python):"
    apt list --installed 2>/dev/null | grep -E "cuda|nvidia|python|dev|build|gcc|g\+\+|cmake|git|ffmpeg|libnvidia|libcudnn" | tee -a "$OUTPUT_FILE"
elif command_exists yum; then
    log "Red Hat/CentOS/Fedora-basiertes System erkannt."
    log "Wichtige installierte Pakete (Entwicklung, CUDA, Python):"
    yum list installed | grep -E "cuda|nvidia|python|dev|devel|gcc|g\+\+|cmake|git|ffmpeg|libnvidia|libcudnn" | tee -a "$OUTPUT_FILE"
else
    warn "Kein bekanntes Paketsystem gefunden."
fi

# 5. Python-Umgebung
section "PYTHON-UMGEBUNG"
if command_exists python || command_exists python3; then
    PYTHON_CMD="python3"
    if ! command_exists python3; then
        PYTHON_CMD="python"
    fi
    
    log "Python-Version:"
    $PYTHON_CMD --version | tee -a "$OUTPUT_FILE"
    
    log "Python-Pfad:"
    which $PYTHON_CMD | tee -a "$OUTPUT_FILE"
    
    log "Installierte Python-Pakete (pip):"
    if command_exists pip3; then
        pip3 list | tee -a "$OUTPUT_FILE"
    elif command_exists pip; then
        pip list | tee -a "$OUTPUT_FILE"
    else
        warn "Pip nicht gefunden."
    fi
    
    log "Python kann CUDA sehen?"
    $PYTHON_CMD -c "
import sys
print('Python-Version:', sys.version)
try:
    import torch
    print('PyTorch-Version:', torch.__version__)
    print('CUDA verfügbar:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('CUDA-Version:', torch.version.cuda)
        print('GPU-Name:', torch.cuda.get_device_name(0))
except ImportError:
    print('PyTorch ist nicht installiert')
try:
    import tensorflow as tf
    print('TensorFlow-Version:', tf.__version__)
    print('TensorFlow sieht GPUs:', tf.config.list_physical_devices('GPU'))
except ImportError:
    print('TensorFlow ist nicht installiert')
" | tee -a "$OUTPUT_FILE"
else
    warn "Python nicht gefunden."
fi

# 6. Docker und Container
section "DOCKER UND CONTAINER"
if command_exists docker; then
    log "Docker gefunden!"
    log "Docker-Version:"
    docker --version | tee -a "$OUTPUT_FILE"
    
    log "Docker-Dienst-Status:"
    systemctl status docker 2>/dev/null | grep "Active:" | tee -a "$OUTPUT_FILE"
    
    log "Laufende Container:"
    docker ps | tee -a "$OUTPUT_FILE"
    
    log "Alle vorhandenen Images:"
    docker images | tee -a "$OUTPUT_FILE"
    
    log "Docker-Compose-Dateien finden:"
    find / -name "docker-compose.yml" -o -name "docker-compose.yaml" 2>/dev/null | head -10 | tee -a "$OUTPUT_FILE"
else
    warn "Docker nicht gefunden."
fi

# 7. Umgebungsvariablen
section "UMGEBUNGSVARIABLEN"
log "Wichtige Umgebungsvariablen für CUDA und ML:"
env | grep -E "CUDA|LD_LIBRARY|NVIDIA|TORCH|PYTHON|VIRTUAL|CONDA|PATH|TF_|TENSORFLOW|NV|OMP_NUM_THREADS|MKL|NUMBA|HF_|HUGGING|TRANSFORMERS" | tee -a "$OUTPUT_FILE"

# 8. Systemdienste
section "SYSTEMDIENSTE"
if command_exists systemctl; then
    log "Relevante aktive Dienste:"
    systemctl list-units --type=service --state=active | grep -E "nvidia|cuda|docker|gpu|ml|ai|python|jupyter|tensor|torch" | tee -a "$OUTPUT_FILE"
fi

# 9. Laufende Prozesse
section "LAUFENDE PROZESSE"
log "Relevante laufende Prozesse:"
ps aux | grep -E "python|nvidia|cuda|docker|gpu|ml|ai|jupyter|tensor|torch|whisper" | grep -v grep | tee -a "$OUTPUT_FILE"

# 10. Netzwerkverbindungen
section "NETZWERKVERBINDUNGEN"
log "Offene Ports und Verbindungen:"
if command_exists ss; then
    ss -tuln | tee -a "$OUTPUT_FILE"
elif command_exists netstat; then
    netstat -tuln | tee -a "$OUTPUT_FILE"
fi

# 11. CUDA-Bibliotheken
section "CUDA-BIBLIOTHEKEN"
log "CUDA-Bibliotheken im System:"
find /usr -name "libcudnn*" -o -name "libcuda*" -o -name "libnvidia*" 2>/dev/null | sort | tee -a "$OUTPUT_FILE"

log "Dynamische Bibliotheken für ML-Frameworks:"
find /usr -name "libtorch*" -o -name "libtensorflow*" -o -name "libonnx*" 2>/dev/null | sort | tee -a "$OUTPUT_FILE"

# 12. Neuere WhisperX-Dateien
section "WHISPERX-DATEIEN"
log "Kürzlich bearbeitete WhisperX-bezogene Dateien:"
find / -type f -name "*whisper*" -o -name "*transcript*" -mtime -14 2>/dev/null | grep -v "/proc/" | head -20 | tee -a "$OUTPUT_FILE"

# 13. Installationsanleitung generieren
section "INSTALLATIONSANLEITUNG"
log "Basierend auf der Analyse, hier ist eine Installationsanleitung für eine ähnliche Umgebung:"

cat << EOF | tee -a "$OUTPUT_FILE"
# Installationsschritte für eine ähnliche Umgebung

## 1. Betriebssystem
Das analysierte System basiert auf $(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2).
Stelle sicher, dass du ein ähnliches Betriebssystem verwendest.

## 2. NVIDIA-Treiber und CUDA
Installiere die NVIDIA-Treiber und CUDA wie folgt:
EOF

if command_exists nvidia-smi; then
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    CUDA_VERSION=$(nvidia-smi --query-gpu=cuda_version --format=csv,noheader | head -1 | sed 's/\./\./g')
    echo "# Installiere NVIDIA-Treiber Version $DRIVER_VERSION" | tee -a "$OUTPUT_FILE"
    echo "# Installiere CUDA Version $CUDA_VERSION" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get update" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get install -y build-essential" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get install -y linux-headers-\$(uname -r)" | tee -a "$OUTPUT_FILE"
    echo "# Lade den NVIDIA-Treiber von https://www.nvidia.com/Download/index.aspx herunter" | tee -a "$OUTPUT_FILE"
    echo "# Lade CUDA von https://developer.nvidia.com/cuda-downloads herunter" | tee -a "$OUTPUT_FILE"
fi

cat << EOF | tee -a "$OUTPUT_FILE"

## 3. Python und Pakete
EOF

if command_exists python3; then
    PY_VERSION=$(python3 --version 2>&1)
    echo "# Installiere $PY_VERSION" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get install -y python3 python3-pip python3-dev" | tee -a "$OUTPUT_FILE"
    
    if command_exists pip3; then
        echo -e "\n# Installiere wichtige Python-Pakete:" | tee -a "$OUTPUT_FILE"
        pip3 list | grep -E "torch|numpy|tensorflow|whisper|transformers|ffmpeg|pydub" | awk '{print "pip3 install " $1 "==" $2}' | tee -a "$OUTPUT_FILE"
    fi
fi

cat << EOF | tee -a "$OUTPUT_FILE"

## 4. Docker (falls verwendet)
EOF

if command_exists docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo "# Installiere Docker Version $DOCKER_VERSION" | tee -a "$OUTPUT_FILE"
    echo "curl -fsSL https://get.docker.com -o get-docker.sh" | tee -a "$OUTPUT_FILE"
    echo "sudo sh get-docker.sh" | tee -a "$OUTPUT_FILE"
    echo "sudo usermod -aG docker \$USER" | tee -a "$OUTPUT_FILE"
    
    if [ -f /usr/bin/docker-compose ] || [ -f /usr/local/bin/docker-compose ]; then
        DC_VERSION=$(docker-compose --version 2>/dev/null | awk '{print $3}' | sed 's/,//')
        echo "# Installiere Docker Compose Version $DC_VERSION" | tee -a "$OUTPUT_FILE"
        echo "sudo curl -L \"https://github.com/docker/compose/releases/download/$DC_VERSION/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose" | tee -a "$OUTPUT_FILE"
        echo "sudo chmod +x /usr/local/bin/docker-compose" | tee -a "$OUTPUT_FILE"
    fi
    
    echo -e "\n# Konfiguriere NVIDIA Docker:" | tee -a "$OUTPUT_FILE"
    echo "distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)" | tee -a "$OUTPUT_FILE"
    echo "curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get update" | tee -a "$OUTPUT_FILE"
    echo "sudo apt-get install -y nvidia-docker2" | tee -a "$OUTPUT_FILE"
    echo "sudo systemctl restart docker" | tee -a "$OUTPUT_FILE"
fi

cat << EOF | tee -a "$OUTPUT_FILE"

## 5. Wichtige Pakete
Installiere diese zusätzlichen Pakete:
EOF

echo "sudo apt-get install -y ffmpeg libsndfile1 git" | tee -a "$OUTPUT_FILE"

if command_exists nvidia-smi; then
    FOUND_CUDNN=$(find /usr -name "libcudnn*" 2>/dev/null | head -1)
    if [ -n "$FOUND_CUDNN" ]; then
        echo "# Installiere cuDNN (herunterladbar von https://developer.nvidia.com/cudnn)" | tee -a "$OUTPUT_FILE"
    fi
fi

cat << EOF | tee -a "$OUTPUT_FILE"

## 6. WhisperX
# WhisperX installieren:
git clone https://github.com/dmuehlberg/transcript-summarization.git
cd transcript-summarization

# Falls die Umgebung HF_TOKEN benötigt, setze ihn:
export HF_TOKEN=your_huggingface_token_here
EOF

section "ZUSAMMENFASSUNG"
log "Analysebericht wurde in $OUTPUT_FILE gespeichert."
log "Verwende diesen Bericht, um eine ähnliche Umgebung auf deiner eigenen AWS-Instanz zu erstellen."

# Berechtigungen für die Ausgabe-Datei setzen
chmod 644 "$OUTPUT_FILE"
echo "Die Analyse ist abgeschlossen. Der Bericht wurde in $OUTPUT_FILE gespeichert."