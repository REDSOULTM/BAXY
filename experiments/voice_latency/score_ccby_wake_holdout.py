"""Score a human wake-word partition with runtime-equivalent sliding windows.

Blind scoring is fail-closed: it requires a candidate-freeze manifest whose
model hash, threshold, and preregistration hash match the corpus exactly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Protocol
import wave

import numpy as np


SAMPLE_RATE = 16_000
WINDOW_SECONDS = 2.0
# BAXY's product detector defaults to DEFAULT_HOP_SAMPLES=4_000.  Keep the
# isolated holdout on the same 250 ms scoring cadence as the physical gate.
STEP_SECONDS = 0.25


class Predictor(Protocol):
    def predict(self, audio_chunk: np.ndarray) -> dict[str, float]: ...


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"wav_contract_mismatch:{path}:{contract}")
        payload = source.readframes(source.getnframes())
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def streaming_max_score(
    model: Predictor,
    audio: np.ndarray,
    *,
    sample_rate: int = SAMPLE_RATE,
    window_seconds: float = WINDOW_SECONDS,
    step_seconds: float = STEP_SECONDS,
) -> tuple[float, float, int]:
    """Return max score, its window-end time, and number of runtime windows."""
    window_samples = round(window_seconds * sample_rate)
    step_samples = round(step_seconds * sample_rate)
    if window_samples <= 0 or step_samples <= 0:
        raise ValueError("invalid_window_geometry")
    flattened = np.asarray(audio, dtype=np.float32).flatten()
    # A listener already has a full rolling buffer before and after a spoken
    # phrase.  Silence makes this isolated-corpus simulation deterministic;
    # the physical room gate later supplies real acoustic context.
    padded = np.concatenate(
        [
            np.zeros(window_samples, dtype=np.float32),
            flattened,
            np.zeros(window_samples, dtype=np.float32),
        ]
    )
    best_score = float("-inf")
    best_end_seconds = 0.0
    count = 0
    for end in range(window_samples, len(padded) + 1, step_samples):
        window = padded[end - window_samples : end]
        scores = model.predict(window)
        if len(scores) != 1:
            raise ValueError(f"expected_one_classifier:actual={len(scores)}")
        score = float(next(iter(scores.values())))
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"classifier_score_out_of_range:{score}")
        count += 1
        if score > best_score:
            best_score = score
            best_end_seconds = (end - window_samples) / sample_rate
    if count == 0:
        raise ValueError("no_streaming_windows_scored")
    return best_score, best_end_seconds, count


def validate_blind_freeze(
    *,
    freeze: dict[str, object],
    model_sha256: str,
    threshold: float,
    preregistration_sha256: str,
) -> None:
    if freeze.get("schema") != "baxy.wake-candidate-freeze.v1":
        raise ValueError("unsupported_candidate_freeze_schema")
    if str(freeze.get("model_sha256", "")).casefold() != model_sha256.casefold():
        raise ValueError("blind_model_hash_mismatch")
    try:
        frozen_threshold = float(freeze["threshold"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("blind_threshold_missing") from error
    if abs(frozen_threshold - threshold) > 1e-12:
        raise ValueError("blind_threshold_mismatch")
    if (
        str(freeze.get("preregistration_sha256", "")).casefold()
        != preregistration_sha256.casefold()
    ):
        raise ValueError("blind_preregistration_hash_mismatch")
    if freeze.get("development_only_evidence") is not True:
        raise ValueError("candidate_was_not_frozen_from_development_only_evidence")


def score_partition(
    *,
    model: Predictor,
    model_path: Path,
    corpus_manifest_path: Path,
    partition: str,
    threshold: float,
    output_path: Path,
    freeze_manifest_path: Path | None = None,
) -> dict[str, object]:
    if partition not in {"development", "blind"}:
        raise ValueError(f"unsupported_partition:{partition}")
    if not 0.0 < threshold < 1.0:
        raise ValueError(f"threshold_out_of_range:{threshold}")
    corpus = read_json(corpus_manifest_path)
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("unsupported_corpus_schema")
    model_hash = sha256(model_path)
    preregistration_hash = str(corpus.get("preregistration_sha256", ""))
    freeze_hash: str | None = None
    if partition == "blind":
        if freeze_manifest_path is None:
            raise ValueError("blind_scoring_requires_candidate_freeze")
        freeze = read_json(freeze_manifest_path)
        validate_blind_freeze(
            freeze=freeze,
            model_sha256=model_hash,
            threshold=threshold,
            preregistration_sha256=preregistration_hash,
        )
        freeze_hash = sha256(freeze_manifest_path)

    raw_records = corpus.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("corpus_records_missing")
    corpus_root = corpus_manifest_path.parent
    scored: list[dict[str, object]] = []
    for raw in raw_records:
        if not isinstance(raw, dict) or raw.get("partition") != partition:
            continue
        path = corpus_root / str(raw["output_relative_path"])
        expected_hash = str(raw.get("wav", {}).get("sha256", ""))
        if sha256(path) != expected_hash:
            raise ValueError(f"corpus_clip_hash_mismatch:{path}")
        score, max_window_end, window_count = streaming_max_score(
            model, read_wav(path)
        )
        label = str(raw["label"])
        detected = score >= threshold
        correct = detected if label == "positive" else not detected
        scored.append(
            {
                "source_id": raw["source_id"],
                "speaker_group": raw["speaker_group"],
                "label": label,
                "output_relative_path": raw["output_relative_path"],
                "score": round(score, 9),
                "detected": detected,
                "correct": correct,
                "max_score_window_end_seconds": round(max_window_end, 6),
                "windows_scored": window_count,
            }
        )
    if not scored:
        raise ValueError(f"partition_has_no_records:{partition}")
    positive = [record for record in scored if record["label"] == "positive"]
    negative = [record for record in scored if record["label"] == "hard_negative"]
    true_positive = sum(bool(record["detected"]) for record in positive)
    true_negative = sum(not bool(record["detected"]) for record in negative)
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-holdout-score.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "partition": partition,
        "model_sha256": model_hash,
        "threshold": threshold,
        "corpus_manifest_sha256": sha256(corpus_manifest_path),
        "preregistration_sha256": preregistration_hash,
        "candidate_freeze_sha256": freeze_hash,
        "window_seconds": WINDOW_SECONDS,
        "step_seconds": STEP_SECONDS,
        "positive_recall": true_positive / len(positive) if positive else None,
        "hard_negative_rejection": true_negative / len(negative) if negative else None,
        "counts": {
            "positive": len(positive),
            "true_positive": true_positive,
            "false_negative": len(positive) - true_positive,
            "hard_negative": len(negative),
            "true_negative": true_negative,
            "false_positive": len(negative) - true_negative,
        },
        "records": scored,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--partition", choices=("development", "blind"), required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--freeze-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from livekit.wakeword import WakeWordModel

    model = WakeWordModel(models=[args.model])
    report = score_partition(
        model=model,
        model_path=args.model,
        corpus_manifest_path=args.corpus_manifest,
        partition=args.partition,
        threshold=args.threshold,
        output_path=args.output,
        freeze_manifest_path=args.freeze_manifest,
    )
    print(f"PARTITION|{report['partition']}")
    print(f"COUNTS|{json.dumps(report['counts'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
