#!/bin/bash

echo "=== CONTAINER CUDA DIAGNOSE ==="
echo "Führen Sie dieses Skript IN Ihrem WhisperX Container aus"
echo

# 1. Container Umgebung
echo "1. CONTAINER UMGEBUNG:"
echo "======================"
echo "Container OS:"
cat /etc/os-release | grep PRETTY_NAME
echo

echo "CUDA Umgebungsvariablen:"
env | grep -i cuda
echo

echo "LD_LIBRARY_PATH:"
echo $LD_LIBRARY_PATH
echo

# 2. CUDA Installation im Container
echo "2. CUDA INSTALLATION:"
echo "===================="
echo "NVCC Version (falls verfügbar):"
nvcc --version 2>/dev/null || echo "nvcc nicht verfügbar"
echo

echo "CUDA Libraries:"
find /usr/local/cuda* -name "libcudart*.so*" 2>/dev/null || echo "Keine CUDA Runtime gefunden"
find /usr/lib* -name "libcuda*.so*" 2>/dev/null || echo "Keine CUDA Driver Libraries gefunden"
echo

echo "cuDNN Libraries:"
find /usr -name "libcudnn*.so*" 2>/dev/null || echo "Keine cuDNN Libraries gefunden"
echo

# 3. Python CUDA Test
echo "3. PYTHON CUDA TEST:"
echo "==================="
python3 << 'EOF'
import sys
import os

print(f"Python Version: {sys.version}")
print(f"Python Executable: {sys.executable}")

# Check CUDA Environment
cuda_env = {k: v for k, v in os.environ.items() if 'CUDA' in k.upper()}
if cuda_env:
    print("CUDA Environment Variables:")
    for k, v in cuda_env.items():
        print(f"  {k}: {v}")
else:
    print("Keine CUDA Umgebungsvariablen gefunden")

# Test PyTorch
try:
    import torch
    print(f"\nPyTorch Version: {torch.__version__}")
    print(f"PyTorch compiled with CUDA: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA device count: {torch.cuda.device_count()}")
        print(f"Current CUDA device: {torch.cuda.current_device()}")
        print(f"CUDA device name: {torch.cuda.get_device_name()}")
        
        # Memory info
        total_mem = torch.cuda.get_device_properties(0).total_memory
        print(f"GPU Total Memory: {total_mem / 1e9:.2f} GB")
        
        # Test tensor creation
        try:
            test_tensor = torch.randn(10, 10).cuda()
            print("✓ CUDA Tensor creation successful")
        except Exception as e:
            print(f"✗ CUDA Tensor creation failed: {e}")
    else:
        print("CUDA not available - checking why:")
        # Detailierte CUDA Diagnose
        try:
            # Check if CUDA libraries are found
            import torch.cuda
            print(f"CUDA initialization error: {torch.cuda.init()}")
        except Exception as e:
            print(f"CUDA initialization error: {e}")

except ImportError as e:
    print(f"PyTorch not available: {e}")
except Exception as e:
    print(f"PyTorch error: {e}")

# Test WhisperX imports
try:
    import whisperx
    print(f"\n✓ WhisperX import successful")
    print(f"WhisperX location: {whisperx.__file__}")
except ImportError as e:
    print(f"\n✗ WhisperX import failed: {e}")
except Exception as e:
    print(f"\n✗ WhisperX error: {e}")

EOF

# 4. Detaillierte Library Prüfung
echo
echo "4. LIBRARY DIAGNOSE:"
echo "==================="
echo "Shared Library Dependencies (CUDA related):"
ldd $(python3 -c "import torch; print(torch.__file__.replace('__init__.py', '_C.so'))") 2>/dev/null | grep -i cuda || echo "Keine CUDA Dependencies gefunden"
echo

echo "NVIDIA Driver Version von Container aus:"
nvidia-smi 2>/dev/null || echo "nvidia-smi nicht verfügbar im Container"
echo

# 5. Runtime Test
echo "5. RUNTIME TEST:"
echo "==============="
python3 << 'EOF'
try:
    import torch
    if torch.cuda.is_available():
        print("Führe CUDA Runtime Test durch...")
        device = torch.device('cuda')
        
        # Einfacher Test
        a = torch.randn(1000, 1000, device=device)
        b = torch.randn(1000, 1000, device=device)
        c = torch.matmul(a, b)
        
        print("✓ CUDA Matrix Multiplikation erfolgreich")
        print(f"Result shape: {c.shape}")
        print(f"Result device: {c.device}")
        
    else:
        print("CUDA nicht verfügbar für Runtime Test")
except Exception as e:
    print(f"✗ CUDA Runtime Test fehlgeschlagen: {e}")
    import traceback
    traceback.print_exc()
EOF

echo
echo "=== CONTAINER DIAGNOSE ABGESCHLOSSEN ==="