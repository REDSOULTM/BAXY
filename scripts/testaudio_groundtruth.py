"""Whisper-large ground truth generation for testaudio (Sprint N).

Runs faster-whisper large-v3 offline over an operator-provided
audio file to produce a high-quality reference transcription. The
output is used to compare against the production pipeline (Whisper-
small + quality_check) by computing WER/CER per turn.

Usage:
    python scripts/testaudio_groundtruth.py
    python scripts/testaudio_groundtruth.py path/to/audio.m4a
    python scripts/testaudio_groundtruth.py --no-aligned

Outputs (siblings of the audio file's parent dir):
    testaudio_groundtruth_full.json     — continuous transcription
                                           with per-segment timestamps
    testaudio_groundtruth_aligned.json  — per-wake alignment vs the
                                           Sprint M.1 analysis output
    testaudio_groundtruth_report.md     — human-readable report

NOT a unit-tested module — this is operator tooling. Tests cover
the JSON shape (shape contract), not the integration with Whisper.

Model download: first run will fetch faster-whisper large-v3
(~1.5 GB int8 weights) into the standard HF cache. Subsequent
runs reuse it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

# Resolve repo root regardless of cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

logger = logging.getLogger("groundtruth")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


# --- WER/CER -------------------------------------------------------

def _ensure_jiwer():
    """Import jiwer; install it on first run if missing (operator
    install-authorization is granted per project memory)."""
    try:
        import jiwer  # type: ignore
        return jiwer
    except ImportError:
        logger.info("Installing jiwer (one-time, ~100KB)...")
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "jiwer"])
        import jiwer  # type: ignore
        return jiwer


def _compute_wer_cer(reference: str, hypothesis: str) -> tuple[float | None, float | None]:
    """Return (WER, CER) for a reference/hypothesis pair.

    Both reference and hypothesis are normalized: lower-cased,
    leading/trailing whitespace stripped. We do NOT strip
    punctuation — punctuation differences are legit transcription
    errors (e.g. small puts a period where large doesn't).

    Returns (None, None) when the reference is empty (WER/CER
    are undefined in that case). Otherwise returns floats.
    """
    jiwer = _ensure_jiwer()
    ref = (reference or "").strip().lower()
    hyp = (hypothesis or "").strip().lower()
    if not ref:
        return None, None
    wer = jiwer.wer(ref, hyp)
    cer = jiwer.cer(ref, hyp)
    return float(wer), float(cer)


# --- Audio conversion -----------------------------------------------

def _ensure_wav(audio_path: Path) -> Path:
    """Convert audio to WAV 16kHz mono int16 if it isn't already.

    Returns the WAV path (same dir, .wav extension). Idempotent —
    if the WAV exists and is newer than the source, reuses it."""
    if audio_path.suffix.lower() == ".wav":
        return audio_path
    wav_path = audio_path.with_suffix(".wav")
    if wav_path.exists() and wav_path.stat().st_mtime >= audio_path.stat().st_mtime:
        logger.info(f"Reusing existing {wav_path.name}")
        return wav_path
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found in PATH. Install with: winget install ffmpeg"
        )
    logger.info(f"Converting {audio_path.name} -> {wav_path.name} (16kHz mono int16)")
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
    return wav_path


def _load_audio_int16(wav_path: Path) -> np.ndarray:
    """Read a WAV into a 1-D int16 numpy array."""
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE, (
            f"Expected {SAMPLE_RATE} Hz, got {wf.getframerate()}"
        )
        assert wf.getnchannels() == 1, "Expected mono"
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


# --- Whisper-large loader -------------------------------------------

def _cuda_available() -> bool:
    """Probe whether CUDA + cuBLAS are usable for CTranslate2 inference.

    `WhisperModel(device='cuda')` will construct happily even when the
    runtime cuBLAS DLL is missing — the error only surfaces inside
    `model.transcribe`. We probe via torch first so we can fail fast."""
    try:
        import torch  # type: ignore
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _load_whisper_large(model_size: str = "large-v3"):
    """Load faster-whisper large-v3. ~1.5GB download on first run.

    Tries GPU/float16 when CUDA is actually usable; falls back to
    CPU/int8 otherwise. Disables the in-model VAD filter — the
    operator pipeline has its own VAD; we want raw Whisper output."""
    from faster_whisper import WhisperModel  # lazy import
    logger.info(f"Loading faster-whisper {model_size}... "
                "(first run downloads ~1.5GB)")
    t0 = time.time()
    if _cuda_available():
        try:
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            logger.info(f"Loaded on cuda/float16 in {time.time() - t0:.1f}s")
            return model
        except Exception as exc:
            logger.info(f"GPU load failed ({exc}); falling back to CPU/int8")
    else:
        logger.info("CUDA not available — using CPU/int8")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    logger.info(f"Loaded on cpu/int8 in {time.time() - t0:.1f}s")
    return model


# --- Full transcription --------------------------------------------

def _transcribe_full(model, wav_path: Path) -> dict[str, Any]:
    """Run Whisper-large on the full file. Returns the structured
    JSON-ready dict."""
    logger.info("Running large-v3 over full audio...")
    t0 = time.time()
    segments, info = model.transcribe(
        str(wav_path),
        language=None,           # auto-detect
        vad_filter=False,        # no VAD — we want raw output
        beam_size=5,             # default for large
        temperature=0.0,
    )
    out_segments = []
    for s in segments:
        out_segments.append({
            "id": int(s.id),
            "start": round(float(s.start), 3),
            "end": round(float(s.end), 3),
            "text": s.text.strip(),
            "avg_logprob": round(float(s.avg_logprob), 4),
            "no_speech_prob": round(float(s.no_speech_prob), 4),
            "compression_ratio": round(float(s.compression_ratio), 4),
        })
    elapsed = time.time() - t0
    logger.info(f"Full transcription done in {elapsed:.1f}s "
                f"({len(out_segments)} segments)")
    with wave.open(str(wav_path), "rb") as wf:
        total_s = wf.getnframes() / wf.getframerate()
    return {
        "source_file": wav_path.name,
        "model": "large-v3",
        "language_detected": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "total_duration_s": round(total_s, 2),
        "segments": out_segments,
        "manual_correction": "",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "transcribe_elapsed_s": round(elapsed, 2),
    }


# --- Aligned per-wake transcription ---------------------------------

def _verdict(small_raw: str, small_reason: str, large_text: str) -> str:
    """Classify the small-vs-large divergence.

    - 'agree': both transcribed roughly the same.
    - 'small_overproduced': small produced significantly more
      than large — rapid-fire / window-too-long signature.
    - 'small_underproduced': small produced less than large.
    - 'small_rejected_legit': small rejected AND large agrees
      no useful speech.
    - 'small_rejected_false_positive': small rejected but large
      has clear speech — calibration target.
    - 'undetermined': default fallthrough.
    """
    if not large_text.strip():
        if small_reason in ("no_speech", "no_speech_prob", "too_short"):
            return "small_rejected_legit"
        return "undetermined"
    if not small_raw.strip():
        return "small_underproduced"
    small_len = len(small_raw.split())
    large_len = len(large_text.split())
    if small_len > large_len * 1.4:
        return "small_overproduced"
    if small_len < large_len * 0.6:
        return "small_underproduced"
    if small_reason and small_reason != "ok":
        return "small_rejected_false_positive"
    return "agree"


def _transcribe_aligned(model, audio: np.ndarray,
                        analysis_path: Path) -> dict[str, Any] | None:
    """Per-wake-detection transcription. Returns None if the analysis
    file isn't found.

    Sprint P.1 2026-05-18: aligned-window matches the live pipeline
    endpoint logic (re-uses _live_endpoint from testaudio_analysis.py).
    Previously this used a fixed 15s post-wake slice which gave large
    a wider window than the live pipeline produces.
    """
    if not analysis_path.exists():
        logger.warning(f"{analysis_path} not found — skipping aligned pass")
        return None
    # Inline copy of testaudio_analysis._live_endpoint — keeps this
    # script standalone (no re-import of a sibling script that runs
    # Vosk at module top-level). Both copies must stay in sync.
    from gemma4_agent.voice.stt import VAD_SILENCE_MS
    SPEECH_RMS_THRESHOLD = 200
    SPEECH_MIN_CHUNKS = 2
    CHUNK_SAMPLES = 512

    def _live_endpoint(audio_arr: np.ndarray, start_idx: int,
                       max_s: float = 15.0) -> tuple[int, str]:
        """Same logic as scripts/testaudio_analysis._live_endpoint
        (inlined to keep this script standalone — both must stay in
        sync)."""
        n = len(audio_arr)
        max_samples = int(max_s * SAMPLE_RATE)
        end_cap = min(n, start_idx + max_samples)
        speech_streak = 0
        first_speech_idx: int | None = None
        last_speech_idx: int | None = None
        silence_samples = 0
        silence_samples_threshold = int(
            (VAD_SILENCE_MS / 1000.0) * SAMPLE_RATE
        )
        for i in range(start_idx, end_cap, CHUNK_SAMPLES):
            chunk = audio_arr[i:i + CHUNK_SAMPLES]
            if len(chunk) < CHUNK_SAMPLES:
                break
            chunk_rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if chunk_rms > SPEECH_RMS_THRESHOLD:
                speech_streak += 1
                if speech_streak >= SPEECH_MIN_CHUNKS:
                    if first_speech_idx is None:
                        first_speech_idx = i
                    last_speech_idx = i + CHUNK_SAMPLES
                    silence_samples = 0
            else:
                speech_streak = 0
                if first_speech_idx is not None:
                    silence_samples += CHUNK_SAMPLES
                    if silence_samples >= silence_samples_threshold:
                        assert last_speech_idx is not None
                        return last_speech_idx, "endpoint_silence"
        if first_speech_idx is None:
            return start_idx, "no_speech_detected"
        return end_cap, "max_window"

    with open(analysis_path, encoding="utf-8") as fh:
        analysis = json.load(fh)
    WINDOW_S = 15.0
    WAKE_TAIL_S = 0.5
    turns = []
    for entry in analysis.get("all_results", []):
        wake_idx = int(entry.get("wake_sample_idx", -1))
        if wake_idx < 0:
            continue
        start_idx = max(0, wake_idx - int(WAKE_TAIL_S * SAMPLE_RATE))
        end_idx, endpoint_reason = _live_endpoint(
            audio, start_idx=start_idx, max_s=WINDOW_S,
        )
        segment = audio[start_idx:end_idx].astype(np.float32) / 32768.0
        small_raw = entry.get("whisper_raw_text") or entry.get("text") or ""
        small_reason = entry.get("reject_reason") or ""
        t0 = time.time()
        segs, info = model.transcribe(
            segment,
            language=None,
            vad_filter=False,
            beam_size=5,
            temperature=0.0,
        )
        large_pieces = []
        large_no_speech = []
        large_logprob = []
        for s in segs:
            large_pieces.append(s.text.strip())
            large_no_speech.append(float(s.no_speech_prob))
            large_logprob.append(float(s.avg_logprob))
        large_text = " ".join(p for p in large_pieces if p).strip()
        avg_no_speech = float(np.mean(large_no_speech)) if large_no_speech else None
        avg_logprob = float(np.mean(large_logprob)) if large_logprob else None
        wer, cer = _compute_wer_cer(large_text, small_raw)
        elapsed = time.time() - t0
        turns.append({
            "k": entry.get("k"),
            "wake_ts_s": entry.get("wake_ts_s"),
            "segment_duration_s": round((end_idx - start_idx) / SAMPLE_RATE, 2),
            "endpoint_reason": endpoint_reason,
            "small_raw_text": small_raw,
            "small_reject_reason": small_reason,
            "large_text": large_text,
            "large_avg_logprob": round(avg_logprob, 4) if avg_logprob is not None else None,
            "large_no_speech_prob": round(avg_no_speech, 4) if avg_no_speech is not None else None,
            "wer": round(wer, 4) if wer is not None else None,
            "cer": round(cer, 4) if cer is not None else None,
            "verdict": _verdict(small_raw, small_reason, large_text),
            "large_elapsed_s": round(elapsed, 2),
        })
        logger.info(f"  k={entry.get('k')} verdict={turns[-1]['verdict']} "
                    f"wer={turns[-1]['wer']}")
    return {
        "source_file": analysis.get("source_file"),
        "alignment_source": analysis_path.name,
        "wake_count": len(turns),
        "turns": turns,
    }


# --- Report markdown -----------------------------------------------

def _write_report(full: dict, aligned: dict | None, out_path: Path) -> None:
    lines = []
    lines.append("# testaudio ground-truth report")
    lines.append("")
    lines.append(f"- Source: `{full['source_file']}`")
    lines.append(f"- Model: `faster-whisper {full['model']}`")
    lines.append(f"- Language: `{full['language_detected']}` "
                 f"(prob={full['language_probability']})")
    lines.append(f"- Duration: {full['total_duration_s']}s "
                 f"({full['total_duration_s']/60:.2f} min)")
    lines.append(f"- Segments (continuous): {len(full['segments'])}")
    lines.append(f"- Generated: {full['generated_at']}")
    lines.append("")

    lines.append("## Continuous transcription (first 20 segments)")
    lines.append("")
    lines.append("| Start | End | Text | no_speech | logprob |")
    lines.append("|---|---|---|---|---|")
    for s in full["segments"][:20]:
        text = s["text"].replace("|", "\\|")
        lines.append(f"| {s['start']:.2f}s | {s['end']:.2f}s | {text} | "
                     f"{s['no_speech_prob']} | {s['avg_logprob']} |")
    if len(full["segments"]) > 20:
        lines.append(f"\n*({len(full['segments']) - 20} more segments — "
                     f"see testaudio_groundtruth_full.json)*")
    lines.append("")

    if aligned is not None:
        lines.append("## Per-wake alignment (small vs large)")
        lines.append("")
        lines.append("| k | wake_ts | small_reject | verdict | WER | CER |")
        lines.append("|---|---|---|---|---|---|")
        for t in aligned["turns"]:
            wer = f"{t['wer']:.2f}" if t['wer'] is not None else "—"
            cer = f"{t['cer']:.2f}" if t['cer'] is not None else "—"
            reason = t['small_reject_reason'] or "ok"
            lines.append(f"| {t['k']} | {t['wake_ts_s']:.2f}s | {reason} | "
                         f"{t['verdict']} | {wer} | {cer} |")
        lines.append("")

        from collections import Counter
        counts = Counter(t["verdict"] for t in aligned["turns"])
        lines.append("### Verdict distribution")
        lines.append("")
        for verdict, n in counts.most_common():
            lines.append(f"- **{verdict}**: {n}")
        lines.append("")

        lines.append("### Per-turn detail")
        lines.append("")
        for t in aligned["turns"]:
            lines.append(f"#### Turn k={t['k']} (t={t['wake_ts_s']:.2f}s)")
            lines.append("")
            lines.append(f"- **verdict**: {t['verdict']}")
            lines.append(f"- **small reject**: `{t['small_reject_reason']}`")
            lines.append("- **small raw text**:")
            lines.append(f"  > {t['small_raw_text'] or '(empty)'}")
            lines.append("- **large text**:")
            lines.append(f"  > {t['large_text'] or '(empty)'}")
            if t["wer"] is not None:
                lines.append(f"- WER: {t['wer']:.2%} · CER: {t['cer']:.2%}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Ground truth is from Whisper-large-v3. NOT absolute "
                 "truth — large can still err on dialect-specific forms "
                 "(voseo) and uncommon proper nouns. Annotate corrections "
                 "in `manual_correction` field of testaudio_groundtruth_full.json.*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote report to {out_path}")


# --- CLI ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate Whisper-large ground truth for an audio file."
    )
    parser.add_argument(
        "audio_path",
        nargs="?",
        default=str(ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).m4a"),
        help="Path to operator's audio. Default: Grabación (2).m4a"
    )
    parser.add_argument(
        "--no-aligned",
        action="store_true",
        help="Skip the per-wake alignment pass (faster; only continuous output)",
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        help="faster-whisper model size (default: large-v3)",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    if not audio_path.exists():
        sys.exit(f"Audio not found: {audio_path}")
    out_dir = audio_path.parent
    full_out = out_dir / "testaudio_groundtruth_full.json"
    aligned_out = out_dir / "testaudio_groundtruth_aligned.json"
    report_out = out_dir / "testaudio_groundtruth_report.md"
    analysis_path = out_dir / "testaudio_analysis.json"

    wav_path = _ensure_wav(audio_path)
    audio = _load_audio_int16(wav_path)

    model = _load_whisper_large(args.model)

    full = _transcribe_full(model, wav_path)
    # Preserve operator's original filename in source_file (not the .wav)
    full["source_file"] = audio_path.name
    with open(full_out, "w", encoding="utf-8") as fh:
        json.dump(full, fh, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {full_out}")

    aligned = None
    if not args.no_aligned:
        aligned = _transcribe_aligned(model, audio, analysis_path)
        if aligned is not None:
            with open(aligned_out, "w", encoding="utf-8") as fh:
                json.dump(aligned, fh, indent=2, ensure_ascii=False)
            logger.info(f"Wrote {aligned_out}")

    _write_report(full, aligned, report_out)

    print()
    print("=" * 60)
    print(f"Ground truth: {full_out.name}")
    if aligned is not None:
        print(f"Aligned:      {aligned_out.name}")
    print(f"Report:       {report_out.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
