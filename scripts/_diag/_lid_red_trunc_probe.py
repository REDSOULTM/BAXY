"""Zona ultra-corta con el MIC REAL: clips de RED truncados a 0.7s + validación
textual de la heurística contra los fallos EN reales de los logs vivos."""
import sys
import types
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import soundfile as sf  # noqa: E402

from gemma4_agent.voice.parakeet_stt import ParakeetSTT, SAMPLE_RATE  # noqa: E402
from gemma4_agent.voice.pipeline import VoicePipeline  # noqa: E402
from gemma4_agent.voice.lang_profiles import get_profile  # noqa: E402

shim = types.SimpleNamespace(
    _lang_profile=get_profile(),
    _EN_FUNCTION_WORDS=VoicePipeline._EN_FUNCTION_WORDS,
    _TARGET_MARKERS=VoicePipeline._TARGET_MARKERS,
)


def looks_en(t):
    return VoicePipeline._looks_english_not_target(shim, t)


# 1) textual: los fallos EN reales registrados en logs vivos DEBEN disparar
print("== validación textual (fallos reales de logs) ==")
for t, want in [
    ("Really isn't worth it.", True),
    ("Let's see. I was up.", True),
    ("We've got.", True),
    ("I guess it.", True),
    # NO deben disparar:
    ("Abre Steam.", False),
    ("reproduce The Last of Us en HBO Max", False),   # code-switching legítimo
    ("pon música de Bad Bunny", False),
    ("But sí.", False),                                # mixto con marcador es
]:
    got = looks_en(t)
    print(f"  {'OK ' if got == want else 'FAIL'} {t!r} -> {got} (want {want})")

# 2) audio real ultra-corto (mic de RED truncado a 0.7s)
pk = ParakeetSTT()
assert pk.load(), pk.last_error
mic = ROOT / "data" / "stt_eval" / "real_mic"
rows = []
for line in (mic / "manifest.tsv").read_text(encoding="utf-8").splitlines():
    p = line.split("\t")
    if len(p) >= 6 and p[5] in ("20260523_015719", "20260523_020155"):
        rows.append(p[0])
print(f"\n== mic RED truncado a 0.7s: {len(rows)} clips ==")
en_like = 0
for fname in rows:
    f = mic / fname
    if not f.exists():
        continue
    data, _ = sf.read(str(f), dtype="int16")
    if data.ndim > 1:
        data = data[:, 0]
    audio = data[: int(0.7 * SAMPLE_RATE)]
    t = pk.transcribe(audio)
    if t.strip() and looks_en(t):
        en_like += 1
        print(f"  EN-like: {fname} -> {t!r}")
print(f"outputs EN-like: {en_like}/{len(rows)}")
