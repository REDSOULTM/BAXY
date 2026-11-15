"""RUT17 (INT37B's blind held-out, changing a routine's time 0 of 6 in every arm): «La de las seis y media de la mañana,
pásala a las siete…» → the model called baxy_routines, the closed read said «change» of «06:30», and BAXY asked «¿Qué
cambio de «06:30»: la hora o lo que te digo?» though they had said it. What the order already says of the change (its
time, its days or its text) is read as RUT14 reads a new routine, each value checked against their words, and used:
BAXY asks only what is missing (the half of the day) or repeats the change for their «sí»."""
from __future__ import annotations

from pathlib import Path

from test_mind_int36g_rutina_por_hora import _opened
from test_mind_rut14_rutinas import _read

EARLY = {"id": "r-0006a0", "name": "06:30", "trigger": {"at": "06:30", "repeat": "daily"}, "active": True,
         "steps": [{"say": "Arriba, que llegas tarde"}]}
LATE = {"id": "r-0021b0", "name": "21:00", "trigger": {"at": "21:00", "repeat": "days", "days": ["mon", "fri"]},
        "active": True, "steps": [{"say": "Recoge la cocina"}]}


def test_the_time_said_in_the_order_is_taken(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "21:00"}], [_read(hour=21, minute=30)], routines=[EARLY, LATE])
    asked = mind.decide(1, "Cambia la de las 21:00 a las 21:30, que antes no me da tiempo.")
    assert asked["kind"] == "conversation" and "¿Qué cambio" not in asked["reply"]
    assert asked["reply"].startswith("«21:00» quedará así:") and "9:30 de la noche" in asked["reply"]
    assert "Recoge la cocina" in asked["reply"] and asked["reply"].endswith("¿La cambio?")
    changed = mind.decide(2, "sí")
    assert changed["kind"] == "action" and changed["operation"] == "baxy.routines"
    assert changed["arguments"] == {"action": "change", "name": LATE["id"], "at": "21:30", "repeat": "days",
                                    "days": ["mon", "fri"]}


def test_a_time_without_its_half_asks_only_the_half(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "06:30"}], [_read(hour=7)], routines=[EARLY, LATE])
    asked = mind.decide(1, "La de las seis y media, pásala a las siete, que madrugo demasiado.")
    assert asked["kind"] == "conversation" and "¿Qué cambio" not in asked["reply"]
    assert "7" in asked["reply"] and "mañana" in asked["reply"] and "tarde" in asked["reply"]
    confirm = mind.decide(2, "de la mañana")
    assert "7:00 de la mañana" in confirm["reply"] and confirm["reply"].endswith("¿La cambio?")
    changed = mind.decide(3, "sí")
    assert changed["arguments"] == {"action": "change", "name": EARLY["id"], "at": "07:00", "repeat": "daily"}


def test_a_time_not_in_their_words_is_not_taken(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "06:30"}], [_read(hour=8)], routines=[EARLY, LATE])
    asked = mind.decide(1, "La de las seis y media, pásala a las siete.")
    assert asked["reply"].startswith("¿Qué cambio de «06:30»")


def test_nothing_new_read_asks_what_to_change(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "06:30"}], [_read(hour=6, minute=30, half="am")],
                      routines=[EARLY, LATE])
    assert mind.decide(1, "Quiero cambiar la de las 06:30.")["reply"].startswith("¿Qué cambio de «06:30»")


def test_a_new_text_said_in_the_order_is_taken(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "21:00"}], [_read(text="Friega los platos")], routines=[EARLY, LATE])
    asked = mind.decide(1, "La de las 21:00 que me diga friega los platos.")
    assert "«Friega los platos»" in asked["reply"] and asked["reply"].endswith("¿La cambio?")
    changed = mind.decide(2, "sí")
    assert changed["arguments"] == {"action": "change", "name": LATE["id"], "steps": ["say: Friega los platos"]}


def test_new_days_said_in_the_order_are_taken_and_the_time_kept(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "21:00"}], [_read(repeat="days", days=["tue", "thu"])],
                      routines=[EARLY, LATE])
    asked = mind.decide(1, "La de las 21:00, ponla los martes y los jueves.")
    assert "martes y jueves" in asked["reply"] and "21:00" in asked["reply"] and asked["reply"].endswith("¿La cambio?")
    changed = mind.decide(2, "sí")
    assert changed["arguments"] == {"action": "change", "name": LATE["id"], "at": "21:00", "repeat": "days",
                                    "days": ["tue", "thu"]}


def test_its_own_time_said_without_its_half_names_it_and_is_no_new_time(tmp_path: Path) -> None:
    """RUT17's held-out of changes (k18): «la del domingo a las nueve y cuarto», at 21:15, then the new text: the hour read
    without its half is its own, so the change is of its text, never «¿A las 9:15 de la mañana o de la tarde?»."""
    sunday = {"id": "r-0021c5", "name": "21:15", "trigger": {"at": "21:15", "repeat": "days", "days": ["sun"]},
              "active": True, "steps": [{"say": "Carga el portátil"}]}
    mind, _ = _opened(tmp_path, [{"a": "change", "r": "21:15"}],
                      [_read(hour=9, minute=15, text="mete el cargador en la mochila")], routines=[EARLY, sunday])
    asked = mind.decide(1, "La del domingo a las nueve y cuarto, que me diga mete el cargador en la mochila.")
    assert "mañana o de la tarde" not in asked["reply"] and "«mete el cargador en la mochila»" in asked["reply"]
    assert "9:15 de la noche" in asked["reply"] and asked["reply"].endswith("¿La cambio?")
    changed = mind.decide(2, "sí")
    assert changed["arguments"] == {"action": "change", "name": sunday["id"], "steps": ["say: mete el cargador en la mochila"]}
