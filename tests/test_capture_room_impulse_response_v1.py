from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.signal import fftconvolve


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "capture_room_impulse_response_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_room_impulse_capture", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_exponential_sweep_is_finite_and_faded() -> None:
    capture = _module()
    sweep = capture.generate_exponential_sweep(
        sample_rate=16_000,
        duration_seconds=1.0,
        start_hz=80.0,
        end_hz=7_000.0,
        fade_seconds=0.02,
    )

    assert sweep.shape == (16_000,)
    assert sweep.dtype == np.float32
    assert np.isfinite(sweep).all()
    assert abs(float(sweep[0])) < 1e-7
    assert abs(float(sweep[-1])) < 1e-7
    assert float(np.max(np.abs(sweep))) > 0.9


def test_regularized_deconvolution_recovers_direct_path_and_tail() -> None:
    capture = _module()
    sample_rate = 16_000
    sweep = capture.generate_exponential_sweep(
        sample_rate=sample_rate,
        duration_seconds=1.0,
        start_hz=80.0,
        end_hz=7_000.0,
        fade_seconds=0.02,
    )
    known = np.zeros(round(0.25 * sample_rate), dtype=np.float32)
    known[0] = 1.0
    known[round(0.025 * sample_rate)] = 0.35
    known[round(0.080 * sample_rate)] = -0.15
    pre_roll = round(0.2 * sample_rate)
    observed = np.pad(
        fftconvolve(sweep, known).astype(np.float32),
        (pre_roll, round(0.2 * sample_rate)),
    )

    impulse, metrics = capture.estimate_impulse_response(
        observed,
        sweep,
        sample_rate=sample_rate,
        start_hz=80.0,
        end_hz=7_000.0,
        duration_seconds=0.25,
        pre_peak_seconds=0.005,
        regularization=1e-7,
    )

    direct = int(metrics["directPeakIndex"])
    assert direct == pytest.approx(round(0.005 * sample_rate), abs=2)
    assert int(np.argmax(np.abs(impulse))) == direct
    assert abs(float(impulse[direct + round(0.025 * sample_rate)])) > 0.15
    assert float(metrics["tailEnergyFraction"]) > 0.01


@pytest.mark.parametrize(
    "duration,start,end",
    [(0.5, 80.0, 7_000.0), (1.0, 8_000.0, 7_000.0)],
)
def test_sweep_rejects_invalid_contract(
    duration: float,
    start: float,
    end: float,
) -> None:
    capture = _module()

    with pytest.raises(ValueError, match="room_sweep_contract_invalid"):
        capture.generate_exponential_sweep(
            sample_rate=16_000,
            duration_seconds=duration,
            start_hz=start,
            end_hz=end,
            fade_seconds=0.02,
        )
