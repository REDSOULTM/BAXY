"""Phoneme-audit a hash-bound VoxCPM2 GGUF synthetic wake-word pilot."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_piper_wake_ipa import (  # noqa: E402
    LEGACY_SINGLE_SEQUENCE,
    MODEL_ID,
    MODEL_REVISION,
    SAMPLE_RATE,
    TARGET_SEQUENCES,
    edit_distance,
    normalize_ipa,
    sha256,
    target_distance,
    trim_ctc_predictions,
)


def has_exact_target_subsequence(sequence: tuple[str, ...]) -> bool:
    for target in TARGET_SEQUENCES:
        width = len(target)
        for start in range(0, len(sequence) - width + 1):
            if sequence[start : start + width] == target:
                return True
    return False


def source_class_label(
    manifest: dict[str, object], source_label: str | None = None
) -> str:
    if source_label is not None:
        if source_label == "positive":
            return "positive"
        if source_label == "hard_negative":
            return "adversarial_negative"
        raise ValueError(f"unsupported_source_label:{source_label}")
    generation = manifest.get("generation")
    if isinstance(generation, dict):
        value = str(generation.get("class_label", "positive"))
    else:
        value = str(manifest.get("class_label", "positive"))
    if value not in {"positive", "adversarial_negative"}:
        raise ValueError(f"unsupported_source_class_label:{value}")
    return value


def configure_espeak_backend() -> dict[str, str] | None:
    """Bind the wheel-provided Windows eSpeak data before Transformers loads."""

    if os.name != "nt" or os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
        return None
    try:
        import espeakng_loader
    except ImportError:
        return None
    library = espeakng_loader.get_library_path()
    data = espeakng_loader.get_data_path()
    os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = library
    # espeak-ng itself, not phonemizer, consumes this variable when the wheel's
    # DLL was compiled with a build-machine data path.
    os.environ["ESPEAK_DATA_PATH"] = data
    return {"library": library, "data": data, "source": "espeakng_loader"}


def load_checkpoint(
    path: Path,
    *,
    source_manifest_sha256: str,
    model_sha256: str,
    raw_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != "baxy.voxcpm2-ipa-audit-checkpoint.v1":
        raise ValueError("unsupported_ipa_audit_checkpoint_schema")
    if value.get("source_manifest_sha256") != source_manifest_sha256:
        raise ValueError("ipa_audit_checkpoint_source_mismatch")
    if value.get("model_sha256") != model_sha256:
        raise ValueError("ipa_audit_checkpoint_model_mismatch")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > len(raw_records):
        raise ValueError("ipa_audit_checkpoint_records_invalid")
    typed = [record for record in records if isinstance(record, dict)]
    if len(typed) != len(records):
        raise ValueError("ipa_audit_checkpoint_record_is_not_object")
    for position, (record, raw) in enumerate(
        zip(typed, raw_records, strict=False)
    ):
        if (
            record.get("index") != raw.get("index")
            or record.get("persona_id") != raw.get("persona_id")
            or record.get("source_wav_sha256")
            != raw.get("wav", {}).get("sha256")
        ):
            raise ValueError(f"ipa_audit_checkpoint_record_mismatch:{position}")
    return typed


def write_checkpoint(
    path: Path,
    *,
    source_manifest_sha256: str,
    model_sha256: str,
    records: list[dict[str, object]],
) -> None:
    value = {
        "schema": "baxy.voxcpm2-ipa-audit-checkpoint.v1",
        "source_manifest_sha256": source_manifest_sha256,
        "model_sha256": model_sha256,
        "records": records,
        "blind_human_partition_accessed": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def bounded_batch_end(
    records: list[dict[str, object]],
    start: int,
    *,
    max_batch_size: int,
    max_padded_audio_seconds: float,
) -> int:
    """Choose a prefix batch while bounding CTC padding work and VRAM."""

    if not 0 <= start < len(records):
        raise ValueError("ipa_batch_start_out_of_range")
    end = start
    longest = 0.0
    while end < len(records) and end - start < max_batch_size:
        duration = float(records[end].get("wav", {}).get("duration_seconds", 0.0))
        if duration <= 0.0:
            raise ValueError(f"ipa_source_duration_invalid:{end}")
        candidate_longest = max(longest, duration)
        candidate_count = end - start + 1
        if (
            candidate_count > 1
            and candidate_longest * candidate_count > max_padded_audio_seconds
        ):
            break
        longest = candidate_longest
        end += 1
    return end


def summarize_records(records: list[dict[str, object]]) -> dict[str, object]:
    if not records:
        raise ValueError("ipa_records_empty")
    distances = [int(record["target_edit_distance"]) for record in records]
    legacy_distances = [int(record["legacy_edit_distance"]) for record in records]
    counts = Counter(distances)
    legacy_counts = Counter(legacy_distances)
    subsequence_hits = sum(
        bool(record.get("exact_target_subsequence", False)) for record in records
    )
    persona: dict[str, list[int]] = defaultdict(list)
    for record in records:
        persona[str(record["persona_id"])].append(int(record["target_edit_distance"]))
    return {
        "clip_count": len(records),
        "exact_target_count": counts[0],
        "exact_target_rate": counts[0] / len(records),
        "edit_distance_lte_1_count": counts[0] + counts[1],
        "edit_distance_lte_1_rate": (counts[0] + counts[1]) / len(records),
        "edit_distance_counts": {
            str(distance): counts[distance] for distance in sorted(counts)
        },
        "exact_target_subsequence_count": subsequence_hits,
        "exact_target_subsequence_rate": subsequence_hits / len(records),
        "legacy_single_sequence_comparison": {
            "sequence": list(LEGACY_SINGLE_SEQUENCE),
            "exact_target_count": legacy_counts[0],
            "exact_target_rate": legacy_counts[0] / len(records),
            "edit_distance_lte_1_count": legacy_counts[0] + legacy_counts[1],
            "edit_distance_lte_1_rate": (
                legacy_counts[0] + legacy_counts[1]
            )
            / len(records),
        },
        "by_persona": {
            persona_id: {
                "clip_count": len(values),
                "exact_target_count": sum(value == 0 for value in values),
                "exact_target_rate": sum(value == 0 for value in values)
                / len(values),
                "edit_distance_lte_1_count": sum(value <= 1 for value in values),
                "edit_distance_lte_1_rate": sum(value <= 1 for value in values)
                / len(values),
            }
            for persona_id, values in sorted(persona.items())
        },
    }


def normalize_source_records(
    manifest: dict[str, object],
    *,
    source_partition: str | None = None,
    source_label: str | None = None,
) -> list[dict[str, object]]:
    schema = manifest.get("schema")
    raw_records = manifest.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("pilot_manifest_records_missing")
    normalized: list[dict[str, object]] = []
    if schema == "baxy.voxcpm2-gguf-wake-pilot-corpus.v1":
        for record in raw_records:
            if not isinstance(record, dict):
                raise ValueError("pilot_record_is_not_object")
            normalized.append(record)
        return normalized
    if schema == "baxy.voxcpm2-ipa-filtered-wake-corpus.v1":
        for record in raw_records:
            if not isinstance(record, dict):
                raise ValueError("filtered_record_is_not_object")
            normalized.append(
                {
                    "index": record["output_index"],
                    "persona_id": record["persona_id"],
                    "seed": record["seed"],
                    "phrase_id": record.get("phrase_id", "target"),
                    "phrase_text": record.get("phrase_text"),
                    "output_file": record["output_file"],
                    "wav": record["wav"],
                }
            )
        return normalized
    if schema == "baxy.ccby-wake-holdout-corpus.v1":
        if source_partition != "development":
            raise ValueError("ccby_ipa_audit_requires_development_partition")
        if source_label not in {"positive", "hard_negative"}:
            raise ValueError("ccby_ipa_audit_source_label_invalid")
        for source_index, record in enumerate(raw_records):
            if not isinstance(record, dict):
                raise ValueError("ccby_record_is_not_object")
            if (
                record.get("partition") != source_partition
                or record.get("label") != source_label
            ):
                continue
            normalized.append(
                {
                    "index": source_index,
                    "persona_id": record["speaker_group"],
                    "seed": source_index,
                    "phrase_id": record["label"],
                    "phrase_text": None,
                    "output_file": record["output_relative_path"],
                    "wav": record["wav"],
                }
            )
        if not normalized:
            raise ValueError("ccby_ipa_audit_records_empty")
        return normalized
    raise ValueError("unsupported_voxcpm2_pilot_manifest_schema")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-padded-audio-seconds", type=float, default=32.0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--source-partition", choices=("development",))
    parser.add_argument("--source-label", choices=("positive", "hard_negative"))
    parser.add_argument(
        "--positive-ipa-policy",
        choices=("exact_target", "exact_target_subsequence"),
        default="exact_target",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch_size_must_be_positive")
    if args.max_padded_audio_seconds <= 0.0:
        raise ValueError("max_padded_audio_seconds_must_be_positive")
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema") == "baxy.ccby-wake-holdout-corpus.v1":
        if manifest.get("blind_partition_was_not_scored") is not True:
            raise ValueError("ccby_manifest_blind_boundary_invalid")
        if args.source_partition != "development" or args.source_label is None:
            raise ValueError("ccby_ipa_audit_scope_not_development_only")
    elif manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("pilot_manifest_blind_boundary_invalid")
    elif args.source_partition is not None or args.source_label is not None:
        raise ValueError("synthetic_ipa_audit_does_not_accept_source_filter")
    raw_records = normalize_source_records(
        manifest,
        source_partition=args.source_partition,
        source_label=args.source_label,
    )
    class_label = source_class_label(manifest, args.source_label)
    source_manifest_hash = sha256(manifest_path)

    espeak_backend = configure_espeak_backend()

    import librosa
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    device = (
        "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    )
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    model_dir = args.model_dir.resolve()
    model_weights = model_dir / "pytorch_model.bin"
    if not model_weights.is_file():
        raise FileNotFoundError(model_weights)
    model_hash = sha256(model_weights)
    processor = Wav2Vec2Processor.from_pretrained(model_dir, local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(
        model_dir, local_files_only=True
    ).eval().to(device)

    corpus_root = manifest_path.parent
    checkpoint_path = args.output.with_suffix(args.output.suffix + ".partial.json")
    results = load_checkpoint(
        checkpoint_path,
        source_manifest_sha256=source_manifest_hash,
        model_sha256=model_hash,
        raw_records=raw_records,
    )
    resumed_record_count = len(results)
    start = len(results)
    last_checkpoint_count = len(results)
    while start < len(raw_records):
        end = bounded_batch_end(
            raw_records,
            start,
            max_batch_size=args.batch_size,
            max_padded_audio_seconds=args.max_padded_audio_seconds,
        )
        batch = raw_records[start:end]
        audios = []
        paths = []
        for raw in batch:
            if not isinstance(raw, dict):
                raise ValueError("pilot_record_is_not_object")
            path = corpus_root / str(raw["output_file"])
            expected_hash = str(raw.get("wav", {}).get("sha256", ""))
            if sha256(path) != expected_hash:
                raise ValueError(f"pilot_wav_hash_mismatch:{path}")
            audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
            audios.append(audio)
            paths.append(path)
        inputs = processor(
            audios,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        model_inputs = {"input_values": inputs.input_values.to(device)}
        if getattr(inputs, "attention_mask", None) is not None:
            model_inputs["attention_mask"] = inputs.attention_mask.to(device)
        with torch.inference_mode():
            logits = model(**model_inputs).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        output_lengths = model._get_feat_extract_output_lengths(input_lengths)
        decoded = processor.batch_decode(
            trim_ctc_predictions(predicted_ids, output_lengths.tolist())
        )
        for raw, path, raw_ipa in zip(batch, paths, decoded, strict=True):
            sequence = normalize_ipa(raw_ipa)
            results.append(
                {
                    "index": raw["index"],
                    "persona_id": raw["persona_id"],
                    "seed": raw["seed"],
                    "phrase_id": raw.get("phrase_id", "target"),
                    "phrase_text": raw.get("phrase_text"),
                    "output_file": path.name,
                    "source_wav_sha256": raw["wav"]["sha256"],
                    "source_duration_seconds": raw["wav"]["duration_seconds"],
                    "decoded_ipa": raw_ipa,
                    "normalized_tokens": list(sequence),
                    "target_edit_distance": target_distance(sequence),
                    "exact_target_subsequence": has_exact_target_subsequence(
                        sequence
                    ),
                    "legacy_edit_distance": edit_distance(
                        sequence, LEGACY_SINGLE_SEQUENCE
                    ),
                }
            )
        if (
            len(results) - last_checkpoint_count >= 128
            or len(results) == len(raw_records)
        ):
            write_checkpoint(
                checkpoint_path,
                source_manifest_sha256=source_manifest_hash,
                model_sha256=model_hash,
                records=results,
            )
            last_checkpoint_count = len(results)
        start = end

    metrics = summarize_records(results)
    human_ccby_source = (
        manifest.get("schema") == "baxy.ccby-wake-holdout-corpus.v1"
    )
    if human_ccby_source:
        selection_boundary_passed: bool | None = None
        all_clips_exact: bool | None = None
    elif class_label == "positive":
        if args.positive_ipa_policy == "exact_target_subsequence":
            selection_boundary_passed = (
                metrics["exact_target_subsequence_count"] == metrics["clip_count"]
            )
            all_clips_exact = None
        else:
            selection_boundary_passed = (
                metrics["exact_target_count"] == metrics["clip_count"]
            )
            all_clips_exact = selection_boundary_passed
    else:
        selection_boundary_passed = metrics["exact_target_subsequence_count"] == 0
        all_clips_exact = None
    report = {
        "schema": "baxy.voxcpm2-gguf-wake-ipa-pilot.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            f"development_only_human_ccby_{args.source_label}_pronunciation_audit"
            if human_ccby_source
            else f"development_only_synthetic_{class_label}_pronunciation_audit"
        ),
        "class_label": class_label,
        "positive_ipa_policy": (
            args.positive_ipa_policy if class_label == "positive" else None
        ),
        "source_partition": args.source_partition,
        "source_label": args.source_label,
        "source_manifest": manifest_path.as_posix(),
        "source_manifest_sha256": source_manifest_hash,
        "source_manifest_schema": manifest["schema"],
        "source_runtime": manifest.get("runtime"),
        "source_model": manifest.get("model"),
        "source_generation": manifest.get("generation"),
        "source_filter": manifest.get("filter"),
        "phoneme_recognizer": {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "local_model_directory": model_dir.as_posix(),
            "pytorch_model_sha256": model_hash,
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "device": device,
            "ctc_batch_padding_logits_decoded": False,
            "max_batch_size": args.batch_size,
            "max_padded_audio_seconds": args.max_padded_audio_seconds,
            "espeak_backend": espeak_backend,
        },
        "checkpoint_resumed_record_count": resumed_record_count,
        "accepted_normalized_target_sequences": [
            list(target) for target in TARGET_SEQUENCES
        ],
        "metrics": metrics,
        "selection_boundary_passed": selection_boundary_passed,
        "all_clips_exact_after_source_transform": all_clips_exact,
        "records": results,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": None if human_ccby_source else False,
        "candidate_model_scores_accessed": False,
        "effects_executed": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checkpoint_path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "output": args.output.resolve().as_posix(),
                "class_label": class_label,
                "metrics": metrics,
                "selection_boundary_passed": selection_boundary_passed,
                "checkpoint_resumed_record_count": resumed_record_count,
                "blind_human_partition_accessed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
