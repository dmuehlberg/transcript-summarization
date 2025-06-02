import subprocess
import sys

print("=== Python Version ===")
print(f"Python: {sys.version}")

print("\n=== Host NVIDIA Driver Info ===")
try:
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    print(result.stdout)
except Exception as e:
    print(f"Error running nvidia-smi: {e}")

try:
    import torch
    print("\n=== PyTorch CUDA Info ===")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"cuDNN version: {torch.backends.cudnn.version()}")
        print(f"Number of GPUs: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"  Memory: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
    else:
        print("CUDA is not available!")

    print("\n=== CUDA Runtime vs Driver ===")
    if torch.cuda.is_available():
        print(f"CUDA Runtime Version: {torch.version.cuda}")
    
    # Get driver version from nvidia-smi
    try:
        import re
        result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'], 
                              capture_output=True, text=True)
        driver_version = result.stdout.strip()
        print(f"NVIDIA Driver Version: {driver_version}")
    except:
        print("Could not get driver version")
except ImportError:
    print("PyTorch is not installed on the host system")
    print("This is normal - we mainly need nvidia-smi output from the host")