"""Assemble hash-bound VoxCPM2 clips into leakage-resistant LiveKit splits."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import wave


FILTERED_SCHEMA = "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
SAMPLE_RATE = 16_000
MIN_DURATION_SECONDS = 0.20
MAX_DURATION_SECONDS = 2.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path, expected_class: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != FILTERED_SCHEMA:
        raise ValueError(f"unsupported_filtered_manifest:{path}")
    if value.get("blind_human_partition_accessed") is not False:
        raise ValueError(f"filtered_manifest_blind_boundary_invalid:{path}")
    class_label = str(value.get("class_label", "positive"))
    if class_label != expected_class:
        raise ValueError(
            f"filtered_manifest_class_mismatch:{expected_class}:{class_label}"
        )
    records = value.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError(f"filtered_manifest_records_missing:{path}")
    return value


def select_test_personas(
    persona_ids: set[str], *, count: int, salt: str
) -> tuple[str, ...]:
    if not 0 < count < len(persona_ids):
        raise ValueError("test_persona_count_out_of_range")
    if not salt:
        raise ValueError("split_salt_empty")
    ranked = sorted(
        persona_ids,
        key=lambda value: (
            hashlib.sha256(f"{salt}\0{value}".encode("utf-8")).hexdigest(),
            value,
        ),
    )
    return tuple(sorted(ranked[:count]))


def ordered_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        records,
        key=lambda record: (
            str(record["persona_id"]),
            int(record["seed"]),
            str(record.get("phrase_id", "target")),
            int(record["source_index"]),
        ),
    )


def validate_wav(path: Path, expected_hash: str) -> dict[str, object]:
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(f"filtered_wav_hash_mismatch:{path}")
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
            source.getcomptype(),
        )
        frames = source.getnframes()
        payload = source.readframes(frames + 1)
    if contract != (1, 2, SAMPLE_RATE, "NONE"):
        raise ValueError(f"filtered_wav_contract_mismatch:{path}")
    if frames <= 0 or len(payload) != frames * 2:
        raise ValueError(f"filtered_wav_payload_invalid:{path}")
    duration = frames / SAMPLE_RATE
    if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        raise ValueError(f"filtered_wav_duration_out_of_range:{path}")
    return {
        "sha256": actual_hash,
        "frames": frames,
        "duration_seconds": duration,
    }


def corpus_digest(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        output_file = str(record["output_file"]).encode("ascii")
        digest.update(len(output_file).to_bytes(4, "big"))
        digest.update(output_file)
        digest.update(bytes.fromhex(str(record["source_sha256"])))
    return digest.hexdigest()


def assemble(
    *,
    positive_manifest_path: Path,
    negative_manifest_path: Path,
    output_dir: Path,
    test_persona_count: int,
    split_salt: str,
) -> dict[str, object]:
    positive_path = positive_manifest_path.resolve(strict=True)
    negative_path = negative_manifest_path.resolve(strict=True)
    positive = read_manifest(positive_path, "positive")
    negative = read_manifest(negative_path, "adversarial_negative")
    manifests = {
        "positive": (positive_path, positive),
        "negative": (negative_path, negative),
    }

    typed_records: dict[str, list[dict[str, object]]] = {}
    persona_ids: set[str] = set()
    for class_name, (_, manifest) in manifests.items():
        records = manifest["records"]
        assert isinstance(records, list)
        typed = [record for record in records if isinstance(record, dict)]
        if len(typed) != len(records):
            raise ValueError(f"filtered_record_is_not_object:{class_name}")
        typed_records[class_name] = ordered_records(typed)
        persona_ids.update(str(record["persona_id"]) for record in typed)

    test_personas = set(
        select_test_personas(
            persona_ids, count=test_persona_count, salt=split_salt
        )
    )
    root = output_dir.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"livekit_output_directory_not_empty:{root}")
    root.mkdir(parents=True, exist_ok=True)

    output_splits: dict[str, list[dict[str, object]]] = {}
    for class_name, (manifest_path, _) in manifests.items():
        livekit_prefix = "positive" if class_name == "positive" else "negative"
        for split in ("train", "test"):
            split_name = f"{livekit_prefix}_{split}"
            selected = [
                record
                for record in typed_records[class_name]
                if (str(record["persona_id"]) in test_personas) == (split == "test")
            ]
            if not selected:
                raise ValueError(f"assembled_split_empty:{split_name}")
            split_dir = root / split_name
            split_dir.mkdir()
            emitted: list[dict[str, object]] = []
            for output_index, record in enumerate(selected):
                source_path = manifest_path.parent / str(record["output_file"])
                expected_hash = str(record.get("wav", {}).get("sha256", ""))
                wav = validate_wav(source_path, expected_hash)
                output_path = split_dir / f"clip_{output_index:06d}.wav"
                os.link(source_path, output_path)
                emitted.append(
                    {
                        "output_index": output_index,
                        "output_file": output_path.name,
                        "source_file": source_path.name,
                        "source_sha256": wav["sha256"],
                        "source_index": record["source_index"],
                        "persona_id": record["persona_id"],
                        "seed": record["seed"],
                        "phrase_id": record.get("phrase_id", "target"),
                        "phrase_text": record.get("phrase_text"),
                        "duration_seconds": wav["duration_seconds"],
                    }
                )
            output_splits[split_name] = emitted

    report = {
        "schema": "baxy.voxcpm2-livekit-corpus-assembly.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "hardlink_hash_bound_persona_group_split",
        "positive_manifest": positive_path.as_posix(),
        "positive_manifest_sha256": sha256(positive_path),
        "negative_manifest": negative_path.as_posix(),
        "negative_manifest_sha256": sha256(negative_path),
        "split": {
            "salt": split_salt,
            "unique_persona_count": len(persona_ids),
            "test_persona_count": len(test_personas),
            "test_personas": sorted(test_personas),
            "persona_overlap_between_train_and_test": 0,
        },
        "counts": {name: len(records) for name, records in output_splits.items()},
        "digests": {
            name: corpus_digest(records) for name, records in output_splits.items()
        },
        "records": output_splits,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": False,
        "effects_executed": 0,
    }
    manifest_path = root / "assembly_manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-manifest", type=Path, required=True)
    parser.add_argument("--negative-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-persona-count", type=int, default=8)
    parser.add_argument("--split-salt", default="baxy-voxcpm2-development-v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = assemble(
        positive_manifest_path=args.positive_manifest,
        negative_manifest_path=args.negative_manifest,
        output_dir=args.output_dir,
        test_persona_count=args.test_persona_count,
        split_salt=args.split_salt,
    )
    summary = {
        "schema": report["schema"],
        "output_dir": args.output_dir.resolve().as_posix(),
        "counts": report["counts"],
        "test_personas": report["split"]["test_personas"],
        "persona_overlap_between_train_and_test": report["split"][
            "persona_overlap_between_train_and_test"
        ],
        "manifest": (args.output_dir.resolve() / "assembly_manifest.v1.json").as_posix(),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
