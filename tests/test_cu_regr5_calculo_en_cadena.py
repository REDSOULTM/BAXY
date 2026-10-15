"""Regresiones r4 (live v2-c2, 2026-10-08): «en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de
notas» ended on the editor, whose text glued the paste to its own («lista: pan leche144144», over an earlier paste):
no fact held «144», the model's «pegué 144 en el Bloc de notas» was refused as ungrounded and the floor said «Listo,
lo hice en «Calculadora»». The calculation part now carries what its own window showed when it was reached (``numbers`` of its subgoal)."""

from __future__ import annotations

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals


def _observed(with_numbers: bool) -> dict:
    calc = {"goal": "calcular 12*12", "application": "Calculadora", "reached": True, "stepCount": 2,
            "satisfiedBy": "stepDone:input.key.press:enter"}
    if with_numbers:
        calc["numbers"] = ["Se muestra 144", "12 × 12= 144"]
    return {
        "goal": "calcular 12*12; luego apretar ctrl c; luego apretar ctrl v",
        "application": "Calculadora",
        "reached": True,
        "steps": [
            {"step": 1, "operation": "input.text.type", "text": "12*12", "ok": True, "subgoal": 0},
            {"step": 2, "operation": "input.key.press", "key": "enter", "ok": True, "subgoal": 0},
            {"step": 3, "operation": "input.key.press", "key": "ctrl_c", "ok": True, "subgoal": 1},
            {"step": 4, "operation": "input.key.press", "key": "ctrl_v", "ok": True, "subgoal": 2},
        ],
        "window": {"title": "*lista pan: Bloc de notas", "process": "Notepad"},
        "screen": {
            "title": "*lista pan: Bloc de notas",
            "values": [{"name": "Editor de texto", "value": "lista: pan leche144144"}],
            "numbers": ["Línea 2, Columna 9", "19 caracteres.", "UTF-8"],
        },
        "subgoals": [
            calc,
            {"goal": "apretar ctrl c", "application": "Calculadora", "reached": True},
            {"goal": "apretar ctrl v", "application": "Bloc de notas", "reached": True},
        ],
    }


def test_the_value_its_own_window_showed_grounds_the_paste() -> None:
    draft = "Llegué a la calculadora, escribí 12*12, copié el resultado y pegué 144 en el Bloc de notas."
    said = "en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas"
    folded = missions_fold(draft)
    assert cu_reply_checks.ungrounded_word(folded, cu_projection.project_seen(_observed(False), "es"), said) == "144"
    assert cu_reply_checks.ungrounded_word(folded, cu_projection.project_seen(_observed(True), "es"), said) is None


def test_the_floor_tells_the_calculation_of_a_chain_that_ended_elsewhere() -> None:
    assert cu_finals.floor_sentence(_observed(False), False, True) == "Listo, lo hice en «Calculadora»."
    assert "12 × 12 = 144" in cu_finals.floor_sentence(_observed(True), False, True)


def test_a_part_whose_window_showed_another_value_is_not_told_as_calculated() -> None:
    observed = _observed(True)
    observed["subgoals"][0]["numbers"] = ["Se muestra 0", "0 × 9= 0"]
    assert "144" not in cu_finals.floor_sentence(observed, False, True)
