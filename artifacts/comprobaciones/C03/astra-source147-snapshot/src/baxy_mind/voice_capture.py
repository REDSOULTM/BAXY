"""Bounded WASAPI microphone capture with a native ADC clock."""

from __future__ import annotations

import math
import queue
import threading
import time
from contextlib import ExitStack
from typing import Any

import numpy as np

from .voice_aec import _com_apartment

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512


class WasapiCaptureStream:
    """Copy callback frames; the capture owner performs all DSP outside it."""

    def __init__(self, stop_event: threading.Event) -> None:
        self._stop_event = stop_event
        self._frames: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(64)
        self._error: str | None = None
        self.adc_time: float | None = None
        self._stream: Any = None
        self._resources: ExitStack | None = None

    @property
    def device(self) -> Any:
        return self._stream.device

    def _callback(self, data: np.ndarray, frames: int, timing: Any, status: Any) -> None:
        if self._stop_event.is_set() or self._error is not None:
            return
        adc_time = float(timing.inputBufferAdcTime)
        if status:
            self._error = "input_callback_overflow"
        elif frames != FRAME_SAMPLES or data.shape != (FRAME_SAMPLES, 1):
            self._error = "input_frame_size_invalid"
        elif not math.isfinite(adc_time) or adc_time <= 0:
            self._error = "input_adc_clock_unavailable"
        else:
            try:
                self._frames.put_nowait((data.copy(), adc_time))
            except queue.Full:
                self._error = "input_queue_overflow"

    def __enter__(self) -> WasapiCaptureStream:
        import sounddevice as sd

        with ExitStack() as resources:
            # WASAPI needs COM on the owner thread before open/start and until close.
            resources.enter_context(_com_apartment())
            api = next(
                (item for item in sd.query_hostapis() if item["name"] == "Windows WASAPI"),
                None,
            )
            if api is None or int(api["default_input_device"]) < 0:
                raise RuntimeError("wasapi_input_unavailable")
            self._stream = sd.InputStream(
                device=int(api["default_input_device"]),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=FRAME_SAMPLES,
                extra_settings=sd.WasapiSettings(auto_convert=True),
                callback=self._callback,
            )
            try:
                resources.enter_context(self._stream)
            except Exception:
                self._stream.close()
                raise
            self._resources = resources.pop_all()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._resources is not None:
            self._resources.__exit__(*exc)

    def read(self, frames: int) -> tuple[np.ndarray, bool]:
        if frames != FRAME_SAMPLES:
            raise ValueError("input_read_size_invalid")
        deadline = time.monotonic() + 2.0
        while True:
            if self._stop_event.is_set():
                raise InterruptedError("input_capture_cancelled")
            if self._error is not None:
                raise RuntimeError(self._error)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("input_capture_timeout")
            try:
                audio, adc_time = self._frames.get(timeout=min(0.05, remaining))
            except queue.Empty:
                continue
            if self._error is not None:
                raise RuntimeError(self._error)
            self.adc_time = adc_time
            return audio, False
