"""One-off post-install helper: stage CUDA 12 cuBLAS DLLs into the
ctranslate2 package directory so faster-whisper can find them.

Background (Sprint Q.0 2026-05-18)
----------------------------------
`pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` lands the
runtime DLLs under `site-packages/nvidia/{cublas,cudnn}/bin/`,
but Windows' implicit DLL search path does NOT include those
directories. ctranslate2's loader documentation suggests it can
discover them, but in practice (4.7.1 on Windows + Python 3.10)
it does not, and faster-whisper inference fails with:

    RuntimeError: Library cublas64_12.dll is not found
    or cannot be loaded.

The fix is to copy the cuBLAS DLLs INTO the ctranslate2 package
directory, which IS on the implicit search path (because
`import ctranslate2` already loaded a DLL from there).

This script is idempotent: re-runs are no-ops if the targets
already exist.

Run after `pip install -r requirements.txt`:

    python scripts/setup_cuda_runtime.py

It is also called automatically when the bench-harness GPU
probe trips and detects the mismatch.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# DLLs we need to stage. cudnn64_9.dll is already shipped inside
# ctranslate2 itself; cudnn_*.dll are pulled in by ops at runtime
# via Windows' search path (cudnn pkg). Only cublas is missing.
REQUIRED_DLLS = ["cublas64_12.dll", "cublasLt64_12.dll"]


def _site_packages() -> Path:
    return Path(sys.exec_prefix) / "Lib" / "site-packages"


def stage(verbose: bool = True) -> dict[str, str]:
    """Copy CUDA 12 runtime DLLs into ctranslate2's package dir.

    Returns a dict {dll_name: status} where status is one of:
        "copied"   — newly staged
        "present"  — already in place
        "missing"  — source DLL not found (wheel not installed)
    """
    sp = _site_packages()
    src_dir = sp / "nvidia" / "cublas" / "bin"
    dst_dir = sp / "ctranslate2"

    if not dst_dir.exists():
        raise RuntimeError(
            f"ctranslate2 package dir not found: {dst_dir}\n"
            f"Install it: pip install ctranslate2"
        )

    results: dict[str, str] = {}
    for dll in REQUIRED_DLLS:
        src = src_dir / dll
        dst = dst_dir / dll
        if dst.exists():
            results[dll] = "present"
            if verbose:
                print(f"  {dll}: already present in ctranslate2/")
            continue
        if not src.exists():
            results[dll] = "missing"
            if verbose:
                print(
                    f"  {dll}: SOURCE MISSING at {src}\n"
                    f"  Install the wheel: pip install nvidia-cublas-cu12"
                )
            continue
        shutil.copy2(src, dst)
        results[dll] = "copied"
        if verbose:
            print(f"  {dll}: copied to ctranslate2/")
    return results


def main() -> int:
    print("Staging CUDA 12 cuBLAS DLLs for ctranslate2...")
    try:
        results = stage(verbose=True)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    if any(v == "missing" for v in results.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
