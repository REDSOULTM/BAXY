"""MEN1 (AMD2, hallazgo E, 2026-11-09): baxy_update failed with baxy_update_development_build, nothing had looked for a
newer version, and the answer was «No hay una versión más reciente disponible para instalar». A result that says in its
own typed field that what the call was to find out was not looked at («checked» false) is another thing than a check
that found nothing («checked» true with what it found): the outcome line says so in words, and an absence told after it
is asked once more with that fact (answer_check's «partial»). Nothing here names a tool: the field is the result's."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import CHECK_NOTE, NOT_CHECKED, _outcome, _said_once
from test_answer_check import _r, _rules
from test_mind_final import _call, _mind, _say

# What BaxyUpdateHandler gives through OperationVisibleFacts.FromOutcome, with the field it is to carry.
DEVELOPMENT = {"status": "failed", "error": "baxy_update_development_build",
               "observed": {"version": 1, "channel": "development", "installed": "1.3.2", "checked": False}}
UNREACHABLE = {"status": "pending", "error": "baxy_update_unreachable",
               "observed": {"version": 1, "channel": "github", "installed": "1.3.2", "checked": False}}
BY_THE_STORE = {"status": "completed", "verification": "readback",
                "observed": {"version": 1, "channel": "steam", "installed": "1.3.2", "updatedBy": "steam",
                             "storeUpdatesItself": True, "authority": "baxy_distribution_store", "checked": False}}
ALREADY_LATEST = {"status": "failed", "error": "baxy_update_already_latest",
                  "observed": {"version": 1, "channel": "github", "installed": "1.3.2", "latest": "1.3.2",
                               "newer": False, "checked": True}}
NOTHING_NEWER = {"status": "completed", "verification": "readback",
                 "observed": {"version": 1, "channel": "github", "installed": "1.3.2", "updatedBy": "github",
                              "latest": "1.3.2", "newer": False, "authority": "github_releases_latest",
                              "checked": True}}


def _without_the_field(facts: dict) -> dict:
    return {**facts, "observed": {k: v for k, v in facts["observed"].items() if k != "checked"}}


@pytest.mark.parametrize("facts,told", [
    (DEVELOPMENT, "falló (baxy_update_development_build)"),
    (UNREACHABLE, "no se completó (baxy_update_unreachable)"),
    (BY_THE_STORE, "completado y verificado"),
])
def test_a_result_that_checked_nothing_says_so_whatever_its_status(facts: dict, told: str) -> None:
    assert _outcome(json.dumps(facts)) == told + NOT_CHECKED
    # Without the field the line is today's: only the result's own typed fact adds the words.
    assert _outcome(json.dumps(_without_the_field(facts))) == told


@pytest.mark.parametrize("facts,told", [
    (ALREADY_LATEST, "falló (baxy_update_already_latest)"),
    (NOTHING_NEWER, "completado y verificado"),
])
def test_a_check_that_was_made_keeps_its_line(facts: dict, told: str) -> None:
    assert _outcome(json.dumps(facts)) == told


@pytest.mark.parametrize("value", ["false", 0, None, [], {"value": False}])
def test_only_the_boolean_false_counts(value: object) -> None:
    facts = {"status": "failed", "error": "x", "observed": {"checked": value}}
    assert _outcome(json.dumps(facts)) == "falló (x)"
    # A field of that name deeper in the result (a list's row, a view) is not the result's own.
    nested = {"status": "completed", "verification": "output_only", "observed": {"rows": [{"checked": False}]}}
    assert NOT_CHECKED not in _outcome(json.dumps(nested), read=True)


def test_the_line_says_it_in_full_once_and_short_after() -> None:
    entry = "baxy_update → falló (baxy_update_development_build)" + NOT_CHECKED
    first, again = _said_once([entry, entry])
    assert first == entry
    assert again == "baxy_update → falló (baxy_update_development_build); no se comprobó"


def test_the_model_reads_it_after_the_result(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("baxy_update", {"action": "install"}), _say("No pude comprobarlo.")])
    mind.wire_to_op = {"baxy_update": "baxy.update"}
    mind.decide(1, "actualízate")
    mind.continue_turn(2, json.dumps(DEVELOPMENT))
    tool = next(m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool")
    assert tool.endswith("[En este turno: baxy_update → falló (baxy_update_development_build)" + NOT_CHECKED + "]")
    assert '"checked":false' in tool.replace(" ", "")  # the typed field stays in the result the model reads


# ---- the answer after it ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("answer,flagged", [
    ("No hay una versión más reciente disponible para instalar.", True),   # AMD2 §9, word for word
    ("No, no hay una versión más reciente disponible para instalar.", True),
    ("No hay ninguna actualización nueva.", True),
    ("No pude comprobar si hay una versión nueva: esta copia es de desarrollo.", False),
    ("Esta copia es de desarrollo y se actualiza con git; no comprobé si salió otra versión.", False),
    ("¿Quieres que lo intente de nuevo más tarde?", False),
])
def test_an_absence_told_after_a_result_that_checked_nothing_is_found(answer: str, flagged: bool) -> None:
    receipts = [_r("baxy.update", DEVELOPMENT, {"action": "install"})]
    assert ("partial" in _rules(answer, receipts, "actualízate")) is flagged


def test_a_receipt_without_the_line_still_gives_the_fact() -> None:
    receipt = {**_r("baxy.update", DEVELOPMENT), "outcome": "falló (baxy_update_development_build)"}
    found = check("No hay ninguna actualización nueva.", "actualízate", [receipt], None)
    assert [f["rule"] for f in found] == ["partial"]
    assert found[0]["fact"] == "baxy_update → falló (baxy_update_development_build): no se comprobó lo pedido"


def test_the_same_absence_after_a_check_that_was_made_is_its_reading() -> None:
    answer = "No hay una versión más reciente disponible para instalar."
    for facts in (ALREADY_LATEST, NOTHING_NEWER):
        assert _rules(answer, [_r("baxy.update", facts, {"action": "check"})], "¿hay versión nueva?") == []
    # Today's result, without the field, says nothing either way: the rule does not guess.
    assert _rules(answer, [_r("baxy.update", _without_the_field(DEVELOPMENT))], "actualízate") == []


def test_the_fact_given_back_is_the_results_own(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("baxy_update", {"action": "install"}),
                                    _say("No hay una versión más reciente disponible para instalar."),
                                    _say("No pude comprobar si hay una versión nueva: esta copia es de desarrollo.")])
    mind.wire_to_op = {"baxy_update": "baxy.update"}
    mind.decide(1, "actualízate")
    result = mind.continue_turn(2, json.dumps(DEVELOPMENT))
    # Every word spoken is the model's: its second answer, written with the fact in front of it.
    assert result["reply"] == "No pude comprobar si hay una versión nueva: esta copia es de desarrollo."
    note = server.bodies[-1]["messages"][-1]["content"]
    assert note.startswith(CHECK_NOTE[:40]) and "«No hay una versión más reciente disponible para instalar.»" in note
    assert note.count("baxy_update → falló (baxy_update_development_build)" + NOT_CHECKED) == 1
    assert note.count("no se comprobó lo pedido") == 1  # said once: the fact is the result's own line
