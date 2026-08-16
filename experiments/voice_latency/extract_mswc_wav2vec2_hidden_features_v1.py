"""Decode selected MSWC Opus clips and extract frozen Wav2Vec2 hidden sequences."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_separability_v1 import sha256  # noqa: E402


SAMPLE_RATE = 16_000


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_hidden_json_invalid:{path}")
    return value


def normalize_wave(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("mswc_hidden_audio_invalid")
    return np.ascontiguousarray(
        (values - values.mean()) / np.sqrt(values.var() + np.float32(1e-7)),
        dtype=np.float32,
    )


def decode_opus(path: Path, av: object) -> np.ndarray:
    chunks = []
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError(f"mswc_hidden_audio_stream_missing:{path}")
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(stream):
            for output in resampler.resample(frame):
                chunks.append(output.to_ndarray().reshape(-1).astype(np.float32))
        for output in resampler.resample(None):
            chunks.append(output.to_ndarray().reshape(-1).astype(np.float32))
    if not chunks:
        raise ValueError(f"mswc_hidden_audio_decode_empty:{path}")
    return normalize_wave(np.concatenate(chunks))


def extract(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    model_directory: Path,
    av_site_packages: Path,
    output_root: Path,
    layer: int,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if output_root.exists() or layer < 0 or batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("mswc_hidden_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("mswc_hidden_partial_output_exists")
    corpus = read_object(corpus_manifest_path)
    records = corpus.get("records")
    if (
        corpus.get("schema") != "baxy.mswc-microset-metric-corpus.v1"
        or corpus.get("test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or not isinstance(records, list)
    ):
        raise ValueError("mswc_hidden_corpus_boundary_invalid")
    typed_records = []
    paths = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("mswc_hidden_record_invalid")
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_hidden_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["opus_bytes"])
            or sha256(path) != record["opus_sha256"]
        ):
            raise ValueError(f"mswc_hidden_opus_hash_mismatch:{path}")
        typed_records.append(record)
        paths.append(path)

    av_import_path = str(av_site_packages)
    sys.path.insert(0, av_import_path)
    try:
        import av
    finally:
        sys.path.remove(av_import_path)
    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_hidden_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    if layer > len(model.wav2vec2.encoder.layers):
        raise ValueError("mswc_hidden_layer_invalid")
    model.wav2vec2.encoder.layers = torch.nn.ModuleList(
        list(model.wav2vec2.encoder.layers[:layer])
    )

    started = time.perf_counter()
    audios = [decode_opus(path, av) for path in paths]
    lengths = torch.tensor([len(audio) for audio in audios], dtype=torch.long)
    frame_lengths = (
        model._get_feat_extract_output_lengths(lengths).cpu().numpy().astype(np.int64)
    )
    offsets = np.zeros(len(typed_records) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(frame_lengths)
    hidden_size = int(model.config.hidden_size)
    partial_root.mkdir(parents=True)
    feature_path = partial_root / "features.f16.npy"
    offset_path = partial_root / "offsets.i64.npy"
    output_features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), hidden_size),
    )
    np.save(offset_path, offsets)
    with torch.inference_mode():
        for batch_start in range(0, len(typed_records), batch_size):
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
                range(batch_start, min(batch_start + batch_size, len(typed_records)))
            ):
                length = int(frame_lengths[global_index])
                output_features[offsets[global_index] : offsets[global_index + 1]] = hidden[
                    local, :length
                ].astype(np.float16)
            del outputs, hidden
    output_features.flush()
    del output_features, audios
    metadata_records = [
        {
            **record,
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": int(frame_lengths[index]),
        }
        for index, record in enumerate(typed_records)
    ]
    report: dict[str, object] = {
        "schema": "baxy.mswc-wav2vec2-hidden-features.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "model_weights_sha256": sha256(model_directory / "pytorch_model.bin"),
            "model_config_sha256": sha256(model_directory / "config.json"),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "decoding": "PyAV_Opus_to_float32_mono_16kHz",
            "normalization": "per_clip_mean_variance",
            "layer": layer,
            "encoder_layers_executed": layer,
            "full_model_layers_skipped_after_selected_layer": True,
            "hidden_size": hidden_size,
            "feature_dtype": "float16",
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
            "training_records": sum(record["split"] == "train" for record in metadata_records),
            "development_records": sum(
                record["split"] == "development" for record in metadata_records
            ),
            "classes": len({record["class_name"] for record in metadata_records}),
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
        "candidate_training_started": False,
        "test_audio_accessed": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--layer", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        corpus_manifest_path=arguments.corpus_manifest,
        corpus_root=arguments.corpus_root,
        model_directory=arguments.model_directory,
        av_site_packages=arguments.av_site_packages,
        output_root=arguments.output_root,
        layer=arguments.layer,
        batch_size=arguments.batch_size,
        device=arguments.device,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
