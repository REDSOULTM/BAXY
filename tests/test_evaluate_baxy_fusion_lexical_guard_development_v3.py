from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_fusion_lexical_guard_development_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_fusion_lexical_guard_development_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_established_ctc_is_always_preserved() -> None:
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=True,
        continuous_fusion_accepted=False,
        exact_lexical_target=False,
    ) == (True, "established_ctc")


def test_continuous_fusion_requires_exact_lexical_evidence() -> None:
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        continuous_fusion_accepted=True,
        exact_lexical_target=True,
    ) == (True, "lexically_guarded_continuous_fusion")
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        continuous_fusion_accepted=True,
        exact_lexical_target=False,
    ) == (False, "rejected")


def test_guard_cannot_create_acceptance_without_a_frozen_branch() -> None:
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        continuous_fusion_accepted=False,
        exact_lexical_target=True,
    ) == (False, "rejected")
