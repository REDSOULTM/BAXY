# -*- coding: utf-8 -*-
"""Mide si el VAD (silero_vad) carga torch y cuánta RAM. Proceso efímero."""
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


print("base python:", rss_mb(), "MB | torch?:", "torch" in sys.modules)
from gemma4_agent.voice.vad import SileroVAD  # noqa: E402

v = SileroVAD()
ok = v.load()
print(f"+VAD cargado (ok={ok}):", rss_mb(), "MB")
print("torch cargado por el VAD?:", "torch" in sys.modules)
