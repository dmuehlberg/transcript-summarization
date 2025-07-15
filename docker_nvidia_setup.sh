#!/bin/bash

echo "=== NVIDIA DOCKER SETUP FÜR AWS ==="

# 1. Prüfe aktuelle Docker Konfiguration
echo "1. AKTUELLE DOCKER KONFIGURATION:"
echo "=================================="
docker info | grep -i runtime
echo

# 2. Installiere/Konfiguriere NVIDIA Container Runtime
echo "2. NVIDIA CONTAINER RUNTIME SETUP:"
echo "=================================="

# Für Amazon Linux 2
if [ -f /etc/amazon-linux-release ]; then
    echo "Amazon Linux 2 erkannt - Installiere nvidia-container-runtime..."
    
    # Add NVIDIA repository
    curl -s -L https://nvidia.github.io/nvidia-container-runtime/amazonlinux2/nvidia-container-runtime.repo | \
        sudo tee /etc/yum.repos.d/nvidia-container-runtime.repo
    
    # Install nvidia-container-runtime
    sudo yum install -y nvidia-container-runtime
    
    # Configure Docker daemon
    sudo mkdir -p /etc/docker
    cat << 'EOF' | sudo tee /etc/docker/daemon.json
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF
    
    # Restart Docker
    sudo systemctl restart docker
    
    echo "✓ NVIDIA Container Runtime installiert und konfiguriert"
fi

# Für Ubuntu (falls verwendet)
if [ -f /etc/lsb-release ] && grep -q "Ubuntu" /etc/lsb-release; then
    echo "Ubuntu erkannt - Installiere nvidia-docker2..."
    
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
        sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    
    sudo apt-get update
    sudo apt-get install -y nvidia-docker2
    sudo systemctl restart docker
    
    echo "✓ nvidia-docker2 installiert"
fi

# 3. Test NVIDIA Docker Runtime
echo
echo "3. NVIDIA DOCKER RUNTIME TEST:"
echo "=============================="
echo "Testing nvidia runtime..."
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

echo
echo "Testing mit nvidia runtime (falls konfiguriert):"
docker run --rm --runtime=nvidia nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# 4. Konfigurationsprüfung
echo
echo "4. FINAL CONFIGURATION CHECK:"
echo "============================="
echo "Docker Info (Runtime):"
docker info | grep -A 10 -i runtime

echo
echo "Docker Daemon Configuration:"
sudo cat /etc/docker/daemon.json 2>/dev/null || echo "Keine daemon.json gefunden"

echo
echo "=== SETUP ABGESCHLOSSEN ==="
echo "Verwenden Sie nun eine der folgenden Optionen in docker-compose.yml:"
echo
echo "Option 1 - Runtime nvidia (wenn konfiguriert):"
echo "  runtime: nvidia"
echo
echo "Option 2 - GPU Resources (moderner Ansatz):"
echo "  deploy:"
echo "    resources:"
echo "      reservations:"
echo "        devices:"
echo "          - driver: nvidia"
echo "            count: 1"
echo "            capabilities: [gpu]"
echo
echo "Option 3 - Command Line:"
echo "  docker run --gpus all your_image"