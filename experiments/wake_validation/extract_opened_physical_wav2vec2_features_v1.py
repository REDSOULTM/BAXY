"""Extract sealed Wav2Vec2 and prosodic features from opened physical corpora.

The extractor is development-only. It validates every manifest and audio hash,
forbids the consumed physical v17 corpus, writes no filenames or transcripts,
and keeps the frozen teacher outside the product runtime.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import time
from typing import Any

import numpy as np


SCHEMA = "baxy.opened-physical-wav2vec2-features.v1"
BINDING_SCHEMA = "baxy.opened-physical-wav2vec2-features-binding.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("opened_wav2vec2_json_object_required")
    return value


def forbid_v17(paths: list[Path]) -> None:
    if any("v17" in str(path).lower() for path in paths):
        raise ValueError("opened_wav2vec2_physical_v17_forbidden")


def load_component(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("opened_wav2vec2_component_invalid")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def safe_corpus_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("opened_wav2vec2_manifest_path_escape") from exc
    if candidate.suffix.lower() != ".wav" or not candidate.is_file():
        raise ValueError("opened_wav2vec2_manifest_wav_missing")
    return candidate


def feature_offsets(frame_lengths: list[int]) -> np.ndarray:
    if not frame_lengths or any(
        isinstance(length, bool) or not isinstance(length, int) or length < 1
        for length in frame_lengths
    ):
        raise ValueError("opened_wav2vec2_frame_lengths_invalid")
    offsets = np.zeros(len(frame_lengths) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(np.asarray(frame_lengths, dtype=np.int64))
    return offsets


def load_records(binding: dict[str, Any]) -> list[dict[str, Any]]:
    corpora = binding.get("corpora")
    if not isinstance(corpora, list) or len(corpora) != 3:
        raise ValueError("opened_wav2vec2_three_corpora_required")
    records: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for corpus in corpora:
        if not isinstance(corpus, dict):
            raise ValueError("opened_wav2vec2_corpus_invalid")
        name = corpus.get("name")
        root = Path(str(corpus.get("root"))).resolve()
        manifest_path = root / "manifest.v1.json"
        expected_manifest_hash = corpus.get("manifestSha256")
        expected_counts = corpus.get("counts")
        forbid_v17([root, manifest_path])
        if (
            not isinstance(name, str)
            or not isinstance(expected_manifest_hash, str)
            or not isinstance(expected_counts, dict)
            or sha256(manifest_path) != expected_manifest_hash
        ):
            raise ValueError("opened_wav2vec2_corpus_binding_mismatch")
        manifest = read_object(manifest_path)
        if manifest.get("counts") != expected_counts:
            raise ValueError("opened_wav2vec2_manifest_counts_mismatch")
        raw_records = manifest.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("opened_wav2vec2_manifest_records_invalid")
        observed = {"positive": 0, "negative": 0}
        for raw in raw_records:
            if not isinstance(raw, dict):
                raise ValueError("opened_wav2vec2_manifest_record_invalid")
            record_id = raw.get("recordId")
            relative = raw.get("output")
            audio_hash = raw.get("outputSha256")
            if not all(
                isinstance(item, str) for item in (record_id, relative, audio_hash)
            ):
                raise ValueError("opened_wav2vec2_manifest_record_invalid")
            label = record_id.split("/", 1)[0]
            if label not in observed or not relative.replace("\\", "/").startswith(
                f"{label}/"
            ):
                raise ValueError("opened_wav2vec2_manifest_label_invalid")
            path = safe_corpus_path(root, relative)
            if sha256(path) != audio_hash or audio_hash in seen_hashes:
                raise ValueError("opened_wav2vec2_audio_identity_invalid")
            seen_hashes.add(audio_hash)
            observed[label] += 1
            records.append(
                {
                    "corpus": name,
                    "label": label,
                    "audioSha256": audio_hash,
                    "path": path,
                }
            )
        if observed != expected_counts:
            raise ValueError("opened_wav2vec2_manifest_record_counts_mismatch")
    return records


def extract(binding_path: Path, output_root: Path) -> dict[str, Any]:
    binding_path = binding_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    forbid_v17([binding_path, output_root, partial_root])
    if output_root.exists() or partial_root.exists():
        raise ValueError("opened_wav2vec2_output_exists")
    binding = read_object(binding_path)
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("opened_wav2vec2_binding_schema_invalid")
    program_path = Path(__file__).resolve()
    if binding.get("programSha256") != sha256(program_path):
        raise ValueError("opened_wav2vec2_program_hash_mismatch")
    if Path(str(binding.get("plannedOutputRoot"))).resolve() != output_root:
        raise ValueError("opened_wav2vec2_output_binding_mismatch")

    dependency_path = Path(str(binding.get("prosodyProgram"))).resolve(strict=True)
    if binding.get("prosodyProgramSha256") != sha256(dependency_path):
        raise ValueError("opened_wav2vec2_prosody_hash_mismatch")
    prosody = load_component(dependency_path, "_baxy_opened_prosody_v1")

    teacher = binding.get("teacher")
    if not isinstance(teacher, dict):
        raise ValueError("opened_wav2vec2_teacher_binding_invalid")
    teacher_root = Path(str(teacher.get("root"))).resolve(strict=True)
    weights_path = teacher_root / "pytorch_model.bin"
    config_path = teacher_root / "config.json"
    if teacher.get("weightsSha256") != sha256(weights_path) or teacher.get(
        "configSha256"
    ) != sha256(config_path):
        raise ValueError("opened_wav2vec2_teacher_hash_mismatch")
    layer = int(binding.get("layer"))
    batch_size = int(binding.get("batchSize"))
    if layer < 1 or batch_size < 1:
        raise ValueError("opened_wav2vec2_schedule_invalid")

    records = load_records(binding)
    waveforms: list[np.ndarray] = []
    prosody_features = []
    for record in records:
        waveform, sample_rate = prosody.read_pcm16(Path(record["path"]))
        waveforms.append(waveform)
        prosody_features.append(prosody.extract_features(waveform, sample_rate))

    import torch
    from transformers import Wav2Vec2ForCTC

    if not torch.cuda.is_available():
        raise RuntimeError("opened_wav2vec2_cuda_unavailable")
    load_started = time.perf_counter()
    model = (
        Wav2Vec2ForCTC.from_pretrained(str(teacher_root), local_files_only=True)
        .eval()
        .cuda()
    )
    if layer > len(model.wav2vec2.encoder.layers):
        raise ValueError("opened_wav2vec2_layer_invalid")
    model.wav2vec2.encoder.layers = torch.nn.ModuleList(
        list(model.wav2vec2.encoder.layers[:layer])
    )
    model_load_seconds = time.perf_counter() - load_started
    input_lengths = torch.tensor([len(waveform) for waveform in waveforms])
    frame_lengths = [
        int(value)
        for value in model._get_feat_extract_output_lengths(input_lengths).tolist()
    ]
    offsets = feature_offsets(frame_lengths)
    hidden_size = int(model.config.hidden_size)

    partial_root.mkdir(parents=True)
    feature_path = partial_root / "features.layer2.f16.npy"
    offset_path = partial_root / "offsets.i64.npy"
    prosody_path = partial_root / "prosody.f32.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), hidden_size),
    )
    np.save(offset_path, offsets)
    np.save(prosody_path, np.asarray(prosody_features, dtype=np.float32))
    inference_started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(records), batch_size):
            batch_waveforms = waveforms[start : start + batch_size]
            maximum = max(len(waveform) for waveform in batch_waveforms)
            values = np.zeros((len(batch_waveforms), maximum), dtype=np.float32)
            attention = np.zeros((len(batch_waveforms), maximum), dtype=np.int64)
            for index, waveform in enumerate(batch_waveforms):
                values[index, : len(waveform)] = waveform
                attention[index, : len(waveform)] = 1
            outputs = model.wav2vec2(
                torch.from_numpy(values).cuda(),
                attention_mask=torch.from_numpy(attention).cuda(),
                output_hidden_states=True,
            )
            hidden = outputs.hidden_states[layer].detach().float().cpu().numpy()
            for local, global_index in enumerate(
                range(start, min(start + batch_size, len(records)))
            ):
                length = frame_lengths[global_index]
                features[offsets[global_index] : offsets[global_index + 1]] = hidden[
                    local, :length
                ].astype(np.float16)
            print(
                f"BAXY_OPENED_WAV2VEC2|{min(start + batch_size, len(records))}/"
                f"{len(records)}",
                flush=True,
            )
    inference_seconds = time.perf_counter() - inference_started
    features.flush()
    del features, model, waveforms

    metadata_records = [
        {
            "corpus": record["corpus"],
            "label": record["label"],
            "audioSha256": record["audioSha256"],
            "featureStart": int(offsets[index]),
            "featureEnd": int(offsets[index + 1]),
            "featureFrames": frame_lengths[index],
        }
        for index, record in enumerate(records)
    ]
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_physical_development_only",
        "bindingSha256": sha256(binding_path),
        "programSha256": sha256(program_path),
        "prosodyProgramSha256": sha256(dependency_path),
        "teacher": {
            "weightsSha256": sha256(weights_path),
            "configSha256": sha256(config_path),
            "layer": layer,
            "hiddenSize": hidden_size,
            "encoderLayersExecuted": layer,
        },
        "arrays": {
            "features": {
                "filename": feature_path.name,
                "sha256": sha256(feature_path),
                "dtype": "float16",
                "shape": [int(offsets[-1]), hidden_size],
            },
            "offsets": {
                "filename": offset_path.name,
                "sha256": sha256(offset_path),
                "dtype": "int64",
                "shape": [len(offsets)],
            },
            "prosody": {
                "filename": prosody_path.name,
                "sha256": sha256(prosody_path),
                "dtype": "float32",
                "shape": [len(records), int(np.asarray(prosody_features).shape[1])],
            },
        },
        "counts": {
            "records": len(records),
            "positive": sum(record["label"] == "positive" for record in records),
            "negative": sum(record["label"] == "negative" for record in records),
            "uniqueAudioHashes": len({record["audioSha256"] for record in records}),
        },
        "records": metadata_records,
        "runtime": {
            "device": "cuda",
            "batchSize": batch_size,
            "modelLoadSeconds": model_load_seconds,
            "inferenceSeconds": inference_seconds,
            "torch": importlib.metadata.version("torch"),
            "transformers": importlib.metadata.version("transformers"),
        },
        "filenamesRetained": False,
        "transcriptTextRetained": False,
        "physicalV17Read": False,
        "developmentOnly": True,
        "promotionEligible": False,
        "effectsExecuted": 0,
    }
    manifest_path = partial_root / "features.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    partial_root.replace(output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = extract(arguments.binding, arguments.output_root)
    print(
        f"BAXY_OPENED_WAV2VEC2|complete|records={manifest['counts']['records']}|"
        f"frames={manifest['arrays']['features']['shape'][0]}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
