"""Uso real t2-r4 c01-1 and c01-2 (diagnóstico §a): the final of a play that did not happen says why.

c01-1: Spotify's helper was stopped (input_user_interrupted) and the final said «No pude confirmar el resultado con
«los bunkers»» — the deterministic fallback read only the whole-sentence failures, and the three honest drafts
(«No se pusieron los bunkers en Spotify porque…», «No puse los bunkers…») died wanting «no pude». c01-2: a YouTube video
opened in the person's own browser whose playback was not confirmed (user_browser_playback_unconfirmed) fell to the
same generic sentence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import llm, operation_floor  # noqa: E402
from baxy_mind import deterministic_finals
from baxy_mind import visible_defect
from baxy_mind.semantic import claims  # noqa: E402


def _failed(operation: str, error: str, attempted: dict, target: str = "los bunkers", uncertain: bool = True) -> str:
    reason = {"kind": "operation", "operation": operation, "polarity": "failure", "verified": False,
              "succeeded": False, "error": error, "cause": "external_effect_ambiguous", "effectUncertain": uncertain,
              "target": target, "attempted": attempted}
    return json.dumps({"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0,
                       "steps": [], "reason": reason}, ensure_ascii=False)


SPOTIFY_STOPPED = _failed("media.play.query", "input_user_interrupted", {"provider": "spotify", "query": "los bunkers"})
SPOTIFY_STOPPED_BEFORE = _failed("media.play.query", "input_user_interrupted",
                                 {"provider": "spotify", "query": "los bunkers"}, uncertain=False)
YOUTUBE_UNCONFIRMED = _failed("media.play.youtube", "user_browser_playback_unconfirmed",
                              {"query": "video largo de Los Bunkers"}, "video largo de Los Bunkers")


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _final(text: str, situation: str, drafts: list[str]) -> str:
    return _Scripted(drafts).compose_user_message(text, "error", {"situation": situation, "mustNotAskFollowUp": True})


@pytest.mark.parametrize(
    ("language", "final"),
    [
        ("es", "No pude poner la música «los bunkers»: empezaste a usar el PC mientras lo hacía, así que paré a mitad "
               "para no estorbarte."),
        ("en", "I couldn't play the music «los bunkers»: you started using the PC while I was doing it, so I stopped "
               "halfway so as not to get in your way."),
    ],
)
def test_a_play_stopped_by_the_person_is_said_with_its_cause(language: str, final: str) -> None:
    assert deterministic_finals._deterministic_final(json.loads(SPOTIFY_STOPPED_BEFORE), {}, "pon los bunkers", language) == final


@pytest.mark.parametrize(
    ("language", "final"),
    [
        ("es", "Intenté poner la música «los bunkers», pero no pude confirmar si se hizo: empezaste a usar el PC "
               "mientras lo hacía, así que paré a mitad para no estorbarte."),
        ("en", "I tried to play the music «los bunkers», but I couldn't confirm whether it was done: you started using "
               "the PC while I was doing it, so I stopped halfway so as not to get in your way."),
    ],
)
def test_a_stop_whose_effect_may_have_happened_says_the_cause_without_saying_not_done(
    language: str, final: str
) -> None:
    # Review of 290ff812e: the stopped step carried effectUncertain; «No pude poner…» told an act not done that no
    # fact backs. The floor's own uncertain wording stays, with the stop's cause.
    assert deterministic_finals._deterministic_final(json.loads(SPOTIFY_STOPPED), {}, "pon los bunkers", language) == final


def test_contracase_an_unconfirmed_play_with_no_stop_cause_stays_unconfirmed() -> None:
    situation = json.loads(_failed("media.play.query", "spotify_playback_unconfirmed", {}))
    # Estabilización F: said with the floor's own act tried and not confirmed (no fixed sentence in code).
    assert deterministic_finals._deterministic_final(situation, {}, "pon los bunkers", "es") == (
        "Intenté poner la música «los bunkers», pero no pude confirmar si se hizo."
    )


def test_a_stop_cause_on_an_operation_with_no_plain_clause_says_nothing_new() -> None:
    assert operation_floor.stopped_final({"kind": "operation", "operation": "no.such.op"},
                                         "input_user_interrupted", False) == ""
    assert operation_floor.stopped_final({"kind": "operation", "operation": "media.play.query"},
                                         "spotify_playback_unconfirmed", False) == ""


@pytest.mark.parametrize(
    ("language", "final"),
    [
        ("es", "Abrí el video de «video largo de Los Bunkers» en tu navegador, pero no pude confirmar que esté "
               "sonando; puedes revisarlo ahí."),
        ("en", "I opened the video for «video largo de Los Bunkers» in your web browser, but I couldn't confirm that "
               "it's playing; you can check it there."),
    ],
)
def test_a_video_opened_in_the_persons_browser_and_not_confirmed_says_so(language: str, final: str) -> None:
    assert deterministic_finals._deterministic_final(json.loads(YOUTUBE_UNCONFIRMED), {}, "mejor en YouTube", language) == final


@pytest.mark.parametrize(
    "draft",
    [
        "No puse los bunkers en Spotify porque empezaste a usar el PC mientras lo hacía.",
        "No se pusieron los bunkers en Spotify porque usaste el PC mientras lo intentaba.",
    ],
)
def test_the_act_denied_with_its_own_verb_tells_the_failure(draft: str) -> None:
    assert visible_defect.compose_visible_defect(draft, "error", "pon los bunkers", {"situation": SPOTIFY_STOPPED}) == ""
    # Estabilización F: the stop has its sentence in the floor, so the turn says it and no draft is asked for.
    assert _final("pon los bunkers", SPOTIFY_STOPPED, [draft]) == deterministic_finals._deterministic_final(
        json.loads(SPOTIFY_STOPPED), {}, "pon los bunkers", "es")


@pytest.mark.parametrize(
    "draft",
    [
        # Another act denied («cerrar» is not what a play backs) and a draft that tells no failure.
        "No lo cerré porque empezaste a usar el PC.",
        "Intentaste poner la canción de los bunkers, pero el PC se detuvo a la mitad porque empezaste a usarlo.",
    ],
)
def test_contracase_another_act_denied_or_no_failure_is_still_refused(draft: str) -> None:
    assert visible_defect.compose_visible_defect(draft, "error", "pon los bunkers", {"situation": SPOTIFY_STOPPED}) in {
        "missing_failure", "reversed_polarity",
    }


@pytest.mark.parametrize(
    ("text", "denied"),
    [
        ("No puse los bunkers.", {"poner"}),
        ("No se pusieron los bunkers.", {"poner"}),
        ("No lo cerré.", {"cerrar"}),
        ("Puse los bunkers.", set()),
        ("No sé si se puso.", set()),
        ("Dijiste «no puse nada».", set()),
    ],
)
def test_denied_acts_reads_only_a_plain_negation(text: str, denied: set[str]) -> None:
    assert claims.denied_acts(text) == frozenset(denied)
