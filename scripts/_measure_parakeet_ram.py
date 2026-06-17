# -*- coding: utf-8 -*-
"""Mide RAM de Parakeet STT + introspecciona qué levers de RAM expone sherpa-onnx.
Proceso efímero (sale solo -> sin servers residentes)."""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rss_mb() -> int:
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-c",
         f"[math]::Round((Get-Process -Id {os.getpid()}).WorkingSet64/1MB)"],
        capture_output=True, text=True).stdout.strip()
    try:
        return int(out)
    except ValueError:
        return -1


print("base python:", rss_mb(), "MB")
import sherpa_onnx  # noqa: E402

sig = inspect.signature(sherpa_onnx.OfflineRecognizer.from_transducer)
params = list(sig.parameters)
relevant = [p for p in params if any(k in p.lower() for k in ("arena", "mem", "spinning"))]
print("sherpa from_transducer params RAM (arena/mem/spinning):", relevant or "NINGUNO")
print("  provider expuesto?:", "provider" in params)
print("+sherpa_onnx import:", rss_mb(), "MB")

from gemma4_agent.voice.parakeet_stt import ParakeetSTT  # noqa: E402

p = ParakeetSTT()
ok = p.load()
print(f"+Parakeet cargado (ok={ok}):", rss_mb(), "MB  <- RAM del STT")
print("torch cargado por Parakeet?:", "torch" in sys.modules)
