"""REM4 (REV14 A-R1, A-R2, A-R3): what the fifth blind review found in the questions about the routines and in the
model's «sí» before 1.5.0: what BAXY asks is exactly what is done."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_routine_guide import _guide_mind

WAKE = {"id": "r-000010", "name": "despertar", "trigger": {"at": "07:00", "repeat": "daily", "days": []},
        "active": True, "steps": [{"say": "buenos días, toma tus pastillas"}]}
NIGHT = {"id": "r-000011", "name": "buenas noches", "trigger": {"phrase": "buenas noches"}, "active": True,
         "steps": [], "order": "apaga la luz del cuarto"}


def _asked(act: str = "delete", targets: tuple[str, ...] = ("despertar",), lang: str = "es") -> routine_guide.Guide:
    return routine_guide.Guide(lang=lang, step="confirm_all", mode="all", act=act, targets=targets)


def _change(lang: str = "es") -> routine_guide.Guide:
    guide = routine_guide.Guide.changing(NIGHT, lang, "order")
    guide.answer("apaga todas las luces", [WAKE, NIGHT], False, None)
    assert guide.step == "confirm"
    return guide


# ---------------------------------------------------------------------------------------------------------------------
# A-R1: to «¿Borro…?» and «¿La cambio?» only a plain «sí» or the question's own verb is its «sí»
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["guárdala", "guárdalo", "guarda", "sí, guárdala", "Guárdala, por favor",
                                  "mejor guárdala", "desactívalas", "sí, desactívalas", "cámbiala", "sí, cámbiala",
                                  "guárdalas", "la otra", "sí, la otra", "sí, pero mañana"])
@pytest.mark.parametrize("targets", [("despertar",), ("despertar", "buenas noches")])
def test_another_verb_to_shall_i_delete_deletes_nothing(said: str, targets: tuple[str, ...]) -> None:
    guide = _asked(targets=targets)
    assert guide.answer(said, [WAKE, NIGHT], False, None)[1] is None


@pytest.mark.parametrize("said", ["no, guárdala", "no, mejor guárdala"])
def test_no_keep_it_to_shall_i_delete_is_its_no(said: str) -> None:
    assert _asked().answer(said, [WAKE, NIGHT], False, None) == ("No borré nada.", None, True)


@pytest.mark.parametrize("said", ["sí", "Sí.", "dale", "hazlo", "ok", "vale", "de acuerdo", "está bien", "claro que sí",
                                  "sí, por favor", "bórrala", "Bórrala", "sí, bórrala", "dale, bórrala po", "bórrala, sí",
                                  "bórrela", "borra", "sí, hazlo", "adelante"])
def test_the_plain_yes_and_its_own_verb_still_delete(said: str) -> None:
    assert _asked().answer(said, [WAKE, NIGHT], False, None) == ("", {"action": "delete", "name": "despertar"}, True)


@pytest.mark.parametrize("said", ["sí, todas", "bórralas", "sí, bórralas todas", "dale"])
def test_every_routine_still_deleted_by_its_yes(said: str) -> None:
    guide = _asked(targets=("despertar", "buenas noches"))
    assert guide.answer(said, [WAKE, NIGHT], False, None)[1] == {"action": "delete", "name": "despertar"}


@pytest.mark.parametrize(("said", "done"), [("yes", True), ("delete it", True), ("yes, delete it", True),
                                            ("go ahead", True), ("save it", False), ("yes, save it", False),
                                            ("turn them off", False)])
def test_in_english_its_verb_and_not_save(said: str, done: bool) -> None:
    arguments = _asked(lang="en").answer(said, [WAKE, NIGHT], False, None)[1]
    assert (arguments is not None) == done


@pytest.mark.parametrize(("said", "done"), [("sí", True), ("cámbiala", True), ("sí, cámbiala", True), ("dale", True),
                                            ("guárdala", False), ("bórrala", False), ("sí, desactívala", False)])
def test_shall_i_change_it_takes_its_yes_or_its_verb_only(said: str, done: bool) -> None:
    arguments = _change().answer(said, [WAKE, NIGHT], False, None)[1]
    assert (arguments == {"action": "change", "name": NIGHT["id"], "order": "apaga todas las luces"}) == done


@pytest.mark.parametrize("said", ["guárdala", "sí, guárdala", "sí"])
def test_creating_still_saves_with_guardala(said: str) -> None:
    guide = routine_guide.Guide(step="confirm", kind="word", phrase="hora de leer", order="pon música tranquila")
    assert guide.answer(said, [], False, None)[1] == {"action": "create", "phrase": "hora de leer",
                                                     "order": "pon música tranquila"}


def test_guardala_to_borro_through_the_mind_deletes_nothing_and_asks_again(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    asked = mind.decide(1, "borra la rutina 07:00")
    assert asked["reply"] == "¿Borro tu rutina «despertar»?"
    kept = mind.decide(2, "guárdala")
    assert kept["kind"] == "conversation" and kept["reply"].endswith("¿Borro tu rutina «despertar»?")
    done = mind.decide(3, "sí, bórrala")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": WAKE["id"]}
    assert server.bodies == []


# ---------------------------------------------------------------------------------------------------------------------
# A-R2: two routines at one clock: the one asked about is the one acted on
# ---------------------------------------------------------------------------------------------------------------------

PILL = {"id": "r-000012", "name": "07:00", "trigger": {"at": "07:00", "repeat": "daily", "days": []}, "active": True,
        "steps": [{"say": "toma la pastilla"}]}


def test_a_name_is_looked_for_as_a_name_over_the_whole_list_first() -> None:
    assert routine_guide.find("07:00", [WAKE, PILL]) is PILL
    assert routine_guide.find("despertar", [WAKE, PILL]) is WAKE
    assert routine_guide.find("7:00", [WAKE]) is WAKE


@pytest.mark.parametrize("said", ["borra la rutina 07:00", "desactiva la rutina 07:00", "cambia la rutina 07:00",
                                  "borra la rutina 7:00"])
def test_a_name_two_routines_answer_to_asks_which_before_anything(tmp_path: Path, said: str) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, PILL])
    asked = mind.decide(1, said)
    assert asked["kind"] == "conversation" and asked["reply"] == "¿Cuál de tus rutinas? Tienes: «despertar» y «07:00»."
    assert server.bodies == []


def test_the_one_chosen_by_its_name_is_asked_and_its_yes_deletes_that_one(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, PILL])
    mind.decide(1, "borra la rutina 07:00")
    asked = mind.decide(2, "07:00")
    assert asked["reply"] == "¿Borro tu rutina «07:00»?"
    done = mind.decide(3, "sí")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": PILL["id"]}
    mind, server = _guide_mind(tmp_path, [], [WAKE, PILL])
    mind.decide(1, "desactiva la rutina 07:00")
    done = mind.decide(2, "despertar")
    assert done["kind"] == "action" and done["arguments"] == {"action": "disable", "name": "despertar"}


def test_one_routine_at_that_clock_is_asked_by_its_name_as_before(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    assert mind.decide(1, "borra la rutina 07:00")["reply"] == "¿Borro tu rutina «despertar»?"
    mind, server = _guide_mind(tmp_path, [], [WAKE, NIGHT])
    done = mind.decide(1, "borra la rutina despertar")
    assert done["kind"] == "action" and done["arguments"] == {"action": "delete", "name": "despertar"}
