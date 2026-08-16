"""Score a controlled RAW wake corpus with closed-set openWakeWord models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_openwakeword_evaluator_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_EXTRACTOR = load_component(
    "extract_baxy_openwakeword_embeddings_v1.py",
    "_baxy_openwakeword_evaluator_extractor_v1",
)
_TRAINER = load_component(
    "train_baxy_openwakeword_closed_set_v1.py",
    "_baxy_openwakeword_evaluator_metrics_v1",
)


def controlled_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    records = manifest.get("records")
    counts = manifest.get("counts")
    path = manifest.get("physicalPath")
    if (
        manifest.get("schema") != _EXTRACTOR.PHYSICAL_SCHEMA
        or manifest.get("blindHumanPartitionAccessed") is not False
        or manifest.get("developmentOnly") is not True
        or not isinstance(records, list)
        or not isinstance(counts, dict)
        or not isinstance(path, dict)
        or path.get("captureTransport") != "wasapi_raw_iaudioclient2"
    ):
        raise ValueError("baxy_openwakeword_evaluator_boundary_invalid")
    result: list[dict[str, object]] = []
    observed = {"positive": 0, "negative": 0}
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("recordId"), str)
            or not isinstance(record.get("output"), str)
            or not isinstance(record.get("outputSha256"), str)
            or not isinstance(record.get("sourceSha256"), str)
        ):
            raise ValueError("baxy_openwakeword_evaluator_record_invalid")
        source_label = str(record["recordId"]).split("/", 1)[0]
        if source_label not in observed:
            raise ValueError("baxy_openwakeword_evaluator_label_invalid")
        observed[source_label] += 1
        result.append(
            {
                "label": (
                    "positive"
                    if source_label == "positive"
                    else "adversarial_negative"
                ),
                "record_id": record["recordId"],
                "relative_path": record["output"],
                "audio_sha256": str(record["outputSha256"]).lower(),
                "source_audio_sha256": str(record["sourceSha256"]).lower(),
            }
        )
    expected = {
        label: int(counts.get(label, -1)) for label in ("positive", "negative")
    }
    if observed != expected:
        raise ValueError("baxy_openwakeword_evaluator_counts_invalid")
    return result


def parse_classifier(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path or not name.replace("_", "").isalnum():
        raise argparse.ArgumentTypeError("classifier must be NAME=PATH")
    return name, Path(raw_path)


def evaluate(
    *,
    physical_manifest_path: Path,
    openwakeword_root: Path,
    melspectrogram_model_path: Path,
    embedding_model_path: Path,
    classifiers: list[tuple[str, Path]],
    artifact_path: Path,
    batch_size: int,
    ncpu: int,
) -> dict[str, object]:
    physical_manifest_path = physical_manifest_path.resolve(strict=True)
    openwakeword_root = openwakeword_root.resolve(strict=True)
    melspectrogram_model_path = melspectrogram_model_path.resolve(strict=True)
    embedding_model_path = embedding_model_path.resolve(strict=True)
    artifact_path = artifact_path.resolve()
    if artifact_path.exists() or not classifiers or batch_size < 1 or ncpu < 1:
        raise ValueError("baxy_openwakeword_evaluator_schedule_invalid")
    classifier_paths: list[tuple[str, Path]] = []
    seen_names: set[str] = set()
    for name, path in classifiers:
        if name in seen_names:
            raise ValueError("baxy_openwakeword_evaluator_classifier_duplicate")
        seen_names.add(name)
        classifier_paths.append((name, path.resolve(strict=True)))

    manifest = _EXTRACTOR.read_object(physical_manifest_path)
    sources = controlled_records(manifest)
    import soundfile as sf

    windows: list[np.ndarray] = []
    window_owners: list[int] = []
    for source_index, source in enumerate(sources):
        path = (
            physical_manifest_path.parent / str(source["relative_path"])
        ).resolve(strict=True)
        if _EXTRACTOR.sha256(path) != source["audio_sha256"]:
            raise ValueError("baxy_openwakeword_evaluator_audio_hash_mismatch")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != _EXTRACTOR.SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("baxy_openwakeword_evaluator_wave_invalid")
        for _, window in _EXTRACTOR.continuous_runtime_windows(waveform[:, 0]):
            windows.append(_EXTRACTOR.pcm16(window))
            window_owners.append(source_index)

    while str(openwakeword_root) in sys.path:
        sys.path.remove(str(openwakeword_root))
    sys.path.insert(0, str(openwakeword_root))
    from openwakeword.utils import AudioFeatures
    import onnxruntime as ort

    backbone = AudioFeatures(
        melspec_model_path=str(melspectrogram_model_path),
        embedding_model_path=str(embedding_model_path),
        inference_framework="onnx",
        ncpu=ncpu,
        device="cpu",
    )
    sessions = {
        name: ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        for name, path in classifier_paths
    }
    window_scores = {
        name: np.empty(len(windows), dtype=np.float32) for name in sessions
    }
    feature_seconds = 0.0
    classifier_seconds = {name: 0.0 for name in sessions}
    for start in range(0, len(windows), batch_size):
        end = min(start + batch_size, len(windows))
        began = time.perf_counter()
        embeddings = backbone.embed_clips(
            np.stack(windows[start:end]),
            batch_size=batch_size * _EXTRACTOR.EMBEDDING_FRAMES,
            ncpu=ncpu,
        ).astype(np.float32)
        feature_seconds += time.perf_counter() - began
        for name, session in sessions.items():
            began = time.perf_counter()
            values = session.run(None, {"embeddings": embeddings})[0]
            classifier_seconds[name] += time.perf_counter() - began
            window_scores[name][start:end] = np.asarray(values).reshape(-1)

    records: list[dict[str, object]] = []
    source_scores = {
        name: np.full(len(sources), -np.inf, dtype=np.float32) for name in sessions
    }
    for window_index, source_index in enumerate(window_owners):
        for name in sessions:
            source_scores[name][source_index] = max(
                source_scores[name][source_index], window_scores[name][window_index]
            )
    for source_index, source in enumerate(sources):
        records.append(
            {
                **source,
                "runtime_windows": window_owners.count(source_index),
                "scores": {
                    name: float(source_scores[name][source_index])
                    for name in sessions
                },
            }
        )
    labels = np.asarray(
        [record["label"] == "positive" for record in sources], dtype=np.int64
    )
    metrics = {
        name: _TRAINER._BASE.binary_metrics(labels, scores)
        for name, scores in source_scores.items()
    }
    report: dict[str, object] = {
        "schema": "baxy.openwakeword-raw-corpus-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "controlled_raw_closed_set_wake_diagnostic",
        "sources": {
            "physical_manifest_sha256": _EXTRACTOR.sha256(physical_manifest_path),
            "openwakeword_commit": _EXTRACTOR.git_commit(openwakeword_root),
            "melspectrogram_model_sha256": _EXTRACTOR.sha256(
                melspectrogram_model_path
            ),
            "embedding_model_sha256": _EXTRACTOR.sha256(embedding_model_path),
            "classifiers": {
                name: {
                    "path": str(path),
                    "sha256": _EXTRACTOR.sha256(path),
                }
                for name, path in classifier_paths
            },
        },
        "contract": {
            "runtime_window_samples": _EXTRACTOR.WINDOW_SAMPLES,
            "side_padding_samples": _EXTRACTOR.SIDE_PADDING_SAMPLES,
            "hop_samples": _EXTRACTOR.HOP_SAMPLES,
            "source_score_reduction": "maximum_runtime_window_logit",
            "decision_threshold_selected": False,
        },
        "counts": {
            "positive": int(np.count_nonzero(labels)),
            "adversarial_negative": int(np.count_nonzero(labels == 0)),
            "sources": len(sources),
            "runtime_windows": len(windows),
        },
        "metrics": metrics,
        "timing": {
            "feature_total_seconds": feature_seconds,
            "feature_seconds_per_window": feature_seconds / len(windows),
            "classifier_total_seconds": classifier_seconds,
        },
        "records": records,
        "blind_human_partition_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-manifest", type=Path, required=True)
    parser.add_argument("--openwakeword-root", type=Path, required=True)
    parser.add_argument("--melspectrogram-model", type=Path, required=True)
    parser.add_argument("--embedding-model", type=Path, required=True)
    parser.add_argument(
        "--classifier", type=parse_classifier, action="append", required=True
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--ncpu", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        physical_manifest_path=arguments.physical_manifest,
        openwakeword_root=arguments.openwakeword_root,
        melspectrogram_model_path=arguments.melspectrogram_model,
        embedding_model_path=arguments.embedding_model,
        classifiers=arguments.classifier,
        artifact_path=arguments.artifact,
        batch_size=arguments.batch_size,
        ncpu=arguments.ncpu,
    )
    print(json.dumps({"counts": report["counts"], "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
