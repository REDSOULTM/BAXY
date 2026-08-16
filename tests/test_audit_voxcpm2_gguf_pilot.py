from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_voxcpm2_gguf_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("audit_voxcpm2_gguf_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _record(persona: str, distance: int, legacy: int | None = None) -> dict:
    return {
        "persona_id": persona,
        "target_edit_distance": distance,
        "legacy_edit_distance": distance if legacy is None else legacy,
        "exact_target_subsequence": distance == 0,
    }


def test_summarize_records_reports_global_and_persona_rates() -> None:
    summary = MODULE.summarize_records(
        [_record("a", 0), _record("a", 1), _record("b", 2), _record("b", 0)]
    )

    assert summary["clip_count"] == 4
    assert summary["exact_target_rate"] == pytest.approx(0.5)
    assert summary["edit_distance_lte_1_rate"] == pytest.approx(0.75)
    assert summary["edit_distance_counts"] == {"0": 2, "1": 1, "2": 1}
    assert summary["by_persona"]["a"]["edit_distance_lte_1_rate"] == 1.0
    assert summary["by_persona"]["b"]["exact_target_rate"] == 0.5


def test_summarize_records_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="ipa_records_empty"):
        MODULE.summarize_records([])


def test_legacy_metric_is_independent() -> None:
    summary = MODULE.summarize_records(
        [_record("accent", 0, legacy=1), _record("accent", 0, legacy=0)]
    )

    assert summary["exact_target_rate"] == 1.0
    assert summary["legacy_single_sequence_comparison"]["exact_target_rate"] == 0.5


def test_normalize_filtered_records_maps_dense_output_index() -> None:
    records = MODULE.normalize_source_records(
        {
            "schema": "baxy.voxcpm2-ipa-filtered-wake-corpus.v1",
            "records": [
                {
                    "output_index": 3,
                    "persona_id": "speaker",
                    "seed": 42,
                    "output_file": "clip_000003.wav",
                    "wav": {"sha256": "a" * 64, "duration_seconds": 0.8},
                }
            ],
        }
    )

    assert records[0]["index"] == 3
    assert records[0]["output_file"] == "clip_000003.wav"


def test_normalize_source_records_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="unsupported_voxcpm2_pilot_manifest_schema"):
        MODULE.normalize_source_records({"schema": "unknown", "records": [{}]})


def test_normalize_ccby_records_is_development_label_scoped() -> None:
    manifest = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "records": [
            {
                "partition": "development",
                "label": "positive",
                "speaker_group": "dev-speaker",
                "output_relative_path": "development/positive/dev.wav",
                "wav": {"sha256": "a" * 64, "duration_seconds": 3.0},
            },
            {
                "partition": "blind",
                "label": "positive",
                "speaker_group": "blind-speaker",
                "output_relative_path": "blind/positive/blind.wav",
                "wav": {"sha256": "b" * 64, "duration_seconds": 3.0},
            },
        ],
    }

    records = MODULE.normalize_source_records(
        manifest, source_partition="development", source_label="positive"
    )

    assert len(records) == 1
    assert records[0]["persona_id"] == "dev-speaker"
    assert records[0]["output_file"] == "development/positive/dev.wav"


def test_source_class_label_maps_ccby_hard_negative() -> None:
    assert MODULE.source_class_label({}, "hard_negative") == "adversarial_negative"


def test_exact_target_subsequence_finds_keyword_inside_context() -> None:
    assert MODULE.has_exact_target_subsequence(
        ("k", "ɔ", "l", "b", "a", "k", "s", "i")
    )
    assert not MODULE.has_exact_target_subsequence(
        ("k", "ɔ", "l", "m", "a", "k", "s", "i")
    )
    assert MODULE.has_exact_target_subsequence(
        ("p", "r", "i", "v", "e", "t", "b", "a", "k", "sʲ", "i")
    )


def test_source_class_label_defaults_legacy_manifests_to_positive() -> None:
    assert MODULE.source_class_label({}) == "positive"
    assert (
        MODULE.source_class_label(
            {"generation": {"class_label": "adversarial_negative"}}
        )
        == "adversarial_negative"
    )


def test_source_class_label_rejects_unknown_class() -> None:
    with pytest.raises(ValueError, match="unsupported_source_class_label"):
        MODULE.source_class_label({"generation": {"class_label": "unknown"}})


def test_configure_espeak_backend_binds_wheel_data_on_windows(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PHONEMIZER_ESPEAK_LIBRARY", raising=False)
    monkeypatch.delenv("ESPEAK_DATA_PATH", raising=False)
    library = tmp_path / "libespeak-ng.dll"
    library.touch()
    data = tmp_path / "espeak-ng-data"
    data.mkdir()
    monkeypatch.setitem(
        sys.modules,
        "espeakng_loader",
        SimpleNamespace(
            get_library_path=lambda: str(library),
            get_data_path=lambda: str(data),
        ),
    )

    result = MODULE.configure_espeak_backend()

    if MODULE.os.name == "nt":
        assert result is not None
        assert Path(result["library"]).is_file()
        assert Path(result["data"]).is_dir()
        assert MODULE.os.environ["ESPEAK_DATA_PATH"] == result["data"]
    else:
        assert result is None


def test_audit_checkpoint_is_hash_bound_and_resumable(tmp_path: Path) -> None:
    path = tmp_path / "audit.partial.json"
    raw = [
        {
            "index": 0,
            "persona_id": "speaker",
            "wav": {"sha256": "a" * 64},
        }
    ]
    audited = [
        {
            "index": 0,
            "persona_id": "speaker",
            "source_wav_sha256": "a" * 64,
        }
    ]
    MODULE.write_checkpoint(
        path,
        source_manifest_sha256="b" * 64,
        model_sha256="c" * 64,
        records=audited,
    )

    assert MODULE.load_checkpoint(
        path,
        source_manifest_sha256="b" * 64,
        model_sha256="c" * 64,
        raw_records=raw,
    ) == audited
    with pytest.raises(ValueError, match="ipa_audit_checkpoint_source_mismatch"):
        MODULE.load_checkpoint(
            path,
            source_manifest_sha256="d" * 64,
            model_sha256="c" * 64,
            raw_records=raw,
        )


def test_bounded_batch_end_limits_padding_but_keeps_outlier() -> None:
    records = [
        {"wav": {"duration_seconds": duration}}
        for duration in (1.0, 1.2, 1.5, 12.0, 1.0)
    ]

    assert MODULE.bounded_batch_end(
        records,
        0,
        max_batch_size=16,
        max_padded_audio_seconds=4.0,
    ) == 2
    assert MODULE.bounded_batch_end(
        records,
        3,
        max_batch_size=16,
        max_padded_audio_seconds=4.0,
    ) == 4
