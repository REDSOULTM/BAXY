"""Medición del RESCATE LID frase-corta (Parakeet→Whisper selectivo).

Mide sobre voz REAL, sin tocar prod:
  A) 84 comandos cortos de RED (tandas 20260523_015719/020155, CON expected):
     cuántos disparan el rescate, WER antes/después, y latencia extra.
  B) 180 clips de TERCEROS (FLEURS es + chilenos): el rescate NO debe disparar
     (anti-falso-positivo) — son español largo con contexto.

Reusa la heurística REAL del pipeline (VoicePipeline._looks_english_not_target)
para que lo medido sea lo deployado.
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

MAX_S = 3.0
TANDAS = ("20260523_015719", "20260523_020155")


def wer(ref: str, hyp: str) -> float:
    r = ref.lower().split()
    h = hyp.lower().split()
    if not r:
        return 0.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / len(r)


def norm(t: str) -> str:
    return " ".join("".join(c for c in t.lower() if c.isalnum() or c.isspace()).split())


def load_wav(p: Path) -> np.ndarray:
    data, sr = sf.read(str(p), dtype="int16")
    if data.ndim > 1:
        data = data[:, 0]
    assert sr == SAMPLE_RATE, f"{p}: sr={sr}"
    return data


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
    print(f"perfil={profile.code} whisper_lang={profile.whisper_language}")

    # ---- A) comandos RED ----
    mic_dir = ROOT / "data" / "stt_eval" / "real_mic"
    rows = []
    for line in (mic_dir / "manifest.tsv").read_text(encoding="utf-8").splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 6 and parts[5] in TANDAS:
            rows.append((parts[0], parts[1]))
    print(f"\n== A) comandos RED: {len(rows)} clips ==")
    trig = fixed_en = 0
    wer_before_sum = wer_after_sum = 0.0
    rescue_lat = []
    for fname, expected in rows:
        wav = mic_dir / fname
        if not wav.exists():
            continue
        audio = load_wav(wav)
        ptext = pk.transcribe(audio)
        final = ptext
        dur = audio.size / SAMPLE_RATE
        if dur <= MAX_S and ptext.strip() and looks_en(ptext):
            trig += 1
            t0 = time.time()
            wtext = wh.transcribe(audio, language=profile.whisper_language)
            rescue_lat.append(time.time() - t0)
            if (wtext or "").strip():
                final = wtext.strip()
            print(f"  TRIGGER [{dur:.1f}s] exp={expected!r}")
            print(f"     parakeet={ptext!r} -> whisper={final!r}")
            if wer(norm(expected), norm(final)) < wer(norm(expected), norm(ptext)):
                fixed_en += 1
        wer_before_sum += wer(norm(expected), norm(ptext))
        wer_after_sum += wer(norm(expected), norm(final))
    n = len(rows)
    print(f"\nA) disparos: {trig}/{n} | mejorados: {fixed_en}/{trig if trig else 1}")
    print(f"A) WER antes={wer_before_sum/n:.4f} despues={wer_after_sum/n:.4f}")
    if rescue_lat:
        print(f"A) latencia extra rescate p50={sorted(rescue_lat)[len(rescue_lat)//2]*1000:.0f}ms")

    # ---- B) terceros (anti-FP) ----
    for tag, mpath in (("fleurs", "real_es/manifest.tsv"),
                       ("chileno", "real_es/manifest_cl.tsv")):
        man = ROOT / "data" / "stt_eval" / mpath
        if not man.exists():
            print(f"B) {tag}: manifest no existe, salto")
            continue
        base = man.parent
        fp = total = 0
        for line in man.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            wav = base / parts[0]
            if not wav.exists():
                continue
            total += 1
            audio = load_wav(wav)
            dur = audio.size / SAMPLE_RATE
            if dur > MAX_S:
                continue  # el gate de duración ya lo excluye sin transcribir
            ptext = pk.transcribe(audio)
            if ptext.strip() and looks_en(ptext):
                fp += 1
                print(f"  FP {tag}: {parts[0]} -> {ptext!r}")
        print(f"B) {tag}: falsos disparos {fp}/{total}")


if __name__ == "__main__":
    main()
