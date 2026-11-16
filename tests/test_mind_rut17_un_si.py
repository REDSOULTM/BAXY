"""RUT17 (INT37B §7, the App on the PC, a new conversation each time): «Borra la de las 10:00.» → the model listed the
alarms, read the routines beside their result and asked «No hay alarma a las 10:00, pero sí tienes una rutina … ¿Quieres
que la borre?» → «Sí.» → the model called baxy_routines and the guide asked again «¿Borro esta rutina: los lunes,
miércoles y viernes a las 10:00 de la mañana te digo «…»?»: two «sí» for one routine.

A plain «sí» to BAXY's own last question is the guide's «sí» when that question named that routine and no other of
theirs, by form (its name, phrase or clock: routine_guide.named_in). A question that names none, or two, and any other
words are asked by the guide, saying which; a «no» leaves them."""
from __future__ import annotations

import json
from pathlib import Path

from test_mind_final import _call, _say
from test_mind_int36g_rutina_por_hora import _is_have
from test_mind_int37b_rutina_conversacion_nueva import EIGHT, MORNING, NO_CLOCK, TEN
from test_mind_routine_guide import _guide_mind

# RUT18 C: with its clock in digits («Borra la de las 10:00.») the cancel is held before it runs («said_routine»,
# test_mind_rut18_rutina_dicha); this result and the yes that follows are of the words it does not hold.
SAID = "Borra la de las diez."

NAMED = f"No hay alarma a las 10:00, pero sí tienes una rutina que te dice «{MORNING}» los lunes, miércoles y viernes. " \
        "¿Quieres que la borre?"


def _asked_then(tmp_path: Path, question: str, have: dict, routines: list | None = None):
    """A new conversation: «Borra la de las 10:00.», the model's schedule_alarms cancel and the App's result, the model's
    ``question``; then the person's words make the model call baxy_routines and the closed read answers ``have``."""
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", {"action": "cancel", "at": "10:00"}), _say(question),
                                          _call("baxy_routines", {})], [TEN, EIGHT] if routines is None else routines)
    server.have_asked = []
    plain = server.chat

    def chat(body: dict, timeout: float = 120.0, gives_way: bool = False) -> dict:
        if _is_have(body):
            server.have_asked.append(body)
            return {"choices": [{"message": {"content": json.dumps(have)}}]}
        return plain(body, timeout, gives_way)

    server.chat = chat
    mind.new_session([])
    assert mind.decide(1, SAID)["kind"] == "action"
    assert mind.continue_turn(2, NO_CLOCK)["reply"] == question
    return mind, server


def test_their_yes_to_a_question_that_named_the_routine_deletes_it_in_that_turn(tmp_path: Path) -> None:
    mind, server = _asked_then(tmp_path, NAMED, {"a": "delete", "r": "10:00"})
    deleted = mind.decide(3, "Sí.")
    assert deleted["kind"] == "action" and deleted["operation"] == "baxy.routines"
    assert deleted["arguments"] == {"action": "delete", "name": TEN["id"]}
    assert len(server.have_asked) == 1 and mind._guide is None


def test_their_no_leaves_them(tmp_path: Path) -> None:
    mind, _ = _asked_then(tmp_path, NAMED, {"a": "no"})
    kept = mind.decide(3, "No.")
    assert kept["kind"] == "conversation" and kept["operation"] is None and mind._guide is None


def test_a_question_that_named_no_routine_is_asked_again_by_the_guide(tmp_path: Path) -> None:
    """Esencial in the App: «No se borró porque no era una alarma, era una rutina. ¿Quieres que la borre?»."""
    mind, _ = _asked_then(tmp_path, "No se borró porque no era una alarma, era una rutina. ¿Quieres que la borre?",
                          {"a": "delete", "r": "10:00"})
    asked = mind.decide(3, "Sí.")
    assert asked["kind"] == "conversation" and asked["operation"] is None
    assert asked["reply"].startswith("¿Borro") and "10:00" in asked["reply"] and MORNING in asked["reply"]


def test_a_question_that_named_two_routines_is_asked_again(tmp_path: Path) -> None:
    mind, _ = _asked_then(tmp_path, "Tienes una rutina a las 10:00 y otra a las 20:00. ¿Quieres que la borre?",
                          {"a": "delete", "r": "10:00"})
    asked = mind.decide(3, "Sí.")
    assert asked["kind"] == "conversation" and asked["operation"] is None and asked["reply"].startswith("¿Borro")


def test_two_routines_at_that_clock_are_never_taken_for_one(tmp_path: Path) -> None:
    again = {**TEN, "id": "r-77e0c2", "name": "10:00 (2)"}
    mind, _ = _asked_then(tmp_path, NAMED, {"a": "delete", "r": "10:00"}, routines=[TEN, again, EIGHT])
    asked = mind.decide(3, "Sí.")
    assert asked["kind"] == "conversation" and asked["operation"] is None


def test_the_read_of_another_routine_is_asked_again(tmp_path: Path) -> None:
    mind, _ = _asked_then(tmp_path, NAMED, {"a": "delete", "r": "20:00"})
    asked = mind.decide(3, "Sí.")
    assert asked["kind"] == "conversation" and asked["operation"] is None and "sábados" in asked["reply"]


def test_words_that_are_no_plain_yes_are_asked_again(tmp_path: Path) -> None:
    mind, _ = _asked_then(tmp_path, NAMED, {"a": "delete", "r": "10:00"})
    asked = mind.decide(3, "Sí, y la de los sábados también.")
    assert asked["kind"] == "conversation" and asked["operation"] is None


def test_turning_it_off_on_their_yes_is_one_turn_too(tmp_path: Path) -> None:
    mind, _ = _asked_then(tmp_path, "Tu rutina de las 10:00 sigue activa. ¿Quieres que la desactive?",
                          {"a": "turn_off", "r": "10:00"})
    off = mind.decide(3, "Sí.")
    assert off["kind"] == "action" and off["arguments"] == {"action": "disable", "name": TEN["id"]}


def test_the_result_says_the_routines_tool_asks_them_first(tmp_path: Path) -> None:
    """RUT17 (the App in Esencial: after its cancel at 10:00, the 4B asked «¿Quieres que la desactive o la borre?», 7 of 10
    in INT37A, naming none): the tool asks the person itself, saying which, and the result says so."""
    from baxy_mind import harness_language
    for lang, told in (("es", "y antes se lo pregunta a la persona diciéndole cuál"),
                       ("en", "and asks the person first, saying which")):
        harness_language.use(lang)
        try:
            mind, server = _guide_mind(tmp_path / lang, [_call("schedule_alarms", {"action": "cancel", "at": "10:00"}),
                                                         _say("…")], [TEN, EIGHT])
            mind.new_session([])
            mind.decide(1, SAID)
            mind.continue_turn(2, NO_CLOCK)
            facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
            assert told in facts, lang
        finally:
            harness_language.use("es")
