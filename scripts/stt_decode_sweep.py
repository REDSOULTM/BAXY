"""Barrido de parámetros de decoding de Whisper-small, medido contra la verdad
wake-anchored (testaudio_groundtruth_aligned.json) sobre Grabación (2).wav.

Compara WER + latencia de varias configs vs el baseline actual:
  - baseline      : beam=1, temp=0.0, sin thresholds (config actual del repo)
  - beam5         : beam=5 (default de Whisper), resto igual
  - beam5_thr     : beam=5 + thresholds de filtro (logprob/compression/no_speech)
  - beam5_temp_fb : beam=5 + temperature fallback (0.0..0.4)

Mide WER (wake-anchored, alineación correcta — NO segment-level) y latencia
media por turno. Mandato #3: número antes de decidir. Si la latencia se dispara
(regla <300ms del user), se descarta aunque mejore WER.

Uso:  python scripts/stt_decode_sweep.py
"""
from __future__ import annotations

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

AUDIO = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
ALIGNED = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_groundtruth_aligned.json"
SAMPLE_RATE = 16000


def _load_audio() -> np.ndarray:
    with wave.open(str(AUDIO), "rb") as wf:
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\sáéíóúüñ]", " ", s)
    return " ".join(s.split())


def _wer(ref: str, hyp: str) -> float:
    r, h = _norm(ref).split(), _norm(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
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


CONFIGS = {
    "baseline": dict(beam_size=1, best_of=1, temperature=0.0),
    "beam5": dict(beam_size=5, best_of=5, temperature=0.0),
    "beam5_thr": dict(
        beam_size=5, best_of=5, temperature=0.0,
        log_prob_threshold=-1.0, compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
    ),
    "beam5_temp_fb": dict(
        beam_size=5, best_of=5,
        temperature=[0.0, 0.2, 0.4],
        log_prob_threshold=-1.0, compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
    ),
}

COMMON = dict(
    language="es", task="transcribe",
    condition_on_previous_text=False, vad_filter=False,
    without_timestamps=True,
)


def main() -> int:
    from faster_whisper import WhisperModel
    model = WhisperModel(
        "small", device="cpu", compute_type="int8", cpu_threads=4,
        download_root=str(Path.home() / ".gemma4" / "models" / "whisper"),
    )
    inv = get_inventory(include_discovery=False)
    prompt = build_initial_prompt(inv, lang="es")
    audio = _load_audio()
    turns = json.load(open(ALIGNED, encoding="utf-8"))["turns"]

    results = {}
    for cfg_name, cfg in CONFIGS.items():
        wers, lats = [], []
        for t in turns:
            s0 = int(t["wake_ts_s"] * SAMPLE_RATE)
            s1 = s0 + int(t["segment_duration_s"] * SAMPLE_RATE)
            clip = (audio[s0:s1].astype(np.float32)) / 32768.0
            if clip.size < int(0.08 * SAMPLE_RATE):
                continue
            kwargs = dict(COMMON, **cfg, initial_prompt=prompt)
            t0 = time.time()
            segs, _ = model.transcribe(clip, **kwargs)
            hyp = " ".join(s.text.strip() for s in segs).strip()
            lats.append(time.time() - t0)
            wers.append(_wer(t["large_text"], hyp))
        results[cfg_name] = (
            sum(wers) / len(wers) if wers else 1.0,
            sum(lats) / len(lats) if lats else 0.0,
            max(lats) if lats else 0.0,
            len(wers),
        )

    print(f"\n{'config':16} {'WER':>7} {'lat_avg':>9} {'lat_max':>9} {'n':>3}")
    print("-" * 50)
    for name, (wer, lat, latmax, n) in results.items():
        print(f"{name:16} {wer:7.4f} {lat*1000:7.0f}ms {latmax*1000:7.0f}ms {n:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
