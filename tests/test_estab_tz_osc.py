"""Encargo TZ-OSC (tandas z3/z4 del notebook, fable/estab-fase3 a99fa5bea, t4-c04 t3 «vale y ahora en configuracion pon el
modo oscuro»). La misión escribió «oscuro» en la búsqueda de Configuración, pulsó «Activar el modo oscuro para
aplicaciones» y luego «Oscuro», que quedó elegido («Elige tu modo» = Oscuro). La comprobación lo leyó como eco de la
búsqueda, y la regla de resultados pulsó a continuación «Gris oscuro», «Anaranjado oscuro» y «Menta oscuro», colores de
énfasis que contienen la palabra. El final dijo «no pude hacerlo».

Aquí se prueba la parte de la mente: una vez pulsado el resultado que se llama exactamente así, un nombre que sólo lo
contiene es otra cosa (cu_lookup._result_naming). La parte de la App, que el modo elegido en su lista es prueba de
llegada, está en tests/Baxy.Integration.Tests/ComputerUseTzOscTests.cs. Las vistas y los recibos son los reales,
congelados en tests/data/tz_osc_modo_oscuro.json.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use as cu  # noqa: E402
from baxy_mind import computer_use_finals, cu_model_calls  # noqa: E402
from baxy_mind.cu_lookup import _result_naming  # noqa: E402

FROZEN = json.loads((ROOT / "tests" / "data" / "tz_osc_modo_oscuro.json").read_text(encoding="utf-8"))
NAMES = ["Configuración", "Discord", "Steam", "Bloc de notas"]
STEPS = FROZEN["steps"]
COLOURS = FROZEN["laterClicks"]


def _view() -> dict:
    return copy.deepcopy(FROZEN["views"]["paso4"])


def _decide(history: list[dict], view: dict | None = None, *, objective: str | None = None, goal: str | None = None,
            check: str | None = None) -> dict:
    return cu._decide_step(
        None, objective=objective or FROZEN["objective"], goal=goal or FROZEN["goal"],
        application=FROZEN["application"], success_check=check or FROZEN["successCheck"],
        view=view if view is not None else _view(), history=copy.deepcopy(history), budget_left=8,
        application_names=NAMES, subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )


def _label(decision: dict) -> str:
    arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
    return str(arguments.get("label") or "") if decision.get("operation") == "input.visible.click" else ""


def test_the_rule_presses_the_option_named_exactly_first() -> None:
    decision = _decide(STEPS[:3])
    assert _label(decision) == "Oscuro"


def test_after_the_option_named_exactly_no_name_that_only_holds_it_is_pressed() -> None:
    # z3/z4 step 5: «Gris oscuro» pressed right after «Oscuro», then «Anaranjado oscuro» and «Menta oscuro».
    assert _label(_decide(STEPS[:4])) not in COLOURS
    pressed = {"step": 5, "operation": "input.visible.click", "rule": True, "label": "Gris oscuro", "name": "Gris oscuro",
               "kind": "ListItem", "ok": True, "selected": True, "awaited": True}
    assert _label(_decide([*STEPS[:4], pressed])) not in COLOURS
    assert _result_naming(_view(), "oscuro", STEPS[:4]) is None


def test_contracase_with_nothing_named_exactly_pressed_a_result_that_holds_the_name_is_still_pressed() -> None:
    # Ronda 25 kept: «Activar el modo oscuro para aplicaciones» was the search's result that led to the page.
    view = _view()
    view["controls"] = [control for control in view["controls"] if control["name"] != "Oscuro"]
    picked = _result_naming(view, "oscuro", STEPS[:3])
    assert picked is not None and _label(picked) in COLOURS


def test_contracase_the_colour_asked_is_pressed() -> None:
    """«poné el color de énfasis menta»: the colour is pressed, also after another option was pressed."""

    typed = [STEPS[0], {**STEPS[1], "text": "menta"}]
    assert _label(_result_naming(_view(), "menta", typed) or {}) == "Menta oscuro"
    assert _label(_result_naming(_view(), "menta", [*typed, STEPS[3]]) or {}) == "Menta oscuro"
    for history in (STEPS[:1], typed, STEPS[:4]):
        decision = _decide(history, objective="poné el color de énfasis menta", goal="seleccionar menta",
                           check="control:menta:selected")
        assert _label(decision) == "Menta oscuro"


def test_the_mode_reached_is_told_reached() -> None:
    # The App's check now holds on the look after «Oscuro» (ComputerUseTzOscTests): the final tells the mode, never
    # «no pude hacerlo».
    observed = {
        "goal": FROZEN["goal"], "application": FROZEN["application"], "reached": True,
        "successCheck": FROZEN["successCheck"], "stepCount": 4, "steps": copy.deepcopy(STEPS),
        "window": {"title": "Configuración", "process": "SystemSettings"}, "joined": False,
        "satisfiedBy": "control:oscuro:selected", "arrivedAs": "Oscuro",
        "screen": {"title": "Configuración", "values": [
            {"name": "Elige tu modo", "value": "Oscuro"}, {"name": "Oscuro", "state": "selected"},
            {"name": "Cuadro de búsqueda, Buscar una opción", "value": "oscuro"}]},
    }
    situation = {"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": observed}
    said = computer_use_finals._computer_use_floor_first(situation, "es")
    assert said == "Listo, estoy en «Oscuro»."
    assert computer_use_finals._computer_use_floor_first(situation, "en") == "Done, I'm in «Oscuro»."
    assert "no pude" in FROZEN["published"] and said != FROZEN["published"]
