from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "run_livekit_wake_development_stage.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_livekit_wake_development_stage", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_stage_order_is_strict_and_non_repeatable() -> None:
    MODULE.validate_stage_order("augment", set())
    MODULE.validate_stage_order("train", {"augment"})
    MODULE.validate_stage_order("export", {"augment", "train"})
    MODULE.validate_stage_order("eval", {"augment", "train", "export"})

    with pytest.raises(ValueError, match="development_stage_already_completed"):
        MODULE.validate_stage_order("train", {"augment", "train"})
    with pytest.raises(
        ValueError, match="development_stage_prerequisites_missing:augment"
    ):
        MODULE.validate_stage_order("train", set())


def test_digest_files_is_order_independent_and_content_bound(tmp_path: Path) -> None:
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    forward = MODULE.digest_files([first, second], tmp_path)
    reverse = MODULE.digest_files([second, first], tmp_path)

    assert forward == reverse
    assert forward["file_count"] == 2
    second.write_bytes(b"changed")
    assert MODULE.digest_files([first, second], tmp_path) != forward


def test_seed_process_rejects_out_of_range_seed() -> None:
    with pytest.raises(ValueError, match="development_seed_out_of_range"):
        MODULE.seed_process(-1)


def test_seed_process_requires_startup_hash_seed(monkeypatch) -> None:
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    with pytest.raises(ValueError, match="python_hash_seed_mismatch"):
        MODULE.seed_process(20260803)


def test_configure_utf8_output_reconfigures_both_streams(monkeypatch) -> None:
    class Stream:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def reconfigure(self, **kwargs: str) -> None:
            self.calls.append(kwargs)

    stdout = Stream()
    stderr = Stream()
    monkeypatch.setattr(MODULE.sys, "stdout", stdout)
    monkeypatch.setattr(MODULE.sys, "stderr", stderr)

    MODULE.configure_utf8_output()

    expected = [{"encoding": "utf-8", "errors": "backslashreplace"}]
    assert stdout.calls == expected
    assert stderr.calls == expected


def test_assembly_data_identity_ignores_location_and_timestamp() -> None:
    left = {
        "measured_at_utc": "first",
        "positive_manifest": "first.json",
        "counts": {"positive_train": 1},
        "digests": {"positive_train": "abc"},
        "split": {"salt": "fixed"},
        "positive_manifest_sha256": "positive",
        "negative_manifest_sha256": "negative",
    }
    right = {**left, "measured_at_utc": "second", "positive_manifest": "other.json"}

    assert MODULE.assembly_data_identity(left) == MODULE.assembly_data_identity(right)
    right["digests"] = {"positive_train": "changed"}
    assert MODULE.assembly_data_identity(left) != MODULE.assembly_data_identity(right)


def test_reuse_augmentation_hardlinks_only_verified_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    for split in (
        "positive_train",
        "positive_test",
        "negative_train",
        "negative_test",
    ):
        (source / split).mkdir()
        (target / split).mkdir()
        (source / split / "clip_000000_r0.wav").write_bytes(split.encode())
    for name in (
        "positive_features_train.npy",
        "positive_features_test.npy",
        "negative_features_train.npy",
        "negative_features_test.npy",
    ):
        (source / name).write_bytes(name.encode())

    assembly = {
        "counts": {"positive_train": 1},
        "digests": {"positive_train": "fixed"},
        "split": {"salt": "fixed"},
        "positive_manifest_sha256": "positive",
        "negative_manifest_sha256": "negative",
    }
    source_assembly = source / "assembly_manifest.v1.json"
    source_assembly.write_text(json.dumps(assembly), encoding="utf-8")
    source_artifacts = MODULE.collect_stage_artifacts("augment", source)
    source_run = source / "development_run_manifest.v1.json"
    source_run.write_text(
        json.dumps(
            {
                "schema": MODULE.RUN_SCHEMA,
                "assembly_manifest": str(source_assembly),
                "config_sha256": "config",
                "seed": 20260803,
                "stages": {"augment": {"artifacts": source_artifacts}},
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )

    provenance = MODULE.reuse_augmentation(
        source_run_manifest_path=source_run,
        target_model_dir=target,
        target_assembly=assembly,
        seed=20260803,
    )

    assert provenance["method"] == "verified_hardlink_reuse"
    assert MODULE.collect_stage_artifacts("augment", target) == source_artifacts


def test_append_hard_negatives_replaces_target_without_mutating_source(
    tmp_path: Path,
) -> None:
    import os

    import numpy as np

    source = tmp_path / "source"
    target = tmp_path / "target"
    hard = tmp_path / "hard"
    source.mkdir()
    target.mkdir()
    hard.mkdir()
    source_train = np.full((2, 16, 96), 1.0, dtype=np.float32)
    source_test = np.full((1, 16, 96), 2.0, dtype=np.float32)
    extra_train = np.full((3, 16, 96), 3.0, dtype=np.float32)
    extra_test = np.full((2, 16, 96), 4.0, dtype=np.float32)
    np.save(source / "negative_features_train.npy", source_train)
    np.save(source / "negative_features_test.npy", source_test)
    np.save(hard / "train.npy", extra_train)
    np.save(hard / "development.npy", extra_test)
    os.link(
        source / "negative_features_train.npy",
        target / "negative_features_train.npy",
    )
    os.link(
        source / "negative_features_test.npy",
        target / "negative_features_test.npy",
    )
    manifest = hard / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MODULE.HARD_NEGATIVE_FEATURE_SCHEMA,
                "outputs": {
                    "train": {
                        "path": str(hard / "train.npy"),
                        "sha256": MODULE.sha256(hard / "train.npy"),
                        "shape": list(extra_train.shape),
                    },
                    "development": {
                        "path": str(hard / "development.npy"),
                        "sha256": MODULE.sha256(hard / "development.npy"),
                        "shape": list(extra_test.shape),
                    },
                },
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )

    provenance = MODULE.append_hard_negative_features(
        manifest_path=manifest,
        target_model_dir=target,
    )

    combined_train = np.load(target / "negative_features_train.npy")
    combined_test = np.load(target / "negative_features_test.npy")
    assert combined_train.shape == (5, 16, 96)
    assert combined_test.shape == (3, 16, 96)
    np.testing.assert_array_equal(combined_train[:2], source_train)
    np.testing.assert_array_equal(combined_train[2:], extra_train)
    np.testing.assert_array_equal(combined_test[:1], source_test)
    np.testing.assert_array_equal(combined_test[1:], extra_test)
    np.testing.assert_array_equal(
        np.load(source / "negative_features_train.npy"), source_train
    )
    np.testing.assert_array_equal(
        np.load(source / "negative_features_test.npy"), source_test
    )
    assert provenance["splits"]["train"]["combinedRecords"] == 5
    assert provenance["splits"]["development"]["combinedRecords"] == 3


def test_append_hard_negatives_rejects_blind_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MODULE.HARD_NEGATIVE_FEATURE_SCHEMA,
                "blind_human_partition_accessed": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hard_negative_feature_blind_boundary"):
        MODULE.append_hard_negative_features(
            manifest_path=manifest,
            target_model_dir=tmp_path,
        )


def test_append_physical_features_updates_all_class_splits(tmp_path: Path) -> None:
    import numpy as np

    target = tmp_path / "target"
    extra_root = tmp_path / "extra"
    target.mkdir()
    extra_root.mkdir()
    bindings = {
        "positive_train": "positive_features_train.npy",
        "positive_development": "positive_features_test.npy",
        "negative_train": "negative_features_train.npy",
        "negative_development": "negative_features_test.npy",
    }
    outputs = {}
    for index, (split, target_name) in enumerate(bindings.items(), start=1):
        base = np.full((index, 16, 96), index, dtype=np.float32)
        extra = np.full((2, 16, 96), index + 10, dtype=np.float32)
        np.save(target / target_name, base)
        extra_path = extra_root / f"{split}.npy"
        np.save(extra_path, extra)
        outputs[split] = {
            "path": str(extra_path),
            "sha256": MODULE.sha256(extra_path),
            "shape": list(extra.shape),
        }
    manifest = extra_root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MODULE.PHYSICAL_FEATURE_SCHEMA,
                "outputs": outputs,
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )

    provenance = MODULE.append_physical_features(
        manifest_path=manifest,
        target_model_dir=target,
    )

    assert provenance["method"] == "verified_labeled_float32_feature_concatenation"
    for index, (split, target_name) in enumerate(bindings.items(), start=1):
        combined = np.load(target / target_name)
        assert combined.shape == (index + 2, 16, 96)
        assert provenance["splits"][split]["combinedRecords"] == index + 2
