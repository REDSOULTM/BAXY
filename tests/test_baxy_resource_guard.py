"""The safety monitor trips only after sustained resource pressure."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "baxy_resource_guard.py"
SPEC = importlib.util.spec_from_file_location("baxy_resource_guard", SCRIPT)
assert SPEC and SPEC.loader
GUARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GUARD
SPEC.loader.exec_module(GUARD)


def _sample(*, cpu: float) -> dict:
    return {
        "total_cpu_percent": cpu,
        "baxy_cpu_percent": 0.0,
        "system_ram_percent": 40.0,
        "baxy_rss_mib": 0.0,
        "gpu": {"utilization_percent": 0.0, "memory_percent": 0.0},
        "processes": [],
    }


def test_cpu_pressure_must_be_sustained_before_trip() -> None:
    tracker = GUARD.BreachTracker(GUARD.ResourceLimits())

    assert tracker.observe(_sample(cpu=90.0)) == []
    assert tracker.observe(_sample(cpu=90.0)) == []
    assert tracker.observe(_sample(cpu=90.0)) == ["total_cpu"]


def test_safe_sample_resets_pressure_counter() -> None:
    tracker = GUARD.BreachTracker(GUARD.ResourceLimits())

    assert tracker.observe(_sample(cpu=90.0)) == []
    assert tracker.observe(_sample(cpu=20.0)) == []
    assert tracker.observe(_sample(cpu=90.0)) == []
    assert tracker.observe(_sample(cpu=90.0)) == []
