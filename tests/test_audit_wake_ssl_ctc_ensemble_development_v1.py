from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wake_ssl_ctc_ensemble_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_wake_ssl_ctc_ensemble_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_contains_sequence_requires_contiguous_exact_tokens() -> None:
    collapsed = ((9, 0, 1), (1, 1, 2), (7, 2, 3), (10, 3, 4))
    assert MODULE.contains_sequence(collapsed, ((1, 7, 10),)) is True
    assert MODULE.contains_sequence(collapsed, ((1, 10),)) is False


def test_ensemble_precedence_is_positive_then_veto_then_ssl() -> None:
    assert MODULE.ensemble_accept(
        ssl_accepted=False, explicit_confusable=True, ctc_positive=True
    ) == (True, "ctc_positive_authority")
    assert MODULE.ensemble_accept(
        ssl_accepted=True, explicit_confusable=True, ctc_positive=False
    ) == (False, "ctc_explicit_confusable_veto")
    assert MODULE.ensemble_accept(
        ssl_accepted=True, explicit_confusable=False, ctc_positive=False
    ) == (True, "ssl_product_scan")


def test_summarize_requires_all_positives_and_no_false_accepts() -> None:
    records = [
        {"label": "positive", "ensemble_accepted": True},
        {"label": "hard_negative", "ensemble_accepted": False},
    ]
    assert MODULE.summarize(records)["development_gate_passed"] is True
