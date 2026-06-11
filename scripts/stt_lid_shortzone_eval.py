"""Zona corta REAL del bug LID: FLEURS-es truncado a ~1.2s (habla española
genuina SIN contexto) — la model card dice explícito que ahí el LID falla.

Mide: (1) cuántos outputs de Parakeet salen con pinta de INGLÉS (la tasa real
del bug), (2) cuántos dispara la heurística del pipeline, (3) si el rescate
Whisper(language=es) devuelve ESPAÑOL, (4) latencia del rescate. El ground
truth exacto del fragmento no es alineable (truncado): el resultado medible
es el IDIOMA de salida + inspección manual de los pares impresos.
"""
import sys
import time
import types
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.parakeet_stt import ParakeetSTT, SAMPLE_RATE  # noqa: E402
from gemma4_agent.voice.pipeline import VoicePipeline  # noqa: E402
from gemma4_agent.voice.lang_profiles import get_profile  # noqa: E402

TRUNC_S = 1.2
N_CLIPS = 60


def main() -> None:
    profile = get_profile()
    shim = types.SimpleNamespace(
        _lang_profile=profile,
        _EN_FUNCTION_WORDS=VoicePipeline._EN_FUNCTION_WORDS,
        _TARGET_MARKERS=VoicePipeline._TARGET_MARKERS,
    )

    def looks_en(text: str) -> bool:
        return VoicePipeline._looks_english_not_target(shim, text)

    pk = ParakeetSTT()
    assert pk.load(), pk.last_error
    from gemma4_agent.voice.stt import STT
    wh = STT()
    assert wh.load(), wh.last_error

    base = ROOT / "data" / "stt_eval" / "real_es"
    man = base / "manifest.tsv"
    rows = [l.split("\t") for l in man.read_text(encoding="utf-8").splitlines()[1:]]
    rows = [r for r in rows if len(r) >= 2 and (base / r[0]).exists()][:N_CLIPS]
    print(f"clips truncados a {TRUNC_S}s: {len(rows)}")

    en_out = trig = rescued_es = 0
    lat = []
    for fname, expected, *_ in rows:
        data, sr = sf.read(str(base / fname), dtype="int16")
        if data.ndim > 1:
            data = data[:, 0]
        audio = data[: int(TRUNC_S * SAMPLE_RATE)]
        if audio.size < int(0.4 * SAMPLE_RATE):
            continue
        ptext = pk.transcribe(audio)
        if not ptext.strip():
            continue
        is_en = looks_en(ptext)
        en_out += is_en
        if is_en:
            trig += 1
            t0 = time.time()
            wtext = wh.transcribe(audio, language=profile.whisper_language)
            lat.append(time.time() - t0)
            w_es = bool((wtext or "").strip()) and not looks_en(wtext)
            rescued_es += w_es
            print(f"  TRIGGER exp≈{expected[:42]!r}")
            print(f"    parakeet={ptext!r}")
            print(f"    whisper ={wtext!r}  ({'ES' if w_es else 'no-ES'})")
    print(f"\noutputs con pinta EN (bug LID): {en_out}/{len(rows)}")
    print(f"disparos heurística: {trig} | rescatados a ES: {rescued_es}/{trig if trig else 1}")
    if lat:
        print(f"latencia rescate p50={sorted(lat)[len(lat)//2]*1000:.0f}ms")


if __name__ == "__main__":
    main()
