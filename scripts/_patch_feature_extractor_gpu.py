"""Patch livekit-wakeword's feature_extractor.py to use the GPU (CUDA EP).

WHY: feature extraction (run_extraction, inside the `augment` command) is the
slow CPU phase (~40 min). It runs two frozen ONNX models — melspectrogram.onnx
and embedding_model.onnx — over THOUSANDS of clips, serially. The upstream code
HARDCODES providers=["CPUExecutionProvider"] in two places:
  - feature_extractor.py ~line 42-45 (MelSpectrogramFrontend._init_onnx)
  - feature_extractor.py ~line 101-104 (SpeechEmbedding.__init__)

This patch rewrites BOTH to a GPU-first list with CPU fallback:
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
gated by env GEMMA4_WAKE_FX_GPU (default "1"). If CUDA EP is unavailable, ORT
silently falls back to CPU — so the patch is safe even on a machine without GPU.

PATCH-IN-VENV (the espeak pattern, per CLAUDE.md): the package lives in the
gitignored .venv_livekit; this patch is idempotent and re-runnable, and the
orchestrator applies it automatically. We do NOT vendor the package into git.

PRECONDITION the orchestrator handles: onnxruntime-gpu must be installed AND its
CUDA/cuDNN DLLs must be loadable. torch 2.5.1+cu124 (already in the venv) bundles
cudnn64_9.dll / cublas64_12.dll / cudart64_12.dll in torch/lib; importing torch
before onnxruntime registers that dir on the DLL search path. The orchestrator
sets that up. See _gpu_provider_ready() for the probe used as a gate.

THROTTLE COEXISTENCE (the subtle bit): scripts/_ort_throttle.apply() monkeypatches
ort.InferenceSession.__init__ to INJECT a sess_options (2 intra threads, no
spinning) when none is given — it does NOT touch `providers`. So a CUDA session
keeps running on CUDA; the injected intra_op_num_threads only caps CPU-side ops
(harmless). GPU-extraction and the throttle therefore COEXIST: throttle tames the
CPU fallback / CPU pre-post ops; CUDA EP does the heavy mel+embedding matmuls on
the 4060 Ti. The orchestrator does NOT throttle the augment phase to CPU; it lets
CUDA EP win and relies on ORT's own thread caps for the residual CPU work.

Usage:
    .venv_livekit/Scripts/python.exe scripts/_patch_feature_extractor_gpu.py
    .venv_livekit/Scripts/python.exe scripts/_patch_feature_extractor_gpu.py --revert
    .venv_livekit/Scripts/python.exe scripts/_patch_feature_extractor_gpu.py --check
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = (
    ROOT / ".venv_livekit" / "Lib" / "site-packages"
    / "livekit" / "wakeword" / "models" / "feature_extractor.py"
)

# The two hardcoded CPU-only session constructions, verbatim from the package.
_CPU_BLOCKS = (
    # MelSpectrogramFrontend._init_onnx
    'self._onnx_session = ort.InferenceSession(\n'
    '            str(onnx_path),\n'
    '            providers=["CPUExecutionProvider"],\n'
    '        )',
    # SpeechEmbedding.__init__
    'self._session = ort.InferenceSession(\n'
    '            str(onnx_path),\n'
    '            providers=["CPUExecutionProvider"],\n'
    '        )',
)

# GPU-first replacements (env-gated, CPU fallback baked into the provider list).
_GPU_BLOCKS = (
    'self._onnx_session = ort.InferenceSession(\n'
    '            str(onnx_path),\n'
    '            providers=_gemma4_fx_providers(),  # GEMMA4 GPU patch\n'
    '        )',
    'self._session = ort.InferenceSession(\n'
    '            str(onnx_path),\n'
    '            providers=_gemma4_fx_providers(),  # GEMMA4 GPU patch\n'
    '        )',
)

# Helper injected once at module top (after `import numpy as np`). Reads env each
# call so the gate is dynamic; CPU fallback is always present in the list.
_HELPER = '''

def _gemma4_fx_providers():  # GEMMA4 GPU patch
    """GPU-first provider list with CPU fallback, gated by GEMMA4_WAKE_FX_GPU."""
    import os as _os
    if _os.environ.get("GEMMA4_WAKE_FX_GPU", "1").strip().lower() in ("0", "false", "no"):
        return ["CPUExecutionProvider"]
    try:
        import onnxruntime as _ort
        if "CUDAExecutionProvider" in _ort.get_available_providers():
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception:
        pass
    return ["CPUExecutionProvider"]
'''

_HELPER_ANCHOR = "import numpy as np\n"
_HELPER_MARKER = "_gemma4_fx_providers"


def _read() -> str:
    return FX.read_text(encoding="utf-8")


def _write(text: str) -> None:
    FX.write_text(text, encoding="utf-8")


def check() -> bool:
    if not FX.exists():
        print(f"[fx-gpu] NOT FOUND: {FX}")
        return False
    src = _read()
    patched = _HELPER_MARKER in src
    print(f"[fx-gpu] file: {FX}")
    print(f"[fx-gpu] patched: {patched}")
    return patched


def patch() -> int:
    if not FX.exists():
        print(f"[fx-gpu] ERROR: not found {FX}")
        return 2
    src = _read()
    if _HELPER_MARKER in src:
        print("[fx-gpu] already patched (idempotent no-op)")
        return 0
    # Sanity: both CPU blocks must be present verbatim, else the package changed.
    for i, blk in enumerate(_CPU_BLOCKS):
        if blk not in src:
            print(f"[fx-gpu] ERROR: CPU block #{i} not found verbatim. "
                  "Package layout changed — inspect feature_extractor.py manually.")
            return 3
    new = src
    for cpu, gpu in zip(_CPU_BLOCKS, _GPU_BLOCKS):
        new = new.replace(cpu, gpu, 1)
    if _HELPER_ANCHOR not in new:
        print("[fx-gpu] ERROR: helper anchor 'import numpy as np' not found.")
        return 4
    new = new.replace(_HELPER_ANCHOR, _HELPER_ANCHOR + _HELPER, 1)
    _write(new)
    print("[fx-gpu] patched OK (mel + embedding -> GPU-first, CPU fallback)")
    return 0


def revert() -> int:
    if not FX.exists():
        return 2
    src = _read()
    if _HELPER_MARKER not in src:
        print("[fx-gpu] not patched (nothing to revert)")
        return 0
    new = src
    for cpu, gpu in zip(_CPU_BLOCKS, _GPU_BLOCKS):
        new = new.replace(gpu, cpu, 1)
    # Remove helper (anchor + helper block).
    new = new.replace(_HELPER_ANCHOR + _HELPER, _HELPER_ANCHOR, 1)
    _write(new)
    print("[fx-gpu] reverted to CPU-only")
    return 0


def _gpu_provider_ready() -> bool:
    """True if onnxruntime exposes CUDAExecutionProvider AND a session loads on it.

    Loading actually exercises the CUDA/cuDNN DLLs — a provider that is *listed*
    but cannot load (missing DLLs) would silently fall back to CPU, defeating the
    speedup. This probe makes the gate honest.
    """
    try:
        import torch  # noqa: F401  registers torch/lib DLL dir on Windows
    except Exception:
        pass
    try:
        import os
        # Belt-and-suspenders: explicitly add torch/lib to the DLL search path.
        try:
            import torch as _t
            libdir = os.path.join(os.path.dirname(_t.__file__), "lib")
            if os.path.isdir(libdir) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(libdir)
        except Exception:
            pass
        import onnxruntime as ort
        if "CUDAExecutionProvider" not in ort.get_available_providers():
            return False
        import numpy as np
        # Build a 1-node identity model in-memory? Simpler: load the real mel model.
        mel = (ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
               / "melspectrogram.onnx")
        if not mel.exists():
            # Can't prove load; provider is at least listed.
            return True
        so = ort.SessionOptions()
        sess = ort.InferenceSession(
            str(mel), sess_options=so,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        used = sess.get_providers()
        ok = "CUDAExecutionProvider" in used
        print(f"[fx-gpu] probe providers in use: {used}")
        return ok
    except Exception as exc:
        print(f"[fx-gpu] GPU probe failed: {exc}")
        return False


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if arg == "--check":
        return 0 if check() else 1
    if arg == "--revert":
        return revert()
    if arg == "--probe-gpu":
        ready = _gpu_provider_ready()
        print(f"[fx-gpu] gpu ready: {ready}")
        return 0 if ready else 1
    return patch()


if __name__ == "__main__":
    sys.exit(main())
