"""RUT18 (CAL1, 10 of 10 in the 1.5.3 and the 1.5.4: «cambia la rutina de las 10:00 a las 11» → «No tengo ninguna rutina
«10 00 a las 11». Tienes: «10:00» y «20:00».», false: there is one at 10:00). The fixed order took the whole rest as the
name, its new time too, and the guide said there was no such routine. A name that is none of theirs by form is now read
as the model's own call of baxy_routines is read (the closed question with their routines by what they are), and only
what that reads as none of them is said to be no routine of theirs."""
from __future__ import annotations

from pathlib import Path

from test_mind_int36g_rutina_por_hora import _opened
from test_mind_rut14_rutinas import _read

TEN = {"id": "r-3a1d09", "name": "10:00", "active": True,
       "trigger": {"at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"]},
       "steps": [{"say": "Buenos días, Leonor, que tengas un gran día"}]}
EIGHT = {"id": "r-126adc", "name": "20:00", "active": True,
         "trigger": {"at": "20:00", "repeat": "days", "days": ["sat"]}, "steps": [{"say": "hora de regar las plantas"}]}


def test_a_change_whose_name_carries_the_new_time_is_read_and_changes_that_one(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [{"a": "change", "r": "10:00"}], [_read(hour=11)], routines=[TEN, EIGHT])
    asked = mind.decide(1, "cambia la rutina de las 10:00 a las 11")
    assert "No tengo ninguna rutina" not in asked["reply"]
    assert len(server.have_asked) == 1
    assert "11" in asked["reply"] and "mañana" in asked["reply"] and "tarde" in asked["reply"]
    confirm = mind.decide(2, "de la mañana")
    assert "11:00 de la mañana" in confirm["reply"] and confirm["reply"].endswith("¿La cambio?")
    changed = mind.decide(3, "sí")
    assert changed["operation"] == "baxy.routines"
    assert changed["arguments"] == {"action": "change", "name": TEN["id"], "at": "11:00", "repeat": "days",
                                    "days": ["mon", "wed", "fri"]}


def test_a_change_read_as_none_of_theirs_still_says_which_they_have(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "other"}], routines=[TEN, EIGHT])
    said = mind.decide(1, "cambia la rutina del gimnasio a las 11")["reply"]
    assert said.startswith("No tengo ninguna rutina") and "«10:00» y «20:00»" in said


def test_a_change_of_a_name_they_have_is_not_read_again(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [], routines=[TEN, EIGHT])
    assert mind.decide(1, "cambia la rutina 20:00")["reply"].startswith("¿Qué cambio de «20:00»")
    assert server.have_asked == []
