from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np


def _physical_gate_module():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_wakeword_physical_room_gate.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_wake_physical_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delay_correlation_accepts_a_delayed_acoustic_copy() -> None:
    gate = _physical_gate_module()
    rng = np.random.default_rng(20260804)
    reference = rng.normal(0.0, 0.2, 2_048).astype(np.float32)
    captured = np.zeros(4_096, dtype=np.float32)
    captured[731 : 731 + reference.size] = reference * 0.37

    assert gate.normalized_delay_correlation(captured, reference) > 0.999


def test_delay_correlation_rejects_unrelated_audio() -> None:
    gate = _physical_gate_module()
    rng = np.random.default_rng(20260804)
    reference = rng.normal(0.0, 0.2, 4_096).astype(np.float32)
    captured = rng.normal(0.0, 0.2, 8_192).astype(np.float32)

    assert gate.normalized_delay_correlation(captured, reference) < 0.1


def test_corpus_hash_binds_order_name_and_bytes(tmp_path: Path) -> None:
    gate = _physical_gate_module()
    first = tmp_path / "a.wav"
    second = tmp_path / "b.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    forward = gate._corpus_sha256([first, second], tmp_path)
    repeated = gate._corpus_sha256([first, second], tmp_path)
    reverse = gate._corpus_sha256([second, first], tmp_path)
    second.write_bytes(b"changed")
    changed = gate._corpus_sha256([first, second], tmp_path)

    assert forward == repeated
    assert forward != reverse
    assert forward != changed


def test_score_recording_uses_the_detector_window_contract() -> None:
    gate = _physical_gate_module()

    class _Detector:
        window_samples = 48_000
        config = SimpleNamespace(debounce_seconds=2.0)

        def reset(self) -> None:
            self.samples = 0
            self.fired = False
            self.scored_last_frame = False
            self.last_prediction_seconds = None

        def accept(self, frame: np.ndarray, now: float):
            self.samples += len(frame)
            self.scored_last_frame = True
            self.last_prediction_seconds = 0.01
            if self.samples >= self.window_samples and not self.fired:
                self.fired = True
                return SimpleNamespace(timestamp=now)
            return None

    detector = _Detector()
    hits, first_hit, predictions, scores = gate._score_recording(
        detector,
        np.zeros(1_000, dtype=np.float32),
        10.0,
    )

    assert detector.samples == detector.window_samples
    assert hits == 1
    assert first_hit == 3.0
    assert predictions
    assert scores == []


def test_measure_group_reports_stable_invalid_reason_counts(tmp_path: Path) -> None:
    gate = _physical_gate_module()
    source = tmp_path / "source.wav"
    samples = (np.sin(np.linspace(0.0, 20.0, 16_000)) * 12_000).astype(np.int16)
    with wave.open(str(source), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(samples.tobytes())

    class _SoundDevice:
        @staticmethod
        def playrec(playback, **_kwargs):
            return np.asarray(playback, dtype=np.float32)

    class _Detector:
        window_samples = 16_000
        config = SimpleNamespace(debounce_seconds=2.0)

        def reset(self) -> None:
            self.scored_last_frame = False
            self.last_prediction_seconds = None
            self.last_score = None

        def accept(self, _frame: np.ndarray, now: float):
            self.scored_last_frame = True
            self.last_prediction_seconds = 0.01
            self.last_score = 0.42
            return None

    metrics, _ = gate._measure_group(
        paths=[source],
        detector=_Detector(),
        sounddevice=_SoundDevice(),
        input_device=0,
        output_device=1,
        hardware_rate=16_000,
        gain=0.2,
        pre_roll_seconds=0.5,
        post_roll_seconds=0.5,
        minimum_correlation=0.02,
        minimum_snr_db=3.0,
        timeline=0.0,
    )

    assert metrics["invalid_acoustic_paths"] == 0
    assert metrics["invalid_reason_counts"] == {}
    assert metrics["score_p50"] == 0.42
    assert metrics["score_maximum"] == 0.42
