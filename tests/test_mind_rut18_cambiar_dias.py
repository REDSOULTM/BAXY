"""RUT18 D (RUT17's held-out of changes, k10 and k14: «¿Qué cambio de «21:00»: la hora o lo que te digo?» → «los días» →
«¿A qué hora?» → the days again → «¿A qué hora?», in a loop; RUT17: held-out of changes 3 of 16 in Esencial). The change of
«when» asked the hour again and kept the days; days said alone now keep the routine's own time, and only their «sí»
changes it."""
from __future__ import annotations

from pathlib import Path

from test_mind_routine_guide import _guide_mind, _talk

LATE = {"id": "r-0021b0", "name": "21:00", "trigger": {"at": "21:00", "repeat": "days", "days": ["mon", "fri"]},
        "active": True, "steps": [{"say": "Recoge la cocina"}]}


def test_days_said_alone_keep_its_time(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [LATE])
    said = _talk(mind, ["cambia la rutina 21:00", "los días", "los martes y los jueves"])
    assert said[0]["reply"].startswith("¿Qué cambio de «21:00»")
    assert "martes y jueves" in said[2]["reply"] and "9:00 de la noche" in said[2]["reply"]
    assert said[2]["reply"].endswith("¿La cambio?")
    changed = mind.decide(4, "sí")
    assert changed["operation"] == "baxy.routines"
    assert changed["arguments"] == {"action": "change", "name": LATE["id"], "at": "21:00", "repeat": "days",
                                    "days": ["tue", "thu"]}
    assert server.bodies == []


def test_a_new_hour_said_is_still_taken(tmp_path: Path) -> None:
    mind, _ = _guide_mind(tmp_path, [], [LATE])
    said = _talk(mind, ["cambia la rutina 21:00", "la hora", "a las 22:30"])
    assert "10:30 de la noche" in said[2]["reply"] and "lunes y viernes" in said[2]["reply"]
    assert mind.decide(4, "sí")["arguments"] == {"action": "change", "name": LATE["id"], "at": "22:30",
                                                 "repeat": "days", "days": ["mon", "fri"]}
