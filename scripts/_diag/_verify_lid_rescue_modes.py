"""Verifica EN VIVO la resolución de modo del rescate LID, el camino
subprocess completo desde pipeline._lid_rescue (wav temp → worker → texto)
y la persistencia de evidencia en stt_lid_rescue.jsonl (aislada en un dir
temporal para no contaminar la evidencia real de ~/.gemma4/logs)."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.pipeline import VoicePipeline  # noqa: E402
from gemma4_agent.voice.lang_profiles import get_profile  # noqa: E402

# --- 1. resolución de modo ---
os.environ.pop("GEMMA4_STT_LID_RESCUE_MODE", None)
os.environ.pop("GEMMA4_STT_LID_RESIDENT_MIN_GB", None)
auto = VoicePipeline._lid_rescue_mode()
os.environ["GEMMA4_STT_LID_RESIDENT_MIN_GB"] = "9999"
auto_low = VoicePipeline._lid_rescue_mode()  # simula target 8GB
os.environ["GEMMA4_STT_LID_RESCUE_MODE"] = "resident"
forced_r = VoicePipeline._lid_rescue_mode()
os.environ["GEMMA4_STT_LID_RESCUE_MODE"] = "subprocess"
forced_s = VoicePipeline._lid_rescue_mode()
import psutil  # noqa: E402
total_gb = psutil.virtual_memory().total / 1e9
print(f"RAM total: {total_gb:.1f}GB")
print(f"auto(dev)={auto}  auto(floor=9999, simula 8GB)={auto_low}  "
      f"forced resident={forced_r}  forced subprocess={forced_s}")
ok1 = (auto == ("resident" if total_gb >= 12 else "subprocess")
       and auto_low == "subprocess" and forced_r == "resident"
       and forced_s == "subprocess")
print("modos:", "OK" if ok1 else "FAIL")

# --- 2. camino subprocess completo desde _lid_rescue ---
os.environ.pop("GEMMA4_STT_LID_RESIDENT_MIN_GB", None)
os.environ["GEMMA4_STT_LID_RESCUE_MODE"] = "subprocess"
# evidencia aislada: NO contaminar ~/.gemma4/logs/stt_lid_rescue.jsonl real
_tmp_logs = Path(tempfile.mkdtemp(prefix="lid_rescue_verify_"))
os.environ["GEMMA4_AGENT_LOGS_DIR"] = str(_tmp_logs)
mic = ROOT / "data" / "stt_eval" / "real_mic"
rows = [l.split("\t") for l in (mic / "manifest.tsv").read_text(encoding="utf-8").splitlines()]
wav = None
for p in rows:
    if len(p) >= 6 and (mic / p[0]).exists():
        info = sf.info(str(mic / p[0]))
        if info.frames / info.samplerate <= 3.0:
            wav = mic / p[0]
            break
assert wav is not None
audio, sr = sf.read(str(wav), dtype="int16")
if audio.ndim > 1:
    audio = audio[:, 0]
assert sr == 16000, sr

pipe = VoicePipeline.__new__(VoicePipeline)
pipe._stt_engine = "parakeet"
pipe._lang_profile = get_profile()
pipe._initial_prompt = ""
print(f"perfil: {pipe._lang_profile.code} / clip {wav.name} ({audio.size / sr:.1f}s)")

t0 = time.time()
rescued = pipe._lid_rescue(audio, "what is it really")  # flip EN simulado
dt = time.time() - t0
print(f"rescate subprocess: {dt:.2f}s -> {rescued!r}")
ok2 = bool(rescued) and "steam" in rescued.lower()

# --- 3. evidencia persistida en stt_lid_rescue.jsonl ---
ev_file = _tmp_logs / "stt_lid_rescue.jsonl"
rows_ev = [json.loads(l) for l in ev_file.read_text(encoding="utf-8").splitlines()] \
    if ev_file.exists() else []
print(f"evidencia jsonl: {len(rows_ev)} fila(s) -> "
      f"{rows_ev[-1] if rows_ev else 'NADA'}")
ok_ev = (len(rows_ev) == 1 and rows_ev[0].get("mode") == "subprocess"
         and rows_ev[0].get("whisper") and rows_ev[0].get("parakeet")
         and rows_ev[0].get("ts"))

# --- 4. no-disparo (texto ya en es) NO paga subprocess ni deja evidencia ---
t0 = time.time()
none = pipe._lid_rescue(audio, "abre steam por favor")
dt3 = time.time() - t0
n_after = len(ev_file.read_text(encoding="utf-8").splitlines()) \
    if ev_file.exists() else 0
print(f"no-disparo (texto es): {dt3 * 1000:.0f}ms -> {none!r} "
      f"(evidencia sigue en {n_after})")
ok3 = none is None and dt3 < 0.05 and n_after == len(rows_ev)

os.environ.pop("GEMMA4_STT_LID_RESCUE_MODE", None)
os.environ.pop("GEMMA4_AGENT_LOGS_DIR", None)
print("RESULTADO:", "PASS" if (ok1 and ok2 and ok_ev and ok3) else "FAIL")
sys.exit(0 if (ok1 and ok2 and ok_ev and ok3) else 1)
