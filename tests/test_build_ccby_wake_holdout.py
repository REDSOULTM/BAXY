from __future__ import annotations

import importlib.util
from pathlib import Path
import wave

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_ccby_wake_holdout.py"
)
SPEC = importlib.util.spec_from_file_location("build_ccby_wake_holdout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _entry(*, partition: str, source_id: str, speaker_group: str, name: str) -> dict:
    return {
        "partition": partition,
        "label": "positive",
        "source_id": source_id,
        "speaker_group": speaker_group,
        "source_relative_path": f"sources/{source_id}.wav",
        "target_onset_seconds": 1.0,
        "output_name": name,
    }


def test_validate_entries_rejects_speaker_leak_across_blind_boundary() -> None:
    entries = [
        _entry(
            partition="development",
            source_id="source-a",
            speaker_group="same-speaker",
            name="a.wav",
        ),
        _entry(
            partition="blind",
            source_id="source-b",
            speaker_group="same-speaker",
            name="b.wav",
        ),
    ]

    with pytest.raises(ValueError, match="speaker_crosses_partitions:same-speaker"):
        MODULE.validate_entries(entries)


def test_inspect_wav_enforces_contract_and_measures_signal(tmp_path: Path) -> None:
    path = tmp_path / "clip.wav"
    samples = [1000, -1000] * 24_000
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(
            b"".join(value.to_bytes(2, "little", signed=True) for value in samples)
        )

    result = MODULE.inspect_wav(path, 3.0)

    assert result["frames"] == 48_000
    assert result["duration_seconds"] == 3.0
    assert result["peak"] == pytest.approx(1000 / 32768, abs=1e-9)
    assert result["rms"] == pytest.approx(1000 / 32768, abs=1e-9)


def test_validate_entries_rejects_duplicate_output_name() -> None:
    entries = [
        _entry(
            partition="development",
            source_id="source-a",
            speaker_group="speaker-a",
            name="same.wav",
        ),
        _entry(
            partition="development",
            source_id="source-b",
            speaker_group="speaker-b",
            name="same.wav",
        ),
    ]

    with pytest.raises(ValueError, match="duplicate_output_name:same.wav"):
        MODULE.validate_entries(entries)


def test_choose_clip_start_shifts_back_when_target_is_near_source_end() -> None:
    start = MODULE.choose_clip_start(
        target_onset_seconds=4.72,
        pre_seconds=1.0,
        duration_seconds=3.0,
        source_duration_seconds=5.496,
    )

    assert start == pytest.approx(2.496)
    assert start <= 4.72 <= start + 3.0
