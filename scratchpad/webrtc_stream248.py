"""Isolated original AEC3; causal160-to512 bridge with128sample buffering."""
import hashlib
from pathlib import Path
import sys
import threading
import zipfile

import numpy as np

FOLDER = Path("D:/BAXYRuntime/experiments/voice/webrtc174")
WHEEL = FOLDER / "pywebrtc_audio-0.2.0-cp312-cp312-win_amd64.whl"
WHEEL_SHA = "0dabbdadd5d7fd7dcb88323266e5e14d46aaa136c58fa0573c4b0323b683c80b"
assert hashlib.sha256(WHEEL.read_bytes()).hexdigest() == WHEEL_SHA
with zipfile.ZipFile(WHEEL) as archive:
    for member in archive.namelist():
        if member.endswith((".pyd", ".dll", "__init__.py")):
            assert (FOLDER / "python" / member).read_bytes() == archive.read(member)
sys.path.insert(0, str(FOLDER / "python"))
from pywebrtc_audio import EchoCanceller as Native


class EchoCanceller:
    def __init__(self):
        self._owner = threading.get_ident()
        self._native = Native(16000, 1, 0)
        self._near = np.empty(0, np.float32)
        self._far = np.empty(0, np.float32)
        # max(n*512 mod160)=128; this makes every512output causal.
        self._out = np.zeros(128, np.float32)
        # Native:64block framing +64suppression overlap; bridge adds128.
        self._mic_delay = np.zeros(256, np.float32)
        self._previous_reference = None
        self.sha256 = WHEEL_SHA

    def process(self, microphone, reference):
        assert threading.get_ident() == self._owner and self._native is not None
        mic = np.asarray(microphone, np.float32).reshape(-1)
        ref = np.asarray(reference, np.float32).reshape(-1)
        assert mic.size == 512 and ref.size == 4512
        assert np.isfinite(mic).all() and np.isfinite(ref).all()
        self._near = np.r_[self._near, mic]
        self._far = np.r_[self._far, ref[-512:] / 32768]
        while len(self._near) >= 160:
            clean = self._native.process(np.ascontiguousarray(self._near[:160]), np.ascontiguousarray(self._far[:160]))
            self._out = np.r_[self._out, clean]
            self._near = self._near[160:]
            self._far = self._far[160:]
        assert len(self._out) >= 512
        clean, self._out = self._out[:512].copy(), self._out[512:]
        assert np.isfinite(clean).all() and np.max(abs(clean)) <= 1
        raw = np.r_[self._mic_delay, mic]
        if self._previous_reference is None:
            self._previous_reference = np.r_[np.zeros(512, np.float32), ref[:-512]]
        pair = np.r_[self._previous_reference, ref[-512:]][:-256][-4512:]
        self._mic_delay = raw[512:].copy()
        self._previous_reference = ref.copy()
        return clean, raw[:512] * 32768, pair

    def close(self):
        assert threading.get_ident() == self._owner
        self._native = None
