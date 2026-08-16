"""Extract two frozen SSL layers for the Spanish MSWC QbyE corpus.

Audio is decoded in a length pass and then in bounded inference batches.  The
implementation never retains the complete 35k-clip waveform corpus in RAM.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


_BASE_PATH = Path(__file__).with_name("extract_mswc_wav2vec2_hidden_features_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("_baxy_mswc_decode_v1", _BASE_PATH)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("mswc_qbye_features_base_import_invalid")
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_features_json_invalid:{path}")
    return value


def validate_layers(layers: list[int]) -> list[int]:
    normalized = sorted(set(layers))
    if not normalized or normalized[0] < 0 or normalized != layers:
        raise ValueError("mswc_qbye_features_layers_invalid")
    return normalized


def resolve_record_path(
    record: dict[str, object], *, corpus_root: Path
) -> Path:
    relative = Path(str(record["relative_path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("mswc_qbye_features_relative_path_invalid")
    path = (corpus_root / relative).resolve(strict=True)
    path.relative_to(corpus_root)
    if (
        path.stat().st_size != int(record["audio_bytes"])
        or _BASE.sha256(path) != record["audio_sha256"]
    ):
        raise ValueError(f"mswc_qbye_features_audio_hash_mismatch:{path}")
    return path


def extract(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    model_directory: Path,
    av_site_packages: Path,
    output_root: Path,
    layers: list[int],
    batch_size: int,
    device: str,
) -> dict[str, object]:
    layers = validate_layers(layers)
    if output_root.exists() or batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("mswc_qbye_features_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_qbye_features_partial_exists:{partial_root}")
    corpus = read_object(corpus_manifest_path)
    records_raw = corpus.get("records")
    corpus_schema = corpus.get("schema")
    if (
        corpus_schema
        not in {
            "baxy.mswc-spanish-qbye-corpus.v1",
            "baxy.mswc-spanish-qbye-fresh-evaluation-corpus.v2",
        }
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or corpus.get("speaker_reidentification_attempted") is not False
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_qbye_features_corpus_boundary_invalid")
    records = []
    paths = []
    for record_raw in records_raw:
        if not isinstance(record_raw, dict):
            raise ValueError("mswc_qbye_features_record_invalid")
        record = dict(record_raw)
        records.append(record)
        paths.append(resolve_record_path(record, corpus_root=corpus_root))
    partitions = {str(record["partition"]) for record in records}
    expected_partitions = (
        {"metric_training", "open_keyword_enrollment", "open_keyword_query"}
        if corpus_schema == "baxy.mswc-spanish-qbye-corpus.v1"
        else {"open_keyword_enrollment", "open_keyword_query"}
    )
    if partitions != expected_partitions:
        raise ValueError("mswc_qbye_features_partition_invalid")

    av_import_path = str(av_site_packages)
    sys.path.insert(0, av_import_path)
    try:
        import av
    finally:
        sys.path.remove(av_import_path)
    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_features_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    maximum_layer = layers[-1]
    if maximum_layer > len(model.wav2vec2.encoder.layers):
        raise ValueError("mswc_qbye_features_layer_out_of_range")
    model.wav2vec2.encoder.layers = torch.nn.ModuleList(
        list(model.wav2vec2.encoder.layers[:maximum_layer])
    )

    started = time.perf_counter()
    sample_lengths = np.empty(len(paths), dtype=np.int64)
    for index, path in enumerate(paths):
        sample_lengths[index] = len(_BASE.decode_opus(path, av))
    frame_lengths = (
        model._get_feat_extract_output_lengths(torch.from_numpy(sample_lengths))
        .cpu()
        .numpy()
        .astype(np.int64)
    )
    offsets = np.zeros(len(records) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(frame_lengths)
    hidden_size = int(model.config.hidden_size)
    partial_root.mkdir(parents=True)
    offset_path = partial_root / "offsets.i64.npy"
    np.save(offset_path, offsets)
    output_features = {
        layer: np.lib.format.open_memmap(
            partial_root / f"features.layer{layer}.f16.npy",
            mode="w+",
            dtype=np.float16,
            shape=(int(offsets[-1]), hidden_size),
        )
        for layer in layers
    }

    with torch.inference_mode():
        for batch_start in range(0, len(records), batch_size):
            batch_paths = paths[batch_start : batch_start + batch_size]
            batch_audio = [_BASE.decode_opus(path, av) for path in batch_paths]
            maximum_samples = max(len(audio) for audio in batch_audio)
            values = np.zeros((len(batch_audio), maximum_samples), dtype=np.float32)
            attention = np.zeros((len(batch_audio), maximum_samples), dtype=np.int64)
            for local, audio in enumerate(batch_audio):
                values[local, : len(audio)] = audio
                attention[local, : len(audio)] = 1
            outputs = model.wav2vec2(
                torch.from_numpy(values).to(torch_device),
                attention_mask=torch.from_numpy(attention).to(torch_device),
                output_hidden_states=True,
            )
            hidden_by_layer = {
                layer: outputs.hidden_states[layer].detach().float().cpu().numpy()
                for layer in layers
            }
            for local, global_index in enumerate(
                range(batch_start, min(batch_start + batch_size, len(records)))
            ):
                length = int(frame_lengths[global_index])
                start = int(offsets[global_index])
                end = int(offsets[global_index + 1])
                for layer in layers:
                    output_features[layer][start:end] = hidden_by_layer[layer][
                        local, :length
                    ].astype(np.float16)
            del outputs, hidden_by_layer, batch_audio
    for values in output_features.values():
        values.flush()
    del values
    del output_features

    metadata_records = [
        {
            **record,
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": int(frame_lengths[index]),
        }
        for index, record in enumerate(records)
    ]
    feature_files = {}
    for layer in layers:
        path = partial_root / f"features.layer{layer}.f16.npy"
        feature_files[str(layer)] = {
            "path": path.name,
            "sha256": _BASE.sha256(path),
        }
    report: dict[str, object] = {
        "schema": (
            "baxy.mswc-spanish-qbye-wav2vec2-features.v1"
            if corpus_schema == "baxy.mswc-spanish-qbye-corpus.v1"
            else "baxy.mswc-spanish-qbye-fresh-evaluation-wav2vec2-features.v2"
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_open_keyword_metric_features",
        "sources": {
            "corpus_manifest_sha256": _BASE.sha256(corpus_manifest_path),
            "model_weights_sha256": _BASE.sha256(model_directory / "pytorch_model.bin"),
            "model_config_sha256": _BASE.sha256(model_directory / "config.json"),
        },
        "contract": {
            "sample_rate": _BASE.SAMPLE_RATE,
            "decoding": "PyAV_Opus_to_float32_mono_16kHz",
            "normalization": "per_clip_mean_variance",
            "layers": layers,
            "encoder_layers_executed": maximum_layer,
            "full_model_layers_skipped_after_selected_layer": True,
            "hidden_size": hidden_size,
            "feature_dtype": "float16",
            "memory_contract": "two_pass_decode_then_bounded_inference_batches",
        },
        "dependencies": {
            "av": av.__version__,
            "torch": version("torch"),
            "transformers": version("transformers"),
            "numpy": version("numpy"),
            "torch_cuda": torch.version.cuda,
            "cuda_device": torch.cuda.get_device_name(0) if device == "cuda" else None,
        },
        "counts": {
            "records": len(metadata_records),
            "metric_training": sum(
                record["partition"] == "metric_training" for record in metadata_records
            ),
            "open_keyword_enrollment": sum(
                record["partition"] == "open_keyword_enrollment"
                for record in metadata_records
            ),
            "open_keyword_query": sum(
                record["partition"] == "open_keyword_query" for record in metadata_records
            ),
            "classes": len({record["class_name"] for record in metadata_records}),
            "feature_frames_per_layer": int(offsets[-1]),
        },
        "files": {
            "features_by_layer": feature_files,
            "offsets": offset_path.name,
            "offsets_sha256": _BASE.sha256(offset_path),
        },
        "records": metadata_records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_training_started": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "speaker_reidentification_attempted": False,
        "effects_executed": 0,
    }
    manifest_path = partial_root / "features.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--av-site-packages", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--layers", type=int, nargs="+", default=[2, 16])
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        corpus_manifest_path=args.corpus_manifest,
        corpus_root=args.corpus_root,
        model_directory=args.model_directory,
        av_site_packages=args.av_site_packages,
        output_root=args.output_root,
        layers=args.layers,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
