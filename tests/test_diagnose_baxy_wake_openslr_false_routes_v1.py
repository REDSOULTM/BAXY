from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "diagnose_baxy_wake_openslr_false_routes_v1.py"
    )
    spec = importlib.util.spec_from_file_location("wake_false_routes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_route_prefers_consensus_and_keeps_rescue_separate() -> None:
    module = _module()
    assert module.classify_route(
        [np.asarray([0.6, 0.4, 0.31, -2.0], dtype=np.float32)],
        primary_threshold=0.5,
        secondary_threshold=0.3,
        rescue_alias_index=2,
        rescue_alias_threshold=0.3,
    ) == "consensus"
    assert module.classify_route(
        [np.asarray([0.0, 0.0, 0.31, -2.0], dtype=np.float32)],
        primary_threshold=0.5,
        secondary_threshold=0.3,
        rescue_alias_index=2,
        rescue_alias_threshold=0.3,
    ) == "single_alias_rescue"
    assert module.classify_route(
        [np.asarray([0.4, 0.2, 0.29, -2.0], dtype=np.float32)],
        primary_threshold=0.5,
        secondary_threshold=0.3,
        rescue_alias_index=2,
        rescue_alias_threshold=0.3,
    ) is None
