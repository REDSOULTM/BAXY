"""REM8 (REV16 R-1, REV14 A-R5): leaving a «¿Borro…?» or a change of a routine without a «sí» told the model the note of
the guide that creates one, «quedó sin guardar… dile que no se guardó»: a falsehood the mind itself asked for. The note
says what happened: nothing was deleted, nothing was changed."""
from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_routine_guide import _guide_mind

SAY = {"choices": [{"message": {"role": "assistant", "content": "Vale."}}]}
# Invented routines: a daily one and one named by its clock.
WAKE = {"id": "r-0000a1", "name": "despertar", "trigger": {"at": "07:00", "repeat": "daily", "days": []}, "active": True,
        "steps": ["say: arriba"]}
PILL = {"id": "r-0000a2", "name": "07:00", "trigger": {"at": "07:00", "repeat": "once", "days": []}, "active": True,
        "steps": ["say: la pastilla"]}


def _note(tmp_path: Path, words: list[str]) -> str:
    mind, server = _guide_mind(tmp_path, [SAY] * 6, [WAKE, PILL])
    for turn, said in enumerate(words, 1):
        mind.decide(turn, said)
    assert mind._guide is None and server.bodies
    notes = [str(m["content"]) for m in server.bodies[-1]["messages"]
             if m.get("role") == "user" and "Nota interna" in str(m["content"]) and "rutina" in str(m["content"])]
    assert len(notes) == 1, notes
    return notes[0]


@pytest.mark.parametrize("words", [["borra la rutina 07:00", "07:00", "pon música relajante por favor"],
                                   ["borra todas mis rutinas", "pon música relajante por favor"]])
def test_leaving_a_delete_question_says_nothing_was_deleted(tmp_path: Path, words: list[str]) -> None:
    note = _note(tmp_path, words)
    assert "no se borró" in note and "guard" not in note and "creando" not in note, note


def test_leaving_a_change_says_nothing_was_changed(tmp_path: Path) -> None:
    note = _note(tmp_path, ["cambia la rutina despertar", "la hora", "pon música relajante por favor",
                            "¿qué tiempo hace mañana en la ciudad?"])
    assert "no se cambió" in note and "guard" not in note and "creando" not in note, note


def test_leaving_a_routine_being_created_still_says_it_was_not_saved(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [SAY] * 6, [WAKE, PILL])
    for turn, said in enumerate(["crea una rutina", "con una palabra", "nube", "pon música",
                                 "¿qué tiempo hace mañana en la ciudad?"], 1):
        mind.decide(turn, said)
    assert any(routine_guide.LEFT_NOTE in str(m.get("content")) for m in server.bodies[-1]["messages"])
