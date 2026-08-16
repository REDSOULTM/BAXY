from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import wave

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "assemble_voxcpm2_livekit_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "assemble_voxcpm2_livekit_corpus", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_wav(path: Path, value: int) -> str:
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(value.to_bytes(2, "little", signed=True) * 8_000)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(path: Path, class_label: str) -> None:
    path.parent.mkdir()
    records = []
    for index, persona in enumerate(("a", "b", "c", "d")):
        wav_path = path.parent / f"clip_{index:06d}.wav"
        digest = _write_wav(wav_path, index + 1)
        records.append(
            {
                "output_index": index,
                "output_file": wav_path.name,
                "source_index": index,
                "persona_id": persona,
                "seed": 10 + index,
                "phrase_id": "target" if class_label == "positive" else "taxi",
                "phrase_text": "Baxy." if class_label == "positive" else "Taxi.",
                "wav": {"sha256": digest},
            }
        )
    path.write_text(
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


def test_persona_selection_is_deterministic_and_bounded() -> None:
    personas = {"a", "b", "c", "d"}
    first = MODULE.select_test_personas(personas, count=1, salt="fixed")

    assert first == MODULE.select_test_personas(personas, count=1, salt="fixed")
    assert len(first) == 1
    with pytest.raises(ValueError, match="test_persona_count_out_of_range"):
        MODULE.select_test_personas(personas, count=4, salt="fixed")


def test_assemble_creates_dense_leakage_free_hardlink_splits(tmp_path: Path) -> None:
    positive = tmp_path / "positive" / "manifest.v1.json"
    negative = tmp_path / "negative" / "manifest.v1.json"
    output = tmp_path / "output"
    _write_manifest(positive, "positive")
    _write_manifest(negative, "adversarial_negative")

    report = MODULE.assemble(
        positive_manifest_path=positive,
        negative_manifest_path=negative,
        output_dir=output,
        test_persona_count=1,
        split_salt="fixed",
    )

    assert report["counts"] == {
        "positive_train": 3,
        "positive_test": 1,
        "negative_train": 3,
        "negative_test": 1,
    }
    test_personas = set(report["split"]["test_personas"])
    for split_name, records in report["records"].items():
        expected_test = split_name.endswith("_test")
        assert all((record["persona_id"] in test_personas) == expected_test for record in records)
        assert [record["output_file"] for record in records] == [
            f"clip_{index:06d}.wav" for index in range(len(records))
        ]
    assert (output / "assembly_manifest.v1.json").is_file()


def test_assemble_refuses_nonempty_output(tmp_path: Path) -> None:
    positive = tmp_path / "positive" / "manifest.v1.json"
    negative = tmp_path / "negative" / "manifest.v1.json"
    output = tmp_path / "output"
    _write_manifest(positive, "positive")
    _write_manifest(negative, "adversarial_negative")
    output.mkdir()
    (output / "owned.txt").write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError, match="livekit_output_directory_not_empty"):
        MODULE.assemble(
            positive_manifest_path=positive,
            negative_manifest_path=negative,
            output_dir=output,
            test_persona_count=1,
            split_salt="fixed",
        )
