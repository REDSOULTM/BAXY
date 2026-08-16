"""Select post-transform IPA-safe VoxCPM2 clips without changing audio bytes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from filter_voxcpm2_wake_corpus import ipa_rejection_reason  # noqa: E402


FILTERED_SCHEMA = "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
AUDIT_SCHEMA = "baxy.voxcpm2-gguf-wake-ipa-pilot.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def select_corpus(
    *, source_manifest_path: Path, audit_path: Path, output_dir: Path
) -> dict[str, object]:
    source_path = source_manifest_path.resolve(strict=True)
    audit_path = audit_path.resolve(strict=True)
    source = read_json(source_path)
    audit = read_json(audit_path)
    if source.get("schema") != FILTERED_SCHEMA:
        raise ValueError("unsupported_post_transform_source_schema")
    if audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("unsupported_post_transform_audit_schema")
    if source.get("blind_human_partition_accessed") is not False:
        raise ValueError("post_transform_source_blind_boundary_invalid")
    if audit.get("blind_human_partition_accessed") is not False:
        raise ValueError("post_transform_audit_blind_boundary_invalid")
    if audit.get("source_manifest_sha256") != sha256(source_path):
        raise ValueError("post_transform_source_and_audit_hash_mismatch")
    class_label = str(source.get("class_label", "positive"))
    if class_label not in {"positive", "adversarial_negative"}:
        raise ValueError(f"unsupported_post_transform_class:{class_label}")
    if str(audit.get("class_label", class_label)) != class_label:
        raise ValueError("post_transform_source_and_audit_class_mismatch")
    source_filter = source.get("filter")
    positive_ipa_policy = (
        str(source_filter.get("positive_ipa_policy", "exact_target"))
        if isinstance(source_filter, dict)
        else "exact_target"
    )
    audit_positive_policy = str(audit.get("positive_ipa_policy", "exact_target"))
    if class_label == "positive" and audit_positive_policy != positive_ipa_policy:
        raise ValueError("post_transform_positive_ipa_policy_mismatch")

    source_records = source.get("records")
    audit_records = audit.get("records")
    if not isinstance(source_records, list) or not isinstance(audit_records, list):
        raise ValueError("post_transform_records_missing")
    source_by_index = {
        int(record["output_index"]): record
        for record in source_records
        if isinstance(record, dict)
    }
    audit_by_index = {
        int(record["index"]): record
        for record in audit_records
        if isinstance(record, dict)
    }
    if (
        len(source_by_index) != len(source_records)
        or len(audit_by_index) != len(audit_records)
        or source_by_index.keys() != audit_by_index.keys()
    ):
        raise ValueError("post_transform_record_index_mismatch")

    root = output_dir.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"selected_output_directory_not_empty:{root}")
    root.mkdir(parents=True, exist_ok=True)
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for source_output_index in sorted(source_by_index):
        record = source_by_index[source_output_index]
        audited = audit_by_index[source_output_index]
        source_wav = source_path.parent / str(record["output_file"])
        expected_hash = str(record.get("wav", {}).get("sha256", ""))
        actual_hash = sha256(source_wav)
        if actual_hash != expected_hash or actual_hash != str(
            audited.get("source_wav_sha256", "")
        ):
            raise ValueError(f"post_transform_wav_hash_mismatch:{source_wav}")
        reason = ipa_rejection_reason(
            audited, class_label, positive_ipa_policy
        )
        if reason is not None:
            rejected.append(
                {
                    "source_output_index": source_output_index,
                    "source_index": record["source_index"],
                    "reason": reason,
                    "phrase_id": record.get("phrase_id", "target"),
                    "phrase_text": record.get("phrase_text"),
                    "decoded_ipa": audited["decoded_ipa"],
                    "target_edit_distance": audited["target_edit_distance"],
                    "exact_target_subsequence": audited.get(
                        "exact_target_subsequence"
                    ),
                }
            )
            continue
        output_index = len(accepted)
        output_path = root / f"clip_{output_index:06d}.wav"
        os.link(source_wav, output_path)
        accepted.append(
            {
                **record,
                "output_index": output_index,
                "output_file": output_path.name,
                "post_transform_source_output_index": source_output_index,
                "post_transform_source_file": source_wav.name,
                "decoded_ipa": audited["decoded_ipa"],
                "normalized_tokens": audited["normalized_tokens"],
                "class_label": class_label,
            }
        )

    manifest = {
        "schema": FILTERED_SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "class_label": class_label,
        "source_filtered_manifest": source_path.as_posix(),
        "source_filtered_manifest_sha256": sha256(source_path),
        "post_transform_ipa_audit": audit_path.as_posix(),
        "post_transform_ipa_audit_sha256": sha256(audit_path),
        "filter": {
            "stage": "post_transform_selection",
            "audio_transform": "none_hardlink_exact_bytes",
            "positive_ipa_policy": (
                positive_ipa_policy if class_label == "positive" else None
            ),
            "phoneme_selection_rule": (
                (
                    "target_edit_distance_equals_zero"
                    if positive_ipa_policy == "exact_target"
                    else "exact_target_subsequence_is_true"
                )
                if class_label == "positive"
                else "exact_target_subsequence_is_false"
            ),
        },
        "counts": {
            "source": len(source_by_index),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "phoneme_rejected": len(rejected),
        },
        "records": accepted,
        "rejections": rejected,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": False,
        "effects_executed": 0,
    }
    manifest_path = root / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--post-transform-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = select_corpus(
        source_manifest_path=args.source_manifest,
        audit_path=args.post_transform_audit,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "manifest": (args.output_dir.resolve() / "manifest.v1.json").as_posix(),
                "class_label": manifest["class_label"],
                "counts": manifest["counts"],
                "blind_human_partition_accessed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
