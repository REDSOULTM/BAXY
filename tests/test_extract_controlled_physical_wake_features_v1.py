from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "extract_controlled_physical_wake_features_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_physical_features", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_split_is_deterministic_and_preserves_labels() -> None:
    gate = _module()
    records = [
        {
            "recordId": f"{label}/{index:06d}",
            "sourceSha256": f"{index + offset:064x}",
        }
        for label, offset in (("positive", 0), ("negative", 10_000))
        for index in range(100)
    ]

    first = gate.split_records(records, "fixed")
    second = gate.split_records(records, "fixed")

    assert first == second
    assert sum(len(values) for values in first.values()) == len(records)
    assert all(
        record["recordId"].startswith("positive/")
        for name, values in first.items()
        if name.startswith("positive")
        for record in values
    )


def test_split_rejects_unbound_source_identity() -> None:
    gate = _module()

    try:
        gate.split_records(
            [{"recordId": "positive/000000", "sourceSha256": "short"}],
            "fixed",
        )
    except ValueError as error:
        assert str(error) == "controlled_physical_feature_source_identity_invalid"
    else:
        raise AssertionError("invalid source identity must fail closed")


def test_training_repeat_weights_can_favor_physical_positives() -> None:
    gate = _module()
    common = {
        "default_repeats": 16,
        "positive_repeats": 64,
        "negative_repeats": 8,
    }

    assert gate.training_repeat_weight("positive_train", **common) == 64
    assert gate.training_repeat_weight("negative_train", **common) == 8
    assert gate.training_repeat_weight("positive_development", **common) == 1
    assert gate.training_repeat_weight("negative_development", **common) == 1


def test_target_aligned_window_centers_teacher_span() -> None:
    gate = _module()
    audio = np.arange(48_000, dtype=np.float32)

    aligned = gate.target_aligned_window(audio, (1.20, 1.60))

    assert aligned.shape == (32_000,)
    assert aligned[0] == audio[6_400]
    assert aligned[-1] == audio[38_399]


def test_target_aligned_window_rejects_span_outside_capture() -> None:
    gate = _module()

    try:
        gate.target_aligned_window(np.zeros(16_000, dtype=np.float32), (0.8, 1.2))
    except ValueError as error:
        assert str(error) == "controlled_physical_feature_target_span_outside_audio"
    else:
        raise AssertionError("out-of-range teacher span must fail closed")


def test_retain_localized_positives_drops_only_unlocalized_positive_records() -> None:
    gate = _module()
    split = {
        "positive_train": [
            {"sourceSha256": "a" * 64},
            {"sourceSha256": "b" * 64},
        ],
        "positive_development": [{"sourceSha256": "c" * 64}],
        "negative_train": [{"sourceSha256": "d" * 64}],
        "negative_development": [{"sourceSha256": "e" * 64}],
    }

    filtered = gate.retain_localized_positives(
        split,
        {"a" * 64: (0.2, 0.5), "c" * 64: (0.3, 0.6)},
    )

    assert filtered["positive_train"] == [{"sourceSha256": "a" * 64}]
    assert filtered["positive_development"] == [{"sourceSha256": "c" * 64}]
    assert filtered["negative_train"] == split["negative_train"]
