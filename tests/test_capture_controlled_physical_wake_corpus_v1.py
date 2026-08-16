from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import wave

import numpy as np
import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "capture_controlled_physical_wake_corpus_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_physical_corpus", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _wav(path: Path, value: int, *, frames: int = 320) -> None:
    with wave.open(str(path), "wb") as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(16_000)
        sink.writeframes(np.full(frames, value, dtype="<i2").tobytes())


def test_source_selection_is_seeded_and_ignores_augmented_files(tmp_path: Path) -> None:
    gate = _module()
    for index in range(6):
        _wav(tmp_path / f"clip_{index:06d}.wav", index + 1)
        _wav(tmp_path / f"clip_{index:06d}_r0.wav", index + 1)

    first = gate.select_sources(tmp_path, 3, 17)
    second = gate.select_sources(tmp_path, 3, 17)

    assert first == second
    assert len(first) == 3
    assert all("_r" not in path.stem for path in first)


def test_all_wav_selection_deduplicates_audio_content(tmp_path: Path) -> None:
    gate = _module()
    _wav(tmp_path / "human-a.wav", 1)
    _wav(tmp_path / "human-a-copy.wav", 1)
    _wav(tmp_path / "human-b.wav", 2)

    selected = gate.select_sources(
        tmp_path,
        2,
        3,
        clean_clip_names_only=False,
    )

    assert len(selected) == 2
    assert len({gate.room._sha256(path) for path in selected}) == 2


def test_source_selection_excludes_unexpectedly_long_playback(tmp_path: Path) -> None:
    gate = _module()
    _wav(tmp_path / "short-a.wav", 1, frames=16_000)
    _wav(tmp_path / "short-b.wav", 2, frames=32_000)
    _wav(tmp_path / "long.wav", 3, frames=64_000)

    selected = gate.select_sources(
        tmp_path,
        2,
        3,
        clean_clip_names_only=False,
        maximum_source_seconds=2.5,
    )

    assert {path.name for path in selected} == {"short-a.wav", "short-b.wav"}


def test_alignment_recovers_known_delay() -> None:
    gate = _module()
    reference = np.sin(np.linspace(0.0, 20.0, 2_000)).astype(np.float32)
    captured = np.pad(reference * 0.4, (731, 400))

    aligned, correlation, delay = gate.align_known_playback(captured, reference)

    assert delay == 731
    assert correlation > 0.999
    assert aligned.shape == reference.shape


def test_capture_normalization_is_capped() -> None:
    gate = _module()
    audio = np.linspace(-0.01, 0.01, 2_000, dtype=np.float32)

    normalized, gain = gate.normalize_training_capture(audio)

    assert gain == 30.0
    assert np.max(np.abs(normalized)) < 0.31


def test_capture_quality_retries_without_lowering_floors(monkeypatch) -> None:
    gate = _module()
    played = np.sin(np.linspace(0.0, 30.0, 2_000)).astype(np.float32)
    playback = np.pad(played, (400, 300))
    attempts = [
        np.zeros_like(playback),
        np.pad(played * 0.4, (400, 300)),
    ]

    def fake_play_and_record(*args, **kwargs):
        return attempts.pop(0)

    monkeypatch.setattr(gate, "play_and_record", fake_play_and_record)

    aligned, correlation, snr_db, delay, capture_attempts = (
        gate.capture_validated_playback(
            object(),
            playback,
            played,
            sample_rate=16_000,
            input_device=1,
            output_device=2,
            pre_samples=400,
            minimum_correlation=0.10,
            minimum_snr_db=3.0,
            maximum_attempts=2,
            raw_capture_helper=None,
        )
    )

    assert capture_attempts == 2
    assert correlation > 0.99
    assert snr_db > 3.0
    assert delay == 400
    assert aligned.shape == played.shape


def test_split_stream_is_used_only_for_wdm_ks_duplex() -> None:
    gate = _module()

    class FakeSoundDevice:
        @staticmethod
        def query_devices(device, kind):
            return {"hostapi": device}

        @staticmethod
        def query_hostapis(device):
            return {"name": "Windows WDM-KS" if device in {13, 16} else "Windows WASAPI"}

    assert gate.requires_split_stream(FakeSoundDevice(), 13, 16)
    assert not gate.requires_split_stream(FakeSoundDevice(), 12, 10)
    assert not gate.requires_split_stream(FakeSoundDevice(), 13, 10)


def test_split_stream_uses_callback_api_and_preserves_length() -> None:
    gate = _module()

    class CallbackStop(Exception):
        pass

    class FakeStream:
        def __init__(self, *, callback, finished_callback, is_input: bool):
            self.callback = callback
            self.finished_callback = finished_callback
            self.is_input = is_input

        def start(self):
            try:
                while True:
                    block = np.ones((4, 1), dtype=np.float32)
                    self.callback(block, 4, None, None)
            except CallbackStop:
                self.finished_callback()

        def close(self):
            return None

    class FakeSoundDevice:
        @staticmethod
        def query_devices(device, kind):
            return {"hostapi": 1}

        @staticmethod
        def query_hostapis(device):
            return {"name": "Windows WDM-KS"}

        @staticmethod
        def InputStream(**kwargs):
            return FakeStream(
                callback=kwargs["callback"],
                finished_callback=kwargs["finished_callback"],
                is_input=True,
            )

        @staticmethod
        def OutputStream(**kwargs):
            return FakeStream(
                callback=kwargs["callback"],
                finished_callback=kwargs["finished_callback"],
                is_input=False,
            )

    FakeSoundDevice.CallbackStop = CallbackStop

    playback = np.linspace(-0.5, 0.5, 10, dtype=np.float32)
    captured = gate.play_and_record(
        FakeSoundDevice(),
        playback,
        sample_rate=16_000,
        input_device=13,
        output_device=16,
    )

    assert captured.shape == playback.shape
    assert np.all(captured == 1.0)


def test_progress_round_trip_and_duplicate_rejection(tmp_path: Path) -> None:
    gate = _module()
    progress = tmp_path / "progress.v1.jsonl"
    record = {
        "recordId": "positive/000000",
        "sourceSha256": "a" * 64,
        "output": "positive/clip_000000_r0.wav",
        "outputSha256": "b" * 64,
    }
    gate._append_progress(progress, record)
    assert gate._load_progress(progress) == {record["recordId"]: record}

    gate._append_progress(progress, record)
    with pytest.raises(ValueError, match="controlled_physical_progress_invalid"):
        gate._load_progress(progress)
