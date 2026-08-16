"""Audit speaker-held-out wake separability in Wav2Vec2 hidden layers."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import time
import wave

import numpy as np


SAMPLE_RATE = 16_000
FEATURE_STRIDE_SAMPLES = 320
FEATURE_RECEPTIVE_FIELD_SAMPLES = 400
WINDOW_OFFSETS_SECONDS = (-0.10, 0.0)
WINDOW_DURATIONS_SECONDS = (0.35, 0.50, 0.70, 0.90)
POOLING_METHODS = ("mean", "max")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_development_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("wav2vec2_hidden_corpus_schema_invalid")
    records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(records) != 18:
        raise ValueError("wav2vec2_hidden_development_records_invalid")
    if any(record.get("partition") != "development" for record in records):
        raise ValueError("wav2vec2_hidden_blind_boundary_invalid")
    return records


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        frames = source.getnframes()
        payload = source.readframes(frames)
    if contract != (1, 2, SAMPLE_RATE):
        raise ValueError(f"wav2vec2_hidden_wav_contract_invalid:{path}:{contract}")
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("wav2vec2_hidden_audio_invalid")
    return np.ascontiguousarray(
        (values - values.mean()) / np.sqrt(values.var() + np.float32(1e-7)),
        dtype=np.float32,
    )


def frame_mask(
    frame_count: int,
    *,
    onset_seconds: float,
    offset_seconds: float,
    duration_seconds: float,
) -> np.ndarray:
    centers = (
        np.arange(frame_count, dtype=np.float64) * FEATURE_STRIDE_SAMPLES
        + FEATURE_RECEPTIVE_FIELD_SAMPLES / 2
    ) / SAMPLE_RATE
    start = max(0.0, onset_seconds + offset_seconds)
    end = start + duration_seconds
    mask = (centers >= start) & (centers < end)
    if not np.any(mask):
        raise ValueError("wav2vec2_hidden_pool_window_empty")
    return mask


def pool_hidden(hidden: np.ndarray, mask: np.ndarray, method: str) -> np.ndarray:
    selected = hidden[mask]
    if method == "mean":
        return selected.mean(axis=0)
    if method == "max":
        return selected.max(axis=0)
    raise ValueError(f"wav2vec2_hidden_pooling_invalid:{method}")


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("wav2vec2_hidden_embedding_invalid")
    return vector / norm


def speaker_held_out_scores(
    features: np.ndarray,
    labels: np.ndarray,
    groups: list[str],
) -> np.ndarray:
    normalized = np.stack([_normalize(row) for row in features])
    scores = np.empty(len(labels), dtype=np.float64)
    group_array = np.asarray(groups)
    for group in sorted(set(groups)):
        held = group_array == group
        train = ~held
        positive = normalized[train & (labels == 1)]
        negative = normalized[train & (labels == 0)]
        if len(positive) == 0 or len(negative) == 0:
            raise ValueError(f"wav2vec2_hidden_fold_class_missing:{group}")
        positive_centroid = _normalize(positive.mean(axis=0))
        negative_centroid = _normalize(negative.mean(axis=0))
        scores[held] = (
            normalized[held] @ positive_centroid
            - normalized[held] @ negative_centroid
        )
    return scores


def score_metrics(scores: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.metrics import roc_auc_score

    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    threshold = float(np.nextafter(negatives.max(), math.inf))
    zero_false_accepted = int(np.count_nonzero(positives >= threshold))
    at_zero_positive = int(np.count_nonzero(positives >= 0.0))
    at_zero_false = int(np.count_nonzero(negatives >= 0.0))
    return {
        "speaker_held_out_auc": float(roc_auc_score(labels, scores)),
        "threshold_zero_positive_accepted": at_zero_positive,
        "threshold_zero_positive_total": int(len(positives)),
        "threshold_zero_hard_negative_false": at_zero_false,
        "threshold_zero_hard_negative_total": int(len(negatives)),
        "diagnostic_zero_false_threshold": threshold,
        "diagnostic_zero_false_positive_accepted": zero_false_accepted,
        "diagnostic_zero_false_positive_rate": zero_false_accepted / len(positives),
    }


def audit(
    *,
    corpus_manifest_path: Path,
    model_directory: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("wav2vec2_hidden_output_exists")
    if device not in {"cpu", "cuda"}:
        raise ValueError("wav2vec2_hidden_device_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    output_path = output_path.resolve()
    weights = model_directory / "pytorch_model.bin"
    config = model_directory / "config.json"
    if not weights.is_file() or not config.is_file():
        raise ValueError("wav2vec2_hidden_model_incomplete")
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(corpus, dict):
        raise ValueError("wav2vec2_hidden_corpus_invalid")
    records = select_development_records(corpus)

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wav2vec2_hidden_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    pooled: dict[tuple[int, float, float, str], list[np.ndarray]] = defaultdict(list)
    corpus_root = corpus_manifest_path.parent
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            path = corpus_root / str(record["output_relative_path"])
            wav = record.get("wav")
            if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
                raise ValueError(f"wav2vec2_hidden_audio_hash_mismatch:{path}")
            audio = normalize_audio(read_wav(path))
            outputs = model(
                torch.from_numpy(audio).unsqueeze(0).to(torch_device),
                output_hidden_states=True,
            )
            hidden_states = [
                hidden[0].detach().float().cpu().numpy()
                for hidden in outputs.hidden_states
            ]
            onset = float(record["target_onset_in_clip_seconds"])
            for layer, hidden in enumerate(hidden_states):
                for offset in WINDOW_OFFSETS_SECONDS:
                    for duration in WINDOW_DURATIONS_SECONDS:
                        mask = frame_mask(
                            hidden.shape[0],
                            onset_seconds=onset,
                            offset_seconds=offset,
                            duration_seconds=duration,
                        )
                        for method in POOLING_METHODS:
                            pooled[(layer, offset, duration, method)].append(
                                pool_hidden(hidden, mask, method)
                            )
            del outputs, hidden_states

    labels = np.asarray(
        [1 if record["label"] == "positive" else 0 for record in records],
        dtype=np.int64,
    )
    groups = [str(record["speaker_group"]) for record in records]
    configurations: list[dict[str, object]] = []
    winner_scores: np.ndarray | None = None
    winner_key: tuple[int, float, float, str] | None = None
    for key, rows in pooled.items():
        scores = speaker_held_out_scores(np.stack(rows), labels, groups)
        metrics = score_metrics(scores, labels)
        result = {
            "layer": key[0],
            "window_offset_seconds": key[1],
            "window_duration_seconds": key[2],
            "pooling": key[3],
            "metrics": metrics,
        }
        configurations.append(result)
        candidate_rank = (
            metrics["diagnostic_zero_false_positive_accepted"],
            metrics["speaker_held_out_auc"],
            metrics["threshold_zero_positive_accepted"]
            - metrics["threshold_zero_hard_negative_false"],
        )
        if winner_key is None:
            take = True
        else:
            current = configurations[0]["metrics"]
            assert isinstance(current, dict)
            take = False
            if winner_scores is not None:
                winner_metrics = score_metrics(winner_scores, labels)
                winner_rank = (
                    winner_metrics["diagnostic_zero_false_positive_accepted"],
                    winner_metrics["speaker_held_out_auc"],
                    winner_metrics["threshold_zero_positive_accepted"]
                    - winner_metrics["threshold_zero_hard_negative_false"],
                )
                take = candidate_rank > winner_rank
        if take:
            winner_key = key
            winner_scores = scores.copy()
    assert winner_key is not None and winner_scores is not None
    winner_metrics = score_metrics(winner_scores, labels)
    winner = {
        "layer": winner_key[0],
        "window_offset_seconds": winner_key[1],
        "window_duration_seconds": winner_key[2],
        "pooling": winner_key[3],
        "metrics": winner_metrics,
        "records": [
            {
                "relative_path": record["output_relative_path"],
                "speaker_group": record["speaker_group"],
                "label": record["label"],
                "speaker_held_out_score": float(score),
            }
            for record, score in zip(records, winner_scores, strict=True)
        ],
    }
    configurations.sort(
        key=lambda item: (
            item["metrics"]["diagnostic_zero_false_positive_accepted"],
            item["metrics"]["speaker_held_out_auc"],
        ),
        reverse=True,
    )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-separability-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_speaker_held_out_diagnostic",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "model_weights_sha256": sha256(weights),
            "model_config_sha256": sha256(config),
        },
        "dependencies": {
            "torch": version("torch"),
            "transformers": version("transformers"),
            "numpy": version("numpy"),
            "scikit_learn": version("scikit-learn"),
            "torch_cuda": torch.version.cuda,
            "torch_cudnn": torch.backends.cudnn.version(),
            "cuda_device": (
                torch.cuda.get_device_name(0) if device == "cuda" else None
            ),
        },
        "method": {
            "feature_stride_samples": FEATURE_STRIDE_SAMPLES,
            "feature_receptive_field_samples": FEATURE_RECEPTIVE_FIELD_SAMPLES,
            "speaker_groups": len(set(groups)),
            "cross_validation": "leave_one_speaker_group_out_nearest_centroid",
            "feature_normalization": "l2",
            "score": "cosine_positive_centroid_minus_cosine_negative_centroid",
            "configuration_count": len(configurations),
        },
        "winner": winner,
        "configurations": configurations,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        corpus_manifest_path=arguments.corpus_manifest,
        model_directory=arguments.model_directory,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps(report["winner"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
