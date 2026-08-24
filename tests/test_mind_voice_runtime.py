from __future__ import annotations

import hashlib
import json
import queue
import time
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.voice as voice_module
import baxy_mind.voice_output as voice_output_module
from baxy_mind.voice import (
    MIN_UTTERANCE_S,
    SAMPLE_RATE,
    VoiceEngine,
    WakePhraseMatcher,
    _compile_contextual_hotwords,
    _looks_like_echo,
    _lexical_wake_fallback_enabled,
    _streaming_stt_enabled,
    _wake_activity_onset_sample,
    _wake_turn_start_sample,
    resolve_streaming_stt_directory,
    resolve_stt_directory,
)
from baxy_mind.corrector import FuzzyCorrector
from baxy_mind.voice_aec import EchoCanceller
from baxy_mind.voice_output import (
    NeuralSpeechOutput,
    SapiSpeechOutput,
    _speech_markup,
    _tail_grace_seconds,
    _voice_rank,
)
from baxy_mind.wake_cascade import HyperspotterCascadeDetector
from baxy_mind.wakeword import (
    CALIBRATION_REPORT_FILENAME,
    DEFAULT_HOP_SAMPLES,
    WINDOW_SAMPLES,
    AcousticWakeDetector,
    WakeWordModelConfig,
    WakeWordDetection,
    WakeWordRuntimeError,
    inspect_wakeword_config,
    load_wakeword_config,
)
from baxy_mind.wake_verifier import WakeVerifierConfig, WakeVerifierDecision


class _FakeStream:
    def __init__(self, text: str) -> None:
        self.result = SimpleNamespace(text=text)

    def accept_waveform(self, _sample_rate: int, _audio: np.ndarray) -> None:
        return None


class _FakeRecognizer:
    def __init__(self, text: str) -> None:
        self.text = text

    def create_stream(self) -> _FakeStream:
        return _FakeStream(self.text)

    def decode_stream(self, _stream: _FakeStream) -> None:
        return None


class _FakeWakeVerifier:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted
        self.calls: list[tuple[int, str, float]] = []

    def verify(
        self,
        audio: np.ndarray,
        transcript: str,
        confidence: float,
        *,
        verification_start_sample: int = 0,
    ) -> WakeVerifierDecision:
        self.calls.append(
            (len(audio) - verification_start_sample, transcript, confidence)
        )
        return WakeVerifierDecision(
            self.accepted,
            "ctc_exact" if self.accepted else "rejected",
            2.0 if self.accepted else -1.0,
            True,
        )


def _stage1_config(model_hash: str = "1" * 64) -> WakeWordModelConfig:
    return WakeWordModelConfig(
        manifest_path=Path("wakeword.json"),
        model_path=Path("wakeword.onnx"),
        model_name="baxy",
        phrase="Baxy",
        threshold=0.035,
        hop_samples=2_560,
        debounce_seconds=2.0,
        model_sha256=model_hash,
        calibration={"approved": True},
    )


def _verifier_config(model_hash: str = "1" * 64) -> WakeVerifierConfig:
    return WakeVerifierConfig(
        manifest_path=Path("verifier.json"),
        graph_path=Path("verifier.onnx"),
        graph_data_path=Path("verifier.onnx.data"),
        vocabulary_path=Path("vocab.json"),
        graph_sha256="2" * 64,
        graph_data_sha256="3" * 64,
        vocabulary_sha256="4" * 64,
        stage1_model_sha256=model_hash,
        stage1_phrase="Baxy",
        stage1_hop_samples=2_560,
        stage1_debounce_seconds=2.0,
        stage1_pre_roll_seconds=5.0,
        primary_view_start_samples=64_000,
        activity_lookback_samples=2_560,
        activity_alignment_samples=320,
        activity_vad_threshold=0.1,
        minimum_samples=SAMPLE_RATE,
        maximum_samples=SAMPLE_RATE * 10,
        maximum_turn_samples=SAMPLE_RATE * 30,
        broad_threshold=0.0175,
        strong_threshold=0.035,
        decision_margin=0.5,
        anchor_margin=0.5,
        calibration={"approved": True},
    )


def test_attested_verifier_alone_can_lower_stage1_to_proposal_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector_configs: list[WakeWordModelConfig] = []
    verifier = object()
    monkeypatch.setattr(
        voice_module,
        "inspect_wakeword_config",
        lambda: (None, "wake_word_calibration_required"),
    )
    monkeypatch.setattr(
        voice_module,
        "inspect_wakeword_candidate_config",
        lambda: (_stage1_config(), None),
    )
    monkeypatch.setattr(
        voice_module,
        "inspect_wake_verifier_config",
        lambda: (_verifier_config(), None),
    )
    monkeypatch.setattr(
        voice_module,
        "AcousticWakeDetector",
        lambda config: detector_configs.append(config) or object(),
    )
    monkeypatch.setattr(voice_module, "OnnxWakeVerifier", lambda _config: verifier)
    engine = VoiceEngine.__new__(VoiceEngine)

    engine._load_acoustic_wake_detector()  # noqa: SLF001

    assert detector_configs[0].threshold == 0.0175
    assert engine._wake_verifier is verifier  # noqa: SLF001
    assert engine._wake_verifier_error is None  # noqa: SLF001


def test_mismatched_verifier_cannot_lower_direct_stage1_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector_configs: list[WakeWordModelConfig] = []
    monkeypatch.setattr(
        voice_module, "inspect_wakeword_config", lambda: (_stage1_config(), None)
    )
    monkeypatch.setattr(
        voice_module,
        "inspect_wakeword_candidate_config",
        lambda: (_stage1_config(), None),
    )
    monkeypatch.setattr(
        voice_module,
        "inspect_wake_verifier_config",
        lambda: (_verifier_config("9" * 64), None),
    )
    monkeypatch.setattr(
        voice_module,
        "AcousticWakeDetector",
        lambda config: detector_configs.append(config) or object(),
    )
    engine = VoiceEngine.__new__(VoiceEngine)

    engine._load_acoustic_wake_detector()  # noqa: SLF001

    assert detector_configs[0].threshold == 0.035
    assert engine._wake_verifier is None  # noqa: SLF001
    assert (  # noqa: SLF001
        engine._wake_verifier_error == "wake_verifier_stage1_contract_mismatch"
    )


def test_wake_turn_start_ignores_old_history_and_keeps_context() -> None:
    flags = [True] * 4 + [False] * 24 + [True] * 10 + [False] * 3

    start = _wake_turn_start_sample(flags, frame_samples=512)

    assert start == 20 * 512


def test_wake_activity_onset_uses_low_vad_threshold_and_ctc_alignment() -> None:
    probabilities = [0.0] * 138 + [0.042, 0.185, 0.12]

    start = _wake_activity_onset_sample(
        probabilities,
        threshold=0.1,
        frame_samples=512,
        alignment_samples=320,
        default_start_sample=64_000,
    )

    assert start == 71_040


class _ContextualFakeRecognizer:
    def create_stream(self, hotwords: str | None = None) -> _FakeStream:
        return _FakeStream("Spotify" if hotwords else "Open spati")

    def decode_stream(self, _stream: _FakeStream) -> None:
        return None


class _FakeOnlineStream:
    def __init__(self, text: str) -> None:
        self.result = SimpleNamespace(text=text)
        self.language = ""
        self.accepted = 0
        self.ready = True

    def set_option(self, name: str, value: str) -> None:
        if name == "language":
            self.language = value

    def accept_waveform(self, _sample_rate: int, audio: np.ndarray) -> None:
        self.accepted += int(audio.size)
        self.ready = True


class _FakeOnlineRecognizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.streams: list[_FakeOnlineStream] = []

    def create_stream(self) -> _FakeOnlineStream:
        stream = _FakeOnlineStream(self.text)
        self.streams.append(stream)
        return stream

    @staticmethod
    def is_ready(stream: _FakeOnlineStream) -> bool:
        return stream.ready

    @staticmethod
    def decode_stream(stream: _FakeOnlineStream) -> None:
        stream.ready = False

    @staticmethod
    def get_result_all(stream: _FakeOnlineStream) -> SimpleNamespace:
        return stream.result


class _FakeWakePredictor:
    def __init__(self, score: float = 0.91) -> None:
        self.score = score
        self.calls: list[np.ndarray] = []

    def predict(self, audio: np.ndarray) -> dict[str, float]:
        self.calls.append(audio.copy())
        return {"baxy": self.score}


class _FakeAcousticDetector:
    def __init__(self) -> None:
        self.frames = 0
        self.resets = 0

    def accept(self, _audio: np.ndarray) -> WakeWordDetection | None:
        self.frames += 1
        if self.frames == 1:
            return WakeWordDetection("baxy", "Baxy", 0.91, time.monotonic())
        return None

    def reset(self) -> None:
        self.resets += 1


class _FailingAcousticDetector(_FakeAcousticDetector):
    def accept(self, _audio: np.ndarray) -> WakeWordDetection | None:
        raise WakeWordRuntimeError("wake_word_runtime_predict_failed:RuntimeError")


class _PausingSpeechQueue(queue.Queue):
    def __init__(self) -> None:
        super().__init__(16)
        self.dequeued = threading.Event()
        self.resume = threading.Event()

    def get(self, block: bool = True, timeout: float | None = None):
        item = super().get(block=block, timeout=timeout)
        self.dequeued.set()
        self.resume.wait(2.0)
        return item


class _FakeSapiVoice:
    def __init__(self, *, block_wait: bool = False) -> None:
        self.nonempty_speaks: list[str] = []
        self.wait_entered = threading.Event()
        self.release_wait = threading.Event()
        self.block_wait = block_wait

    @staticmethod
    def GetVoices() -> list[object]:
        return []

    def Speak(self, text: str, _flags: int) -> None:
        if text:
            self.nonempty_speaks.append(text)

    def WaitUntilDone(self, _milliseconds: int) -> bool:
        self.wait_entered.set()
        if self.block_wait:
            self.release_wait.wait(2.0)
        return not self.block_wait


def _install_fake_sapi(monkeypatch, voice: _FakeSapiVoice) -> None:
    pythoncom = ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None
    pythoncom.CoUninitialize = lambda: None
    win32com = ModuleType("win32com")
    client = ModuleType("win32com.client")
    client.Dispatch = lambda _name: voice
    win32com.client = client
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)


class _SilentVad:
    @staticmethod
    def process(_audio: np.ndarray) -> float:
        return 0.0

    @staticmethod
    def reset() -> None:
        return None


class _FakeInputStream:
    def __init__(self, opened: threading.Event | None = None) -> None:
        self.device = 0
        self._opened = opened

    def __enter__(self):
        if self._opened is not None:
            self._opened.wait(2.0)
        return self

    @staticmethod
    def __exit__(_exc_type, _exc, _traceback) -> None:
        return None

    @staticmethod
    def read(samples: int) -> tuple[np.ndarray, bool]:
        time.sleep(0.005)
        return np.zeros((samples, 1), dtype=np.float32), False


def _prepare_voice_engine(monkeypatch, events: list[dict]) -> VoiceEngine:
    engine = VoiceEngine(lambda _text: None, events.append)
    engine._vad = _SilentVad()  # noqa: SLF001 - device lifecycle seam
    monkeypatch.setattr(engine, "load", lambda: None)
    monkeypatch.setattr(engine._loopback, "start", lambda: True)  # noqa: SLF001
    monkeypatch.setattr(engine._loopback, "stop", lambda: None)  # noqa: SLF001
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "latest",
        lambda samples: np.zeros(samples, dtype=np.int16),
    )
    monkeypatch.setattr(VoiceEngine, "probe", classmethod(lambda _cls: {}))
    return engine


def _install_sounddevice(monkeypatch, factory) -> None:
    sounddevice = ModuleType("sounddevice")
    sounddevice.InputStream = factory
    sounddevice.query_devices = lambda *_args, **_kwargs: {
        "name": "micrófono de prueba",
        "max_input_channels": 1,
    }
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)


def _engine(text: str, transcripts: list[str], events: list[dict]) -> VoiceEngine:
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _FakeRecognizer(text)  # noqa: SLF001 - seam del runtime
    return engine


def _write_stt_bundle(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for name in (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ):
        (path / name).write_bytes(b"test")
    return path


def _write_wake_manifest(path: Path, *, approved: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    model = path / "baxy.onnx"
    model.write_bytes(b"test-wake-model")
    model_sha256 = hashlib.sha256(model.read_bytes()).hexdigest()
    measured_at = "2026-07-23T00:00:00+00:00"
    report = {
        "schema": "baxy-wake-corpus-gate-v3",
        "measured_at": measured_at,
        "mode": "acoustic",
        "model": {
            "backend": "livekit-wakeword",
            "model": "baxy",
            "phrase": "Baxy",
            "sample_rate": SAMPLE_RATE,
            "window_samples": WINDOW_SAMPLES,
            "hop_samples": DEFAULT_HOP_SAMPLES,
            "threshold": 0.7,
            "debounce_seconds": 2.0,
            "model_sha256": model_sha256,
        },
        "false_reject_rate": 0.01,
        "far": {
            "method": "poisson_one_sided_upper_exact",
            "confidence": 0.95,
            "upper_confidence_per_hour": 0.09,
        },
        "corpus_sufficient": True,
        "promotion_criteria": {
            "false_reject_rate_lte": 0.05,
            "false_activations_per_hour_lte": 0.1,
            "far_confidence_gte": 0.95,
        },
        "promotable": True,
    }
    report_path = path / CALIBRATION_REPORT_FILENAME
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    calibration = (
        {
            "schema": "baxy-wake-calibration-v1",
            "approved": True,
            "gate_schema": "baxy-wake-corpus-gate-v3",
            "report": CALIBRATION_REPORT_FILENAME,
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "report_model_sha256": model_sha256,
            "measured_at": measured_at,
            "false_reject_rate": 0.01,
            "far_confidence": 0.95,
            "far_upper_confidence_per_hour": 0.09,
            "corpus_sufficient": True,
        }
        if approved
        else {"approved": False}
    )
    manifest = path / "baxy-wakeword-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-wakeword-v1",
                "model": model.name,
                "modelName": "baxy",
                "phrase": "Baxy",
                "sampleRate": SAMPLE_RATE,
                "windowSamples": WINDOW_SAMPLES,
                "hopSamples": DEFAULT_HOP_SAMPLES,
                "threshold": 0.7,
                "debounceSeconds": 2.0,
                "sha256": model_sha256,
                "calibration": calibration,
            }
        ),
        encoding="utf-8",
    )
    return manifest


@pytest.mark.parametrize(
    ("failure_stage", "expected_code"),
    [
        ("generate", "tts_generate_failed"),
        ("play", "tts_play_failed"),
    ],
)
def test_neural_tts_reports_the_async_failure_boundary(
    monkeypatch,
    tmp_path: Path,
    failure_stage: str,
    expected_code: str,
) -> None:
    class Engine:
        sample_rate = 22_050

        def __init__(self, _model: Path) -> None:
            pass

        @staticmethod
        def generate(_text: str) -> np.ndarray:
            if failure_stage == "generate":
                raise RuntimeError("synthetic generation failure")
            return np.ones(128, dtype=np.float32)

    sounddevice = ModuleType("sounddevice")

    def play(*_args: object, **_kwargs: object) -> None:
        if failure_stage == "play":
            raise RuntimeError("synthetic playback failure")

    sounddevice.play = play  # type: ignore[attr-defined]
    sounddevice.stop = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)
    monkeypatch.setattr(
        voice_output_module,
        "resolve_neural_tts_model",
        lambda: tmp_path / "voice.onnx",
    )
    monkeypatch.setattr(voice_output_module, "_PiperOnnxEngine", Engine)
    errors: list[str] = []
    output = NeuralSpeechOutput(on_error=errors.append)
    try:
        assert output.start(timeout=1.0)
        assert output.speak("frase sintética")
        deadline = time.monotonic() + 1.0
        while not errors and time.monotonic() < deadline:
            time.sleep(0.01)
        assert errors == [expected_code]
        assert output.last_error == f"{expected_code}:RuntimeError"
    finally:
        assert output.stop(timeout=1.0)


def test_tts_cancel_after_dequeue_never_speaks_the_stale_item(monkeypatch) -> None:
    voice = _FakeSapiVoice()
    _install_fake_sapi(monkeypatch, voice)
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "0")
    output = SapiSpeechOutput()
    paused_queue = _PausingSpeechQueue()
    output._queue = paused_queue  # noqa: SLF001 - deterministic race seam

    assert output.speak("mensaje obsoleto")
    assert paused_queue.dequeued.wait(1.0)
    output.cancel()
    paused_queue.resume.set()
    time.sleep(0.05)

    assert output.stop()
    assert voice.nonempty_speaks == []


def test_tts_stop_keeps_worker_ownership_until_the_thread_finishes(monkeypatch) -> None:
    voice = _FakeSapiVoice(block_wait=True)
    _install_fake_sapi(monkeypatch, voice)
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "0")
    output = SapiSpeechOutput()

    assert output.speak("mensaje en curso")
    assert voice.wait_entered.wait(1.0)
    worker = output._worker  # noqa: SLF001 - ownership contract
    assert worker is not None

    assert not output.stop(timeout=0.05)
    assert output._worker is worker  # noqa: SLF001
    assert not output.start(timeout=0.05)

    voice.release_wait.set()
    worker.join(1.0)
    assert not worker.is_alive()
    assert output.stop()


def test_tts_start_and_stop_never_raise_a_small_wait_to_a_floor() -> None:
    class WaitProbe:
        def __init__(self) -> None:
            self.calls: list[float] = []

        def wait(self, timeout: float) -> bool:
            self.calls.append(timeout)
            return False

    class LiveWorker:
        def __init__(self) -> None:
            self.join_calls: list[float] = []

        @staticmethod
        def is_alive() -> bool:
            return True

        def join(self, timeout: float) -> None:
            self.join_calls.append(timeout)

    output = SapiSpeechOutput()
    ready = WaitProbe()
    worker = LiveWorker()
    output._ready = ready  # noqa: SLF001
    output._worker = worker  # noqa: SLF001
    output._available = True  # noqa: SLF001

    assert output.start(timeout=0.04)
    assert output.start(timeout=0.0)
    assert not output.stop(timeout=0.04)

    assert ready.calls == [0.04, 0.0]
    assert worker.join_calls == [0.04]


def test_tts_tail_grace_caps_the_last_wait_by_the_remaining_budget(
    monkeypatch,
) -> None:
    class Clock:
        now = 0.0

    class AdvancingCancel:
        def __init__(self, clock: Clock) -> None:
            self._event = threading.Event()
            self._clock = clock
            self.wait_calls: list[float] = []
            self.two_waits = threading.Event()

        def clear(self) -> None:
            self._event.clear()

        def set(self) -> None:
            self._event.set()

        def is_set(self) -> bool:
            return self._event.is_set()

        def wait(self, timeout: float) -> bool:
            self.wait_calls.append(timeout)
            self._clock.now += timeout
            if len(self.wait_calls) >= 2:
                self.two_waits.set()
            return self._event.is_set()

    voice = _FakeSapiVoice()
    _install_fake_sapi(monkeypatch, voice)
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "0.04")
    clock = Clock()
    output = SapiSpeechOutput()
    cancel = AdvancingCancel(clock)
    output._cancel = cancel  # noqa: SLF001
    monkeypatch.setattr(
        "baxy_mind.voice_output.time.monotonic",
        lambda: clock.now,
    )

    assert output.speak("mensaje")
    assert cancel.two_waits.wait(1.0)
    assert output.stop()

    assert cancel.wait_calls[0] == 0.025
    assert 0.0 < cancel.wait_calls[-1] < 0.025
    assert all(timeout <= 0.025 for timeout in cancel.wait_calls)


def test_voice_start_ack_waits_until_the_microphone_is_open(monkeypatch) -> None:
    events: list[dict] = []
    opened = threading.Event()
    engine = _prepare_voice_engine(monkeypatch, events)
    _install_sounddevice(monkeypatch, lambda **_kwargs: _FakeInputStream(opened))
    result: list[bool] = []
    starter = threading.Thread(target=lambda: result.append(engine.start("direct")))

    starter.start()
    time.sleep(0.05)
    assert starter.is_alive()
    assert not any(
        event.get("event") == "state" and event.get("listening") is True
        for event in events
    )

    opened.set()
    starter.join(1.0)
    assert result == [True]
    assert engine.status()["listening"] is True
    assert engine.stop()


def test_capture_failure_turns_voice_off_and_allows_a_clean_restart(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)

    def fail_input(**_kwargs):
        raise OSError("device disappeared")

    _install_sounddevice(monkeypatch, fail_input)
    assert not engine.start("direct")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and engine._capture_worker is not None:  # noqa: SLF001
        time.sleep(0.01)

    assert engine.mode == "off"
    assert engine.status()["listening"] is False
    assert engine.last_error == "capture_failed:OSError"

    _install_sounddevice(monkeypatch, lambda **_kwargs: _FakeInputStream())
    assert engine.start("direct")
    assert engine.status()["listening"] is True
    assert engine.stop()


def test_voice_stop_has_one_deadline_and_retains_a_live_worker(monkeypatch) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    release = threading.Event()
    worker = threading.Thread(target=lambda: release.wait(2.0), daemon=True)
    worker.start()
    engine._capture_worker = worker  # noqa: SLF001 - ownership contract
    engine._mode = "direct"  # noqa: SLF001
    engine._lifecycle_state = "ready"  # noqa: SLF001

    started_at = time.monotonic()
    assert not engine.stop(timeout=0.1)
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.4
    assert engine._capture_worker is worker  # noqa: SLF001
    assert not engine.start("direct")

    release.set()
    worker.join(1.0)
    assert engine.stop(timeout=0.1)
    assert engine._capture_worker is None  # noqa: SLF001
    assert engine._lifecycle_state == "off"  # noqa: SLF001
    starts: list[str] = []
    monkeypatch.setattr(
        engine,
        "_start",
        lambda mode: not starts.append(mode),
    )
    assert engine.start("direct")
    assert starts == ["direct"]


def test_voice_stop_budget_includes_a_contended_lifecycle_lock(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    lifecycle_held = threading.Event()
    release_lifecycle = threading.Event()

    def hold_lifecycle() -> None:
        with engine._lifecycle_lock:  # noqa: SLF001
            lifecycle_held.set()
            release_lifecycle.wait(2.0)

    holder = threading.Thread(
        target=hold_lifecycle,
        name="voice-test-lifecycle-holder",
        daemon=True,
    )
    holder.start()
    assert lifecycle_held.wait(1.0)

    started = time.perf_counter()
    try:
        assert not engine.stop(timeout=0.04)
        elapsed = time.perf_counter() - started
        job = engine._cleanup_job  # noqa: SLF001
        assert elapsed < 0.2
        assert job is not None
        assert job.thread is not None
        assert job.thread.daemon
        nonfinite_started = time.perf_counter()
        assert not engine.stop(timeout=float("inf"))
        assert not engine.stop(timeout=float("nan"))
        assert time.perf_counter() - nonfinite_started < 0.2
        assert engine._cleanup_job is job  # noqa: SLF001
    finally:
        release_lifecycle.set()
        holder.join(1.0)

    assert engine.stop(timeout=1.0)


def test_voice_stop_never_rounds_cleanup_join_above_its_total_budget(
    monkeypatch,
) -> None:
    class CleanupThread:
        def __init__(self) -> None:
            self.join_calls: list[float] = []

        def join(self, timeout: float) -> None:
            self.join_calls.append(timeout)

        @staticmethod
        def is_alive() -> bool:
            return True

    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    cleanup_thread = CleanupThread()
    job = SimpleNamespace(
        thread=cleanup_thread,
        done=threading.Event(),
        launch_done=threading.Event(),
        success=False,
        timeout_observed=False,
    )
    job.launch_done.set()
    clock = 133_604.703
    monkeypatch.setattr(engine, "_request_cleanup", lambda **_kwargs: job)
    monkeypatch.setattr(
        "baxy_mind.voice.time.monotonic",
        lambda: clock,
    )

    assert not engine.stop(timeout=0.04)

    assert len(cleanup_thread.join_calls) == 1
    assert 0.0 <= cleanup_thread.join_calls[0] <= 0.04


def test_voice_cleanup_launch_does_not_hold_the_publication_lock(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    launch_entered = threading.Event()
    release_launch = threading.Event()
    original_start = threading.Thread.start

    def delayed_start(thread: threading.Thread) -> None:
        if thread.name.startswith("baxy-voice-cleanup-"):
            launch_entered.set()
            release_launch.wait(2.0)
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", delayed_start)
    first_result: list[bool] = []
    first_caller = threading.Thread(
        target=lambda: first_result.append(engine.stop(timeout=1.0)),
        name="voice-test-stop-caller",
        daemon=True,
    )
    first_caller.start()
    assert launch_entered.wait(1.0)

    started = time.perf_counter()
    try:
        assert not engine.stop(timeout=0.02)
        assert time.perf_counter() - started < 0.2
    finally:
        release_launch.set()

    first_caller.join(1.0)
    assert first_result == [True]


def test_voice_cleanup_launch_failure_is_explicit_and_retryable(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    original_start = threading.Thread.start

    def fail_cleanup_start(thread: threading.Thread) -> None:
        if thread.name.startswith("baxy-voice-cleanup-"):
            raise RuntimeError("native thread launch failed")
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_cleanup_start)

    assert not engine.stop(timeout=0.1)
    failed_job = engine._cleanup_job  # noqa: SLF001
    assert failed_job is not None
    assert failed_job.launch_done.is_set()
    assert failed_job.done.is_set()
    assert not failed_job.success
    assert engine.last_error == "voice_cleanup_start_failed"
    assert engine._lifecycle_state == "failed"  # noqa: SLF001
    assert not engine.start("direct")

    monkeypatch.setattr(threading.Thread, "start", original_start)
    assert engine.stop(timeout=1.0)
    assert engine._cleanup_job is not failed_job  # noqa: SLF001
    assert engine._lifecycle_state == "off"  # noqa: SLF001


def test_voice_stop_reuses_one_cleanup_owner_and_gates_start(monkeypatch) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    loopback_entered = threading.Event()
    release_loopback = threading.Event()
    calls = {"cancel": 0, "ducker": 0, "loopback": 0}

    def cancel() -> None:
        calls["cancel"] += 1

    def restore() -> bool:
        calls["ducker"] += 1
        return True

    def stop_loopback() -> bool:
        calls["loopback"] += 1
        loopback_entered.set()
        release_loopback.wait(2.0)
        return True

    monkeypatch.setattr(engine, "cancel_speech", cancel)
    monkeypatch.setattr(engine._ducker, "restore", restore)  # noqa: SLF001
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        stop_loopback,
    )

    try:
        started = time.perf_counter()
        assert not engine.stop(timeout=0.02)
        elapsed = time.perf_counter() - started
        assert loopback_entered.wait(1.0)
        job = engine._cleanup_job  # noqa: SLF001
        assert job is not None
        assert job.thread is not None
        assert job.thread.daemon
        assert elapsed < 0.2
        assert not engine.stop(timeout=0.0)
        assert engine._cleanup_job is job  # noqa: SLF001
        assert not engine.start("direct")
        assert engine.last_error == "voice_session_still_stopping"
        assert calls == {"cancel": 1, "ducker": 1, "loopback": 1}
    finally:
        release_loopback.set()

    assert engine.stop(timeout=1.0)
    assert engine._lifecycle_state == "off"  # noqa: SLF001
    assert calls == {"cancel": 1, "ducker": 1, "loopback": 1}


def test_voice_cleanup_restores_ducking_before_stopping_loopback(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    ducker_entered = threading.Event()
    release_ducker = threading.Event()
    order: list[str] = []

    monkeypatch.setattr(
        engine,
        "cancel_speech",
        lambda: order.append("cancel"),
    )

    def restore() -> bool:
        order.append("ducker-enter")
        ducker_entered.set()
        release_ducker.wait(2.0)
        order.append("ducker-exit")
        return True

    def stop_loopback() -> bool:
        order.append("loopback")
        return True

    monkeypatch.setattr(engine._ducker, "restore", restore)  # noqa: SLF001
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        stop_loopback,
    )

    started = time.perf_counter()
    try:
        assert not engine.stop(timeout=0.02)
        elapsed = time.perf_counter() - started
        assert ducker_entered.wait(1.0)
        assert elapsed < 0.2
        assert "loopback" not in order
    finally:
        release_ducker.set()

    assert engine.stop(timeout=1.0)
    assert order == [
        "cancel",
        "ducker-enter",
        "ducker-exit",
        "loopback",
    ]


def test_voice_cleanup_finishes_physical_effects_before_observer_backpressure(
    monkeypatch,
) -> None:
    observer_entered = threading.Event()
    release_observer = threading.Event()
    physical_effects: list[str] = []

    def observe(event: dict) -> None:
        if event.get("event") == "state":
            observer_entered.set()
            release_observer.wait(2.0)

    engine = VoiceEngine(lambda _text: None, observe)
    engine._vad = _SilentVad()  # noqa: SLF001 - device lifecycle seam
    monkeypatch.setattr(engine, "load", lambda: None)
    monkeypatch.setattr(
        engine,
        "cancel_speech",
        lambda: physical_effects.append("cancel"),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not physical_effects.append("ducker"),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        lambda: not physical_effects.append("loopback"),
    )

    try:
        assert engine.stop(timeout=0.1)
        assert observer_entered.wait(1.0)
        job = engine._cleanup_job  # noqa: SLF001
        assert job is not None
        assert job.done.is_set()
        assert job.thread is not None
        assert job.thread.is_alive()
        assert engine._stop_event.is_set()  # noqa: SLF001
        assert physical_effects == ["cancel", "ducker", "loopback"]
    finally:
        release_observer.set()

    assert job.thread is not None
    job.thread.join(1.0)


def test_late_voice_shutdown_stops_output_before_a_stuck_mic_worker(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    release_worker = threading.Event()
    worker = threading.Thread(
        target=lambda: release_worker.wait(2.0),
        name="voice-test-stuck-capture",
        daemon=True,
    )
    worker.start()
    engine._capture_worker = worker  # noqa: SLF001 - ownership contract
    engine._mode = "direct"  # noqa: SLF001
    engine._lifecycle_state = "ready"  # noqa: SLF001
    loopback_stopped = threading.Event()
    output_stopped = threading.Event()
    output_stop_calls = 0

    monkeypatch.setattr(
        engine._loopback,  # noqa: SLF001
        "stop",
        lambda: not loopback_stopped.set(),
    )

    def stop_output() -> bool:
        nonlocal output_stop_calls
        output_stop_calls += 1
        output_stopped.set()
        return True

    monkeypatch.setattr(engine._output, "stop", stop_output)  # noqa: SLF001

    try:
        assert not engine.stop(timeout=0.02)
        assert loopback_stopped.wait(1.0)
        job = engine._cleanup_job  # noqa: SLF001
        assert job is not None
        assert not engine._stop(timeout=0.1, shutdown=True)  # noqa: SLF001
        assert output_stopped.wait(1.0)
        assert worker.is_alive()
        assert output_stop_calls == 1
        assert engine._cleanup_job is job  # noqa: SLF001
    finally:
        release_worker.set()

    worker.join(1.0)
    assert engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
    assert engine._cleanup_job is job  # noqa: SLF001
    assert output_stop_calls == 1


def test_concurrent_stop_shutdown_and_failure_share_one_cleanup_owner(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    loopback_entered = threading.Event()
    release_loopback = threading.Event()
    calls = {"cancel": 0, "ducker": 0, "loopback": 0, "output": 0}

    monkeypatch.setattr(
        engine,
        "cancel_speech",
        lambda: calls.__setitem__("cancel", calls["cancel"] + 1),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not calls.__setitem__("ducker", calls["ducker"] + 1),
    )

    def stop_loopback() -> bool:
        calls["loopback"] += 1
        loopback_entered.set()
        release_loopback.wait(2.0)
        return True

    def stop_output() -> bool:
        calls["output"] += 1
        return True

    monkeypatch.setattr(engine._loopback, "stop", stop_loopback)  # noqa: SLF001
    monkeypatch.setattr(engine._output, "stop", stop_output)  # noqa: SLF001

    assert not engine.stop(timeout=0.02)
    assert loopback_entered.wait(1.0)
    job = engine._cleanup_job  # noqa: SLF001
    assert job is not None
    shutdown_result: list[bool] = []
    shutdown_caller = threading.Thread(
        target=lambda: shutdown_result.append(
            engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
        ),
        daemon=True,
    )
    shutdown_caller.start()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not job.shutdown_requested:
        time.sleep(0.001)

    failure_job = engine._request_cleanup(expected_session=17)  # noqa: SLF001
    assert failure_job is job
    assert engine._cleanup_job is job  # noqa: SLF001
    assert engine._cleanup_sequence == 1  # noqa: SLF001
    assert not engine.stop(timeout=0.0)
    assert calls == {"cancel": 1, "ducker": 1, "loopback": 1, "output": 0}

    release_loopback.set()
    shutdown_caller.join(1.0)
    assert shutdown_result == [True]
    assert calls == {"cancel": 1, "ducker": 1, "loopback": 1, "output": 1}
    assert engine._cleanup_job is job  # noqa: SLF001


def test_voice_cleanup_survives_a_signal_error_without_losing_ownership(
    monkeypatch,
) -> None:
    class RaisingStopEvent:
        @staticmethod
        def set() -> None:
            raise RuntimeError("signal failed")

    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    engine._stop_event = RaisingStopEvent()  # noqa: SLF001
    calls = {"cancel": 0, "ducker": 0, "loopback": 0}
    monkeypatch.setattr(
        engine,
        "cancel_speech",
        lambda: calls.__setitem__("cancel", calls["cancel"] + 1),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not calls.__setitem__("ducker", calls["ducker"] + 1),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        lambda: not calls.__setitem__("loopback", calls["loopback"] + 1),
    )

    assert not engine.stop(timeout=0.2)
    job = engine._cleanup_job  # noqa: SLF001
    assert job is not None
    assert job.done.wait(1.0)
    assert calls == {"cancel": 1, "ducker": 1, "loopback": 1}
    assert engine._lifecycle_state == "failed"  # noqa: SLF001
    assert not engine.start("direct")


def test_stale_voice_cleanup_never_touches_the_current_session(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    engine._session_epoch = 7  # noqa: SLF001
    engine._mode = "direct"  # noqa: SLF001
    engine._lifecycle_state = "ready"  # noqa: SLF001
    calls: list[str] = []
    monkeypatch.setattr(engine, "cancel_speech", lambda: calls.append("cancel"))
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not calls.append("ducker"),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        lambda: not calls.append("loopback"),
    )

    job = engine._request_cleanup(expected_session=6)  # noqa: SLF001
    assert job.thread is not None
    job.thread.join(1.0)

    assert job.done.is_set()
    assert job.success
    assert not job.applied
    assert calls == []
    assert engine._session_epoch == 7  # noqa: SLF001
    assert engine._lifecycle_state == "ready"  # noqa: SLF001


def test_current_failure_after_completed_stale_cleanup_gets_a_new_owner(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    engine._session_epoch = 12  # noqa: SLF001
    calls: list[str] = []
    monkeypatch.setattr(engine, "cancel_speech", lambda: calls.append("cancel"))
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not calls.append("ducker"),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        lambda: not calls.append("loopback"),
    )

    stale_job = engine._request_cleanup(expected_session=11)  # noqa: SLF001
    assert stale_job.done.wait(1.0)
    assert not stale_job.applied

    current_job = engine._request_cleanup(expected_session=12)  # noqa: SLF001
    assert current_job is not stale_job
    assert current_job.done.wait(1.0)
    assert current_job.applied
    assert current_job.success
    assert calls == ["cancel", "ducker", "loopback"]


def test_new_failure_escalates_an_active_stale_cleanup_to_current_session(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    engine._session_epoch = 8  # noqa: SLF001
    engine._mode = "direct"  # noqa: SLF001
    engine._lifecycle_state = "ready"  # noqa: SLF001
    stale_pass_finished = threading.Event()
    release_stale_pass = threading.Event()
    calls: list[str] = []
    monkeypatch.setattr(engine, "cancel_speech", lambda: calls.append("cancel"))
    monkeypatch.setattr(  # noqa: SLF001
        engine._ducker,
        "restore",
        lambda: not calls.append("ducker"),
    )
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "stop",
        lambda: not calls.append("loopback"),
    )
    original_finish_cleanup = engine._finish_cleanup  # noqa: SLF001
    finish_calls = 0

    def pause_first_finish(*args, **kwargs) -> bool:
        nonlocal finish_calls
        finish_calls += 1
        if finish_calls == 1:
            stale_pass_finished.set()
            release_stale_pass.wait(2.0)
        return original_finish_cleanup(*args, **kwargs)

    monkeypatch.setattr(engine, "_finish_cleanup", pause_first_finish)
    job = engine._request_cleanup(expected_session=7)  # noqa: SLF001
    assert stale_pass_finished.wait(1.0)
    try:
        current_failure_job = engine._request_cleanup(  # noqa: SLF001
            expected_session=8
        )
        assert current_failure_job is job
        assert job.expected_session is None
        assert job.request_version == 1
    finally:
        release_stale_pass.set()

    assert job.done.wait(1.0)
    assert finish_calls == 2
    assert job.applied
    assert job.success
    assert calls == ["cancel", "ducker", "loopback"]
    assert engine._session_epoch == 9  # noqa: SLF001
    assert engine._lifecycle_state == "off"  # noqa: SLF001


def test_voice_shutdown_is_terminal_and_stops_output_once(monkeypatch) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    output_stops = 0
    output_speaks = 0

    def stop_output() -> bool:
        nonlocal output_stops
        output_stops += 1
        return True

    def speak_output(_text: str) -> bool:
        nonlocal output_speaks
        output_speaks += 1
        return True

    monkeypatch.setattr(engine._output, "stop", stop_output)  # noqa: SLF001
    monkeypatch.setattr(engine._output, "speak", speak_output)  # noqa: SLF001

    engine.shutdown()
    engine.shutdown()

    assert output_stops == 1
    assert not engine.start("direct")
    assert not engine.speak("mensaje tardÃ­o")
    assert output_speaks == 0


def test_voice_shutdown_waits_for_an_admitted_speak_before_output_stop(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    assert engine.stop(timeout=1.0)
    completed_job = engine._cleanup_job  # noqa: SLF001
    assert completed_job is not None
    speak_entered = threading.Event()
    release_speak = threading.Event()
    speak_finished = threading.Event()
    output_stops = 0
    output_speaks = 0

    def speak_output(_text: str) -> bool:
        nonlocal output_speaks
        output_speaks += 1
        speak_entered.set()
        release_speak.wait(2.0)
        speak_finished.set()
        return True

    def stop_output() -> bool:
        nonlocal output_stops
        assert speak_finished.is_set()
        output_stops += 1
        return True

    monkeypatch.setattr(engine._output, "speak", speak_output)  # noqa: SLF001
    monkeypatch.setattr(engine._output, "stop", stop_output)  # noqa: SLF001
    result: list[bool] = []
    speaker = threading.Thread(
        target=lambda: result.append(engine.speak("mensaje")),
        daemon=True,
    )
    speaker.start()
    assert speak_entered.wait(1.0)

    started = time.perf_counter()
    try:
        assert not engine._stop(timeout=0.02, shutdown=True)  # noqa: SLF001
        elapsed = time.perf_counter() - started
        job = engine._cleanup_job  # noqa: SLF001
        assert job is not None
        assert job is not completed_job
        assert elapsed < 0.2
        assert output_stops == 0
    finally:
        release_speak.set()

    speaker.join(1.0)
    assert result == [True]
    assert engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
    assert engine._cleanup_job is job  # noqa: SLF001
    assert output_stops == 1
    assert output_speaks == 1
    assert not engine.start("direct")
    assert not engine.speak("mensaje tardÃ­o")
    assert output_speaks == 1


def test_voice_stop_waits_for_admitted_speech_before_cancel_and_reuses_owner(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    assert engine.stop(timeout=1.0)
    completed_job = engine._cleanup_job  # noqa: SLF001
    assert completed_job is not None
    speak_entered = threading.Event()
    release_speak = threading.Event()
    speak_finished = threading.Event()
    output_speaks = 0
    cancel_calls = 0

    def speak_output(_text: str) -> bool:
        nonlocal output_speaks
        output_speaks += 1
        speak_entered.set()
        release_speak.wait(2.0)
        speak_finished.set()
        return True

    def cancel_speech() -> None:
        nonlocal cancel_calls
        assert speak_finished.is_set()
        cancel_calls += 1

    monkeypatch.setattr(engine._output, "speak", speak_output)  # noqa: SLF001
    monkeypatch.setattr(engine, "cancel_speech", cancel_speech)
    result: list[bool] = []
    speaker = threading.Thread(
        target=lambda: result.append(engine.speak("mensaje")),
        daemon=True,
    )
    speaker.start()
    assert speak_entered.wait(1.0)

    started = time.perf_counter()
    try:
        assert not engine.stop(timeout=0.02)
        elapsed = time.perf_counter() - started
        job = engine._cleanup_job  # noqa: SLF001
        assert job is not None
        assert job is not completed_job
        assert elapsed < 0.2
        assert cancel_calls == 0
        assert not engine.stop(timeout=0.0)
        assert engine._cleanup_job is job  # noqa: SLF001
        assert not engine.speak("durante cleanup")
        assert output_speaks == 1
        assert events[-1]["code"] == "voice_session_still_stopping"
    finally:
        release_speak.set()

    speaker.join(1.0)
    assert result == [True]
    assert engine.stop(timeout=1.0)
    assert engine._cleanup_job is job  # noqa: SLF001
    assert cancel_calls == 1

    monkeypatch.setattr(engine._output, "speak", lambda _text: True)  # noqa: SLF001
    assert engine.speak("despuÃ©s del stop") is True


def test_voice_completed_stop_is_invalidated_only_by_accepted_speech(
    monkeypatch,
) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    monkeypatch.setattr(engine, "cancel_speech", lambda: None)
    monkeypatch.setattr(engine._ducker, "restore", lambda: True)  # noqa: SLF001
    monkeypatch.setattr(engine._loopback, "stop", lambda: True)  # noqa: SLF001

    assert engine.stop(timeout=1.0)
    first_job = engine._cleanup_job  # noqa: SLF001
    assert first_job is not None

    monkeypatch.setattr(engine._output, "speak", lambda _text: True)  # noqa: SLF001
    assert engine.speak("aceptado") is True
    assert engine.stop(timeout=1.0)
    second_job = engine._cleanup_job  # noqa: SLF001
    assert second_job is not None
    assert second_job is not first_job

    monkeypatch.setattr(engine._output, "speak", lambda _text: False)  # noqa: SLF001
    assert engine.speak("rechazado") is False
    assert engine.stop(timeout=1.0)
    assert engine._cleanup_job is second_job  # noqa: SLF001


def test_failed_output_stop_is_not_marked_stopped_or_reused(monkeypatch) -> None:
    events: list[dict] = []
    engine = _prepare_voice_engine(monkeypatch, events)
    output_results = iter((False, True))
    output_stops = 0

    def stop_output() -> bool:
        nonlocal output_stops
        output_stops += 1
        return next(output_results)

    monkeypatch.setattr(engine._output, "stop", stop_output)  # noqa: SLF001

    assert not engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
    failed_job = engine._cleanup_job  # noqa: SLF001
    assert failed_job is not None
    assert failed_job.output_stop_attempted
    assert not failed_job.output_stopped
    assert not failed_job.success

    assert engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
    recovered_job = engine._cleanup_job  # noqa: SLF001
    assert recovered_job is not None
    assert recovered_job is not failed_job
    assert recovered_job.output_stopped
    assert output_stops == 2
    assert engine._stop(timeout=1.0, shutdown=True)  # noqa: SLF001
    assert engine._cleanup_job is recovered_job  # noqa: SLF001
    assert output_stops == 2


def test_wake_matcher_requires_a_leading_closed_alias() -> None:
    matcher = WakePhraseMatcher()

    assert matcher.strip("Baxy, abre Spotify") == (True, "abre Spotify")
    assert matcher.strip("oye baxi dime la hora") == (True, "dime la hora")
    assert matcher.strip("abre Baxy y después Spotify") == (
        False,
        "abre Baxy y después Spotify",
    )
    assert matcher.strip("bastante fácil") == (False, "bastante fácil")
    assert matcher.strip("Vaxi, abre Spotify") == (False, "Vaxi, abre Spotify")


def test_extra_wake_alias_requires_explicit_calibration(monkeypatch) -> None:
    monkeypatch.setenv("BAXY_VOICE_WAKE_ALIASES", "baxy,baxi,vaxi")
    assert WakePhraseMatcher().strip("Vaxi, abre Spotify") == (True, "abre Spotify")


def test_streaming_partial_is_non_authoritative() -> None:
    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append)
    engine._mode = "wake"  # noqa: SLF001
    engine._streaming_recognizer = _FakeOnlineRecognizer("Baxy abre Spotify")  # noqa: SLF001

    stream = engine._create_streaming_stream()  # noqa: SLF001
    assert stream is not None
    assert (
        engine._streaming_accept(stream, np.zeros(512, dtype=np.float32))
        == "Baxy abre Spotify"
    )  # noqa: SLF001

    assert transcripts == []
    assert engine._armed_until == 0.0  # noqa: SLF001


def test_streaming_worker_emits_partial_without_wake_detection() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._mode = "wake"  # noqa: SLF001
    engine._streaming_recognizer = _FakeOnlineRecognizer("Baxy abre Spotify")  # noqa: SLF001
    worker = threading.Thread(target=engine._streaming_loop, daemon=True)  # noqa: SLF001
    engine._streaming_worker = worker  # noqa: SLF001
    worker.start()
    started = time.monotonic()

    assert engine._enqueue_streaming(("start", 1, (), started))  # noqa: SLF001
    assert engine._enqueue_streaming(("audio", 1, np.zeros(512, dtype=np.float32)))  # noqa: SLF001
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not any(
        event["event"] == "partial" for event in events
    ):
        time.sleep(0.01)
    engine.stop()

    assert any(event["event"] == "partial" for event in events)
    assert not any(event["event"] == "wake_candidate" for event in events)
    assert transcripts == []
    assert engine._armed_until == 0.0  # noqa: SLF001


def test_acoustic_detector_uses_rolling_audio_and_debounce(tmp_path) -> None:
    config = load_wakeword_config(_write_wake_manifest(tmp_path))
    predictor = _FakeWakePredictor()
    detector = AcousticWakeDetector(config, predictor=predictor)

    hit = detector.accept(np.zeros(WINDOW_SAMPLES, dtype=np.float32), now=10.0)

    assert hit is not None
    assert hit.model_name == "baxy"
    assert hit.confidence == 0.91
    assert detector.last_score == 0.91
    assert len(predictor.calls) == 1
    assert predictor.calls[0].shape == (WINDOW_SAMPLES,)
    assert (
        detector.accept(np.zeros(DEFAULT_HOP_SAMPLES, dtype=np.float32), now=10.5)
        is None
    )


def test_acoustic_detector_reset_clears_debounce_state(tmp_path) -> None:
    config = load_wakeword_config(_write_wake_manifest(tmp_path))
    predictor = _FakeWakePredictor()
    detector = AcousticWakeDetector(config, predictor=predictor)

    assert (
        detector.accept(np.zeros(WINDOW_SAMPLES, dtype=np.float32), now=10.0)
        is not None
    )
    detector.reset()
    assert detector.last_score is None

    assert (
        detector.accept(np.zeros(WINDOW_SAMPLES, dtype=np.float32), now=10.1)
        is not None
    )


def test_acoustic_detector_fails_closed_for_nonfinite_score(tmp_path) -> None:
    config = load_wakeword_config(_write_wake_manifest(tmp_path))
    detector = AcousticWakeDetector(config, predictor=_FakeWakePredictor(float("nan")))

    try:
        detector.accept(np.zeros(WINDOW_SAMPLES, dtype=np.float32), now=10.0)
    except WakeWordRuntimeError as error:
        assert str(error) == "wake_word_runtime_invalid_score"
    else:
        raise AssertionError("El KWS aceptÃ³ una puntuaciÃ³n no finita.")


def test_wake_manifest_rejects_modified_calibration_report(tmp_path) -> None:
    manifest = _write_wake_manifest(tmp_path)
    report_path = tmp_path / CALIBRATION_REPORT_FILENAME
    report_path.write_text('{"altered":true}\n', encoding="utf-8")

    config, error = inspect_wakeword_config(manifest)

    assert config is None
    assert error == "wake_word_calibration_report_hash_mismatch"


def test_wake_manifest_requires_calibration_unless_explicit_dev_override(
    monkeypatch, tmp_path
) -> None:
    manifest = _write_wake_manifest(tmp_path, approved=False)

    config, error = inspect_wakeword_config(manifest)
    assert config is None
    assert error == "wake_word_calibration_required"

    monkeypatch.setenv("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", "on")
    config, error = inspect_wakeword_config(manifest)
    assert config is not None
    assert error is None


def test_acoustic_worker_reports_hit_without_running_asr() -> None:
    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append)
    detector = _FakeAcousticDetector()
    engine._acoustic_wake_detector = detector  # noqa: SLF001 - runtime seam
    worker = threading.Thread(target=engine._acoustic_wake_loop, daemon=True)  # noqa: SLF001
    engine._acoustic_wake_worker = worker  # noqa: SLF001
    worker.start()

    assert engine._enqueue_acoustic_wake(np.zeros(512, dtype=np.float32))  # noqa: SLF001
    deadline = time.monotonic() + 1.0
    hit = None
    while time.monotonic() < deadline and hit is None:
        hit = engine._take_acoustic_wake_hit()  # noqa: SLF001
        time.sleep(0.01)
    engine.stop()

    assert hit is not None
    assert hit.model_name == "baxy"
    assert transcripts == []


def test_reset_invalidates_a_queued_acoustic_hit() -> None:
    engine = VoiceEngine(lambda _text: None)
    detector = _FakeAcousticDetector()
    engine._mode = "wake"  # noqa: SLF001 - runtime seam
    engine._wake_backend = "acoustic"  # noqa: SLF001 - runtime seam
    engine._acoustic_wake_detector = detector  # noqa: SLF001 - runtime seam
    worker = threading.Thread(target=engine._acoustic_wake_loop, daemon=True)  # noqa: SLF001
    engine._acoustic_wake_worker = worker  # noqa: SLF001 - runtime seam
    worker.start()

    assert engine._enqueue_acoustic_wake(np.zeros(512, dtype=np.float32))  # noqa: SLF001
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and detector.frames == 0:
        time.sleep(0.01)
    engine._reset_acoustic_wake()  # noqa: SLF001 - stale KWS work must die here
    time.sleep(0.05)
    hit = engine._take_acoustic_wake_hit()  # noqa: SLF001
    engine.stop()

    assert detector.frames == 1
    assert hit is None


def test_kws_worker_failure_turns_wake_mode_off() -> None:
    events: list[dict] = []
    engine = VoiceEngine(lambda _text: None, events.append)
    engine._mode = "wake"  # noqa: SLF001 - runtime seam
    engine._wake_backend = "acoustic"  # noqa: SLF001 - runtime seam
    engine._acoustic_wake_detector = _FailingAcousticDetector()  # noqa: SLF001
    worker = threading.Thread(target=engine._acoustic_wake_loop, daemon=True)  # noqa: SLF001
    engine._acoustic_wake_worker = worker  # noqa: SLF001 - runtime seam
    worker.start()

    assert engine._enqueue_acoustic_wake(np.zeros(512, dtype=np.float32))  # noqa: SLF001
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and engine.mode != "off":
        time.sleep(0.01)
    engine.stop()

    assert engine.mode == "off"
    assert engine._wake_backend == "unavailable"  # noqa: SLF001
    assert any(
        event
        == {"event": "error", "code": "wake_word_runtime_predict_failed:RuntimeError"}
        for event in events
    )


def test_wake_mode_refuses_to_claim_listening_without_kws(monkeypatch) -> None:
    events: list[dict] = []
    engine = VoiceEngine(lambda _text: None, events.append)
    engine._wake_backend = "unavailable"  # noqa: SLF001 - status seam
    engine._wake_error = "wake_word_manifest_missing"  # noqa: SLF001
    monkeypatch.setattr(engine, "load", lambda: None)

    engine.start("wake")

    assert engine.mode == "off"
    assert engine._capture_worker is None  # noqa: SLF001
    assert events[0] == {"event": "error", "code": "wake_word_manifest_missing"}
    assert events[1] == {
        "event": "state",
        "mode": "off",
        "listening": False,
        "speaking": False,
    }


def test_stt_resolution_uses_registered_bundle_when_no_explicit_path(
    monkeypatch, tmp_path
) -> None:
    registered = _write_stt_bundle(tmp_path / "registered-stt")
    manifest = tmp_path / "BAXYRuntime" / "mind-runtime-v1.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps({"schema": "baxy-mind-runtime-v1", "stt_dir": str(registered)}),
        encoding="utf-8",
    )
    monkeypatch.delenv("BAXY_MIND_STT_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_stt_directory() == registered


def test_streaming_bundle_requires_all_model_files(monkeypatch, tmp_path) -> None:
    incomplete = tmp_path / "nemotron"
    incomplete.mkdir()
    monkeypatch.setenv("BAXY_VOICE_STREAMING_STT_DIR", str(incomplete))

    assert resolve_streaming_stt_directory() is None

    complete = _write_stt_bundle(incomplete)
    assert resolve_streaming_stt_directory() == complete


def test_streaming_first_pass_requires_an_explicit_rollout(monkeypatch) -> None:
    monkeypatch.delenv("BAXY_VOICE_STREAMING_STT", raising=False)
    assert not _streaming_stt_enabled()
    monkeypatch.setenv("BAXY_VOICE_STREAMING_STT", "on")
    assert _streaming_stt_enabled()
    monkeypatch.setenv("BAXY_VOICE_STREAMING_STT", "auto")
    assert not _streaming_stt_enabled()


def test_lexical_wake_fallback_requires_an_explicit_rollout(monkeypatch) -> None:
    monkeypatch.delenv("BAXY_VOICE_LEXICAL_WAKE_FALLBACK", raising=False)
    assert not _lexical_wake_fallback_enabled()
    monkeypatch.setenv("BAXY_VOICE_LEXICAL_WAKE_FALLBACK", "on")
    assert _lexical_wake_fallback_enabled()


def test_acoustic_wake_emits_command_without_a_textual_wake_prefix() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = _engine("abre Spotify", transcripts, events)
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
    )

    assert transcripts == ["abre Spotify"]
    assert any(
        event["event"] == "recognized" and event["origin"] == "acoustic_wake"
        for event in events
    )


def test_attested_verifier_authorizes_an_acoustic_proposal() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = _engine("abre Spotify", transcripts, events)
    verifier = _FakeWakeVerifier(True)
    engine._wake_verifier = verifier  # noqa: SLF001
    engine._wake_model_name = "candidate"  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
    )

    assert verifier.calls == [(SAMPLE_RATE, "abre Spotify", 0.1)]
    assert transcripts == ["abre Spotify"]
    assert any(event["event"] == "wake_detected" for event in events)


def test_attested_verifier_rejection_cannot_open_a_turn() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = _engine("abre Spotify", transcripts, events)
    engine._wake_verifier = _FakeWakeVerifier(False)  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
    )

    assert transcripts == []
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_verifier_rejected",
        "backend": "acoustic_verified",
    }


class _SequenceRecognizer:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)

    def create_stream(self, **_kwargs) -> _FakeStream:
        return _FakeStream(self.texts.pop(0))

    def decode_stream(self, _stream: _FakeStream) -> None:
        return None


class _EndpointCascade(HyperspotterCascadeDetector):
    def __init__(self, score: float) -> None:
        self.score = score

    def score_endpoint_lexical(self, _audio: np.ndarray) -> float:
        return self.score


def _endpoint_config() -> SimpleNamespace:
    return SimpleNamespace(
        endpoint_lexical_verifier_index=2,
        endpoint_lexical_score_threshold=-1.0,
        endpoint_lexical_retry_speed_factors=(0.85, 1.14),
        endpoint_lexical_aliases=frozenset(("baxy", "baxi", "bakse", "backsy", "boxy")),
    )


def test_score_gated_endpoint_authorizes_a_leading_canonical_name() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        ["Baxy open the settings window"]
    )
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = _endpoint_config()  # noqa: SLF001
    engine._acoustic_wake_detector = _EndpointCascade(-0.5)  # noqa: SLF001
    engine._wake_model_name = "cascade"  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "endpoint_wake_candidate",
    )

    assert transcripts == ["open the settings window"]
    assert any(
        event.get("event") == "wake_detected"
        and event.get("backend") == "acoustic_endpoint"
        and event.get("method") == "score_gated_endpoint_exact_leading_alias"
        for event in events
    )


def test_score_gated_endpoint_rejects_weak_acoustic_evidence_before_asr() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    recognizer = _SequenceRecognizer(["Baxy open the settings window"])
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = recognizer  # noqa: SLF001
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = _endpoint_config()  # noqa: SLF001
    engine._acoustic_wake_detector = _EndpointCascade(-1.01)  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "endpoint_wake_candidate",
    )

    assert transcripts == []
    assert recognizer.texts == ["Baxy open the settings window"]
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_endpoint_acoustic_rejected",
        "backend": "acoustic_endpoint",
    }


def test_score_gated_endpoint_rejects_basi_even_with_acoustic_evidence() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        [
            "Basi turn on airplane mode",
            "Basic turn on airplane mode",
            "Vas y turn on airplane mode",
        ]
    )
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = _endpoint_config()  # noqa: SLF001
    engine._acoustic_wake_detector = _EndpointCascade(6.0)  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "endpoint_wake_candidate",
    )

    assert transcripts == []
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_endpoint_lexical_rejected",
        "backend": "acoustic_endpoint",
    }


class _SequenceVad:
    def __init__(self, probabilities: list[float]) -> None:
        self.probabilities = list(probabilities)
        self.resets = 0

    def process(self, _audio: np.ndarray) -> float:
        return self.probabilities.pop(0) if self.probabilities else 0.0

    def reset(self) -> None:
        self.resets += 1


class _FiniteInputStream:
    def __init__(self, stop_event: threading.Event, frames: int) -> None:
        self.device = 0
        self.stop_event = stop_event
        self.frames = frames
        self.reads = 0

    def __enter__(self):
        return self

    @staticmethod
    def __exit__(_exc_type, _exc, _traceback) -> None:
        return None

    def read(self, samples: int) -> tuple[np.ndarray, bool]:
        if self.reads >= self.frames:
            self.stop_event.set()
            return np.zeros((samples, 1), dtype=np.float32), False
        self.reads += 1
        return np.full((samples, 1), 0.02, dtype=np.float32), False


def _endpoint_capture_engine(monkeypatch, probabilities: list[float]) -> VoiceEngine:
    engine = VoiceEngine(lambda _text: None)
    engine._vad = _SequenceVad(probabilities)  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001
    engine._wake_backend = "acoustic"  # noqa: SLF001
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = _endpoint_config()  # noqa: SLF001
    engine._acoustic_wake_detector = _EndpointCascade(0.0)  # noqa: SLF001
    engine._acoustic_wake_worker = object()  # type: ignore[assignment]  # noqa: SLF001
    monkeypatch.setattr(  # noqa: SLF001
        engine._loopback,
        "latest",
        lambda samples: np.zeros(samples, dtype=np.int16),
    )
    return engine


def test_wake_capture_segments_speech_silently_for_endpoint_authorization(
    monkeypatch,
) -> None:
    probabilities = [0.0, 0.0, *([0.9] * 12), *([0.0] * 23)]
    stop_event = threading.Event()
    decode_queue: queue.Queue[object] = queue.Queue()
    engine = _endpoint_capture_engine(monkeypatch, probabilities)
    duck_calls: list[bool] = []
    monkeypatch.setattr(engine._ducker, "duck", lambda: duck_calls.append(True))  # noqa: SLF001
    _install_sounddevice(
        monkeypatch,
        lambda **_kwargs: _FiniteInputStream(stop_event, len(probabilities)),
    )

    engine._capture_loop(  # noqa: SLF001
        stop_event=stop_event,
        decode_queue=decode_queue,
        streaming_queue=queue.Queue(),
        wake_queue=queue.Queue(),
        wake_hits=queue.Queue(),
        capture_ready_event=threading.Event(),
    )

    request = decode_queue.get_nowait()
    assert request.origin == "endpoint_wake_candidate"
    assert request.audio.size >= MIN_UTTERANCE_S * SAMPLE_RATE
    assert duck_calls == []


def test_acoustic_hit_upgrades_an_active_endpoint_candidate(monkeypatch) -> None:
    probabilities = [0.0, 0.0, *([0.9] * 12), *([0.0] * 23)]
    stop_event = threading.Event()
    decode_queue: queue.Queue[object] = queue.Queue()
    engine = _endpoint_capture_engine(monkeypatch, probabilities)
    duck_calls: list[bool] = []
    monkeypatch.setattr(engine._ducker, "duck", lambda: duck_calls.append(True))  # noqa: SLF001
    hit = WakeWordDetection(
        "cascade",
        "Baxy",
        0.95,
        time.monotonic(),
        method="logmel_verifier",
        verifier_score=3.5,
    )
    calls = 0

    def take_hit(**_kwargs):
        nonlocal calls
        calls += 1
        return hit if calls == 5 else None

    monkeypatch.setattr(engine, "_take_acoustic_wake_hit", take_hit)
    _install_sounddevice(
        monkeypatch,
        lambda **_kwargs: _FiniteInputStream(stop_event, len(probabilities)),
    )

    engine._capture_loop(  # noqa: SLF001
        stop_event=stop_event,
        decode_queue=decode_queue,
        streaming_queue=queue.Queue(),
        wake_queue=queue.Queue(),
        wake_hits=queue.Queue(),
        capture_ready_event=threading.Event(),
    )

    request = decode_queue.get_nowait()
    assert request.origin == "acoustic_wake"
    assert request.wake_method == "logmel_verifier"
    assert request.wake_verifier_score == 3.5
    assert duck_calls == [True]


def test_cascade_lexical_rescue_decodes_only_the_candidate_window() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        ["Boxy, abre Spotify"]
    )
    engine._wake_cascade_config = SimpleNamespace(  # noqa: SLF001
        lexical_aliases=frozenset(("baxy", "baxi", "boxy"))
    )
    engine._wake_model_name = "cascade"  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
        wake_method="strict_lexical_rescue",
        wake_verifier_score=-4.0,
        wake_lexical_rescue_required=True,
    )

    assert transcripts == ["abre Spotify"]
    assert any(
        event.get("event") == "wake_detected"
        and event.get("method") == "strict_lexical_rescue"
        for event in events
    )


def test_cascade_lexical_rescue_rejects_a_confusable_candidate() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        ["Vaxi, abre Spotify"]
    )
    engine._wake_cascade_config = SimpleNamespace(  # noqa: SLF001
        lexical_aliases=frozenset(("baxy", "baxi", "boxy"))
    )
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
        wake_method="strict_lexical_rescue",
        wake_verifier_score=-4.0,
        wake_lexical_rescue_required=True,
    )

    assert transcripts == []
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_cascade_lexical_rejected",
        "backend": "acoustic_cascade",
    }


def test_direct_lexical_proposal_uses_a_bounded_speed_retry() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        [
            "ordinary first pass",
            "Maxi viene en camino",
            "Vaxi open the calculator",
        ]
    )
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = SimpleNamespace(  # noqa: SLF001
        lexical_aliases=frozenset(("baxy", "baxi", "boxy")),
        direct_lexical_retry_speed_factors=(0.85, 1.14),
    )
    engine._wake_model_name = "cascade"  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
        wake_method="direct_lexical_proposal",
        wake_verifier_score=3.1,
        wake_lexical_rescue_required=True,
    )

    assert transcripts == ["open the calculator"]
    assert any(
        event.get("event") == "wake_detected"
        and event.get("method") == "bounded_phonetic_alias"
        for event in events
    )


def test_direct_lexical_proposal_fails_closed_after_all_retries() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = VoiceEngine(transcripts.append, events.append)
    engine._recognizer = _SequenceRecognizer(  # noqa: SLF001
        [
            "ordinary first pass",
            "Maxi viene en camino",
            "Back see whether the light is on",
            "La caja esta vacia",
        ]
    )
    engine._wake_hotwords = "tokenized-baxy"  # noqa: SLF001
    engine._wake_cascade_config = SimpleNamespace(  # noqa: SLF001
        lexical_aliases=frozenset(("baxy", "baxi", "boxy")),
        direct_lexical_retry_speed_factors=(0.85, 1.14),
    )
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
        wake_confidence=0.1,
        wake_method="direct_lexical_proposal",
        wake_verifier_score=3.1,
        wake_lexical_rescue_required=True,
    )

    assert transcripts == []
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_cascade_lexical_rejected",
        "backend": "acoustic_cascade",
    }


def test_contextual_second_pass_supplies_independent_entity_evidence() -> None:
    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append)
    engine._recognizer = _ContextualFakeRecognizer()  # noqa: SLF001
    engine._corrector = FuzzyCorrector(("spotify",))  # noqa: SLF001
    engine._contextual_hotwords = "tokenized-spotify"  # noqa: SLF001
    engine._mode = "direct"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
    )

    assert transcripts == ["Open spotify"]


def test_contextual_hotwords_are_derived_from_the_runtime_token_vocabulary(
    tmp_path: Path,
) -> None:
    tokens = tmp_path / "tokens.txt"
    tokens.write_text(
        "<unk> 0\n▁s 1\npot 2\nif 3\ny 4\n",
        encoding="utf-8",
    )

    assert _compile_contextual_hotwords(tokens, ("spotify",)) == "▁s pot if y"


def test_lexical_fallback_ignores_ordinary_background_speech() -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = _engine("mañana va a llover", transcripts, events)
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "lexical_fallback",
    )

    assert transcripts == []
    assert events[-1] == {
        "event": "ignored",
        "reason": "wake_not_present",
        "backend": "lexical_fallback",
    }


def test_lexical_fallback_remains_a_compatibility_path() -> None:
    transcripts: list[str] = []
    engine = _engine("oye baxi abre Spotify", transcripts, [])
    engine._mode = "wake"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "lexical_fallback",
    )

    assert transcripts == ["abre Spotify"]


def test_acoustic_bare_wake_arms_exactly_one_followup(monkeypatch) -> None:
    transcripts: list[str] = []
    events: list[dict] = []
    engine = _engine("Baxy", transcripts, events)
    engine._mode = "wake"  # noqa: SLF001
    spoken: list[str] = []
    monkeypatch.setattr(engine, "speak", lambda text: not spoken.append(text))

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
    )
    assert spoken == ["Sí."]
    assert engine._armed_until > time.monotonic()  # noqa: SLF001

    engine._recognizer = _FakeRecognizer("dime la hora")  # noqa: SLF001
    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
        "acoustic_wake",
    )
    assert transcripts == ["dime la hora"]
    assert engine._armed_until == 0.0  # noqa: SLF001


def test_direct_mode_never_requires_wake() -> None:
    transcripts: list[str] = []
    engine = _engine("crea una nota", transcripts, [])
    engine._mode = "direct"  # noqa: SLF001

    engine._decode_utterance(  # noqa: SLF001
        np.zeros(SAMPLE_RATE, dtype=np.float32),
        np.empty(0, dtype=np.int16),
    )

    assert transcripts == ["crea una nota"]


def test_echo_guard_distinguishes_correlated_output_from_near_speech() -> None:
    rng = np.random.default_rng(7)
    reference = rng.normal(0, 1_000, 4_512).astype(np.float32)
    echo = reference[-512:] * 0.4
    near_speech = rng.normal(0, 400, 512).astype(np.float32)

    assert _looks_like_echo(echo, reference)
    assert not _looks_like_echo(near_speech, reference)


def test_nlms_aec_reduces_a_delayed_reference() -> None:
    rng = np.random.default_rng(11)
    reference = rng.normal(0, 800, 8_000).astype(np.int16)
    microphone = np.zeros_like(reference)
    microphone[80:] = (reference[:-80].astype(np.float64) * 0.65).astype(np.int16)

    clean = EchoCanceller(filter_samples=128).process(microphone, reference)
    before = float(np.sqrt(np.mean(microphone[4_000:].astype(np.float64) ** 2)))
    after = float(np.sqrt(np.mean((clean[4_000:] * 32_768.0) ** 2)))

    assert after < before * 0.7


def test_tts_tail_grace_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "99")
    assert _tail_grace_seconds() == 2.0
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "nan")
    assert _tail_grace_seconds() == 0.55
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "inf")
    assert _tail_grace_seconds() == 0.55
    monkeypatch.setenv("BAXY_VOICE_TTS_TAIL_GRACE_S", "invalid")
    assert _tail_grace_seconds() == 0.55


def test_tts_prefers_a_feminine_spanish_voice_over_a_masculine_one() -> None:
    assert _voice_rank("Microsoft Sabina", "80A", "Female", "") < _voice_rank(
        "Microsoft Raul",
        "80A",
        "Male",
        "",
    )
    assert _voice_rank("Microsoft Sabina", "80A", "Female", "raul") > _voice_rank(
        "Microsoft Raul",
        "80A",
        "Male",
        "raul",
    )


def test_tts_assistant_markup_escapes_model_text_and_uses_calm_defaults(
    monkeypatch,
) -> None:
    monkeypatch.delenv("BAXY_VOICE_RATE", raising=False)
    markup = _speech_markup("Baxy <lista> & confirma")

    assert 'absspeed="-1"' in markup
    assert "Baxy &lt;lista&gt; &amp; confirma" in markup
    assert markup.startswith('<rate absspeed="-1"><pitch absmiddle="0">')
