"""Calibración del initial_prompt de Whisper-small contra la grabación real.

Mide WER de Whisper-small con DISTINTOS initial_prompts contra la verdad de
faster-whisper large-v3 (testaudio_groundtruth_full.json) sobre Grabación (2).wav
(~4.9 min, 118 segmentos de comandos reales en español-Spanglish).

Compara:
  - baseline_no_prompt : sin initial_prompt (peor caso).
  - prompt_es          : el initial_prompt nuevo (perfil 'es' Spanglish).

Reporta WER global y, lo mas util, los comandos donde small se equivoca
(small_text vs large_text) para ver si el prompt nuevo arregla los anglicismos
("Aurekrom"->"Chrome", "prende"->"pon", etc.).

Uso:
    python scripts/stt_prompt_calibration.py
    python scripts/stt_prompt_calibration.py --segments 30   # subset rapido

Mandato #3 del repo: medir, no celebrar. Esto produce el NUMERO antes de
declarar que el prompt nuevo mejora algo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.inventory import build_initial_prompt, get_inventory
from gemma4_agent.voice.stt import STT, SAMPLE_RATE

AUDIO = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
GROUNDTRUTH = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_groundtruth_full.json"


def _load_audio() -> np.ndarray:
    with wave.open(str(AUDIO), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE, f"{wf.getframerate()} != {SAMPLE_RATE}"
        assert wf.getnchannels() == 1, "mono required"
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)


def _normalize(s: str) -> str:
    """Normaliza para WER: lower, sin puntuacion, colapsa espacios. NO quita
    acentos (queremos saber si small los pierde)."""
    s = s.lower()
    s = re.sub(r"[^\w\sáéíóúüñ]", " ", s)
    return " ".join(s.split())


def _wer(ref: str, hyp: str) -> float:
    """Word Error Rate por distancia de edición a nivel palabra."""
    r = _normalize(ref).split()
    h = _normalize(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
    # DP edit distance
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, len(h) + 1):
            cur = d[j]
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + cost)
            prev = cur
    return d[len(h)] / len(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", type=int, default=0,
                     help="limitar a los primeros N segmentos (0 = todos)")
    args = ap.parse_args()

    gt = json.load(open(GROUNDTRUTH, encoding="utf-8"))
    segments = gt["segments"]
    if args.segments:
        segments = segments[: args.segments]

    audio = _load_audio()
    inv = get_inventory(include_discovery=False)
    prompt_es = build_initial_prompt(inv, lang="es")

    stt = STT()
    if not stt.load():
        print(f"ERROR cargando STT: {stt.last_error}")
        return 1

    variants = {
        "no_prompt": None,
        "prompt_es_nuevo": prompt_es,
    }

    print(f"Audio: {AUDIO.name}  segmentos: {len(segments)}")
    print(f"Prompt nuevo (es): {prompt_es[:120]}...\n")

    totals = {k: [] for k in variants}
    mismatches = []  # (ref, {variant: hyp})

    for seg in segments:
        ref = seg["text"]
        s0 = int(seg["start"] * SAMPLE_RATE)
        s1 = int(seg["end"] * SAMPLE_RATE)
        clip = audio[s0:s1]
        if clip.size < int(0.08 * SAMPLE_RATE):
            continue
        row = {}
        for name, prompt in variants.items():
            hyp = stt.transcribe(clip, initial_prompt=prompt, language="es")
            w = _wer(ref, hyp)
            totals[name].append(w)
            row[name] = (hyp, w)
        # Registrar donde el prompt nuevo difiere o falla
        if row["prompt_es_nuevo"][1] > 0.15:
            mismatches.append((ref, row))

    print("=== WER medio por variante ===")
    for name, ws in totals.items():
        if ws:
            print(f"  {name:18} WER={sum(ws)/len(ws):.4f}  (n={len(ws)})")

    print(f"\n=== Comandos con WER>0.15 con el prompt nuevo ({len(mismatches)}) ===")
    for ref, row in mismatches[:25]:
        print(f"\n  REF : {ref[:90]}")
        for name in variants:
            hyp, w = row[name]
            print(f"  {name:16}: [{w:.2f}] {hyp[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
