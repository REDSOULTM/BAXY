# Reproducible setup for the router-encoder training venv (Step 6).
# Mirrors the .venv_train / .venv_livekit precedent: an ISOLATED env with CUDA
# torch so distillation never pollutes the 3.10 runtime. Idempotent-ish: re-run
# safely; pip skips already-satisfied packages.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/setup_router_train_venv.ps1
#
# Produces .venv_router_train with: CUDA torch (cu124), sentence-transformers,
# optimum[onnxruntime], onnx — everything train_router_encoder.py needs on the
# RTX 4060 Ti. Python 3.11 (matches the working .venv_livekit CUDA stack).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv_router_train"

# Prefer the Python that already runs CUDA torch in .venv_livekit (3.11).
$py = "py -3.11"

if (-not (Test-Path $venv)) {
    Write-Host "creating $venv"
    & cmd /c "$py -m venv `"$venv`""
}
$vpy = Join-Path $venv "Scripts\python.exe"

& $vpy -m pip install --upgrade pip
# CUDA torch matching the driver (cu124 verified working in .venv_livekit).
& $vpy -m pip install torch --index-url https://download.pytorch.org/whl/cu124
& $vpy -m pip install "sentence-transformers>=3.0" "optimum[onnxruntime]" onnx

& $vpy -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
Write-Host "router-train venv ready: $venv"
