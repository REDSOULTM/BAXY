from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_baxy_hyperspotter_logmel_lexical_cascade_raw_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_logmel_lexical_cascade", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("text", ["BAXY", "Baxi!", "  Boxy.  "])
def test_strict_lexical_rescue_accepts_only_entire_exact_alias(text: str) -> None:
    gate = _module()
    assert gate.has_strict_exact_alias(text)


@pytest.mark.parametrize(
    "text", ["Vaxi", "Foxy", "Baki", "Boxes", "Back soon", "Baxy abre Chrome", ""]
)
def test_strict_lexical_rescue_rejects_confusables_and_commands(text: str) -> None:
    gate = _module()
    assert not gate.has_strict_exact_alias(text)


def test_leading_alias_rescue_allows_a_command_but_not_a_confusable() -> None:
    gate = _module()
    assert gate.has_strict_leading_alias("Baxy, abre Chrome")
    assert not gate.has_strict_leading_alias("Vaxi, abre Chrome")


def test_candidate_window_union_is_sorted_and_deduplicated() -> None:
    gate = _module()
    reports = [
        {"positive": {"records": [{"record": 0, "accepted": True, "firstAcceptedWindowIndex": 3}]}},
        {"positive": {"records": [{"record": 0, "accepted": True, "firstAcceptedWindowIndex": 1}]}},
        {"positive": {"records": [{"record": 0, "accepted": True, "firstAcceptedWindowIndex": 3}]}},
    ]
    assert gate.candidate_window_indexes(reports, "positive", 0) == (1, 3)
    assert gate.verifier_window_indexes((1, 3)) == (0, 1)
    assert gate.verifier_window_indexes(()) == ()


def test_cascade_requires_upstream_and_uses_strict_rescue_only_below_threshold() -> None:
    gate = _module()
    assert gate.cascade_decision(
        upstream_candidate=False, logmel_score=None, threshold=3.0,
        lexical_exact_alias=True,
    ) == (False, "no_upstream_candidate")
    assert gate.cascade_decision(
        upstream_candidate=True, logmel_score=3.0, threshold=3.0,
        lexical_exact_alias=False,
    ) == (True, "logmel_verifier")
    assert gate.cascade_decision(
        upstream_candidate=True, logmel_score=-1.0, threshold=3.0,
        lexical_exact_alias=True,
    ) == (True, "strict_lexical_rescue")
    assert gate.cascade_decision(
        upstream_candidate=True, logmel_score=-1.0, threshold=3.0,
        lexical_exact_alias=False,
    ) == (False, "candidate_rejected")
