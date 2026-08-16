"""Evaluate the frozen hidden wake embedding on expanded human development data."""

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
from audit_wav2vec2_hidden_wake_product_scan_v1 import sliding_vectors  # noqa: E402
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    _normalize,
    frame_mask,
    normalize_audio,
    pool_hidden,
    read_wav,
    score_metrics,
    sha256,
)


JESUS_MARCOS_SOURCE_IDS = frozenset({"LNZyJcCArhc", "Axgc6aHutvw", "Olv3YYWA7g0"})


def canonical_group(record: dict[str, object]) -> str:
    if str(record.get("source_id")) in JESUS_MARCOS_SOURCE_IDS:
        return "jesus_marcos"
    return str(record["speaker_group"])


def selected_records(
    legacy: dict[str, object], expanded: dict[str, object]
) -> list[dict[str, object]]:
    if legacy.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("wake_expanded_legacy_corpus_invalid")
    if (
        expanded.get("schema") != "baxy.ccby-wake-v5-development-corpus.v1"
        or expanded.get("scope") != "development_only"
        or expanded.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_expanded_new_corpus_invalid")
    records = [
        {**record, "corpus": "legacy"}
        for record in legacy.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    records.extend(
        {**record, "corpus": "expanded"}
        for record in expanded.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    )
    if len(records) != 30:
        raise ValueError(f"wake_expanded_record_count_invalid:{len(records)}")
    return records


def held_out_scores(
    query_vectors: list[np.ndarray], labels: np.ndarray, groups: list[str]
) -> np.ndarray:
    group_array = np.asarray(groups)
    scores = np.empty(len(labels), dtype=np.float64)
    normalized = [np.stack([_normalize(row) for row in rows]) for rows in query_vectors]
    for group in sorted(set(groups)):
        held = group_array == group
        train = ~held
        positive_rows = [
            normalized[index][0]
            for index in np.flatnonzero(train & (labels == 1))
        ]
        negative_rows = [
            row
            for index in np.flatnonzero(train & (labels == 0))
            for row in normalized[index]
        ]
        if not positive_rows or not negative_rows:
            raise ValueError(f"wake_expanded_fold_class_missing:{group}")
        positive_centroid = _normalize(np.stack(positive_rows).mean(axis=0))
        negative_centroid = _normalize(np.stack(negative_rows).mean(axis=0))
        for index in np.flatnonzero(held):
            values = (
                normalized[index] @ positive_centroid
                - normalized[index] @ negative_centroid
            )
            scores[index] = float(values.max())
    return scores


def category_metrics(
    scores: np.ndarray, records: list[dict[str, object]], threshold: float
) -> dict[str, object]:
    values: dict[str, object] = {}
    for label in ("positive", "hard_negative", "matched_negative"):
        indexes = [index for index, record in enumerate(records) if record["label"] == label]
        accepted = int(np.count_nonzero(scores[indexes] >= threshold))
        values[label] = {
            "accepted": accepted,
            "total": len(indexes),
            "rate": accepted / len(indexes),
        }
    return values


def audit(
    *,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    frozen_audit_path: Path,
    model_directory: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or device not in {"cpu", "cuda"}:
        raise ValueError("wake_expanded_schedule_invalid")
    legacy_manifest_path = legacy_manifest_path.resolve(strict=True)
    expanded_manifest_path = expanded_manifest_path.resolve(strict=True)
    frozen_audit_path = frozen_audit_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    output_path = output_path.resolve()
    legacy = json.loads(legacy_manifest_path.read_text(encoding="utf-8-sig"))
    expanded = json.loads(expanded_manifest_path.read_text(encoding="utf-8-sig"))
    frozen = json.loads(frozen_audit_path.read_text(encoding="utf-8-sig"))
    if not isinstance(legacy, dict) or not isinstance(expanded, dict):
        raise ValueError("wake_expanded_manifest_invalid")
    records = selected_records(legacy, expanded)
    if (
        frozen.get("schema") != "baxy.wav2vec2-hidden-wake-separability-audit.v1"
        or frozen.get("sources", {}).get("corpus_manifest_sha256")
        != sha256(legacy_manifest_path)
    ):
        raise ValueError("wake_expanded_frozen_audit_invalid")
    winner = frozen.get("winner")
    if not isinstance(winner, dict):
        raise ValueError("wake_expanded_frozen_winner_missing")
    layer = int(winner["layer"])
    duration = float(winner["window_duration_seconds"])
    pooling = str(winner["pooling"])

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_expanded_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    roots = {
        "legacy": legacy_manifest_path.parent,
        "expanded": expanded_manifest_path.parent,
    }
    query_vectors: list[np.ndarray] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            path = roots[str(record["corpus"])] / str(record["output_relative_path"])
            wav = record.get("wav")
            if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
                raise ValueError(f"wake_expanded_audio_hash_mismatch:{path}")
            outputs = model(
                torch.from_numpy(normalize_audio(read_wav(path)))
                .unsqueeze(0)
                .to(torch_device),
                output_hidden_states=True,
            )
            hidden = outputs.hidden_states[layer][0].detach().float().cpu().numpy()
            if record["label"] == "matched_negative":
                vectors, _ = sliding_vectors(
                    hidden, duration_seconds=duration, pooling=pooling
                )
                query_vectors.append(vectors)
            else:
                onset = float(record["target_onset_in_clip_seconds"])
                mask = frame_mask(
                    hidden.shape[0],
                    onset_seconds=onset,
                    offset_seconds=0.0,
                    duration_seconds=duration,
                )
                query_vectors.append(pool_hidden(hidden, mask, pooling)[None, :])
            del outputs
    labels = np.asarray(
        [1 if record["label"] == "positive" else 0 for record in records],
        dtype=np.int64,
    )
    groups = [canonical_group(record) for record in records]
    scores = held_out_scores(query_vectors, labels, groups)
    metrics = score_metrics(scores, labels)
    threshold = float(metrics["diagnostic_zero_false_threshold"])
    metrics["by_label_at_diagnostic_zero_false_threshold"] = category_metrics(
        scores, records, threshold
    )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-expanded-development-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "expanded_development_only_speaker_held_out",
        "sources": {
            "legacy_manifest_sha256": sha256(legacy_manifest_path),
            "expanded_manifest_sha256": sha256(expanded_manifest_path),
            "frozen_audit_sha256": sha256(frozen_audit_path),
            "model_weights_sha256": sha256(model_directory / "pytorch_model.bin"),
        },
        "frozen_embedding": {
            "layer": layer,
            "window_duration_seconds": duration,
            "pooling": pooling,
            "positive_and_hard_negative": "ground_truth_aligned_window",
            "matched_negative": "all_20ms_sliding_windows_max_score",
            "cross_validation": "leave_one_canonical_speaker_group_out_nearest_centroid",
        },
        "metrics": metrics,
        "records": [
            {
                "corpus": record["corpus"],
                "relative_path": record["output_relative_path"],
                "source_id": record.get("source_id"),
                "speaker_group": canonical_group(record),
                "label": record["label"],
                "speaker_held_out_score": float(score),
            }
            for record, score in zip(records, scores, strict=True)
        ],
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
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--frozen-audit", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        frozen_audit_path=arguments.frozen_audit,
        model_directory=arguments.model_directory,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
