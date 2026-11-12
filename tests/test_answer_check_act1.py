"""ACT1 (VER2, held-out V08, 10-11-2026): to «are you up to date?» the model answered that BAXY was up to date, «I checked
and there's no newer version», with no call at all (base and candidate alike); in Spanish, «Sí, estoy al día». Only a
look for a newer version (baxy.update check) can say that: the claim is read against the conversation's calls, and the
model is asked once more with that fact, keeping its tools so it may look. The answers here are VER2's (paraphrased)."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import STATE_NOTE
from test_answer_check import _r, _rules
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say

CHECKED = {"status": "completed", "verification": "readback", "observed": {
    "installed": "1.4.2", "checked": True, "updatedBy": "github", "latest": "1.4.2", "newer": False}}
TIME = {"status": "completed", "verification": "output_only", "observed": {"local": "2026-11-10T19:05:00-03:00"}}
PACKAGE = {"status": "completed", "verification": "readback", "observed": {"name": "Editor", "version": "3.1",
                                                                          "upgradable": False}}


@pytest.mark.parametrize("answer,flagged", [
    ("Yes, I'm up to date. I checked and there's no newer version of me available.", True),
    ("Sí, estoy al día. ¿Necesitas que busque algo en internet?", True),
    ("Estoy en la versión más reciente, la 1.4.2.", True),
    ("Tienes la última versión de BAXY.", True),
    ("No hay una versión más nueva: estás en la 1.4.2.", True),
    ("You're on the latest version.", True),
    # What the model knows, a question, or a doubt claims nothing.
    ("Soy la versión 1.4.2.", False),
    ("Tengo instalada la 1.4.2; ¿quieres que mire si hay una más nueva?", False),
    ("No sé si estoy al día: no lo he comprobado. ¿Lo miro?", False),
    ("I'm not sure if I'm up to date. Want me to check for updates?", False),
    ("Let me check whether there's no newer version.", False),
    ("¿Quieres que compruebe si estás al día?", False),
])
def test_up_to_date_told_with_no_look_for_a_newer_version_is_read_against_the_conversation(
        answer: str, flagged: bool) -> None:
    assert ("unchecked_update" in _rules(answer, [], "are you up to date?")) is flagged


@pytest.mark.parametrize("answer", [
    "Yes, I'm up to date: there's no newer version.",
    "Sí, estás al día: no hay una versión más nueva.",
])
def test_up_to_date_after_the_look_stands(answer: str) -> None:
    # Looked in this turn, or earlier in the conversation.
    assert "unchecked_update" not in _rules(answer, [_r("baxy.update", CHECKED, {"action": "check"})])
    assert "unchecked_update" not in _rules(answer, [], session=[("baxy.update", True, False)])


def test_a_look_of_the_turn_that_failed_is_left_to_its_own_fields() -> None:
    # MEN1's rule «partial» reads a failed look by its «checked»; this one reads only answers with no look at all.
    failed = {"status": "failed", "error": "baxy_update_unreachable"}
    assert "unchecked_update" not in _rules("Sí, estoy al día.", [_r("baxy.update", failed, {"action": "check"})])
    # A look that failed in an earlier turn backs nothing now.
    assert "unchecked_update" in _rules("Sí, estoy al día.", [], session=[("baxy.update", False, False)])


def test_another_reading_backs_only_the_impersonal_form() -> None:
    # «No newer version» may tell what another reading of the turn showed (a program's own version); «I am» may not.
    assert "unchecked_update" not in _rules("No hay una versión más nueva del editor.", [_r("package.info", PACKAGE)])
    assert "unchecked_update" in _rules("I'm up to date.", [_r("system.time", TIME)])


def test_a_session_not_known_whole_is_not_read() -> None:
    from baxy_mind.answer_check import check
    assert not [f for f in check("Sí, estoy al día.", "¿estás al día?", [], None) if f["rule"] == "unchecked_update"]


# ---- the mind --------------------------------------------------------------------------------------------------------
def test_the_model_is_told_and_may_look(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "Yes, I'm up to date. I checked and there's no newer version."
    mind, server = _mind(tmp_path, [_say(said), _call("baxy_update", {"action": "check"}),
                                    _say("I looked: 1.4.2 is the newest.")])
    mind.configure({"capabilities": [
        {"name": "baxy.update", "description": "Checks for a newer BAXY.", "risk": "read_only",
         "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]})
    result = mind.decide(1, "are you up to date?")
    assert result["kind"] == "action" and result["operation"] == "baxy.update"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(STATE_NOTE[:40])
    assert "tool_choice" not in server.bodies[-1]  # its tools stay: it may look
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert checks[0]["findings"][0]["rule"] == "unchecked_update"
    final = mind.continue_turn(1, json.dumps(CHECKED))
    assert final.get("reply") == "I looked: 1.4.2 is the newest."
