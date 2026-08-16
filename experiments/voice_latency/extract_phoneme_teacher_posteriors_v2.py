"""Extract maxout-compressed teacher posteriors for the v2 tiny verifier."""

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
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
)
from extract_mdtc_ctc_fbank_features import read_wav  # noqa: E402
from extract_phoneme_teacher_posteriors import source_partitions  # noqa: E402
from phoneme_student_vocabulary_v2 import (  # noqa: E402
    CATEGORY_NAMES,
    CATEGORY_TOKENS,
    CONFUSABLE_IDS,
    TARGET_IDS,
    resolve_category_ids,
)
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


TEACHER_FRAMES = 99


def extract(
    *,
    feature_manifest_path: Path,
    teacher_directory: Path,
    oracle_report_path: Path,
    output_directory: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if batch_size <= 0 or device not in {"cpu", "cuda"}:
        raise ValueError("phoneme_teacher_v2_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    teacher_directory = teacher_directory.resolve(strict=True)
    oracle_report_path = oracle_report_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"phoneme_teacher_v2_output_exists:{output_directory}")
    feature_manifest = read_json(feature_manifest_path)
    oracle = read_json(oracle_report_path)
    if feature_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_phoneme_teacher_v2_feature_schema")
    if oracle.get("schema") != "baxy.phoneme-teacher-category-oracle-development.v2":
        raise ValueError("unsupported_phoneme_teacher_v2_oracle_schema")
    metrics = oracle.get("metrics")
    if not isinstance(metrics, dict) or metrics.get("development_gate_passed") is not True:
        raise ValueError("phoneme_teacher_v2_oracle_gate_not_passed")
    if (
        feature_manifest.get("blind_human_partition_accessed") is not False
        or oracle.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("phoneme_teacher_v2_blind_boundary_invalid")
    oracle_sources = oracle.get("sources")
    if not isinstance(oracle_sources, dict) or oracle_sources.get(
        "teacher_model_sha256"
    ) != sha256(teacher_directory / "pytorch_model.bin"):
        raise ValueError("phoneme_teacher_v2_oracle_teacher_mismatch")
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
        raise ValueError(f"phoneme_teacher_v2_frame_contract_mismatch:{output_length}")
    category_ids = resolve_category_ids(
        processor.tokenizer.get_vocab(), int(processor.tokenizer.pad_token_id)
    )
    output_directory.mkdir(parents=True)
    outputs: dict[str, object] = {}
    inference_seconds = 0.0
    for name, records in partitions.items():
        path = output_directory / f"{name}_teacher_probabilities.npy"
        values = np.lib.format.open_memmap(
            path,
            mode="w+",
            dtype=np.float16,
            shape=(len(records), TEACHER_FRAMES, len(CATEGORY_NAMES)),
        )
        hard_counts = np.zeros(len(CATEGORY_NAMES), dtype=np.int64)
        probability_sums = np.zeros(len(CATEGORY_NAMES), dtype=np.float64)
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
                logits = model(input_values=prepared.input_values.to(device)).logits.float()
                categories = compress_category_logits(
                    torch, logits, category_ids
                ).cpu().numpy()
            if device == "cuda":
                torch.cuda.synchronize()
            inference_seconds += time.perf_counter() - started
            hard_counts += np.bincount(
                categories.argmax(axis=-1).reshape(-1),
                minlength=len(CATEGORY_NAMES),
            )
            probability_sums += categories.sum(axis=(0, 1))
            values[start : start + len(batch_records)] = categories.astype(np.float16)
            completed = start + len(batch_records)
            if completed % 1000 < batch_size or completed == len(records):
                print(f"TEACHER_V2|{name}|{completed}/{len(records)}", flush=True)
        values.flush()
        del values
        frame_count = len(records) * TEACHER_FRAMES
        outputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(path),
            "shape": [len(records), TEACHER_FRAMES, len(CATEGORY_NAMES)],
            "dtype": "float16",
            "hard_category_counts": hard_counts.tolist(),
            "mean_category_probabilities": (probability_sums / frame_count).tolist(),
        }
    report: dict[str, object] = {
        "schema": "baxy.phoneme-teacher-maxout-posteriors.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_teacher_student_distillation_after_category_oracle",
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_model_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "teacher_config_sha256": sha256(teacher_directory / "config.json"),
            "teacher_vocabulary_sha256": sha256(teacher_directory / "vocab.json"),
            "oracle_report": oracle_report_path.as_posix(),
            "oracle_report_sha256": sha256(oracle_report_path),
        },
        "student_head": {
            "category_names": list(CATEGORY_NAMES),
            "category_tokens": CATEGORY_TOKENS,
            "category_count": len(CATEGORY_NAMES),
            "teacher_ids": category_ids,
            "compression": "maximum_teacher_logit_per_category_then_softmax",
            "target_category_sequences": [list(value) for value in TARGET_IDS],
            "confusable_category_sequences": [list(value) for value in CONFUSABLE_IDS],
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
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        feature_manifest_path=args.feature_manifest,
        teacher_directory=args.teacher_dir,
        oracle_report_path=args.oracle_report,
        output_directory=args.output_dir,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps({"outputs": report["outputs"], "runtime": report["runtime"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
