"""Experiment: compare language=es vs language=None vs enhanced prompt
on the 6 testaudio turns. Goal: figure out which config minimizes WER
on the Spanish+English-app-names case (operator says 'abre Chrome',
'open Chrome', 'Búscame Benson Boone').

Runs each config over the same 6 audio segments and tabulates WER.
"""
from __future__ import annotations

import json
import sys
import wave
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ALIGNED_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_groundtruth_aligned.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"


SAMPLE_RATE = 16000


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _wer(ref: str, hyp: str) -> float:
    import jiwer
    return float(jiwer.wer(ref.strip().lower(), hyp.strip().lower()))


# 4 prompt variants to test
PROMPTS = {
    "original_es": (
        "Conversacion con el asistente Gemma. "
        "Hey Gemma, abre Steam. Hey Gemma, abre Spotify y reproduce musica. "
        "Comandos breves en espanol dirigidos al asistente Gemma."
    ),
    "bilingual_apps": (
        # Mezcla explícita español + inglés con app names tal cual se escriben
        "Conversacion con el asistente Gemma en espanol con apps en ingles. "
        "Hey Gemma, abre Chrome. Hey Gemma, open Chrome. "
        "Hey Gemma, abre Steam. Hey Gemma, open Steam. "
        "Hey Gemma, abre Spotify. Hey Gemma, open Spotify. "
        "Hey Gemma, abre Discord, abre WhatsApp, abre Telegram, abre YouTube, "
        "abre Netflix, abre Counter-Strike 2, abre GTA V. "
        "Hey Gemma, reproduce Bohemian Rhapsody. "
        "Hey Gemma, buscame info sobre Benson Boone. "
        "Hey Gemma, mandale un mensaje a Juan por WhatsApp. "
        "Hey Gemma, ponme musica tranquila. Hey Gemma, sube el volumen. "
        "Comandos breves en espanol rioplatense con nombres de aplicaciones en ingles."
    ),
}

LANG_OPTIONS = [
    ("es_orig",       "es",  PROMPTS["original_es"]),
    ("es_bilingual",  "es",  PROMPTS["bilingual_apps"]),
    ("auto_orig",     None,  PROMPTS["original_es"]),
    ("auto_bilingual", None, PROMPTS["bilingual_apps"]),
]


def main():
    with open(ALIGNED_PATH, encoding="utf-8") as fh:
        aligned = json.load(fh)
    audio = _load_wav(AUDIO_PATH)

    # Lazy-load Whisper small CPU (production config)
    from faster_whisper import WhisperModel
    print("Loading Whisper-small CPU/int8...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    print("Loaded.")

    # Build the 6 audio segments from the cached turn timings
    segments = []
    for turn in aligned["turns"]:
        wake_ts = turn["wake_ts_s"]
        dur = turn["segment_duration_s"]
        start_idx = int(max(0, wake_ts - 0.5) * SAMPLE_RATE)
        end_idx = start_idx + int(dur * SAMPLE_RATE)
        audio_f32 = audio[start_idx:end_idx].astype(np.float32) / 32768.0
        segments.append({
            "k": turn["k"],
            "audio": audio_f32,
            "duration_s": dur,
            "large_text": turn.get("large_text", ""),
        })

    # Run each config over the 6 segments
    results = {}
    for config_name, language, prompt in LANG_OPTIONS:
        print(f"\n=== Config: {config_name} (language={language}) ===")
        wers = []
        transcripts = []
        for seg in segments:
            dur = seg["duration_s"]
            beam_size = 1 if dur < 3.0 else 5
            best_of = 1 if dur < 3.0 else 5
            temperature = 0.0 if dur < 3.0 else (0.0, 0.2, 0.4)
            t0 = time.time()
            try:
                segs_gen, info = model.transcribe(
                    seg["audio"],
                    language=language,
                    initial_prompt=prompt,
                    beam_size=beam_size,
                    best_of=best_of,
                    temperature=temperature,
                    task="transcribe",
                    condition_on_previous_text=False,
                    vad_filter=False,
                    without_timestamps=False,
                )
                pieces = [s.text.strip() for s in segs_gen]
                hyp = " ".join(p for p in pieces if p).strip()
                detected_lang = getattr(info, "language", "?")
                elapsed = time.time() - t0
            except Exception as exc:
                hyp = f"ERROR: {exc}"
                detected_lang = "?"
                elapsed = 0.0
            ref = seg["large_text"]
            w = _wer(ref, hyp) if ref else None
            wers.append(w)
            transcripts.append({
                "k": seg["k"],
                "dur": dur,
                "ref": ref,
                "hyp": hyp,
                "wer": w,
                "lang_detected": detected_lang,
                "elapsed_s": round(elapsed, 2),
            })
            print(f"  k={seg['k']} dur={dur:.2f}s lang_det={detected_lang} wer={w:.3f} elapsed={elapsed:.2f}s")
            print(f"    ref: {ref[:80]}")
            print(f"    hyp: {hyp[:80]}")
        mean_wer = float(np.mean([w for w in wers if w is not None]))
        print(f"  MEAN WER: {mean_wer:.4f}")
        results[config_name] = {
            "mean_wer": mean_wer,
            "wers": wers,
            "transcripts": transcripts,
        }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Config':<20s} {'Mean WER':>10s} {'k=0':>8s} {'k=1':>8s} {'k=2':>8s} {'k=3':>8s} {'k=4':>8s} {'k=5':>8s}")
    for name, res in results.items():
        wers = res["wers"]
        print(f"{name:<20s} {res['mean_wer']:>10.4f} "
              + " ".join(f"{w:>8.3f}" for w in wers))

    # Save full results to JSON for inspection
    out_path = ROOT / "bench_results" / "stt_language_experiment.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
