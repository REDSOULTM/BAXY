"""Compare wake-detection backends (Vosk vs openWakeWord) over the
operator's annotated testaudio (Sprint R2 2026-05-18).

For each (backend, threshold) configuration, the script:
  1. Loads the WAV.
  2. Feeds it chunk-by-chunk to the detector.
  3. Records the timestamp of every detected wake.
  4. Matches detections against the annotated expected wakes in
     testaudio_v2_expected.json (within +/- 1.0s tolerance).
  5. Computes recall, precision, F1.

Outputs a markdown table to stdout + optional --json. Used to
decide Sprint R2 outcome A vs B.

Usage:
  python scripts/wake_backend_audit.py
  python scripts/wake_backend_audit.py --json reports/wake_audit.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

VOICE_TESTS = ROOT / "gemma4_agent" / "voice" / "tests"
WAV = VOICE_TESTS / "Grabación (2).wav"
EXPECTED = VOICE_TESTS / "testaudio_v2_expected.json"

CHUNK = 512
MATCH_TOLERANCE_S = 1.0


def _load_audio() -> np.ndarray:
    with wave.open(str(WAV), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _load_expected() -> list[float]:
    with open(EXPECTED, encoding="utf-8") as fh:
        d = json.load(fh)
    return [
        float(e["timestamp_s"])
        for e in d.get("wakes", [])
        if e.get("expected", True)
    ]


def _match_detections(
    detections_s: list[float],
    expected_s: list[float],
    tolerance_s: float = MATCH_TOLERANCE_S,
) -> tuple[int, int, int]:
    """Bipartite-greedy match. Each expected wake can absorb at
    most one detection within tolerance; remaining detections are
    false positives.

    Returns (tp, fp, fn).
    """
    used_expected = [False] * len(expected_s)
    tp = 0
    fp = 0
    for d in detections_s:
        best_i = -1
        best_gap = tolerance_s + 1.0
        for i, e in enumerate(expected_s):
            if used_expected[i]:
                continue
            gap = abs(d - e)
            if gap <= tolerance_s and gap < best_gap:
                best_i = i
                best_gap = gap
        if best_i >= 0:
            used_expected[best_i] = True
            tp += 1
        else:
            fp += 1
    fn = sum(1 for u in used_expected if not u)
    return tp, fp, fn


def _run_vosk(audio: np.ndarray) -> list[float]:
    from gemma4_agent.voice.wake_vosk import VoskWakeDetector
    detections: list[float] = []

    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        # ts here is time.monotonic(); we want audio-time. Patch
        # via index below.
        detections.append((-1.0, phrase, confidence))  # type: ignore[arg-type]

    det = VoskWakeDetector(on_wake=_on_wake)
    if not det.load():
        raise RuntimeError(f"Vosk load failed: {det.last_error}")

    # Replace the callback so we can record the SAMPLE INDEX at
    # the moment of fire, then convert to seconds.
    idx_fires: list[int] = []

    def _on_wake_indexed(phrase: str, ts: float, tail_s: float = 0.0,
                         confidence: float = 0.0) -> None:
        idx_fires.append(_walker[0])

    det._on_wake = _on_wake_indexed
    _walker = [0]  # mutable so closure can mutate
    for i in range(0, len(audio) - CHUNK, CHUNK):
        _walker[0] = i + CHUNK
        det.feed(audio[i:i + CHUNK])
    return [idx / SAMPLE_RATE for idx in idx_fires]


def _run_oww(audio: np.ndarray, threshold: float) -> list[float]:
    # Import lazily; respect the operator's env var override of
    # OWW_THRESHOLD by stomping it for this run.
    import os
    os.environ["GEMMA4_OWW_THRESHOLD"] = str(threshold)
    # Force reload so the constant picks up the env override.
    import importlib
    from gemma4_agent.voice import wake_oww
    importlib.reload(wake_oww)
    detector_class = wake_oww.OpenWakeWordDetector

    idx_fires: list[int] = []

    _walker = [0]

    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        idx_fires.append(_walker[0])

    det = detector_class(on_wake=_on_wake)
    if not det.load():
        raise RuntimeError(f"oww load failed: {det.last_error}")
    for i in range(0, len(audio) - CHUNK, CHUNK):
        _walker[0] = i + CHUNK
        det.feed(audio[i:i + CHUNK])
    return [idx / SAMPLE_RATE for idx in idx_fires]


def _evaluate(
    backend_label: str, threshold: str | float,
    detections_s: list[float], expected_s: list[float],
) -> dict[str, Any]:
    tp, fp, fn = _match_detections(detections_s, expected_s)
    fires = tp + fp
    recall = tp / max(1, len(expected_s))
    precision = tp / max(1, fires) if fires > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )
    return {
        "backend": backend_label,
        "threshold": threshold,
        "fires": fires,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "recall": recall,
        "precision": precision,
        "f1": f1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare wake-detection backends over annotated testaudio."
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None,
        help="Optional JSON output path."
    )
    parser.add_argument(
        "--oww-thresholds", nargs="+", type=float,
        default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        help="Threshold values to sweep for the openWakeWord backend.",
    )
    args = parser.parse_args(argv)

    if not WAV.exists():
        print(f"ERROR: {WAV} not found.")
        return 2
    if not EXPECTED.exists():
        print(f"ERROR: {EXPECTED} not found.")
        return 2

    audio = _load_audio()
    expected = _load_expected()
    print(f"Audio: {len(audio)/SAMPLE_RATE:.1f}s  Expected wakes: {len(expected)}")

    rows: list[dict[str, Any]] = []

    # Vosk pass.
    print("\nRunning Vosk...")
    t0 = time.time()
    vosk_det = _run_vosk(audio)
    elapsed = time.time() - t0
    rows.append({
        **_evaluate("vosk", "n/a", vosk_det, expected),
        "elapsed_s": round(elapsed, 2),
    })

    # openWakeWord pass per threshold.
    for thr in args.oww_thresholds:
        print(f"Running openWakeWord (threshold={thr})...")
        t0 = time.time()
        try:
            oww_det = _run_oww(audio, threshold=thr)
        except Exception as exc:
            print(f"  oww failed at threshold={thr}: {exc}")
            rows.append({
                "backend": "oww/hey_jarvis",
                "threshold": thr,
                "error": str(exc),
            })
            continue
        elapsed = time.time() - t0
        rows.append({
            **_evaluate("oww/hey_jarvis", thr, oww_det, expected),
            "elapsed_s": round(elapsed, 2),
        })

    # Render table.
    print()
    print("| Backend           | Threshold | Fires | TP  | FP  | Recall | Precision | F1     |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print(f"| {r['backend']:<18s}| {str(r['threshold']):<10s}| ERROR: {r['error']}")
            continue
        print(
            f"| {r['backend']:<18s}| {str(r['threshold']):<10s}| "
            f"{r['fires']:<6d}| {r['tp']:<4d}| {r['fp']:<4d}| "
            f"{r['recall']:.3f}  | {r['precision']:.3f}     | {r['f1']:.3f}  |"
        )

    # Identify the best F1 row (excluding Vosk so we get the
    # oww recommendation explicitly).
    oww_rows = [r for r in rows if r.get("backend", "").startswith("oww") and "error" not in r]
    if oww_rows:
        best = max(oww_rows, key=lambda r: r["f1"])
        print(
            f"\nBest oww config: threshold={best['threshold']}  "
            f"recall={best['recall']:.3f}  "
            f"precision={best['precision']:.3f}  "
            f"f1={best['f1']:.3f}"
        )
        vosk_row = next((r for r in rows if r["backend"] == "vosk"), None)
        if vosk_row is not None:
            print(
                f"Vosk baseline:    recall={vosk_row['recall']:.3f}  "
                f"precision={vosk_row['precision']:.3f}  "
                f"f1={vosk_row['f1']:.3f}"
            )
            if best["recall"] > 0:
                ratio = best["recall"] / max(0.001, vosk_row["recall"])
                print(f"Recall improvement vs Vosk: {ratio:.2f}x")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "audio_file": str(WAV.name),
            "audio_duration_s": round(len(audio) / SAMPLE_RATE, 2),
            "expected_wakes": len(expected),
            "tolerance_s": MATCH_TOLERANCE_S,
            "rows": rows,
        }
        args.json_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
