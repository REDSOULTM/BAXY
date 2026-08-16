"""Fit a small QbyT verifier from opened human-development embeddings.

The first-pass acoustic cascade localizes a fixed product view.  This builder
fits the second-pass direction and a zero-training-false threshold using the
speaker-held-out layer/window configuration selected before the 100 h failure
analysis.  The resulting JSON contains only a direction vector and policy;
audio and record identities are not embedded.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_expanded_development_v1 import (  # noqa: E402
    selected_records,
)
from audit_wav2vec2_hidden_wake_product_scan_v1 import (  # noqa: E402
    sliding_vectors,
)
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    _normalize,
    frame_mask,
    normalize_audio,
    pool_hidden,
    read_wav,
    sha256,
)


def normalize_rows(values: np.ndarray) -> np.ndarray:
    rows = np.asarray(values, dtype=np.float32)
    if rows.ndim != 2 or not len(rows) or not np.isfinite(rows).all():
        raise ValueError("wake_qbyt_vectors_invalid")
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise ValueError("wake_qbyt_vector_norm_invalid")
    return rows / norms


def fit_candidate(
    *,
    aligned_positive_vectors: np.ndarray,
    product_vectors: list[np.ndarray],
    labels: np.ndarray,
) -> tuple[np.ndarray, float, np.ndarray, dict[str, object]]:
    targets = np.asarray(labels, dtype=np.int64)
    aligned = normalize_rows(aligned_positive_vectors)
    scans = [normalize_rows(values) for values in product_vectors]
    if (
        len(aligned) != int(np.count_nonzero(targets == 1))
        or len(scans) != len(targets)
        or set(targets.tolist()) != {0, 1}
    ):
        raise ValueError("wake_qbyt_fit_alignment_invalid")
    positive_centroid = _normalize(aligned.mean(axis=0))
    negative_centroid = _normalize(
        np.concatenate(
            [values for values, label in zip(scans, targets, strict=True) if label == 0],
            axis=0,
        ).mean(axis=0)
    )
    direction = np.asarray(positive_centroid - negative_centroid, dtype=np.float32)
    scores = np.asarray(
        [float(np.max(values @ direction)) for values in scans], dtype=np.float64
    )
    negative_scores = scores[targets == 0]
    threshold = float(np.nextafter(negative_scores.max(), math.inf))
    accepted = scores >= threshold
    positive_total = int(np.count_nonzero(targets == 1))
    negative_total = int(np.count_nonzero(targets == 0))
    metrics = {
        "positiveAccepted": int(np.count_nonzero(accepted & (targets == 1))),
        "positiveTotal": positive_total,
        "negativeFalseAccepts": int(np.count_nonzero(accepted & (targets == 0))),
        "negativeTotal": negative_total,
        "developmentFitGatePassed": bool(
            np.count_nonzero(accepted & (targets == 1)) == positive_total
            and np.count_nonzero(accepted & (targets == 0)) == 0
        ),
        "minimumAcceptedPositiveMargin": (
            float(np.min(scores[targets == 1] - threshold))
        ),
        "maximumNegativeMargin": float(np.max(negative_scores - threshold)),
    }
    return direction, threshold, scores, metrics


def build(
    *,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    hidden_sweep_path: Path,
    model_directory: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or device not in {"cpu", "cuda"}:
        raise ValueError("wake_qbyt_schedule_invalid")
    legacy_manifest_path = legacy_manifest_path.resolve(strict=True)
    expanded_manifest_path = expanded_manifest_path.resolve(strict=True)
    hidden_sweep_path = hidden_sweep_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    output_path = output_path.resolve()
    legacy = json.loads(legacy_manifest_path.read_text(encoding="utf-8-sig"))
    expanded = json.loads(expanded_manifest_path.read_text(encoding="utf-8-sig"))
    sweep = json.loads(hidden_sweep_path.read_text(encoding="utf-8-sig"))
    winner = sweep.get("winner") if isinstance(sweep, dict) else None
    if (
        not isinstance(legacy, dict)
        or not isinstance(expanded, dict)
        or sweep.get("schema")
        != "baxy.wav2vec2-hidden-wake-expanded-layer-sweep.v1"
        or not isinstance(winner, dict)
        or winner.get("layer") != 2
        or winner.get("window_offset_seconds") != 0.0
        or winner.get("window_duration_seconds") != 0.9
        or winner.get("pooling") != "max"
        or winner.get("metrics", {}).get("positive_accepted") != 17
        or winner.get("metrics", {}).get("positive_total") != 18
        or winner.get("metrics", {}).get("negative_false_accepts") != 1
        or winner.get("metrics", {}).get("negative_total") != 12
        or sweep.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_qbyt_selection_evidence_invalid")
    records = selected_records(legacy, expanded)
    if (
        len(records) != 30
        or sum(record["label"] == "positive" for record in records) != 18
        or any(record.get("partition") != "development" for record in records)
    ):
        raise ValueError("wake_qbyt_human_boundary_invalid")

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_qbyt_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    roots = {
        "legacy": legacy_manifest_path.parent,
        "expanded": expanded_manifest_path.parent,
    }
    aligned: list[np.ndarray] = []
    product: list[np.ndarray] = []
    labels: list[int] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            path = roots[str(record["corpus"])] / str(record["output_relative_path"])
            wav = record.get("wav")
            if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
                raise ValueError("wake_qbyt_audio_hash_mismatch")
            audio = normalize_audio(read_wav(path))
            hidden = model.wav2vec2(
                torch.from_numpy(audio).unsqueeze(0).to(torch_device),
                output_hidden_states=True,
            ).hidden_states[2][0].detach().float().cpu().numpy()
            vectors, _ = sliding_vectors(
                hidden, duration_seconds=0.9, pooling="max"
            )
            product.append(vectors)
            positive = record["label"] == "positive"
            labels.append(1 if positive else 0)
            if positive:
                mask = frame_mask(
                    hidden.shape[0],
                    onset_seconds=float(record["target_onset_in_clip_seconds"]),
                    offset_seconds=0.0,
                    duration_seconds=0.9,
                )
                aligned.append(pool_hidden(hidden, mask, "max"))
    direction, threshold, _, metrics = fit_candidate(
        aligned_positive_vectors=np.stack(aligned),
        product_vectors=product,
        labels=np.asarray(labels, dtype=np.int64),
    )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-qbyt-wake-candidate.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_development_fit_after_speaker_held_out_selection",
        "sources": {
            "legacyManifestSha256": sha256(legacy_manifest_path),
            "expandedManifestSha256": sha256(expanded_manifest_path),
            "hiddenSweepSha256": sha256(hidden_sweep_path),
            "modelWeightsSha256": sha256(model_directory / "pytorch_model.bin"),
            "modelConfigSha256": sha256(model_directory / "config.json"),
        },
        "policy": {
            "layer": 2,
            "windowOffsetSeconds": 0.0,
            "windowDurationSeconds": 0.9,
            "pooling": "max",
            "query": "maximum_20ms_sliding_window_score",
            "threshold": threshold,
            "normalization": "l2_per_window",
        },
        "parameters": {"direction": direction.astype(float).tolist()},
        "metrics": metrics,
        "runtimeSeconds": time.perf_counter() - started,
        "developmentOnly": True,
        "blindHumanAudioAccessed": False,
        "audioOrRecordIdentitiesRetained": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "effectsExecuted": 0,
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
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--hidden-sweep", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = build(
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        hidden_sweep_path=arguments.hidden_sweep,
        model_directory=arguments.model_directory,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if report["metrics"]["developmentFitGatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
