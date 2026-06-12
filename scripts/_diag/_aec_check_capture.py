"""¿Hay voz del usuario en la captura AEC fase 2? STT sobre crudo y cancelado."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import _ort_throttle  # noqa: F401,E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.parakeet_stt import ParakeetSTT  # noqa: E402

stt = ParakeetSTT()
assert stt.load()
for name in ("mic_crudo", "mic_cancelado"):
    a, sr = sf.read(str(ROOT / "documentacion" / "_aec_live" / f"{name}.wav"),
                    dtype="int16")
    print(f"{name}: {stt.transcribe(a)!r}")
