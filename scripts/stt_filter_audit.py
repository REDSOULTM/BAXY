"""Per-turn STT filter audit (Sprint O).

Goal: identify whether `_quality_check` gates or decoding params
are the dominant contributor to the bench's stt_wer_mean. The
output of this script is the input to the Sprint O calibration
decision -- DO NOT calibrate before reading the output.

For each wake in testaudio_analysis.json, the script:
  1. Re-slices the corresponding window from testaudio_full.wav
     (using the Sprint P live-endpoint sim).
  2. Calls StreamingSTT._run_whisper directly -- that returns the
     raw Whisper text + per-segment metrics (avg_logprob,
     no_speech_prob, compression_ratio) and the gate decision.
  3. Compares both the raw (pre-filter) text and the post-filter
     text against the Whisper-large-v3 ground truth via jiwer.

Outputs:
  - stdout: per-turn table + pre/post WER means + gate reject
    histogram + interpretation hint (which path A/B/C/D the
    numbers suggest).
  - --json reports/stt_filter_audit_<ts>.json: structured payload
    that future re-runs can diff against.

Usage:
  python scripts/stt_filter_audit.py
  python scripts/stt_filter_audit.py --json reports/audit.json

NOT a calibration tool -- pure diagnostic. The calibration step
edits gemma4_agent/voice/stt.py and is its own decision.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE, CHUNK_SAMPLES  # noqa: E402
from gemma4_agent.voice.stt import (  # noqa: E402
    StreamingSTT, VAD_SILENCE_MS,
)

VOICE_TESTS = ROOT / "gemma4_agent" / "voice" / "tests"
WAV = VOICE_TESTS / "testaudio_full.wav"
ANALYSIS = VOICE_TESTS / "testaudio_analysis.json"
ALIGNED = VOICE_TESTS / "testaudio_groundtruth_aligned.json"

# Mirror the Sprint P live-endpoint constants. These match the
# production transcribe_stream RMS gating.
SPEECH_RMS_THRESHOLD = 200
SPEECH_MIN_CHUNKS = 2
WAKE_TAIL_S = 0.5
WINDOW_S = 15.0


def _live_endpoint(audio: np.ndarray, start_idx: int,
                   max_s: float = WINDOW_S) -> tuple[int, str]:
    """Same as scripts/testaudio_analysis._live_endpoint; inlined
    to keep this script standalone."""
    n = len(audio)
    end_cap = min(n, start_idx + int(max_s * SAMPLE_RATE))
    speech_streak = 0
    first_speech_idx: int | None = None
    last_speech_idx: int | None = None
    silence_samples = 0
    silence_threshold = int((VAD_SILENCE_MS / 1000.0) * SAMPLE_RATE)
    for i in range(start_idx, end_cap, CHUNK_SAMPLES):
        chunk = audio[i:i + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            break
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        if rms > SPEECH_RMS_THRESHOLD:
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
                if silence_samples >= silence_threshold:
                    assert last_speech_idx is not None
                    return last_speech_idx, "endpoint_silence"
    if first_speech_idx is None:
        return start_idx, "no_speech_detected"
    return end_cap, "max_window"


def _load_full_wav() -> np.ndarray:
    with wave.open(str(WAV), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _ensure_jiwer():
    try:
        import jiwer  # type: ignore
        return jiwer
    except ImportError:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "jiwer"]
        )
        import jiwer  # type: ignore
        return jiwer


def _wer(ref: str, hyp: str) -> float | None:
    jiwer = _ensure_jiwer()
    ref_n = (ref or "").strip().lower()
    hyp_n = (hyp or "").strip().lower()
    if not ref_n:
        return None
    return float(jiwer.wer(ref_n, hyp_n))


def audit_turns(turns_meta: list[dict]) -> dict[str, Any]:
    """Run the audit over a list of turn metadata dicts.

    Each entry must include: k, wake_sample_idx, large_text.
    Returns a dict suitable for JSON serialization plus stdout
    rendering. Exposed at module level for unit testing.
    """
    audio = _load_full_wav() if WAV.exists() else None

    if audio is None:
        # Synthetic-test path: caller passed pre-built turns
        # with their own raw_text / post_text / segments. We
        # skip the Whisper call and only do aggregation.
        return _aggregate(turns_meta)

    # Real path: load STT once.
    stt = StreamingSTT()
    if not stt.load():
        raise RuntimeError(f"STT load failed: {stt.last_error}")

    out_turns: list[dict[str, Any]] = []
    for entry in turns_meta:
        k = entry.get("k")
        wake_idx = int(entry.get("wake_sample_idx", -1))
        large_text = entry.get("large_text") or ""
        if wake_idx < 0:
            continue
        start_idx = max(0, wake_idx - int(WAKE_TAIL_S * SAMPLE_RATE))
        end_idx, endpoint_reason = _live_endpoint(audio, start_idx)
        segment = audio[start_idx:end_idx]
        duration_s = (end_idx - start_idx) / SAMPLE_RATE

        # Run the actual Whisper call + quality_check exactly the
        # way the pipeline does. Use _run_whisper so we get
        # Segment objects (with per-segment metrics).
        # _run_whisper expects a float32 audio array post-VAD-trim;
        # we replicate the pipeline preprocessing for fairness.
        from gemma4_agent.voice.stt import _preprocess
        audio_f32 = _preprocess(segment)
        trimmed = stt._vad.trim(audio_f32) if stt._vad else audio_f32
        if trimmed is None:
            # VAD rejected before Whisper -- no segments, no text.
            raw_text = ""
            post_text = ""
            reason = "vad_no_speech"
            segments_meta: list[dict[str, Any]] = []
        else:
            segments, raw_text, ok, reason, _avg_lp = (
                stt._run_whisper(trimmed, duration_s)
            )
            post_text = raw_text if ok else ""
            segments_meta = [
                {
                    "avg_logprob": getattr(s, "avg_logprob", None),
                    "no_speech_prob": getattr(s, "no_speech_prob", None),
                    "compression_ratio": getattr(s, "compression_ratio", None),
                }
                for s in segments
            ]

        wer_pre = _wer(large_text, raw_text)
        wer_post = _wer(large_text, post_text)

        out_turns.append({
            "k": k,
            "duration_s": round(duration_s, 2),
            "endpoint_reason": endpoint_reason,
            "large_text": large_text,
            "small_raw_text": raw_text,
            "small_post_text": post_text,
            "reason": reason,
            "wer_pre": round(wer_pre, 4) if wer_pre is not None else None,
            "wer_post": round(wer_post, 4) if wer_post is not None else None,
            "segments": segments_meta,
        })
        print(
            f"  k={k} dur={duration_s:>5.2f}s "
            f"reason={reason:<22s} "
            f"wer_pre={wer_pre if wer_pre is None else round(wer_pre, 3):<6} "
            f"wer_post={wer_post if wer_post is None else round(wer_post, 3)}"
        )

    return _aggregate(out_turns)


def _aggregate(turns: list[dict[str, Any]]) -> dict[str, Any]:
    pre_wers = [t["wer_pre"] for t in turns if t.get("wer_pre") is not None]
    post_wers = [t["wer_post"] for t in turns if t.get("wer_post") is not None]
    gate_counts: dict[str, int] = {}
    for t in turns:
        # Normalize "low_logprob (-1.23)" -> "low_logprob" for the histogram.
        raw_reason = (t.get("reason") or "").split(" ")[0] or "ok"
        gate_counts[raw_reason] = gate_counts.get(raw_reason, 0) + 1
    return {
        "n_turns": len(turns),
        "pre_wer_mean":  statistics.fmean(pre_wers)  if pre_wers  else None,
        "post_wer_mean": statistics.fmean(post_wers) if post_wers else None,
        "delta_post_minus_pre": (
            (statistics.fmean(post_wers) - statistics.fmean(pre_wers))
            if pre_wers and post_wers else None
        ),
        "gate_reject_counts": gate_counts,
        "turns": turns,
    }


def _render_table(turns: list[dict[str, Any]]) -> str:
    lines = []
    lines.append("| k | duration | reason | wer_pre | wer_post | endpoint |")
    lines.append("|---|---|---|---|---|---|")
    for t in turns:
        wp = t.get("wer_pre")
        wq = t.get("wer_post")
        lines.append(
            f"| {t.get('k')} | {t.get('duration_s')}s | "
            f"`{t.get('reason')}` | "
            f"{wp if wp is None else f'{wp:.3f}'} | "
            f"{wq if wq is None else f'{wq:.3f}'} | "
            f"{t.get('endpoint_reason', 'n/a')} |"
        )
    return "\n".join(lines)


def _interpret(summary: dict[str, Any]) -> str:
    pre = summary.get("pre_wer_mean")
    post = summary.get("post_wer_mean")
    if pre is None or post is None:
        return "(no WER data -- empty or all-skip input)"
    delta = post - pre
    # Heuristic interpretation (mirrors the Sprint O.2 4-path
    # decision table). Threshold of 0.05 WER is the "noise floor"
    # on n=6; larger differences merit a decision.
    if delta > 0.05:
        return (
            f"Filters appear to be the bottleneck: post-filter WER "
            f"({post:.3f}) is meaningfully worse than pre-filter "
            f"({pre:.3f}) -- delta {delta:+.3f}. Suggests Camino A "
            f"(relax the gate that rejects most legitimate turns)."
        )
    if abs(delta) <= 0.05:
        return (
            f"Filters look neutral: pre={pre:.3f}, post={post:.3f}, "
            f"delta {delta:+.3f}. Calibrating gates won't move WER; "
            f"the bottleneck is in the model output itself. "
            f"Suggests Camino B (decoding params) or Camino D "
            f"(no actionable lever at n={summary['n_turns']})."
        )
    return (
        f"Filters are helping: pre={pre:.3f}, post={post:.3f}, "
        f"delta {delta:+.3f}. Don't relax anything."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STT filter audit (Sprint O).")
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None,
        help="Optional JSON output path."
    )
    args = parser.parse_args(argv)

    if not ALIGNED.exists():
        print(f"ERROR: {ALIGNED} not found.")
        return 2
    if not ANALYSIS.exists():
        print(f"ERROR: {ANALYSIS} not found.")
        return 2

    with open(ALIGNED, encoding="utf-8") as fh:
        aligned = json.load(fh)
    with open(ANALYSIS, encoding="utf-8") as fh:
        analysis = json.load(fh)

    # Cross-reference: aligned has the large_text + wer; analysis
    # has the wake_sample_idx we need to re-slice the wav.
    idx_by_k = {
        e["k"]: int(e["wake_sample_idx"])
        for e in analysis.get("all_results", [])
        if e.get("wake_sample_idx") is not None
    }

    turns_meta = []
    for t in aligned.get("turns", []):
        k = t.get("k")
        wake_idx = idx_by_k.get(k)
        if wake_idx is None:
            continue
        turns_meta.append({
            "k": k,
            "wake_sample_idx": wake_idx,
            "large_text": t.get("large_text"),
        })

    print(f"Auditing {len(turns_meta)} turns from {ALIGNED.name}...")
    summary = audit_turns(turns_meta)
    print()
    print(_render_table(summary["turns"]))
    print()
    pre = summary["pre_wer_mean"]
    post = summary["post_wer_mean"]
    delta = summary["delta_post_minus_pre"]
    print(f"Pre-filter  WER mean: {pre if pre is None else f'{pre:.4f}'}")
    print(f"Post-filter WER mean: {post if post is None else f'{post:.4f}'}")
    print(f"Delta (post - pre):   "
          f"{delta if delta is None else f'{delta:+.4f}'}")
    print()
    print("Gate reject histogram:")
    for k, v in sorted(summary["gate_reject_counts"].items(),
                       key=lambda kv: -kv[1]):
        print(f"  {k:<28s} {v}")
    print()
    print("Interpretation:")
    print(f"  {_interpret(summary)}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            **summary,
        }
        args.json_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
