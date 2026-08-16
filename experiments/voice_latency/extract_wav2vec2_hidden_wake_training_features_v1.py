"""Extract frozen early Wav2Vec2 sequences for discriminative wake training."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_separability_v1 import sha256  # noqa: E402


SAMPLE_RATE = 16_000


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_hidden_features_json_invalid:{path}")
    return value


def normalize_wave(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("wake_hidden_features_audio_invalid")
    return np.ascontiguousarray(
        (values - values.mean()) / np.sqrt(values.var() + np.float32(1e-7)),
        dtype=np.float32,
    )


def read_wav(path: Path, expected_hash: str) -> np.ndarray:
    if sha256(path) != expected_hash:
        raise ValueError(f"wake_hidden_features_audio_hash_mismatch:{path}")
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        payload = source.readframes(source.getnframes())
    if contract != (1, 2, SAMPLE_RATE):
        raise ValueError(f"wake_hidden_features_audio_contract_invalid:{path}")
    return normalize_wave(
        np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
    )


def dataset_records(
    *,
    positive_manifest: dict[str, object],
    negative_manifest: dict[str, object],
    legacy_manifest: dict[str, object],
    expanded_manifest: dict[str, object],
    roots: dict[str, Path],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for corpus, manifest, label in (
        ("synthetic_positive", positive_manifest, "positive"),
        ("synthetic_negative", negative_manifest, "negative"),
    ):
        for record in manifest.get("records", []):
            if not isinstance(record, dict):
                raise ValueError("wake_hidden_features_synthetic_record_invalid")
            records.append(
                {
                    "corpus": corpus,
                    "label": label,
                    "group": f"synthetic_persona_{record['persona_id']}",
                    "relative_path": record["output_file"],
                    "path": roots[corpus] / str(record["output_file"]),
                    "sha256": record["wav"]["sha256"],
                    "target_onset_seconds": None,
                    "phrase_id": record.get("phrase_id"),
                }
            )
    for record in legacy_manifest.get("records", []):
        if not isinstance(record, dict) or record.get("partition") != "development":
            continue
        records.append(
            {
                "corpus": "human_legacy",
                "label": (
                    "positive" if record["label"] == "positive" else "negative"
                ),
                "group": record["speaker_group"],
                "relative_path": record["output_relative_path"],
                "path": roots["human_legacy"] / str(record["output_relative_path"]),
                "sha256": record["wav"]["sha256"],
                "target_onset_seconds": record.get("target_onset_in_clip_seconds"),
                "source_label": record["label"],
                "source_id": record.get("source_id"),
            }
        )
    for record in expanded_manifest.get("records", []):
        if not isinstance(record, dict) or record.get("partition") != "development":
            continue
        group = record["speaker_group"]
        if record.get("source_id") in {"Axgc6aHutvw", "Olv3YYWA7g0"}:
            group = "jesus_marcos"
        records.append(
            {
                "corpus": "human_expanded",
                "label": (
                    "positive" if record["label"] == "positive" else "negative"
                ),
                "group": group,
                "relative_path": record["output_relative_path"],
                "path": roots["human_expanded"] / str(record["output_relative_path"]),
                "sha256": record["wav"]["sha256"],
                "target_onset_seconds": record.get("target_onset_in_clip_seconds"),
                "source_label": record["label"],
                "source_id": record.get("source_id"),
            }
        )
    return records


def extract(
    *,
    positive_manifest_path: Path,
    negative_manifest_path: Path,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    model_directory: Path,
    output_root: Path,
    layer: int,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if output_root.exists() or layer < 0 or batch_size < 1:
        raise ValueError("wake_hidden_features_schedule_invalid")
    if device not in {"cpu", "cuda"}:
        raise ValueError("wake_hidden_features_device_invalid")
    paths = [
        positive_manifest_path,
        negative_manifest_path,
        legacy_manifest_path,
        expanded_manifest_path,
        model_directory,
    ]
    (
        positive_manifest_path,
        negative_manifest_path,
        legacy_manifest_path,
        expanded_manifest_path,
        model_directory,
    ) = [path.resolve(strict=True) for path in paths]
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("wake_hidden_features_partial_output_exists")
    manifests = {
        "positive": read_object(positive_manifest_path),
        "negative": read_object(negative_manifest_path),
        "legacy": read_object(legacy_manifest_path),
        "expanded": read_object(expanded_manifest_path),
    }
    if (
        manifests["positive"].get("class_label") != "positive"
        or manifests["negative"].get("class_label") != "adversarial_negative"
        or manifests["legacy"].get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or manifests["expanded"].get("schema")
        != "baxy.ccby-wake-v5-development-corpus.v1"
    ):
        raise ValueError("wake_hidden_features_manifest_boundary_invalid")
    roots = {
        "synthetic_positive": positive_manifest_path.parent,
        "synthetic_negative": negative_manifest_path.parent,
        "human_legacy": legacy_manifest_path.parent,
        "human_expanded": expanded_manifest_path.parent,
    }
    records = dataset_records(
        positive_manifest=manifests["positive"],
        negative_manifest=manifests["negative"],
        legacy_manifest=manifests["legacy"],
        expanded_manifest=manifests["expanded"],
        roots=roots,
    )
    expected_counts = {
        "synthetic_positive": 2695,
        "synthetic_negative": 1975,
        "human_legacy": 18,
        "human_expanded": 12,
    }
    actual_counts = {
        corpus: sum(record["corpus"] == corpus for record in records)
        for corpus in expected_counts
    }
    if actual_counts != expected_counts:
        raise ValueError(f"wake_hidden_features_counts_invalid:{actual_counts}")

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_hidden_features_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    if layer > len(model.wav2vec2.encoder.layers):
        raise ValueError("wake_hidden_features_layer_invalid")
    model.wav2vec2.encoder.layers = torch.nn.ModuleList(
        list(model.wav2vec2.encoder.layers[:layer])
    )
    audios = [read_wav(Path(record["path"]), str(record["sha256"])) for record in records]
    lengths = torch.tensor([len(audio) for audio in audios], dtype=torch.long)
    frame_lengths = (
        model._get_feat_extract_output_lengths(lengths).cpu().numpy().astype(np.int64)
    )
    offsets = np.zeros(len(records) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(frame_lengths)
    hidden_size = int(model.config.hidden_size)
    partial_root.mkdir(parents=True)
    feature_path = partial_root / "features.f16.npy"
    offset_path = partial_root / "offsets.i64.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), hidden_size),
    )
    np.save(offset_path, offsets)
    started = time.perf_counter()
    with torch.inference_mode():
        for batch_start in range(0, len(records), batch_size):
            batch_audio = audios[batch_start : batch_start + batch_size]
            maximum = max(len(audio) for audio in batch_audio)
            values = np.zeros((len(batch_audio), maximum), dtype=np.float32)
            attention = np.zeros((len(batch_audio), maximum), dtype=np.int64)
            for index, audio in enumerate(batch_audio):
                values[index, : len(audio)] = audio
                attention[index, : len(audio)] = 1
            outputs = model.wav2vec2(
                torch.from_numpy(values).to(torch_device),
                attention_mask=torch.from_numpy(attention).to(torch_device),
                output_hidden_states=True,
            )
            hidden = outputs.hidden_states[layer].detach().float().cpu().numpy()
            for local, global_index in enumerate(
                range(batch_start, min(batch_start + batch_size, len(records)))
            ):
                length = int(frame_lengths[global_index])
                features[offsets[global_index] : offsets[global_index + 1]] = hidden[
                    local, :length
                ].astype(np.float16)
            del outputs, hidden
    features.flush()
    del features, audios
    metadata_records = [
        {
            key: value
            for key, value in record.items()
            if key not in {"path", "sha256"}
        }
        | {
            "audio_sha256": record["sha256"],
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": int(frame_lengths[index]),
        }
        for index, record in enumerate(records)
    ]
    manifest: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-training-features.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "positive_manifest_sha256": sha256(positive_manifest_path),
            "negative_manifest_sha256": sha256(negative_manifest_path),
            "legacy_manifest_sha256": sha256(legacy_manifest_path),
            "expanded_manifest_sha256": sha256(expanded_manifest_path),
            "model_weights_sha256": sha256(model_directory / "pytorch_model.bin"),
            "model_config_sha256": sha256(model_directory / "config.json"),
        },
        "contract": {
            "layer": layer,
            "feature_dtype": "float16",
            "hidden_size": hidden_size,
            "normalization": "per_clip_mean_variance",
            "encoder_layers_executed": layer,
            "full_model_layers_skipped_after_selected_layer": True,
        },
        "counts": {
            **actual_counts,
            "records": len(records),
            "feature_frames": int(offsets[-1]),
        },
        "files": {
            "features": feature_path.name,
            "features_sha256": sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": sha256(offset_path),
        },
        "records": metadata_records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_model_training_started": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    manifest_path = partial_root / "features.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-manifest", type=Path, required=True)
    parser.add_argument("--negative-manifest", type=Path, required=True)
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--layer", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    manifest = extract(
        positive_manifest_path=arguments.positive_manifest,
        negative_manifest_path=arguments.negative_manifest,
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        model_directory=arguments.model_directory,
        output_root=arguments.output_root,
        layer=arguments.layer,
        batch_size=arguments.batch_size,
        device=arguments.device,
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
