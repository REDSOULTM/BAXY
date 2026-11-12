"""RUT1 (owner, 2026-11-10; documentacion/RUTINAS.md §5): a turn that is, whole, the phrase of a routine the person
saved runs it without the model (the person's own shortcut). A run's steps are then proposed one by one as calls of
BAXY, each authorized by the kernel as any other, and a routine's own texts are said once every call of it completed.
(RUT7: the note with the routines the model read each turn is gone; tests/test_mind_routine_guide.py.)"""
import json
from pathlib import Path

import pytest

from baxy_mind import routines
from test_mind_final import _mind, _say

NEXT = {"id": "r-000001", "name": "siguiente", "trigger": {"phrase": "¡Siguiente!"}, "active": True,
        "steps": [{"op": "media.control", "arguments": {"action": "next"}}, {"say": "Listo, la próxima."}]}
OFF = {"id": "r-000002", "name": "silencio", "trigger": {"phrase": "silencio"}, "active": False,
       "steps": [{"op": "audio.mute", "arguments": {}}]}


def _routines_mind(tmp_path: Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op = {"baxy_routines": "baxy.routines", "media_control": "media.control", "audio_mute": "audio.mute"}
    mind.routines = [NEXT, OFF]
    return mind, server


def _ran(routine: dict) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": {"run": routine}})


DONE = json.dumps({"status": "completed", "verification": "readback", "observed": {"playing": True}})
FAILED = json.dumps({"status": "failed", "error": "media_session_not_found"})


@pytest.mark.parametrize("words", ["siguiente", "Baxy, siguiente.", "¡SIGUIENTE!", "baxi siguiente"])
def test_the_whole_turn_being_a_saved_phrase_runs_its_routine_without_the_model(tmp_path: Path, words: str) -> None:
    mind, server = _routines_mind(tmp_path, [])
    result = mind.decide(1, words)
    assert result["kind"] == "action" and result["operation"] == "baxy.routines"
    assert result["arguments"] == {"action": "run", "name": "siguiente"}
    step = mind.continue_turn(2, _ran(NEXT))
    assert step["kind"] == "action" and step["operation"] == "media.control" and step["arguments"] == {"action": "next"}
    reply = mind.continue_turn(3, DONE)
    assert reply["kind"] == "conversation" and reply["reply"] == "Listo, la próxima."
    assert server.bodies == []  # the model was never asked


@pytest.mark.parametrize("words", ["pasa a la siguiente canción", "¿qué es siguiente?", "siguiente y sube el volumen",
                                   "silencio"])
def test_a_phrase_inside_other_words_or_of_an_inactive_routine_goes_to_the_model(tmp_path: Path, words: str) -> None:
    mind, server = _routines_mind(tmp_path, [_say("Vale.")])
    assert mind.decide(1, words)["reply"] == "Vale."
    assert len(server.bodies) == 1
    # RUT7: the model reads the person's words and no note with the routines.
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": words}
    assert all("→ siguiente" not in str(m.get("content")) for m in server.bodies[0]["messages"])


def test_nothing_waiting_for_the_words_is_needed_and_a_failed_step_ends_the_routine_with_the_model(tmp_path: Path) -> None:
    mind, server = _routines_mind(tmp_path, [_say("¿Pongo música?"), _say("Ok."), _say("No había nada sonando.")])
    mind.decide(1, "hola")
    assert mind.decide(2, "siguiente")["reply"] == "Ok."  # after BAXY's question the words answer it
    mind.decide(3, "siguiente", None, [("siguiente", 0.3)])  # the ear was unsure: the model reads it
    assert len(server.bodies) == 3
    mind2, server2 = _routines_mind(tmp_path, [_say("No había nada sonando.")])
    mind2.decide(1, "siguiente")
    mind2.continue_turn(2, _ran(NEXT))
    reply = mind2.continue_turn(3, FAILED)
    assert reply["reply"] == "No había nada sonando."  # its own text is not said after a failed step
    assert len(server2.bodies) == 1


def test_the_model_writes_steps_with_its_tool_names_and_the_store_gets_the_catalogs() -> None:
    arguments = {"action": "create", "phrase": "pausa", "steps": ['media_control {"action": "pause"}', "say: hecho"]}
    named = routines.named_steps(arguments, {"media_control": "media.control"})
    assert named["steps"] == ['media.control {"action": "pause"}', "say: hecho"]


def test_bare_keys_are_quoted_and_a_tool_off_in_the_profile_keeps_its_operation() -> None:
    # RUT1 held-out cp06: «{app: "pc", level: 10}» refused the routine three times; Esencial named media_control,
    # withheld, as «not one of BAXY's tools» instead of off in the profile.
    arguments = {"action": "create", "phrase": "noche", "steps": ['audio_app_volume_set {app: "pc", level: 10}',
                                                                  'media_control {"action": "pause"}', "say: {a: 1}"]}
    named = routines.named_steps(arguments, {"audio_app_volume_set": "audio.app.volume.set", "media_control": "media.control"})
    assert named["steps"] == ['audio.app.volume.set {"app": "pc", "level": 10}', 'media.control {"action": "pause"}',
                              "say: {a: 1}"]


def test_bare_word_values_are_quoted_and_true_false_null_and_numbers_stay() -> None:
    # RUT4, the owner's example «cuando te diga pantalla, desactiva la pantalla de la izquierda» (Completo and Esencial,
    # seed 0): the step came as «display_monitor_set {active: false, monitor: left}», keys and the word value bare; with
    # the keys alone quoted it was still no JSON and the routine was refused twice.
    arguments = {"action": "create", "phrase": "pantalla", "steps": [
        "display_monitor_set {active: false, monitor: left}", "audio_volume {level: 20, note: null}",
        'media_control {"action": "pause"}', "say: {deja: esto}"]}
    named = routines.named_steps(arguments, {"display_monitor_set": "display.monitor.set", "audio_volume": "audio.volume",
                                             "media_control": "media.control"})
    assert named["steps"] == ['display.monitor.set {"active": false, "monitor": "left"}',
                              'audio.volume {"level": 20, "note": null}', 'media.control {"action": "pause"}',
                              "say: {deja: esto}"]


ORDER = {"id": "r-000003", "name": "altavoces", "trigger": {"phrase": "Altavoces"}, "active": True, "steps": [],
         "order": "cambia a los altavoces Vantor"}


@pytest.mark.parametrize("words", ["altavoces", "Baxi, altavoces.", "¡ALTAVOCES!"])
def test_the_phrase_of_a_routine_kept_as_an_order_makes_that_order_the_turn(tmp_path: Path, words: str) -> None:
    # RUT6 (RUTINAS.md §5 c): the model is asked, and what it reads as the person's request is the order they saved;
    # no run is proposed for it and the list of routines is not told again.
    # RUT7: and nothing else. The note RUT6 put in front («la persona dijo «X», la frase de una rutina suya…») made
    # the 4B ask back instead of doing a short order (saved order equal to the same order said directly: 37 of 48
    # with the note, 47 of 48 without; INFORME_RUT7.md): the turn is the order alone, as if they had just said it.
    mind, server = _routines_mind(tmp_path, [_say("Cambié a los altavoces.")])
    mind.routines = [NEXT, ORDER]
    assert mind.decide(1, words)["reply"] == "Cambié a los altavoces."
    assert len(server.bodies) == 1
    asked = server.bodies[0]["messages"]
    assert asked[-1] == {"role": "user", "content": "cambia a los altavoces Vantor"}
    assert asked[-2]["content"] == mind._clock()
    assert not any("rutina" in str(m["content"]) for m in asked[1:])


def test_an_order_is_not_taken_inside_other_words_nor_when_baxy_waits_for_them(tmp_path: Path) -> None:
    mind, server = _routines_mind(tmp_path, [_say("¿Cuáles?"), _say("Ok."), _say("Vale.")])
    mind.routines = [ORDER]
    mind.decide(1, "sube el volumen de los altavoces")  # inside a longer sentence: the person's own words
    assert server.bodies[0]["messages"][-1]["content"] == "sube el volumen de los altavoces"
    mind.decide(2, "altavoces")  # the answer to BAXY's question
    assert server.bodies[1]["messages"][-1]["content"] == "altavoces"
    mind.decide(3, "altavoces", None, [("altavoces", 0.3)])  # the ear was unsure of the word
    assert server.bodies[2]["messages"][-1]["content"] == "altavoces"


def test_fired_and_ordered_tell_the_two_kinds_apart() -> None:
    assert routines.fired("Baxy, altavoces", [NEXT, ORDER]) is None
    assert routines.ordered("Baxy, altavoces", [NEXT, ORDER]) == ("altavoces", "Altavoces", "cambia a los altavoces Vantor")
    assert routines.ordered("siguiente", [NEXT, ORDER]) is None and routines.fired("siguiente", [NEXT, ORDER]) == "siguiente"
    assert routines.ordered("altavoces", [{**ORDER, "active": False}]) is None


def test_no_routines_no_note(tmp_path: Path) -> None:
    mind, server = _routines_mind(tmp_path, [_say("Hola.")])
    mind.routines = []
    mind.decide(1, "hola")
    assert all("rutinas" not in str(m.get("content")) for m in server.bodies[0]["messages"])


@pytest.mark.parametrize(("text", "folded"), [("¡Audio, ya!", "audio ya"), ("  Pantálla   IZQUIERDA ", "pantalla izquierda"),
                                              ("...", "")])
def test_fold_is_the_stores(text: str, folded: str) -> None:
    assert routines.fold(text) == folded  # as LocalRoutineStore.Folded (RoutinesHandlerTests)
