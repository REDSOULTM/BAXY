"""REM2 (REV13 B-1, B-2, A-1, A-3): what the fourth blind review asked to close before 1.5.0 in the routines and in
the person's «sí»."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_final import _call, _say
from test_mind_routine_guide import HEADSET, MORNING, _guide_mind, _receipt

WAKE = {"id": "r-000010", "name": "despertar", "trigger": {"at": "07:00", "repeat": "daily", "days": []},
        "active": True, "steps": [{"say": "buenos días, toma tus pastillas"}]}
NIGHT = {"id": "r-000011", "name": "buenas noches", "trigger": {"phrase": "buenas noches"}, "active": True,
         "steps": [], "order": "apaga la luz del cuarto"}


# ---------------------------------------------------------------------------------------------------------------------
# B-1: a routine found by anything but its own name or phrase is acted on only after BAXY's question and their «sí»
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["borra la rutina pastillas", "borra la rutina de la luz",
                                  "ya no quiero la rutina del cuarto", "desactiva la rutina tus",
                                  "borra la rutina de las siete de la mañana"])
def test_a_routine_said_by_what_it_does_is_never_the_one_acted_on(tmp_path: Path, said: str) -> None:
    # INT33F: without rut11's model path the closed order does not look a routine up by what it says or by a time in
    # words: the name goes to RoutinesHandler as said, which acts on a name, phrase or clock only (routine_not_found).
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    asked = mind.decide(1, said)
    assert (asked.get("arguments") or {}).get("name") not in ("despertar", "buenas noches")


def test_a_deletion_by_its_clock_alone_is_asked_before_anything_is_done(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    asked = mind.decide(1, "borra la rutina 07:00")
    assert asked["kind"] == "conversation" and asked["reply"] == "¿Borro tu rutina «despertar»?"
    assert server.bodies == []


def test_its_yes_does_it_and_its_no_does_nothing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    mind.decide(1, "borra la rutina 07:00")
    done = mind.decide(2, "sí")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": WAKE["id"]}
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    mind.decide(1, "borra la rutina 07:00")
    kept = mind.decide(2, "no")
    assert kept["kind"] == "conversation" and kept["reply"] == "No borré nada."
    assert server.bodies == []


@pytest.mark.parametrize(("said", "name"), [("borra la rutina despertar", "despertar"),
                                            ("Borra la rutina BUENAS NOCHES", "buenas noches"),
                                            ("desactiva la rutina audífonos", "audifonos")])
def test_a_routine_said_by_its_own_name_or_phrase_is_still_done_at_once(tmp_path: Path, said: str, name: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT, HEADSET])
    asked = mind.decide(1, said)
    # INT33F: the name goes as said; RoutinesHandler folds it (case, accents) to the routine's own name or phrase
    assert asked["kind"] == "action" and routine_guide.unnamed(asked["arguments"]["name"]) == routine_guide.unnamed(name)


def test_changing_a_routine_found_by_what_it_does_asks_before_changing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    asked = mind.decide(1, "cambia la rutina pastillas")
    assert asked["kind"] == "conversation" and "«despertar»" in asked["reply"]
    assert server.bodies == []


def test_by_name_is_its_name_or_phrase_only() -> None:
    assert routine_guide.by_name("Buenas Noches", NIGHT) and routine_guide.by_name("despertar", WAKE)
    assert not routine_guide.by_name("pastillas", WAKE) and not routine_guide.by_name("07:00", WAKE)
    assert not routine_guide.by_name("", WAKE) and not routine_guide.by_name("la luz", NIGHT)
    assert routine_guide.by_name("buen dia", MORNING)


def test_the_closed_order_after_its_yes_reads_its_receipt(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    mind.decide(1, "borra la rutina 07:00")
    mind.decide(2, "sí")
    told = mind.continue_turn(3, _receipt({"deleted": WAKE}))
    assert told["kind"] == "conversation" and "despertar" in told["reply"]


# ---------------------------------------------------------------------------------------------------------------------
# B-2: the routine chosen at «¿Cuál de tus rutinas?» is asked by name before it is deleted or turned off
# ---------------------------------------------------------------------------------------------------------------------

def test_the_one_chosen_to_delete_is_asked_and_only_its_yes_deletes(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "qué rutinas tengo")
    mind.continue_turn(2, _receipt({"routines": [HEADSET, MORNING], "count": 2}))
    mind.decide(3, "bórrala")
    mind.decide(4, "audifonos")
    done = mind.decide(5, "sí")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": HEADSET["id"]}


def test_a_no_after_choosing_which_does_nothing(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "qué rutinas tengo")
    mind.continue_turn(2, _receipt({"routines": [HEADSET, MORNING], "count": 2}))
    mind.decide(3, "bórrala")
    mind.decide(4, "audifonos")
    kept = mind.decide(5, "no")
    assert kept["kind"] == "conversation" and kept["reply"] == "No borré nada."
    assert server.bodies == []


def test_turning_off_the_one_chosen_is_done_at_once_and_never_asked_as_a_deletion() -> None:
    # INT33F: the guide has no «¿Desactivo…?» without rut11's model path; turning one off is undone by turning it on.
    guide = routine_guide.Guide(lang="es", step="which", mode="which", act="disable", targets=("audifonos", "buen dia"))
    said, arguments, ended = guide.answer("audifonos", [HEADSET, MORNING], False, None)
    assert (said, arguments, ended) == ("", {"action": "disable", "name": "audifonos"}, True)


def test_borrala_with_several_named_asks_which_and_then_its_yes(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [HEADSET, MORNING])
    mind.decide(1, "qué rutinas tengo")
    mind.continue_turn(2, _receipt({"routines": [HEADSET, MORNING], "count": 2}))
    mind.decide(3, "bórrala")
    chosen = mind.decide(4, "audifonos")
    assert chosen["kind"] == "conversation" and chosen["reply"] == "¿Borro tu rutina «audifonos»?"
    assert server.bodies == []


# ---------------------------------------------------------------------------------------------------------------------
# A-3: the question of their «sí» reads what BAXY asked them, the ask_user question the App published
# ---------------------------------------------------------------------------------------------------------------------

def test_the_yes_question_reads_the_question_published_not_the_words_beside_it(tmp_path: Path) -> None:
    from test_mind_su_si import PENDING, Closed
    from test_mind_final import _mind

    beside = {"choices": [{"message": {"content": "Encontré la página del museo.", "tool_calls": [
        {"id": "c2", "function": {"name": "ask_user",
                                  "arguments": json.dumps({"question": "¿Enciendo la búsqueda web?"})}}]}}]}
    mind, server = _mind(tmp_path, [_call("baxy_settings_set", PENDING["arguments"]), beside])
    mind.wire_to_op = {"baxy_settings_set": "baxy.settings.set"}
    mind.decide(1, "busca el horario del museo")
    asked = mind.continue_turn(2, json.dumps({"status": "needs_confirmation", "next": "ask the person"}))
    assert asked["kind"] == "clarify" and asked["question"] == "¿Enciendo la búsqueda web?"
    closed = Closed(server, "now")
    mind.decide(3, "dale", PENDING)
    note = closed.asked[0]["messages"][-1]["content"]
    assert "«¿Enciendo la búsqueda web?»" in note and "museo" not in note


# ---------------------------------------------------------------------------------------------------------------------
# A-1: the model's yes that is not theirs reaches the App as «unclear»: what waits still waits, as its receipt says
# ---------------------------------------------------------------------------------------------------------------------

ASKED_AGAIN = json.dumps({"status": "needs_confirmation", "operation": "baxy.settings.set",
                          "next": "nothing ran and it still waits: ask the person again"})


def test_the_models_yes_that_is_not_theirs_reaches_the_app_as_unclear(tmp_path: Path) -> None:
    from test_mind_su_si import PENDING, _asked_mind

    mind, server, _ = _asked_mind(tmp_path, [_call("confirm_pending", {"answer": "yes"}),
                                             _say("Vale, como quieras. ¿La enciendo entonces?")], "other")
    result = mind.decide(3, "puede ser", PENDING)
    assert (result["kind"], result["operation"], result["arguments"]) == ("action", "confirmation.answer",
                                                                         {"answer": "unclear"})
    assert result.get("theirYes") is None
    told = mind.continue_turn(4, ASKED_AGAIN)
    assert told["reply"].startswith("Vale, como quieras.")
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert json.loads(tool.split("\n[En este turno")[0])["error"] == "not_their_yes"


def test_when_the_app_no_longer_holds_it_the_model_reads_the_apps_receipt(tmp_path: Path) -> None:
    from test_mind_su_si import PENDING, _asked_mind

    mind, server, _ = _asked_mind(tmp_path, [_call("confirm_pending", {"answer": "yes"}), _say("Ya no está pendiente.")],
                                  "other")
    mind.decide(3, "puede ser", PENDING)
    expired = json.dumps({"status": "failed", "error": "confirmation_expired"})
    mind.continue_turn(4, expired)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert json.loads(tool.split("\n[En este turno")[0])["error"] == "confirmation_expired"


def test_a_call_queued_behind_the_models_yes_does_not_run(tmp_path: Path) -> None:
    from test_mind_su_si import PENDING, _asked_mind

    both = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": "confirm_pending", "arguments": json.dumps({"answer": "yes"})}},
        {"id": "c2", "function": {"name": "baxy_settings_set",
                                  "arguments": json.dumps({"setting": "web_search", "value": "on"})}}]}}]}
    mind, server, _ = _asked_mind(tmp_path, [both, _say("¿La enciendo entonces?")], "other")
    mind.decide(3, "puede ser", PENDING)
    told = mind.continue_turn(4, ASKED_AGAIN)
    assert told["kind"] == "conversation" and told["reply"] == "¿La enciendo entonces?"
