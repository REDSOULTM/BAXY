"""RUT17 (VIVO22, 14-11, Esencial: the owner's routine made again while the same one was kept was saved as «10:00 (2)»,
and nobody was told): when the routine BAXY repeats for their «sí» already is one of theirs (the same time, days and text,
compared by form), BAXY says so by its name and asks whether to save another one; their «sí» saves it, their «no» does
not. Nothing is saved twice in silence."""
from __future__ import annotations

from pathlib import Path

from test_mind_int36g_rutina_por_hora import _opened
from test_mind_rut14_rutinas import CREATE, FIRST, REPEATED, SAVED, TEXT, TIMED, _read

TWIN = (f"Ya tienes una rutina igual, «10:00»: los lunes, miércoles y viernes a las 10:00 de la mañana, te digo: «{TEXT}». "
        "¿Guardo otra igual?")
OTHER = {**SAVED, "id": "r-00000c", "name": "20:00", "trigger": {"at": "20:00", "repeat": "days", "days": ["sat"]},
         "steps": [{"say": "Riega las plantas"}]}


def test_the_same_routine_again_is_said_by_the_one_they_have(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "new"}], [TIMED], routines=[OTHER, SAVED])
    asked = mind.decide(1, FIRST)
    assert asked["kind"] == "conversation" and asked["reply"] == TWIN


def test_their_yes_saves_another_one_and_their_no_does_not(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path / "si", [{"a": "new"}], [TIMED], routines=[SAVED])
    mind.decide(1, FIRST)
    saved = mind.decide(2, "sí")
    assert saved["kind"] == "action" and saved["arguments"] == CREATE
    mind, _ = _opened(tmp_path / "no", [{"a": "new"}], [TIMED], routines=[SAVED])
    mind.decide(1, FIRST)
    left = mind.decide(2, "no")
    assert left["kind"] == "conversation" and left["operation"] is None and mind._guide is None


def test_said_in_one_breath_too(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [], [], routines=[SAVED])
    asked = mind.decide(1, f"Todos los lunes, miércoles y viernes a las 10 de la mañana dime «{TEXT}».")
    assert asked["kind"] == "conversation" and asked["reply"] == TWIN


def test_another_text_days_or_time_is_no_twin(tmp_path: Path) -> None:
    for name, read in (("texto", _read(trigger="time", hour=10, half="am", repeat="days", days=["mon", "wed", "fri"],
                                      text="Buenas tardes")),
                       ("dias", _read(trigger="time", hour=10, half="am", repeat="days", days=["mon", "wed"], text=TEXT)),
                       ("hora", _read(trigger="time", hour=11, half="am", repeat="days", days=["mon", "wed", "fri"],
                                      text=TEXT))):
        mind, _ = _opened(tmp_path / name, [{"a": "new"}], [read], routines=[SAVED])
        asked = mind.decide(1, FIRST)
        assert asked["kind"] == "conversation" and "Ya tienes" not in asked["reply"], name
    mind, _ = _opened(tmp_path / "igual", [{"a": "new"}], [TIMED], routines=[OTHER])
    assert mind.decide(1, FIRST)["reply"] == REPEATED
