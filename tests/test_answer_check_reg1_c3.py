"""REG1, C-3 of REV11 (the rule of ACT1 «unchecked_update»): «al día / la última versión» of anything was taken as BAXY's
(REV11's battery, tmp\\REV11\\zonas\\C\\casos.py act1: 6 of 7 flagged, 0 on int31-cand), and its note keeps the tools,
among them baxy.update, whose install downloads the installer before the person's yes.
- The second person («tienes / estás / you're») and the impersonal form («no hay una versión más nueva») are of BAXY only
  when the sentence names BAXY, or the person asked BAXY of itself (names it, or «¿estás al día?», «are you up to date?»)
  and no reading of the turn completed (a task list, a game's state: it may be what they tell).
- «al día con / hasta / en / on / with …» tells of what: of something else, it is not BAXY's version, in any person."""
from __future__ import annotations

import pytest

from baxy_mind.answer_check import check
from test_answer_check import _r

TASKS = {"status": "completed", "verification": "output_only", "observed": {"tasks": [], "total": 0}}
GAME = {"status": "completed", "verification": "output_only", "observed": {"name": "Juego", "updateRequired": False}}
TIME = {"status": "completed", "verification": "output_only", "observed": {"local": "2026-11-10T19:05:00-03:00"}}


def _flagged(answer: str, request: str, receipts: list | None = None) -> bool:
    receipts = receipts or []
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return any(f["rule"] == "unchecked_update" for f in check(answer, request, receipts, session))


# REV11 battery FP1-FP5, FP7, and their kin.
@pytest.mark.parametrize(("answer", "request_", "receipts"), [
    ("Sobre noticias no tengo nada en vivo, pero estoy al día hasta mi entrenamiento.",
     "¿Estás al día con las noticias?", []),
    ("Según la hoja que leíste, estás al día con tus pagos.", "¿Debo algo?", []),
    ("Sí, tienes la última versión de Chrome.", "¿Mi Chrome está actualizado?", []),
    ("Estás al día: no te queda ninguna tarea.", "¿Me queda alguna tarea?", [_r("task.list", TASKS)]),
    ("Tienes la última versión del juego instalada.", "¿Hollow Knight está actualizado?", [_r("game.status", GAME)]),
    ("You're up to date on your payments.", "Do I owe anything?", []),
    ("Yes, you have the latest version of Firefox.", "Is my Firefox up to date?", []),
    ("No hay una versión más nueva de ese programa por ahora.", "¿Salió algo nuevo de mi editor?", []),
    ("Estás al día: ya no te queda nada pendiente.", "¿Tengo pendientes para hoy?", [_r("task.list", TASKS)]),
])
def test_up_to_date_of_something_else_is_no_finding(answer: str, request_: str, receipts: list) -> None:
    assert not _flagged(answer, request_, receipts)


# What ACT1 caught stays caught.
@pytest.mark.parametrize(("answer", "request_", "receipts"), [
    ("Sí, estoy al día.", "¿Estás al día?", []),
    ("Yes, I'm up to date. I checked and there's no newer version of me available.", "are you up to date?", []),
    ("Tienes la última versión de BAXY.", "are you up to date?", []),
    ("No hay una versión más nueva: estás en la 1.4.2.", "are you up to date?", []),
    ("You're on the latest version.", "are you up to date?", []),
    ("Sí, tienes la última.", "baxy tienes la ultima version?", []),
    ("Sí, estás en la última versión.", "che, ¿vos tenés la última versión o ya salió otra?", []),
    ("No hay versión más nueva de BAXY.", "¿Estás al día?", [_r("system.time", TIME)]),
    ("Estoy al día.", "¿Me queda alguna tarea?", [_r("task.list", TASKS)]),  # BAXY of itself, whatever was read
    ("Estoy al día con las actualizaciones.", "¿Estás al día?", []),
])
def test_up_to_date_of_baxy_with_no_look_stays(answer: str, request_: str, receipts: list) -> None:
    assert _flagged(answer, request_, receipts)


def test_the_fact_names_the_look_that_only_asks() -> None:
    fact = next(f["fact"] for f in check("Sí, estoy al día.", "¿Estás al día?", [], [])
                if f["rule"] == "unchecked_update")
    assert "baxy_update" not in fact or "check" in fact
    named = next(f["fact"] for f in check("Sí, estoy al día.", "¿Estás al día?", [], [], wire_of=lambda op: "baxy_update")
                 if f["rule"] == "unchecked_update")
    assert "baxy_update" in named and "«check»" in named and "install" not in named
