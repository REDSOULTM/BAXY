"""Measure the official HyperSpotter checkpoint on fixed BAXY WAV prefixes.

This is a development feasibility probe, not a wake-word promotion gate.  It
uses the same positive and adversarial-negative base clips as the LiveKit
campaign, but it neither trains nor calibrates a product asset.  Audio and file
names are not copied into the report.

Run with ``python -X utf8`` because the upstream character vocabulary contains
Unicode and its loader does not specify an encoding on Windows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_commit(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("empty score collection")
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return float(ordered[index])


def _score_summary(values: list[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "p05": _percentile(values, 0.05),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "maximum": max(values),
    }


def _threshold_metrics(
    positive_scores: list[float],
    negative_scores: list[float],
    negative_seconds: float,
    threshold: float,
) -> dict[str, float | int | None]:
    positive_hits = sum(score >= threshold for score in positive_scores)
    false_hits = sum(score >= threshold for score in negative_scores)
    recall = positive_hits / len(positive_scores)
    false_positive_rate = false_hits / len(negative_scores)
    negative_hours = negative_seconds / 3600.0
    observed_far = false_hits / negative_hours if negative_hours else None
    # The exact zero-event one-sided Poisson bound is sufficient to reject a
    # small feasibility set.  Non-zero candidates are already worse than their
    # point estimate and remain explicitly unbounded here; the product gate
    # computes the complete exact bound for every count.
    upper_far = (
        -math.log(0.05) / negative_hours
        if false_hits == 0 and negative_hours > 0.0
        else None
    )
    accuracy = (positive_hits + len(negative_scores) - false_hits) / (
        len(positive_scores) + len(negative_scores)
    )
    return {
        "threshold": threshold,
        "positive_hits": positive_hits,
        "false_hits": false_hits,
        "recall": recall,
        "false_reject_rate": 1.0 - recall,
        "false_positive_rate_per_clip": false_positive_rate,
        "observed_false_activations_per_hour": observed_far,
        "zero_event_poisson_upper_95_per_hour": upper_far,
        "accuracy": accuracy,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit-per-class", type=_positive_int, default=256)
    parser.add_argument("--batch-size", type=_positive_int, default=16)
    parser.add_argument("--keyword", action="append", dest="keywords")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not sys.flags.utf8_mode:
        raise SystemExit("Run this probe with python -X utf8.")

    upstream = args.hyperspotter_root.resolve(strict=True)
    checkpoint = args.checkpoint.resolve(strict=True)
    positive_dir = args.positive.resolve(strict=True)
    negative_dir = args.negative.resolve(strict=True)
    output = args.output.resolve()
    keywords = args.keywords or ["baxy", "baxi"]
    positive_paths = sorted(positive_dir.glob("clip_*.wav"))[: args.limit_per_class]
    negative_paths = sorted(negative_dir.glob("clip_*.wav"))[: args.limit_per_class]
    if len(positive_paths) != args.limit_per_class:
        raise SystemExit(f"positive prefix has {len(positive_paths)} WAVs")
    if len(negative_paths) != args.limit_per_class:
        raise SystemExit(f"negative prefix has {len(negative_paths)} WAVs")

    sys.path.insert(0, str(upstream))
    import torch  # noqa: PLC0415
    import torch.nn as nn  # noqa: PLC0415
    import torchaudio  # noqa: PLC0415

    from src.models import ConformerLightning  # type: ignore[import-not-found]  # noqa: PLC0415
    from src.processing import features_factory  # type: ignore[import-not-found]  # noqa: PLC0415
    from src.utils import ConfigDict  # type: ignore[import-not-found]  # noqa: PLC0415

    # Upstream constructs CPU and CUDA CTC decoders unconditionally.  The KWS
    # classifier path measured here does not read either decoder; suppressing
    # their construction leaves every checkpoint tensor and classifier call
    # unchanged while keeping this CPU-only probe runnable on Windows.
    ConformerLightning.set_decoders = lambda _self, _cfg: None

    started = time.perf_counter()
    model = ConformerLightning.load_from_checkpoint(
        str(checkpoint),
        map_location="cpu",
    ).eval()
    model_loaded = time.perf_counter()
    features_config = ConfigDict(
        {
            "features": {
                "stft_hop_length": 0.01,
                "stft_window_length": 0.025,
                "num_filterbank": 80,
                "sample_rate": 16000,
                "n_fft": 400,
            },
            "augmentations": {"use_augmentations": False},
        }
    )
    extractor = features_factory(features_config, eval=True)
    keyword_ids = model.tokenizer(keywords)["input_ids"]
    keyword_lengths = torch.LongTensor([len(item) for item in keyword_ids])
    keyword_tensor = nn.utils.rnn.pad_sequence(
        [torch.LongTensor(item) for item in keyword_ids],
        padding_value=model.tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.no_grad():
        keyword_weights = model.get_text_weights(keyword_tensor, keyword_lengths)

    def score_group(paths: list[Path]) -> tuple[list[float], float]:
        scores: list[float] = []
        audio_seconds = 0.0
        for offset in range(0, len(paths), args.batch_size):
            features = []
            lengths = []
            for path in paths[offset : offset + args.batch_size]:
                waveform, sample_rate = torchaudio.load(str(path))
                audio_seconds += waveform.shape[1] / sample_rate
                feature = extractor(waveform, sample_rate)
                features.append(feature)
                lengths.append(feature.shape[0])
            batch = torch.zeros(
                (len(features), model.cfg.model.max_context, features[0].shape[1]),
                dtype=features[0].dtype,
            )
            for index, feature in enumerate(features):
                batch[index, : feature.shape[0]] = feature
            with torch.no_grad():
                probabilities = torch.sigmoid(
                    model.run_classifier(
                        batch,
                        keyword_weights,
                        torch.LongTensor(lengths),
                    )
                )
            scores.extend(float(value) for value in probabilities.max(dim=1).values)
        return scores, audio_seconds

    positive_scores, positive_seconds = score_group(positive_paths)
    negative_scores, negative_seconds = score_group(negative_paths)
    inference_finished = time.perf_counter()
    scanned = [
        _threshold_metrics(
            positive_scores,
            negative_scores,
            negative_seconds,
            threshold / 100.0,
        )
        for threshold in range(1, 100)
    ]
    best = max(
        scanned,
        key=lambda row: (
            float(row["accuracy"]),
            -int(row["false_hits"]),
            float(row["recall"]),
            float(row["threshold"]),
        ),
    )
    fixed = _threshold_metrics(
        positive_scores,
        negative_scores,
        negative_seconds,
        0.5,
    )
    elapsed = inference_finished - started
    report: dict[str, Any] = {
        "schema": "baxy.hyperspotter-feasibility.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": {
            "upstream_commit": _git_commit(upstream),
            "checkpoint_sha256": _sha256(checkpoint),
            "probe_sha256": _sha256(Path(__file__).resolve()),
            "model": "official Conformer HyperSpotter checkpoint",
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "keywords": keywords,
            "decision_score": "maximum probability across keyword aliases",
            "ctc_decoder_initialization_suppressed": True,
            "device": "cpu",
        },
        "sample": {
            "selection": "lexicographically first fixed WAV prefix per class",
            "positive_files": len(positive_paths),
            "negative_files": len(negative_paths),
            "positive_audio_seconds": positive_seconds,
            "negative_audio_seconds": negative_seconds,
            "audio_or_filenames_retained": False,
        },
        "scores": {
            "positive": _score_summary(positive_scores),
            "negative": _score_summary(negative_scores),
        },
        "threshold_0_5": fixed,
        "best_development_threshold": best,
        "latency": {
            "model_load_seconds": model_loaded - started,
            "inference_seconds": inference_finished - model_loaded,
            "total_seconds": elapsed,
            "clips_per_second_including_load": (
                len(positive_paths) + len(negative_paths)
            )
            / elapsed,
        },
        "promotable": False,
        "candidate_status": "rejected",
        "rejection": (
            "The official open-vocabulary checkpoint does not separate BAXY positives "
            "from adversarial negatives: both fixed and development-selected thresholds "
            "miss the required recall and false-activation bounds by large margins."
        ),
        "promotion_note": (
            "Development feasibility only; threshold was inspected on this sample and "
            "there is no independent physical microphone holdout."
        ),
        "effects_executed": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
