"""Polyphase FIR resampling with numpy alone: the voice's small pitch shift and the echo stage's reference.

uso-116 (N26): these were scipy.signal's resample_poly, upfirdn and firwin, and importing scipy.signal for them took
1.1 s alone (827 modules, 57 MB, 784 MB of commit with its own OpenBLAS) and 3.4 s of the 4.2 s the first answer waited
for the voice beside the rest of the start, 21 s on the worst one measured. The same arithmetic, sample by sample within
2e-5 (tests/test_voice_sin_scipy.py); the voice sounds as it was chosen.
"""
from __future__ import annotations

from math import gcd

import numpy as np

_BLOCK = 4096   # outputs per pass: a long take is not one table as wide as the take


def lowpass(taps: int, cutoff: float, window: np.ndarray) -> np.ndarray:
    """A linear-phase low-pass with unit gain at DC (scipy.signal.firwin); cutoff relative to Nyquist."""
    middle = np.arange(taps) - (taps - 1) / 2
    filter_ = cutoff * np.sinc(cutoff * middle) * window
    return filter_ / np.sum(filter_)


class Polyphase:
    """x upsampled by ``up``, filtered by ``taps`` and downsampled by ``down`` (scipy.signal.upfirdn): output k is
    the sum of x[j] * taps[k*down - j*up]. The table of branches is built once, for a stream of short chunks."""

    def __init__(self, taps: np.ndarray, up: int, down: int) -> None:
        self._up, self._down, self._taps = up, down, len(taps)
        self._width = -(-len(taps) // up)
        self._branches = np.zeros((up, self._width), np.float32)
        for phase in range(up):
            branch = taps[phase::up]
            self._branches[phase, :len(branch)] = branch

    def __call__(self, signal: np.ndarray) -> np.ndarray:
        size = ((len(signal) - 1) * self._up + self._taps - 1) // self._down + 1
        out = np.zeros(size, np.float32)
        held = np.concatenate([np.zeros(self._width - 1, np.float32), signal.astype(np.float32, copy=False),
                               np.zeros(self._width, np.float32)])
        back = np.arange(self._width)
        for start in range(0, size, _BLOCK):
            at = np.arange(start, min(start + _BLOCK, size)) * self._down
            newest = at // self._up + self._width - 1
            out[start:start + _BLOCK] = np.sum(self._branches[at % self._up] * held[newest[:, None] - back], axis=1)
        return out


def resample_poly(signal: np.ndarray, up: int, down: int) -> np.ndarray:
    """``signal`` at up/down its rate (scipy.signal.resample_poly with its defaults: Kaiser window, beta 5), its first
    sample where it was and its length rounded up."""
    divisor = gcd(up, down)
    up, down = up // divisor, down // divisor
    if up == down:
        return signal.astype(np.float32, copy=True)
    size = -(-len(signal) * up // down)
    width = max(up, down)
    half = 10 * width
    taps = lowpass(2 * half + 1, 1 / width, np.kaiser(2 * half + 1, 5.0)) * up
    # Zeros before the filter so its centre falls on an output, and after it so the output reaches ``size``.
    before = down - half % down
    skip = (half + before) // down
    after = 0
    while ((len(signal) - 1) * up + before + len(taps) + after - 1) // down + 1 < size + skip:
        after += 1
    padded = np.concatenate([np.zeros(before), taps, np.zeros(after)])
    return Polyphase(padded, up, down)(signal)[skip:skip + size]
