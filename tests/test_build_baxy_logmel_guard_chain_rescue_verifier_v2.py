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
        / "build_baxy_logmel_guard_chain_rescue_verifier_v2.py"
    )
    spec = importlib.util.spec_from_file_location("guard_chain", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_adding_a_guard_can_only_remove_non_rescue_acceptances() -> None:
    module = _module()
    base = np.asarray([2.9, 3.5, 3.5, 5.9, 6.1], dtype=np.float32)
    first = np.asarray([9.0, 4.0, 2.0, 1.0, 1.0], dtype=np.float32)
    second = np.asarray([9.0, 2.0, 9.0, 1.0, 1.0], dtype=np.float32)
    parent = module.guard_chain_rescue_score(
        base, [first], deployment_threshold=3.0, rescue_threshold=5.9
    )
    child = module.guard_chain_rescue_score(
        base, [first, second], deployment_threshold=3.0, rescue_threshold=5.9
    )

    assert np.all(child <= parent)
    assert (parent >= 3.0).tolist() == [False, True, False, True, True]
    assert (child >= 3.0).tolist() == [False, False, False, True, True]
