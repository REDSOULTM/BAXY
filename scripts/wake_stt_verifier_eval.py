"""¿Sirve un VERIFICADOR post-wake por STT para matar los fake-fires?

Idea (parche runtime, sin reentrenar): al disparar el wake, transcribir el
tramo final del preroll con Parakeet (~100 ms) y verificar FONÉTICAMENTE que
lo dicho sea "baxy" (match dual Metaphone ES/EN, igual que el strip del
corrector) — si claramente fue OTRA palabra ("taxi"), rechazar el wake.

Este script mide la SEPARABILIDAD offline con los held-outs existentes:
  - 500 positivos baxy (25 voces × 13 idiomas) → ¿cuántos SOBREVIVEN?
  - 550 confusables (taxi/maxi/basta/boxeo...) → ¿cuántos se RECHAZAN?
Para cada clip: Parakeet → último token → score fonético vs wake words →
curva accept-rate vs threshold para ambos sets. La política de rechazo es
CONSERVADORA: transcript vacío o inaudible = ACEPTAR (no matar recall por
fallas del STT); solo rechaza un NON-match claro.

Uso: python scripts/wake_stt_verifier_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import _ort_throttle  # noqa: F401,E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.parakeet_stt import ParakeetSTT  # noqa: E402
from gemma4_agent.voice.corrector import (  # noqa: E402
    _normalise, _metaphone, _metaphone_es,
)

POS = ROOT / "data" / "wake_universal_eval" / "positives_baxy"
CONF = ROOT / "data" / "wake_universal_eval" / "confusables_baxy"
WAKES = ("baxy", "baxi", "backsy")


def phon_score(token_norm: str) -> float:
    """Máximo score fonético/textual del token contra las wake words
    (la misma maquinaria dual ES/EN del corrector)."""
    from rapidfuzz import fuzz
    best = 0.0
    for w in WAKES:
        wn = _normalise(w)
        best = max(best, fuzz.ratio(token_norm, wn))
        en_t, en_w = _metaphone(token_norm), _metaphone(wn)
        if en_t and en_w:
            best = max(best, fuzz.ratio(en_t, en_w))
        es_t, es_w = _metaphone_es(token_norm), _metaphone_es(wn)
        if es_t and es_w:
            best = max(best, fuzz.ratio(es_t, es_w))
    return best


def clip_score(stt: ParakeetSTT, path: Path) -> tuple[float, str]:
    a, sr = sf.read(str(path), dtype="int16")
    if a.ndim > 1:
        a = a[:, 0]
    text = (stt.transcribe(a) or "").strip()
    norm = _normalise(text)
    if not norm:
        return (999.0, "(vacio)")     # vacío => ACEPTAR (conservador)
    # el token MÁS parecido del transcript (el wake puede venir con cola)
    return (max(phon_score(t) for t in norm.split()), text)


def main() -> int:
    stt = ParakeetSTT()
    assert stt.load(), stt.last_error

    pos = sorted(POS.glob("*.wav"))
    conf = sorted(CONF.glob("*.wav"))
    print(f"positivos {len(pos)} | confusables {len(conf)}")

    pos_scores, conf_scores = [], []
    conf_texts: dict[str, list[float]] = {}
    for i, p in enumerate(pos):
        pos_scores.append(clip_score(stt, p)[0])
        if (i + 1) % 200 == 0:
            print(f"  pos {i + 1}")
    for i, p in enumerate(conf):
        s, _t = clip_score(stt, p)
        conf_scores.append(s)
        word_idx = p.stem.split("__w")[1].split("__")[0]
        conf_texts.setdefault(word_idx, []).append(s)
        if (i + 1) % 200 == 0:
            print(f"  conf {i + 1}")

    ps = np.asarray(pos_scores)
    cs = np.asarray(conf_scores)
    print("\nthr  | wakes ACEPTADOS | confusables RECHAZADOS")
    for thr in (60, 65, 70, 75, 80, 85, 90):
        keep = float(np.mean(ps >= thr) + np.mean(ps >= 999) * 0)  # 999 cuenta
        keep = float(np.mean((ps >= thr) | (ps >= 999.0)))
        rej = float(np.mean(cs < thr))
        print(f" {thr:3} |     {keep:6.1%}     |       {rej:6.1%}")
    print(f"\nscores positivos: p10={np.percentile(ps[ps < 999], 10):.0f} "
          f"p50={np.percentile(ps[ps < 999], 50):.0f} "
          f"(vacios/aceptar: {float(np.mean(ps >= 999)):.1%})")
    print(f"scores confusables: p50={np.percentile(cs[cs < 999], 50):.0f} "
          f"p90={np.percentile(cs[cs < 999], 90):.0f} "
          f"(vacios: {float(np.mean(cs >= 999)):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
