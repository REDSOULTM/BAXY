# Sets up .venv_train with everything needed to run openwakeword training
# locally on GPU. Sprint R3.1 path.
#
# Usage (from project root in PowerShell):
#     .\scripts\setup_train_venv.ps1
#
# Time: ~10-15 min total (downloads ~5GB). One-time setup.
# Disk: ~5GB.
#
# After this completes:
#   .venv_train/Scripts/python.exe -m jupyter notebook scripts/notebooks/train_hey_gemma.ipynb
#
# To delete and start over: rm -r .venv_train

$ErrorActionPreference = "Stop"
$Python = "C:\Users\usuario\AppData\Local\Programs\Python\Python310\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Python 3.10 not found at $Python"
    exit 1
}

Write-Host "1/5  Creating venv..."
& $Python -m venv .venv_train

Write-Host "2/5  Upgrading pip..."
& .venv_train\Scripts\python.exe -m pip install --upgrade pip

Write-Host "3/5  Installing torch + CUDA 12.1 (largest download, ~2 GB)..."
& .venv_train\Scripts\python.exe -m pip install torch==2.5.1 torchaudio==2.5.1 `
    --index-url https://download.pytorch.org/whl/cu121

Write-Host "4/5  Installing openwakeword + inference deps..."
& .venv_train\Scripts\python.exe -m pip install `
    numpy librosa soundfile openwakeword onnx onnxruntime-gpu `
    ipykernel jupyter scipy matplotlib

Write-Host "5/5  Installing openwakeword TRAINING extras (not declared in install_requires)..."
# These are imported by openwakeword.train but not declared. Discovered
# iteratively during R3.1 setup. Versions left open so pip resolves
# compatible ones against torch 2.5.1.
& .venv_train\Scripts\python.exe -m pip install `
    torchinfo torchmetrics pytorch-lightning datasets `
    pronouncing mutagen acoustics speechbrain `
    tensorflow onnx-tf
& .venv_train\Scripts\python.exe -m pip install audiomentations torch-audiomentations `
    --only-binary=:all:

Write-Host ""
Write-Host "Verification:"
& .venv_train\Scripts\python.exe -c "import torch; print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available(), 'gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
& .venv_train\Scripts\python.exe -c "import openwakeword.train; print('openwakeword.train: OK')"

Write-Host ""
Write-Host "Done. Next: launch jupyter from this venv:"
Write-Host "    .venv_train\Scripts\python.exe -m jupyter notebook scripts/notebooks/train_hey_gemma.ipynb"
