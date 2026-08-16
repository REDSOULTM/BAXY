from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


def _module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "build_baxy_logmel_guarded_rescue_verifier_v1.py"
    )
    spec = importlib.util.spec_from_file_location("guarded_rescue", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_score_exactly_matches_guarded_or_high_confidence_policy() -> None:
    module = _module()
    base = np.asarray([2.9, 3.2, 3.2, 5.8, 5.9, 6.2], dtype=np.float32)
    guard = np.asarray([9.0, 2.0, 3.1, 2.0, 2.0, 2.0], dtype=np.float32)

    scores = module.guarded_rescue_score(
        base, guard, deployment_threshold=3.0, rescue_threshold=5.9
    )

    expected = (base >= 3.0) & ((guard >= 3.0) | (base >= 5.9))
    assert (scores >= 3.0).tolist() == expected.tolist()


def test_score_rejects_invalid_threshold_order() -> None:
    module = _module()
    with pytest.raises(ValueError, match="score_invalid"):
        module.guarded_rescue_score(
            np.asarray([1.0]),
            np.asarray([1.0]),
            deployment_threshold=3.0,
            rescue_threshold=3.0,
        )
