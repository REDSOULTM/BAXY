"""Evaluate a frozen cheap acoustic ensemble on an opened RAW room corpus.

The policy combines three independently trained LiveKit-compatible heads and
the temporal shape of the primary score.  It consumes an already captured,
known-playback development corpus so repeated room captures can be compared
without touching a blind human partition or replaying effects.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wakeword import AcousticWakeDetector, WakeWordModelConfig  # noqa: E402


SCHEMA = "baxy.raw-acoustic-ensemble-wake-corpus-development.v1"
SAMPLE_RATE = 16_000
PRIMARY_FIRST_SCORE = 0.05
PRIMARY_PEAK_MAXIMUM_INDEX = 1
PRIMARY_TAIL_TO_PEAK_MAXIMUM = 0.20
BASE_TO_PRIMARY_MINIMUM = 0.50
ALIGNED_TO_PRIMARY_MINIMUM = 0.60


def ensemble_decision(
    *,
    base_maximum: float,
    aligned_maximum: float,
    primary_scores: list[float] | np.ndarray,
) -> tuple[bool, str]:
    primary = np.asarray(primary_scores, dtype=np.float64).reshape(-1)
    if (
        primary.size < 2
        or not np.isfinite(primary).all()
        or not math.isfinite(base_maximum)
        or not math.isfinite(aligned_maximum)
    ):
        raise ValueError("raw_acoustic_ensemble_evidence_invalid")
    maximum = float(np.max(primary))
    if maximum <= 1e-9:
        return False, "primary_signal_absent"
    if float(primary[0]) < PRIMARY_FIRST_SCORE:
        return False, "wake_not_at_utterance_start"
    if int(np.argmax(primary)) > PRIMARY_PEAK_MAXIMUM_INDEX:
        return False, "late_primary_peak"
    if float(primary[-1]) / maximum > PRIMARY_TAIL_TO_PEAK_MAXIMUM:
        return False, "sustained_non_wake_response"
    if base_maximum / maximum < BASE_TO_PRIMARY_MINIMUM:
        return False, "base_model_disagrees"
    if aligned_maximum / maximum < ALIGNED_TO_PRIMARY_MINIMUM:
        return False, "aligned_model_disagrees"
    return True, "early_three_model_consensus"


def _detector(path: Path, name: str) -> AcousticWakeDetector:
    return AcousticWakeDetector(
        WakeWordModelConfig(
            manifest_path=path.parent / "offline-opened-development.json",
            model_path=path,
            model_name=name,
            phrase="Baxy",
            threshold=0.0,
            hop_samples=4_000,
            debounce_seconds=2.0,
            model_sha256=room._sha256(path),
            calibration={},
        )
    )


def _scores(detector: AcousticWakeDetector, audio: np.ndarray) -> list[float]:
    detector.reset()
    _, _, _, values = room._score_recording(detector, audio, 0.0)
    if not values:
        raise ValueError("raw_acoustic_ensemble_scores_empty")
    return [float(value) for value in values]


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"minimum": None, "p50": None, "maximum": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.min(array)),
        "p50": float(np.percentile(array, 50)),
        "maximum": float(np.max(array)),
    }


def _evaluate_group(
    paths: list[Path],
    *,
    base: AcousticWakeDetector,
    aligned: AcousticWakeDetector,
    primary: AcousticWakeDetector,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        started = time.perf_counter()
        base_scores = _scores(base, audio)
        aligned_scores = _scores(aligned, audio)
        primary_scores = _scores(primary, audio)
        accepted, reason = ensemble_decision(
            base_maximum=max(base_scores),
            aligned_maximum=max(aligned_scores),
            primary_scores=primary_scores,
        )
        latencies.append(time.perf_counter() - started)
        primary_maximum = max(primary_scores)
        records.append(
            {
                "record": index,
                "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "accepted": accepted,
                "reason": reason,
                "primaryFirst": primary_scores[0],
                "primaryMaximum": primary_maximum,
                "primaryPeakIndex": int(np.argmax(primary_scores)),
                "primaryTailToPeak": primary_scores[-1] / primary_maximum,
                "baseToPrimary": max(base_scores) / primary_maximum,
                "alignedToPrimary": max(aligned_scores) / primary_maximum,
            }
        )
    return {
        "files": len(paths),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "decisionSeconds": _summary(latencies),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--aligned-model", type=Path, required=True)
    parser.add_argument("--primary-model", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    manifest_path = corpus / "manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("blindHumanPartitionAccessed") is not False:
        raise SystemExit("Corpus blind-boundary attestation is missing.")
    if manifest.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2":
        raise SystemExit("Corpus is not an attested WASAPI RAW capture.")
    positive_paths = room._wav_paths(corpus / "positive", None)
    negative_paths = room._wav_paths(corpus / "negative", None)
    if not positive_paths or not negative_paths:
        raise SystemExit("Both corpus groups require WAV files.")

    model_paths = {
        "base": args.base_model.resolve(strict=True),
        "aligned": args.aligned_model.resolve(strict=True),
        "primary": args.primary_model.resolve(strict=True),
    }
    detectors = {
        name: _detector(path, name) for name, path in model_paths.items()
    }
    started = time.perf_counter()
    positive = _evaluate_group(positive_paths, **detectors)
    negative = _evaluate_group(negative_paths, **detectors)
    passed = (
        positive["acceptedFiles"] == positive["files"]
        and negative["acceptedFiles"] == 0
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_playback_wasapi_raw_room_corpus",
        "policy": {
            "primaryFirstScoreGte": PRIMARY_FIRST_SCORE,
            "primaryPeakMaximumIndex": PRIMARY_PEAK_MAXIMUM_INDEX,
            "primaryTailToPeakLte": PRIMARY_TAIL_TO_PEAK_MAXIMUM,
            "baseToPrimaryGte": BASE_TO_PRIMARY_MINIMUM,
            "alignedToPrimaryGte": ALIGNED_TO_PRIMARY_MINIMUM,
        },
        "models": {
            name: {"sha256": room._sha256(path)}
            for name, path in model_paths.items()
        },
        "corpusManifestSha256": room._sha256(manifest_path),
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedDevelopmentPassed": passed,
        "blindHumanPartitionAccessed": False,
        "candidateFrozen": passed,
        "promotable": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "positive": positive["acceptedFiles"],
                "negative": negative["acceptedFiles"],
                "latencyP50": positive["decisionSeconds"]["p50"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
