"""Latencia end-to-end del rescate LID en modo subprocess (worker efímero):
spawn + import faster_whisper + carga small int8 + transcripción de un clip real."""
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
mic = ROOT / "data" / "stt_eval" / "real_mic"
rows = [l.split("\t") for l in (mic / "manifest.tsv").read_text(encoding="utf-8").splitlines()]

import soundfile as sf  # noqa: E402

wav = None
for p in rows:
    if len(p) >= 6 and (mic / p[0]).exists():
        info = sf.info(str(mic / p[0]))
        if info.frames / info.samplerate <= 3.0:  # la zona real del rescate
            wav = mic / p[0]
            break
assert wav is not None, "no hay clip <=3s en el manifest"
worker = ROOT / "gemma4_agent" / "voice" / "_lid_rescue_worker.py"
info = sf.info(str(wav))
print(f"clip: {wav.name} ({info.frames / info.samplerate:.1f}s)")
for i in range(3):
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(worker), str(wav), "es"],
        capture_output=True, timeout=60,
    )
    dt = time.time() - t0
    out = proc.stdout.decode("utf-8", "replace").strip()
    print(f"run{i + 1}: {dt:.2f}s exit={proc.returncode} text={out[:70]!r}")
    if proc.returncode != 0:
        print("stderr:", proc.stderr.decode("utf-8", "replace")[:200])
