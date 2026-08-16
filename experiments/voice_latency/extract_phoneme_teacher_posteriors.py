"""Distill relevant phoneme posteriors from the frozen Wav2Vec2 teacher."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_voxcpm2_gguf_pilot import configure_espeak_backend  # noqa: E402
from extract_mdtc_ctc_fbank_features import (  # noqa: E402
    augmented_synthetic_records,
    hard_negative_records,
    human_records,
    read_wav,
)
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "blank": (),
    "B": ("b", "β"),
    "V": ("v",),
    "F": ("f",),
    "P": ("p",),
    "A": ("a", "æ", "ɑ", "ʌ"),
    "K": ("k",),
    "S": ("s", "sʲ"),
    "SH": ("ʃ",),
    "I": ("i", "ɪ"),
    "other": (),
}
CATEGORY_NAMES = tuple(CATEGORY_TOKENS)
TEACHER_FRAMES = 99


def resolve_category_ids(
    vocabulary: dict[str, int], blank_id: int
) -> dict[str, tuple[int, ...]]:
    values: dict[str, tuple[int, ...]] = {"blank": (int(blank_id),)}
    used = {int(blank_id)}
    for category, tokens in CATEGORY_TOKENS.items():
        if category in {"blank", "other"}:
            continue
        missing = [token for token in tokens if token not in vocabulary]
        if missing:
            raise ValueError(f"phoneme_teacher_vocabulary_missing:{missing[0]}")
        ids = tuple(sorted({int(vocabulary[token]) for token in tokens}))
        if used.intersection(ids):
            raise ValueError(f"phoneme_teacher_category_overlap:{category}")
        values[category] = ids
        used.update(ids)
    values["other"] = tuple(
        index for index in range(max(vocabulary.values()) + 1) if index not in used
    )
    return values


def aggregate_categories(
    torch: object,
    probabilities: object,
    category_ids: dict[str, tuple[int, ...]],
) -> object:
    if probabilities.ndim != 3:
        raise ValueError("phoneme_teacher_probability_shape_invalid")
    categories = []
    for name in CATEGORY_NAMES:
        ids = category_ids.get(name)
        if not ids:
            raise ValueError(f"phoneme_teacher_category_empty:{name}")
        categories.append(probabilities[:, :, list(ids)].sum(dim=-1))
    output = torch.stack(categories, dim=-1)
    if not bool(torch.isfinite(output).all()):
        raise ValueError("phoneme_teacher_category_values_invalid")
    return output / output.sum(dim=-1, keepdim=True).clamp_min(1e-12)


def source_partitions(
    feature_manifest: dict[str, object]
) -> dict[str, list[dict[str, object]]]:
    sources = feature_manifest.get("sources")
    outputs = feature_manifest.get("outputs")
    if not isinstance(sources, dict) or not isinstance(outputs, dict):
        raise ValueError("phoneme_teacher_feature_sources_missing")
    synthetic_directory = Path(str(sources.get("synthetic_directory"))).resolve(
        strict=True
    )
    assembly_path = synthetic_directory / "assembly_manifest.v1.json"
    assembly = read_json(assembly_path)
    hard_manifest_path = Path(str(sources.get("hard_manifest"))).resolve(strict=True)
    human_manifest_path = Path(str(sources.get("human_manifest"))).resolve(
        strict=True
    )
    if sha256(assembly_path) != sources.get("assembly_manifest_sha256"):
        raise ValueError("phoneme_teacher_assembly_hash_mismatch")
    if sha256(hard_manifest_path) != sources.get("hard_manifest_sha256"):
        raise ValueError("phoneme_teacher_hard_hash_mismatch")
    if sha256(human_manifest_path) != sources.get("human_manifest_sha256"):
        raise ValueError("phoneme_teacher_human_hash_mismatch")
    hard = read_json(hard_manifest_path)
    human = read_json(human_manifest_path)
    hard_directory = Path(str(hard.get("output_directory"))).resolve(strict=True)
    partitions = {
        "base_train": augmented_synthetic_records(
            synthetic_directory, assembly, "train"
        )
        + hard_negative_records(hard_directory, hard, "train"),
        "base_development": augmented_synthetic_records(
            synthetic_directory, assembly, "test"
        )
        + hard_negative_records(hard_directory, hard, "development"),
        "human_development": human_records(human, human_manifest_path),
    }
    for name, records in partitions.items():
        output = outputs.get(name)
        if not isinstance(output, dict) or output.get("records") != [
            record["record"] for record in records
        ]:
            raise ValueError(f"phoneme_teacher_record_order_mismatch:{name}")
    return partitions


def extract(
    *,
    feature_manifest_path: Path,
    teacher_directory: Path,
    output_directory: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if batch_size <= 0 or device not in {"cpu", "cuda"}:
        raise ValueError("phoneme_teacher_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    teacher_directory = teacher_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"phoneme_teacher_output_exists:{output_directory}")
    feature_manifest = read_json(feature_manifest_path)
    if feature_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_phoneme_teacher_feature_schema")
    if feature_manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("phoneme_teacher_blind_boundary_invalid")
    partitions = source_partitions(feature_manifest)
    espeak = configure_espeak_backend()
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    load_started = time.perf_counter()
    processor = Wav2Vec2Processor.from_pretrained(
        teacher_directory, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().to(device)
    load_seconds = time.perf_counter() - load_started
    output_length = int(
        model._get_feat_extract_output_lengths(torch.tensor([32_000])).item()
    )
    if output_length != TEACHER_FRAMES:
        raise ValueError(f"phoneme_teacher_frame_contract_mismatch:{output_length}")
    vocabulary = processor.tokenizer.get_vocab()
    category_ids = resolve_category_ids(
        vocabulary, int(processor.tokenizer.pad_token_id)
    )
    output_directory.mkdir(parents=True)
    outputs = {}
    inference_seconds = 0.0
    for name, records in partitions.items():
        path = output_directory / f"{name}_teacher_probabilities.npy"
        values = np.lib.format.open_memmap(
            path,
            mode="w+",
            dtype=np.float16,
            shape=(len(records), TEACHER_FRAMES, len(CATEGORY_NAMES)),
        )
        for start in range(0, len(records), batch_size):
            batch_records = records[start : start + batch_size]
            audios = []
            for record in batch_records:
                audio_value = record.get("audio")
                audios.append(
                    np.asarray(audio_value, dtype=np.float32)
                    if audio_value is not None
                    else read_wav(Path(str(record["path"])))
                )
            prepared = processor(
                audios,
                sampling_rate=16_000,
                return_tensors="pt",
                padding=True,
            )
            started = time.perf_counter()
            with torch.inference_mode():
                logits = model(
                    input_values=prepared.input_values.to(device)
                ).logits.float()
                probabilities = torch.softmax(logits, dim=-1)
                categories = aggregate_categories(
                    torch, probabilities, category_ids
                ).cpu().numpy()
            if device == "cuda":
                torch.cuda.synchronize()
            inference_seconds += time.perf_counter() - started
            values[start : start + len(batch_records)] = categories.astype(
                np.float16
            )
            completed = start + len(batch_records)
            if completed % 1000 < batch_size or completed == len(records):
                print(
                    f"TEACHER|{name}|{completed}/{len(records)}",
                    flush=True,
                )
        values.flush()
        del values
        outputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(path),
            "shape": [len(records), TEACHER_FRAMES, len(CATEGORY_NAMES)],
            "dtype": "float16",
        }
    report: dict[str, object] = {
        "schema": "baxy.phoneme-teacher-relevant-posteriors.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_teacher_student_distillation",
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_model_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "teacher_config_sha256": sha256(teacher_directory / "config.json"),
            "teacher_vocabulary_sha256": sha256(teacher_directory / "vocab.json"),
        },
        "categories": {
            "names": CATEGORY_NAMES,
            "tokens": CATEGORY_TOKENS,
            "teacher_ids": category_ids,
        },
        "alignment": {
            "audio_samples": 32_000,
            "teacher_frames": TEACHER_FRAMES,
            "student_fbank_frames": 198,
            "student_downsampling": "features[:, 1::2] gives 99 frames",
        },
        "outputs": outputs,
        "runtime": {
            "device": device,
            "batch_size": batch_size,
            "model_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "espeak": espeak,
        },
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    manifest_path = output_directory / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        feature_manifest_path=args.feature_manifest,
        teacher_directory=args.teacher_dir,
        output_directory=args.output_dir,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps({"outputs": report["outputs"], "runtime": report["runtime"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
