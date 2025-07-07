#!/bin/bash

echo "=== CUDA DIAGNOSE SUITE ==="
echo "Datum: $(date)"
echo

# 1. HOST-SYSTEM PRÜFUNG
echo "1. HOST-SYSTEM INFORMATIONEN:"
echo "================================="
echo "NVIDIA Treiber Version:"
nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits
echo

echo "CUDA Version auf Host:"
nvcc --version 2>/dev/null || echo "nvcc nicht verfügbar auf Host"
echo

echo "NVIDIA Runtime Information:"
nvidia-smi --query-gpu=name,driver_version,cuda_version --format=csv
echo

# 2. DOCKER NVIDIA RUNTIME TEST
echo "2. DOCKER NVIDIA RUNTIME TEST:"
echo "==============================="
echo "Docker Version:"
docker --version
echo

echo "NVIDIA Docker Runtime Test:"
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
echo

# 3. CONTAINER CUDA VERSION TEST
echo "3. CONTAINER CUDA VERSIONEN:"
echo "============================="
echo "Testing verschiedene CUDA Versionen in Containern:"

echo "CUDA 11.8:"
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 sh -c "nvcc --version && nvidia-smi"
echo

echo "CUDA 12.1:"
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 sh -c "nvcc --version && nvidia-smi" 2>/dev/null || echo "CUDA 12.1 nicht verfügbar"
echo

echo "CUDA 12.4:"
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 sh -c "nvcc --version && nvidia-smi" 2>/dev/null || echo "CUDA 12.4 nicht verfügbar"
echo

# 4. PYTORCH CUDA TEST
echo "4. PYTORCH CUDA KOMPATIBILITÄT:"
echo "==============================="
cat > test_pytorch_cuda.py << 'EOF'
import sys
print(f"Python Version: {sys.version}")

try:
    import torch
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA verfügbar: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Version (PyTorch): {torch.version.cuda}")
        print(f"cuDNN Version: {torch.backends.cudnn.version()}")
        print(f"GPU Count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        
        # Test CUDA Tensor
        try:
            x = torch.rand(5, 3).cuda()
            print("CUDA Tensor Test: ERFOLGREICH")
            print(f"Test Tensor: {x}")
        except Exception as e:
            print(f"CUDA Tensor Test FEHLGESCHLAGEN: {e}")
    else:
        print("CUDA nicht verfügbar in PyTorch")
except ImportError as e:
    print(f"PyTorch nicht installiert: {e}")
except Exception as e:
    print(f"Fehler beim PyTorch Test: {e}")
EOF

echo "PyTorch Test mit CUDA 11.8:"
docker run --rm --gpus all -v $(pwd)/test_pytorch_cuda.py:/test.py nvidia/cuda:11.8.0-runtime-ubuntu22.04 sh -c "
    apt-get update > /dev/null 2>&1 && 
    apt-get install -y python3 python3-pip > /dev/null 2>&1 && 
    pip3 install torch==2.0.1+cu118 -f https://download.pytorch.org/whl/cu118 > /dev/null 2>&1 &&
    python3 /test.py
"
echo

echo "PyTorch Test mit CUDA 12.1:"
docker run --rm --gpus all -v $(pwd)/test_pytorch_cuda.py:/test.py nvidia/cuda:12.1.0-runtime-ubuntu22.04 sh -c "
    apt-get update > /dev/null 2>&1 && 
    apt-get install -y python3 python3-pip > /dev/null 2>&1 && 
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 > /dev/null 2>&1 &&
    python3 /test.py
" 2>/dev/null || echo "CUDA 12.1 PyTorch Test fehlgeschlagen"
echo

# 5. WHISPERX SPEZIFISCHER TEST
echo "5. WHISPERX CUDA TEST:"
echo "======================"
cat > test_whisperx_cuda.py << 'EOF'
import os
import sys

print("=== WhisperX CUDA Diagnostics ===")
print(f"Python: {sys.version}")

# Umgebungsvariablen
print("\nUmgebungsvariablen:")
cuda_vars = [k for k in os.environ.keys() if 'CUDA' in k.upper()]
for var in cuda_vars:
    print(f"{var}: {os.environ[var]}")

# PyTorch
try:
    import torch
    print(f"\nPyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    if torch.cuda.is_available():
        print(f"Current device: {torch.cuda.current_device()}")
        print(f"Device name: {torch.cuda.get_device_name()}")
except Exception as e:
    print(f"PyTorch error: {e}")

# WhisperX Test
try:
    import whisperx
    print(f"\nWhisperX importiert erfolgreich")
    
    # Versuche Device zu setzen
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Gewähltes Device: {device}")
    
    if device == "cuda":
        # Test CUDA Memory
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        print(f"GPU Memory cached: {torch.cuda.memory_reserved(0) / 1e9:.1f} GB")
        
except ImportError as e:
    print(f"WhisperX nicht verfügbar: {e}")
except Exception as e:
    print(f"WhisperX Fehler: {e}")
EOF

echo "WhisperX Test mit aktuellem Container:"
# Hier würden wir Ihren aktuellen Container verwenden
echo "Bitte führen Sie diesen Test in Ihrem WhisperX Container aus:"
echo "docker exec -it <container_name> python3 /path/to/test_whisperx_cuda.py"
echo

# 6. TREIBER KOMPATIBILITÄTSPRÜFUNG
echo "6. TREIBER KOMPATIBILITÄTSPRÜFUNG:"
echo "=================================="
echo "Checking NVIDIA Driver CUDA Compatibility:"

# Extrahiere Treiber Version
driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)
echo "Host Treiber Version: $driver_version"

# Kompatibilitätstabelle
echo "CUDA Kompatibilität für Treiber $driver_version:"
if [[ $(echo "$driver_version >= 520.61" | bc -l) == 1 ]]; then
    echo "✓ CUDA 11.8 - Kompatibel"
    echo "✓ CUDA 12.0 - Kompatibel"
    echo "✓ CUDA 12.1 - Kompatibel"
    echo "✓ CUDA 12.2 - Kompatibel"
fi
if [[ $(echo "$driver_version >= 525.60" | bc -l) == 1 ]]; then
    echo "✓ CUDA 12.3 - Kompatibel"
fi
if [[ $(echo "$driver_version >= 535.54" | bc -l) == 1 ]]; then
    echo "✓ CUDA 12.4 - Kompatibel"
fi

echo
echo "=== DIAGNOSE ABGESCHLOSSEN ==="
echo "Bitte senden Sie die komplette Ausgabe für weitere Analyse."

# Cleanup
rm -f test_pytorch_cuda.py test_whisperx_cuda.py