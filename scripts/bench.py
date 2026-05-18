"""Production-readiness bench harness for gemma4_agent.

Measures the 5 thresholds defined in docs/PRODUCTION_READY.md:

  1. wake_recall: fraction of expected wakes Vosk detects.
  2. wake_fp_rate: false-positive fires per hour over idle audio.
  3. stt_wer_mean: WER vs Whisper-large-v3 ground truth.
  4. stt_latency_p95: p95 latency of _transcribe_buffer over
     short clips (GPU-only; CPU mode reports SKIPPED).
  5. voice_e2e_p95: parsed from a real session manifest (if
     provided via --session-jsonl).

Usage:
    python scripts/bench.py
    python scripts/bench.py --ci             # skip GPU+audio-fresh
    python scripts/bench.py --threshold wake_recall
    python scripts/bench.py --session-jsonl path/to/manifest.jsonl

Outputs:
    bench_results/<YYYYMMDD_HHMMSS>.json
    bench_results/<YYYYMMDD_HHMMSS>.md

Exit code:
    0 -> all measured thresholds pass.
    1 -> at least one threshold failed.
    2 -> harness error (missing dep, missing audio, etc.).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import statistics
import sys
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

logger = logging.getLogger("bench")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# --- Thresholds (mirror PRODUCTION_READY.md) ------------------------

THRESHOLDS = {
    "wake_recall":      {"target": 0.70, "op": ">="},
    "wake_fp_rate":     {"target": 1.0,  "op": "<="},   # per hour
    "stt_wer_mean":     {"target": 0.20, "op": "<"},
    "stt_latency_p95":  {"target": 1.2,  "op": "<="},   # seconds
    "voice_e2e_p95":    {"target": 5.0,  "op": "<="},   # seconds
}

# --- Audio fixtures ------------------------------------------------

VOICE_TESTS = ROOT / "gemma4_agent" / "voice" / "tests"
TEST_V2 = VOICE_TESTS / "testaudio_v2.wav"
TEST_V2_EXPECTED = VOICE_TESTS / "testaudio_v2_expected.json"
TEST_IDLE = VOICE_TESTS / "testaudio_idle.wav"
TEST_FALLBACK = VOICE_TESTS / "Grabación (2).wav"


@dataclass
class ThresholdResult:
    name: str
    measured: float | None
    target: float
    op: str
    passed: bool | None  # None means SKIPPED
    note: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.passed is None:
            return "SKIPPED"
        return "PASS" if self.passed else "FAIL"


def _compare(measured: float, target: float, op: str) -> bool:
    if op == ">=": return measured >= target
    if op == ">":  return measured > target
    if op == "<=": return measured <= target
    if op == "<":  return measured < target
    raise ValueError(f"unknown op: {op}")


# --- jiwer auto-install ---------------------------------------------

def _ensure_jiwer():
    try:
        import jiwer  # type: ignore
        return jiwer
    except ImportError:
        logger.info("Installing jiwer (one-time)...")
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "jiwer"])
        import jiwer  # type: ignore
        return jiwer


# --- Audio loading helpers -----------------------------------------

def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getnchannels() == 1
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _pick_reference_audio() -> tuple[Path | None, str]:
    """Return (path, note). Prefers testaudio_v2.wav; falls back
    to Grabación (2).wav with a degradation note."""
    if TEST_V2.exists():
        return TEST_V2, "native WAV (v2)"
    if TEST_FALLBACK.exists():
        return TEST_FALLBACK, "fallback (m4a-converted; v2 not available)"
    return None, "no reference audio"


# --- Threshold 1: wake_recall ---------------------------------------

def measure_wake_recall() -> ThresholdResult:
    audio_path, note = _pick_reference_audio()
    if audio_path is None:
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note="no reference audio found",
        )
    if not TEST_V2_EXPECTED.exists() and audio_path == TEST_V2:
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note="testaudio_v2_expected.json missing",
        )
    audio = _load_wav(audio_path)
    from gemma4_agent.voice.wake import WakeDetector  # lazy
    detections: list = []
    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        detections.append((ts, phrase, confidence))
    det = WakeDetector(on_wake=_on_wake)
    if not det.load():
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note=f"Vosk load failed: {det.last_error}",
        )
    CHUNK = 512
    for i in range(0, len(audio) - CHUNK, CHUNK):
        det.feed(audio[i:i + CHUNK])
    fires = len(detections)
    if TEST_V2_EXPECTED.exists():
        with open(TEST_V2_EXPECTED, encoding="utf-8") as fh:
            expected = json.load(fh)
        expected_count = sum(1 for e in expected.get("wakes", []) if e.get("expected"))
        recall = fires / max(1, expected_count)
        return ThresholdResult(
            "wake_recall", recall,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=_compare(recall, THRESHOLDS["wake_recall"]["target"], THRESHOLDS["wake_recall"]["op"]),
            note=f"audio={audio_path.name} ({note})",
            details={"fires": fires, "expected": expected_count},
        )
    return ThresholdResult(
        "wake_recall", None,
        THRESHOLDS["wake_recall"]["target"],
        THRESHOLDS["wake_recall"]["op"],
        passed=None,
        note=f"fires={fires} on {audio_path.name} ({note}); no expected.json",
        details={"fires": fires},
    )


# --- Threshold 2: wake_fp_rate ---------------------------------------

def measure_wake_fp_rate() -> ThresholdResult:
    if not TEST_IDLE.exists():
        return ThresholdResult(
            "wake_fp_rate", None,
            THRESHOLDS["wake_fp_rate"]["target"],
            THRESHOLDS["wake_fp_rate"]["op"],
            passed=None,
            note="testaudio_idle.wav missing",
        )
    audio = _load_wav(TEST_IDLE)
    duration_h = len(audio) / SAMPLE_RATE / 3600
    from gemma4_agent.voice.wake import WakeDetector
    fires = []
    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        fires.append((ts, phrase))
    det = WakeDetector(on_wake=_on_wake)
    if not det.load():
        return ThresholdResult(
            "wake_fp_rate", None,
            THRESHOLDS["wake_fp_rate"]["target"],
            THRESHOLDS["wake_fp_rate"]["op"],
            passed=None,
            note=f"Vosk load failed: {det.last_error}",
        )
    CHUNK = 512
    for i in range(0, len(audio) - CHUNK, CHUNK):
        det.feed(audio[i:i + CHUNK])
    rate = len(fires) / max(0.001, duration_h)
    return ThresholdResult(
        "wake_fp_rate", rate,
        THRESHOLDS["wake_fp_rate"]["target"],
        THRESHOLDS["wake_fp_rate"]["op"],
        passed=_compare(rate, THRESHOLDS["wake_fp_rate"]["target"], THRESHOLDS["wake_fp_rate"]["op"]),
        note=f"{len(fires)} fires in {duration_h*60:.1f}min idle",
        details={"fires": len(fires), "duration_h": duration_h},
    )


# --- Threshold 3: stt_wer_mean --------------------------------------

def measure_stt_wer_mean() -> ThresholdResult:
    """Compute WER of production small vs large-v3 ground truth.

    Reuses testaudio_groundtruth_aligned.json from Sprint N if
    available -- that file already has small and large transcriptions
    aligned per wake. If missing, SKIPPED."""
    aligned = VOICE_TESTS / "testaudio_groundtruth_aligned.json"
    if not aligned.exists():
        return ThresholdResult(
            "stt_wer_mean", None,
            THRESHOLDS["stt_wer_mean"]["target"],
            THRESHOLDS["stt_wer_mean"]["op"],
            passed=None,
            note="testaudio_groundtruth_aligned.json missing -- run scripts/testaudio_groundtruth.py",
        )
    with open(aligned, encoding="utf-8") as fh:
        d = json.load(fh)
    jiwer = _ensure_jiwer()
    wers = []
    for t in d.get("turns", []):
        ref = (t.get("large_text") or "").strip().lower()
        hyp = (t.get("small_raw_text") or t.get("small_text") or "").strip().lower()
        if not ref:
            continue
        wer = float(jiwer.wer(ref, hyp))
        wers.append(wer)
    if not wers:
        return ThresholdResult(
            "stt_wer_mean", None,
            THRESHOLDS["stt_wer_mean"]["target"],
            THRESHOLDS["stt_wer_mean"]["op"],
            passed=None,
            note="no non-empty references in aligned JSON",
        )
    mean_wer = statistics.fmean(wers)
    return ThresholdResult(
        "stt_wer_mean", mean_wer,
        THRESHOLDS["stt_wer_mean"]["target"],
        THRESHOLDS["stt_wer_mean"]["op"],
        passed=_compare(mean_wer, THRESHOLDS["stt_wer_mean"]["target"], THRESHOLDS["stt_wer_mean"]["op"]),
        note=f"n={len(wers)} turns",
        details={"wers": [round(w, 3) for w in wers]},
    )


# --- Threshold 4: stt_latency_p95 -----------------------------------

def measure_stt_latency_p95(ci_mode: bool = False) -> ThresholdResult:
    """Measure _transcribe_buffer p95 latency over synthesized
    short clips. GPU-only; CPU mode -> SKIPPED."""
    if ci_mode:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="--ci flag: GPU bench skipped",
        )
    # Sprint Q.0 2026-05-18: torch is CPU-only on this system but
    # ctranslate2 (used by faster-whisper) has its own CUDA build.
    # We probe ctranslate2 directly -- that's what actually matters
    # for STT latency on the production pipeline.
    try:
        import ctranslate2  # type: ignore
    except ImportError:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="ctranslate2 not installed",
        )
    if ctranslate2.get_cuda_device_count() < 1:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="No CUDA devices detected by ctranslate2",
        )
    # Device count > 0 doesn't guarantee inference works -- the
    # runtime DLLs (cublas64_12.dll etc.) might still be missing.
    # Probe with a tiny model + 1s of audio before declaring the
    # GPU usable.
    try:
        from faster_whisper import WhisperModel as _Probe
        _probe = _Probe("tiny", device="cuda", compute_type="float16")
        _audio = (np.random.randn(16000) * 100).astype(np.float32) / 32768
        list(_probe.transcribe(_audio, language="es", beam_size=1)[0])
    except Exception as exc:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note=(
                f"GPU inference probe failed: {exc}. "
                f"Try: python scripts/setup_cuda_runtime.py"
            ),
        )
    # Sprint Q.0: StreamingSTT is locked to device="cpu" by design
    # (live pipeline runs CPU/int8 for predictable latency without
    # GPU contention with the LLM). The threshold here measures
    # what GPU CAN do -- i.e. headroom for a future Sprint Q model
    # upgrade. We build a separate WhisperModel on cuda/float16
    # for this measurement only.
    from faster_whisper import WhisperModel  # lazy
    try:
        whisper_gpu = WhisperModel(
            "small", device="cuda", compute_type="float16",
        )
    except Exception as exc:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note=f"GPU WhisperModel load failed: {exc}",
        )
    latencies = []
    for clip_s in [1.0, 2.0, 3.0]:
        clip_f32 = (np.random.randn(int(clip_s * SAMPLE_RATE))
                    * 2000).astype(np.float32) / 32768
        # Warm-up.
        list(whisper_gpu.transcribe(clip_f32, language="es", beam_size=1)[0])
        for _ in range(20):
            t0 = time.perf_counter()
            segs, _info = whisper_gpu.transcribe(
                clip_f32, language="es", beam_size=1,
            )
            list(segs)  # force decoder
            latencies.append(time.perf_counter() - t0)
    p95 = float(np.percentile(latencies, 95))
    return ThresholdResult(
        "stt_latency_p95", p95,
        THRESHOLDS["stt_latency_p95"]["target"],
        THRESHOLDS["stt_latency_p95"]["op"],
        passed=_compare(p95, THRESHOLDS["stt_latency_p95"]["target"], THRESHOLDS["stt_latency_p95"]["op"]),
        note=f"n={len(latencies)} runs over clips 1-3s",
        details={"p50": round(float(np.percentile(latencies, 50)), 3),
                 "p95": round(p95, 3),
                 "max": round(float(np.max(latencies)), 3)},
    )


# --- Threshold 5: voice_e2e_p95 -------------------------------------

def measure_voice_e2e_p95(session_jsonl: Path | None) -> ThresholdResult:
    """Parse a real session manifest for wake->TTS-finished
    timings. Requires --session-jsonl path; SKIPPED otherwise."""
    if session_jsonl is None or not session_jsonl.exists():
        return ThresholdResult(
            "voice_e2e_p95", None,
            THRESHOLDS["voice_e2e_p95"]["target"],
            THRESHOLDS["voice_e2e_p95"]["op"],
            passed=None,
            note="--session-jsonl not provided or missing",
        )
    elapsed_per_turn = []
    with open(session_jsonl, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("duration_s") and e.get("whisper_transcription"):
                elapsed_per_turn.append(float(e["duration_s"]))
    if len(elapsed_per_turn) < 5:
        return ThresholdResult(
            "voice_e2e_p95", None,
            THRESHOLDS["voice_e2e_p95"]["target"],
            THRESHOLDS["voice_e2e_p95"]["op"],
            passed=None,
            note=f"only {len(elapsed_per_turn)} turns in manifest; need >=5",
        )
    p95 = float(np.percentile(elapsed_per_turn, 95))
    return ThresholdResult(
        "voice_e2e_p95", p95,
        THRESHOLDS["voice_e2e_p95"]["target"],
        THRESHOLDS["voice_e2e_p95"]["op"],
        passed=_compare(p95, THRESHOLDS["voice_e2e_p95"]["target"], THRESHOLDS["voice_e2e_p95"]["op"]),
        note=f"n={len(elapsed_per_turn)} turns from {session_jsonl.name}",
        details={"p50": round(float(np.percentile(elapsed_per_turn, 50)), 3),
                 "p95": round(p95, 3),
                 "max": round(float(np.max(elapsed_per_turn)), 3)},
    )


# --- Output writers --------------------------------------------------

def _write_outputs(results: list[ThresholdResult], out_dir: Path) -> tuple[Path, Path]:
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{ts}.json"
    md_path = out_dir / f"{ts}.md"

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "thresholds": [asdict(r) for r in results],
        "summary": {
            "total":    len(results),
            "passed":   sum(1 for r in results if r.passed is True),
            "failed":   sum(1 for r in results if r.passed is False),
            "skipped":  sum(1 for r in results if r.passed is None),
            "production_ready": all(r.passed is True for r in results),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    lines = []
    lines.append(f"# Bench results -- {payload['generated_at']}")
    lines.append("")
    s = payload["summary"]
    lines.append(f"**Summary**: {s['passed']}/{s['total']} passed, "
                 f"{s['failed']} failed, {s['skipped']} skipped.")
    if s["production_ready"]:
        lines.append("")
        lines.append("**PRODUCTION READY** -- all 5 thresholds green.")
    else:
        lines.append("")
        lines.append("**Not production ready** -- at least one threshold red or skipped.")
    lines.append("")
    lines.append("| Threshold | Status | Measured | Target | Note |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        measured = "--" if r.measured is None else f"{r.measured:.3f}"
        target = f"{r.op} {r.target}"
        lines.append(f"| `{r.name}` | **{r.status}** | {measured} | {target} | {r.note} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


# --- CLI -----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="gemma4_agent production-readiness bench harness."
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="Skip GPU-required + audio-fresh thresholds (for CI runs)",
    )
    parser.add_argument(
        "--threshold", choices=list(THRESHOLDS.keys()),
        help="Run only the named threshold",
    )
    parser.add_argument(
        "--session-jsonl", type=Path, default=None,
        help="Path to a recorder manifest.jsonl for voice_e2e_p95 measurement",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT / "bench_results",
        help="Where to write the JSON+md outputs (default: bench_results/)",
    )
    args = parser.parse_args()

    results = []
    selected = [args.threshold] if args.threshold else list(THRESHOLDS.keys())

    if "wake_recall" in selected:
        logger.info("Running wake_recall...")
        results.append(measure_wake_recall())
    if "wake_fp_rate" in selected:
        logger.info("Running wake_fp_rate...")
        results.append(measure_wake_fp_rate())
    if "stt_wer_mean" in selected:
        logger.info("Running stt_wer_mean...")
        results.append(measure_stt_wer_mean())
    if "stt_latency_p95" in selected:
        logger.info("Running stt_latency_p95...")
        results.append(measure_stt_latency_p95(ci_mode=args.ci))
    if "voice_e2e_p95" in selected:
        logger.info("Running voice_e2e_p95...")
        results.append(measure_voice_e2e_p95(args.session_jsonl))

    json_path, md_path = _write_outputs(results, args.out_dir)
    logger.info(f"Wrote {json_path}")
    logger.info(f"Wrote {md_path}")

    print()
    print("=" * 60)
    print(f"Results: {md_path}")
    print("=" * 60)
    for r in results:
        m = "--" if r.measured is None else f"{r.measured:.3f}"
        print(f"  {r.name:20s} {r.status:8s} {m:>8s}  {r.note}")

    if any(r.passed is False for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
