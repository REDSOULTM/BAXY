"""M101b (2026-10-01): the two empty finals of DEV-D v4a (code e4c7b368, with M101).

- D-w08-t3 reminder.create: the verified reminder reached the composer without its observed record; the three drafts
  stated a date the facts did not hold (extra_claim) and the mind's last resort had no final for reminder.create, so
  the App exhausted with «no_response;retry_exhausted». The floor says what was verified, from the facts.
- D-p16-t1 web.search: the mind published «No results mention valet parking…» as the not-found of a verified search;
  the App's twin did not read «no results» as one and refused it as reversed_result (C# M101bSinVaciosTests).

Every phrasing below is our own. Evidence: tests/data/c03_m101b_evidence.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import llm

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m101b_evidence.json").read_text(encoding="utf-8"))


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _reminder(observed: dict | None = None, *, error: str | None = None, uncertain: bool = False) -> dict:
    situation: dict = {"kind": "operation", "operation": "reminder.create",
                       "polarity": "failure" if error else "success", "verified": error is None,
                       "succeeded": error is None}
    if observed is not None:
        situation["observed"] = {"version": 1, **observed}
    if error:
        situation["error"] = error
    if uncertain:
        situation["effectUncertain"] = True
    return situation


def _final(text: str, situation: dict, drafts: list[str], intent: str = "status") -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return _Scripted(drafts).compose_user_message(text, intent, facts)


def test_the_evidence_is_the_two_empty_turns() -> None:
    turns = {turn["id"]: turn for turn in EVIDENCE["turns"]}
    assert set(turns) == {"D-p16-t1", "D-w08-t3"}
    assert turns["D-w08-t3"]["error"] == "composition_failed: no_response;retry_exhausted"
    assert turns["D-p16-t1"]["error"] == "composition_failed: reversed_result;retry_exhausted"


@pytest.mark.parametrize(
    ("observed", "language", "final"),
    [
        (None, "es", "Creé el recordatorio."),
        (None, "en", "I created the reminder."),
        ({"title": "Partido del domingo", "dueUtc": "2026-10-04T21:00:00+00:00"}, "es",
         "Creé el recordatorio «Partido del domingo»."),
    ],
)
def test_a_verified_reminder_has_a_final_from_its_facts(observed: dict | None, language: str, final: str) -> None:
    asked = "remind me an hour before the game" if language == "en" else "avísame una hora antes del partido"
    situation = _reminder(observed)
    assert llm._deterministic_final(situation, {}, asked, language) == final
    # The drafts stated a day and an hour the facts do not hold; the floor states none.
    drafts = ["Te puse el recordatorio para el domingo 4 de octubre a las 18:00."] * 3
    assert _final(asked, situation, drafts) == final


@pytest.mark.parametrize(
    ("error", "uncertain", "final"),
    [
        ("invalid_reminder", False, "No pude crear el recordatorio: la hora indicada ya pasó o no es válida."),
        ("verification_failed", True, "No pude confirmar que el recordatorio quedara creado."),
        ("invalid_arguments", False, "No pude crear el recordatorio."),
    ],
)
def test_a_reminder_not_created_says_its_cause(error: str, uncertain: bool, final: str) -> None:
    situation = _reminder(error=error, uncertain=uncertain)
    asked = "recuérdame lo del dentista ayer a las tres"
    assert llm._deterministic_final(situation, {}, asked, "es") == final
    assert _final(asked, situation, ["Listo, quedó agendado."] * 3, intent="error") == final


def test_a_draft_that_states_only_the_verified_facts_still_publishes() -> None:
    situation = _reminder({"title": "Partido del domingo"})
    asked = "avísame una hora antes del partido"
    assert _final(asked, situation, ["Listo, creé el recordatorio «Partido del domingo»."]) == (
        "Listo, creé el recordatorio «Partido del domingo»."
    )
