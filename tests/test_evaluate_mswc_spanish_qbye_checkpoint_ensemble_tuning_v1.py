from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_checkpoint_ensemble_tuning_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_checkpoint_ensemble_tuning_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_concatenation_preserves_component_cosines_equally() -> None:
    first = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    second = np.asarray([[1.0, 0.0], [1.0, 0.0]])
    fused = MODULE.concatenate_embeddings([first, second])
    np.testing.assert_allclose(np.linalg.norm(fused, axis=1), [1.0, 1.0])
    np.testing.assert_allclose(fused[0] @ fused[1], 0.5, atol=1e-8)
