"""scripts/setup_mind_voice.ps1's last step (bootstrap.ps1 runs it): the voice probe, run here by itself with this
Python on the checkout's mind; nothing is installed and no microphone is opened."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_mind_voice.ps1"


def test_the_voice_probe_reads_the_ear_of_this_mind() -> None:
    # Calidad PC 2026-10-25: the probe imported baxy_mind.voice.VoiceEngine, which BAXY Renew replaced by Voice
    # (d3dc61bb2): the setup, and bootstrap.ps1 with it, always ended in «mind_runtime_setup_failed: voice_probe».
    code = re.search(r"\$probeCode = @'\r?\n(.*?)\r?\n'@", SCRIPT.read_text(encoding="utf-8"), re.S).group(1)
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, cwd=ROOT, timeout=120)
    assert done.returncode in (0, 2), done.stderr  # 2: this Python lacks a part of the ear, as the probe reports
    probe = json.loads(done.stdout)
    assert set(probe) == {"stt", "vad"} and done.returncode == (0 if probe["stt"] and probe["vad"] else 2)
