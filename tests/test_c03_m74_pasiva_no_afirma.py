"""Fase 3.5b M74: a passive «could not be reached» is the failure's cause, not a claim of reaching anything.

DEV-D v3l D-p22-t2, D-p24-t3, D-p24-t4 (streaming.play.named with web_adapter_unavailable): every draft told the cause
the shell gives, «the web browser could not be reached», and died as reversed_polarity on «reached»; the turn ended
in ⚠. «I reached the page» still reverses a failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.llm import compose_visible_defect  # noqa: E402

_SITUATION = {
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {
        "kind": "operation", "operation": "streaming.play.named", "polarity": "failure", "verified": False,
        "succeeded": False, "error": "web_adapter_unavailable", "cause": "external_effect_ambiguous",
        "effectUncertain": True,
    },
}


def _defect(text: str) -> str:
    return compose_visible_defect(text, "error", "play Hustlers on Netflix", {"situation": _SITUATION})


def test_the_passive_cause_is_not_a_reversed_polarity() -> None:
    assert _defect(
        "I couldn't play Hustlers on Netflix because the web browser could not be reached, so nothing was played.",
    ) != "reversed_polarity"


def test_reaching_something_still_reverses_a_failure() -> None:
    assert _defect("I reached Netflix but Hustlers did not start.") == "reversed_polarity"
