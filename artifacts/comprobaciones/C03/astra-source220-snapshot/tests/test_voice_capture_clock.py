"""Capture timing, continuity and resource ownership without physical devices."""
# ruff: noqa: SLF001
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.voice_aec import LoopbackReference
import baxy_mind.voice_capture as capture_module
from baxy_mind.voice_capture import WasapiCaptureStream


def test_reference_cursor_survives_bursts_and_wrap_without_repeats():
    reference = LoopbackReference()
    reference._ring = np.zeros(2048, np.int16)
    stop = threading.Event()
    reference._append(np.arange(1024, dtype=np.int16), 100.0)
    cursor = reference.sample_index(100.032, stop)
    assert cursor == 512
    np.testing.assert_array_equal(reference.window_at(cursor + 512, 512, stop), np.arange(512, 1024))
    # Producer runs ahead in a burst; callback clock jitter cannot move the origin.
    reference._append(np.arange(1024, 2560, dtype=np.int16), 100.066)
    assert reference.sample_index(100.032, stop) == 512
    for end in (1536, 2048, 2560):
        np.testing.assert_array_equal(reference.window_at(end, 512, stop), np.arange(end - 512, end))
    with pytest.raises(RuntimeError, match="reader_overrun"):
        reference.window_at(512, 512, stop)


def test_reference_startup_padding_and_future_wait():
    reference = LoopbackReference()
    stop = threading.Event()
    reference._append(np.arange(512, dtype=np.int16), 100.0)
    np.testing.assert_array_equal(reference.window_at(512, 1024, stop), np.r_[np.zeros(512), np.arange(512)])
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(reference.window_at, 1024, 512, stop, timeout=1.0)
        reference._append(np.arange(512, 1024, dtype=np.int16), 100.032)
        np.testing.assert_array_equal(pending.result(timeout=1), np.arange(512, 1024))


@pytest.mark.parametrize("failure", ["cancel", "stop", "callback", "timeout"])
def test_reference_wait_reports_loss_or_cancellation(failure):
    reference = LoopbackReference()
    stop = threading.Event()
    if failure == "cancel":
        stop.set()
    elif failure == "stop":
        reference.stop()
    elif failure == "callback":
        reference.last_error = "loopback_callback_overflow"
    expected = InterruptedError if failure == "cancel" else RuntimeError
    with pytest.raises(expected):
        reference.window_at(512, 512, stop, timeout=0.005)
    with pytest.raises(expected):
        reference.sample_index(100.0, stop, timeout=0.005)


def _install_capture(monkeypatch, *, available=True, fail_start=False):
    calls = []

    @contextmanager
    def apartment():
        calls.append("com_start")
        try:
            yield
        finally:
            calls.append("com_stop")

    monkeypatch.setattr(capture_module, "_com_apartment", apartment)

    class Stream:
        device = 37

        def __init__(self, **kwargs):
            assert calls == ["com_start"]
            self.options = kwargs

        def __enter__(self):
            calls.append("start")
            if fail_start:
                raise RuntimeError("start_failed")
            return self

        def close(self):
            calls.append("close")

        def __exit__(self, *_):
            calls.append("stop_close")

    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(
        query_hostapis=lambda: [
            {"name": "MME", "default_input_device": 1},
            {"name": "Windows WASAPI", "default_input_device": 37 if available else -1},
        ],
        InputStream=Stream,
        WasapiSettings=lambda **kwargs: SimpleNamespace(
            **kwargs, _streaminfo=SimpleNamespace(streamOption=0),
        ),
        _lib=SimpleNamespace(eStreamOptionRaw=1),
    ))
    return calls


def test_capture_uses_wasapi_default_and_copies_frames_with_native_clock(monkeypatch):
    calls = _install_capture(monkeypatch)
    with WasapiCaptureStream(threading.Event()) as capture:
        assert capture.device == 37
        assert capture._stream.options["device"] == 37
        settings = capture._stream.options["extra_settings"]
        assert settings.auto_convert is True
        assert settings._streaminfo.streamOption == 1
        audio = np.ones((512, 1), np.float32)
        for timestamp in (100.0, 100.032, 100.064):
            capture._callback(audio, 512, SimpleNamespace(inputBufferAdcTime=timestamp), False)
        audio.fill(9)
        for timestamp in (100.0, 100.032, 100.064):
            frame, overflow = capture.read(512)
            assert capture.adc_time == timestamp and not overflow
            np.testing.assert_array_equal(frame, np.ones((512, 1)))
    assert calls == ["com_start", "start", "stop_close", "com_stop"]


@pytest.mark.parametrize("failure", ["flags", "clock", "size", "queue"])
def test_capture_never_silently_loses_a_frame(monkeypatch, failure):
    _install_capture(monkeypatch)
    with WasapiCaptureStream(threading.Event()) as capture:
        audio = np.zeros((512, 1), np.float32)
        timing = SimpleNamespace(inputBufferAdcTime=0.0 if failure == "clock" else 100.0)
        for _ in range(65 if failure == "queue" else 1):
            capture._callback(audio, 511 if failure == "size" else 512, timing, failure == "flags")
        with pytest.raises(RuntimeError, match="input_"):
            capture.read(512)


def test_capture_cancel_and_failed_start_release_device(monkeypatch):
    calls = _install_capture(monkeypatch)
    stop = threading.Event()
    with WasapiCaptureStream(stop) as capture:
        stop.set()
        with pytest.raises(InterruptedError):
            capture.read(512)
    assert calls == ["com_start", "start", "stop_close", "com_stop"]
    calls = _install_capture(monkeypatch, fail_start=True)
    with pytest.raises(RuntimeError, match="start_failed"), WasapiCaptureStream(threading.Event()):
        pytest.fail("failed stream must not enter")
    assert calls == ["com_start", "start", "close", "com_stop"]


def test_capture_has_no_implicit_mme_fallback(monkeypatch):
    calls = _install_capture(monkeypatch, available=False)
    with pytest.raises(RuntimeError, match="wasapi_input_unavailable"), WasapiCaptureStream(threading.Event()):
        pytest.fail("missing WASAPI must not enter")
    assert calls == ["com_start", "com_stop"]


@pytest.mark.parametrize("failure", [None, "open", "start", "stop"])
def test_loopback_native_lifecycle_and_callback_errors(monkeypatch, failure):
    calls, options = [], {}

    def start():
        calls.append("start")
        if failure == "start":
            raise RuntimeError("start_failed")

    def stop():
        calls.append("stop")
        if failure == "stop":
            raise RuntimeError("stop_failed")

    def open_stream(**kwargs):
        options.update(kwargs)
        if failure == "open":
            raise RuntimeError("open_failed")
        return SimpleNamespace(start_stream=start, stop_stream=stop, close=lambda: calls.append("close"))

    backend = SimpleNamespace(
        get_default_wasapi_loopback=lambda: {"defaultSampleRate": 16000, "maxInputChannels": 1, "index": 29},
        open=open_stream, terminate=lambda: calls.append("terminate"),
    )
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(
        PyAudio=lambda: backend, paInt16=8, paAbort=2, paContinue=0,
    ))
    reference = LoopbackReference()
    assert reference.start() is (failure not in {"open", "start"})
    assert options["start"] is False
    if failure not in {"open", "start"}:
        callback = options["stream_callback"]
        assert callback(np.zeros(512, np.int16).tobytes(), 512, {"input_buffer_adc_time": 100.0}, 0) == (None, 0)
        assert callback(b"", 512, {"input_buffer_adc_time": 100.032}, 1) == (None, 2)
        with pytest.raises(RuntimeError, match="callback_overflow"):
            reference.window_at(512, 512, threading.Event())
        assert reference.stop() is (failure != "stop")
    assert calls.count("terminate") == 1
    assert calls.count("close") == (0 if failure == "open" else 1)
    assert not reference.active
