from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "select_voxcpm2_post_transform_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "select_voxcpm2_post_transform_corpus", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_source(root: Path, class_label: str) -> Path:
    root.mkdir()
    records = []
    for index in range(2):
        path = root / f"clip_{index:06d}.wav"
        path.write_bytes(f"audio-{index}".encode())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(
            {
                "output_index": index,
                "output_file": path.name,
                "source_index": index + 10,
                "persona_id": "speaker",
                "persona": "voice",
                "seed": index,
                "phrase_id": "target" if class_label == "positive" else "taxi",
                "phrase_text": "Baxy." if class_label == "positive" else "Taxi.",
                "wav": {"sha256": digest},
            }
        )
    manifest = root / "manifest.v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MODULE.FILTERED_SCHEMA,
                "class_label": class_label,
                "records": records,
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_audit(source: Path, class_label: str) -> Path:
    manifest = json.loads(source.read_text(encoding="utf-8"))
    records = []
    for index, source_record in enumerate(manifest["records"]):
        records.append(
            {
                "index": index,
                "source_wav_sha256": source_record["wav"]["sha256"],
                "decoded_ipa": "b a k s i",
                "normalized_tokens": ["b", "a", "k", "s", "i"],
                "target_edit_distance": 0 if index == 0 else 1,
                "exact_target_subsequence": index == 0,
            }
        )
    audit = source.parent / "audit.json"
    audit.write_text(
        json.dumps(
            {
                "schema": MODULE.AUDIT_SCHEMA,
                "class_label": class_label,
                "source_manifest_sha256": MODULE.sha256(source),
                "records": records,
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )
    return audit


def test_positive_selection_keeps_only_post_transform_exact_clip(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "source", "positive")
    audit = _write_audit(source, "positive")

    result = MODULE.select_corpus(
        source_manifest_path=source,
        audit_path=audit,
        output_dir=tmp_path / "selected",
    )

    assert result["counts"] == {
        "source": 2,
        "accepted": 1,
        "rejected": 1,
        "phoneme_rejected": 1,
    }
    assert result["records"][0]["post_transform_source_output_index"] == 0
    assert result["rejections"][0]["reason"] == "ipa_not_exact"


def test_negative_selection_removes_embedded_target_collision(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "source", "adversarial_negative")
    audit = _write_audit(source, "adversarial_negative")

    result = MODULE.select_corpus(
        source_manifest_path=source,
        audit_path=audit,
        output_dir=tmp_path / "selected",
    )

    assert result["counts"]["accepted"] == 1
    assert result["records"][0]["post_transform_source_output_index"] == 1
    assert (
        result["rejections"][0]["reason"]
        == "exact_target_subsequence_collision"
    )


def test_context_positive_selection_uses_subsequence_policy(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "source", "positive")
    source_value = json.loads(source.read_text(encoding="utf-8"))
    source_value["filter"] = {
        "positive_ipa_policy": "exact_target_subsequence"
    }
    source.write_text(json.dumps(source_value), encoding="utf-8")
    audit = _write_audit(source, "positive")
    audit_value = json.loads(audit.read_text(encoding="utf-8"))
    audit_value["positive_ipa_policy"] = "exact_target_subsequence"
    audit.write_text(json.dumps(audit_value), encoding="utf-8")

    result = MODULE.select_corpus(
        source_manifest_path=source,
        audit_path=audit,
        output_dir=tmp_path / "selected",
    )

    assert result["counts"]["accepted"] == 1
    assert result["filter"]["positive_ipa_policy"] == "exact_target_subsequence"
