"""The final voice of a computer-use mission, second pass (live 2026-10-07, cu-universal v2 bench).

Two gaps after cu-r7: the App's floor (OperationFloor, used when the mind returns no final) still said «Lo hice en la
aplicación «Reloj»; hay 2: …» / «No pude hacerlo en la aplicación «Configuración».», and «Ya elegí la alarma de las
7:00» passed over a mission that only went to the «Alarma» tab. The App's floor now reads the mind's computer-use data
(operation_floor.v1.json «computerUse»), checked on both sides by tests/data/cu_floor_twins.json. Every situation here
is our own shape of those runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use, llm, operation_floor  # noqa: E402
from baxy_mind.semantic import missions  # noqa: E402

TWINS = json.loads((ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))


def _mission(goal: str, clicks: list[tuple[str, str]], screen: dict, application: str) -> dict:
    return {
        "kind": "operation",
        "operation": "mission.computer.use",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "goal": goal,
            "application": application,
            "reached": True,
            "steps": [
                {"step": index, "operation": "input.visible.click", "label": label, "ok": True, "name": label,
                 "kind": kind, "selected": True, "changed": True}
                for index, (label, kind) in enumerate(clicks, 1)
            ],
            "window": {"title": application, "process": "ApplicationFrameHost"},
            "joined": False,
            "screen": screen,
        },
    }


ALARM = _mission("ir a alarma", [("Alarma", "ListItem")], {
    "title": "Reloj",
    "values": [{"name": "Alarma", "state": "selected"}],
    "numbers": ["EDITAR ALARMA, Buenos días, 7\u200e:\u200e00\u200e, Diariamente,", "7:00"],
    "lines": ["7:00", "Buenos días"],
}, "Reloj")
DESIGN = _mission("ir a la pestaña diseño", [("Documento en blanco", "ListItem"), ("Diseño", "TabItem")], {
    "title": "Documento1 - Word",
    "values": [{"name": "Diseño", "state": "selected"}],
    "lines": ["Títulos", "Colores", "Fuentes"],
}, "Word")
PENCIL = _mission("seleccionar el lápiz", [("Lápiz", "Button")], {"title": "Sin título: Paint"}, "Paint")


def _mission_defect(text: str, situation: dict) -> str | None:
    folded = llm._accent_folded_with_punctuation(text)
    return computer_use.mission_defect(folded, computer_use.project_seen(situation["observed"], "es"))


def _defect(text: str, situation: dict, said: str = "") -> str:
    return llm.compose_visible_defect(text, "status", said, {"situation": json.dumps(situation, ensure_ascii=False)})


@pytest.mark.parametrize("draft", [
    "Ya elegí la alarma de las 7:00.",
    "Listo, seleccioné la alarma de las 7:00 en el Reloj.",
    "Escogí la alarma «Buenos días».",
    "Ya estoy en Alarma y elegí la de las 7:00.",
])
def test_a_navigation_never_claims_a_pick_inside_the_place(draft: str) -> None:
    assert _defect(draft, ALARM) == "extra_claim"


def test_a_navigation_never_claims_an_act_in_the_present_or_the_future() -> None:
    # Live v6 «en Word andá a la pestaña Diseño»: the mission opened a blank document and clicked the tab.
    assert _defect("Ya estoy en la pestaña Diseño y ahora selecciono Títulos.", DESIGN) == "extra_claim"
    assert _mission_defect("Ya estoy en Diseño; voy a elegir Títulos.", DESIGN) == "extra_claim"
    assert _defect("Ya estoy en Alarma y ahora pongo la de las 7:00.", ALARM) == "extra_claim"
    assert _mission_defect("Ya estoy en Alarma; voy a cambiar la de las 7:00.", ALARM) == "extra_claim"
    said = "in the clock go to alarm"
    assert _defect("Done, I selected the 7:00 alarm.", ALARM, said) == "extra_claim"
    assert _mission_defect("I'm in Alarm and I'll pick the 7:00 one.", ALARM) == "extra_claim"
    # The arrival alone, or an act offered, is not a claim.
    assert _defect("Ya estoy en la pestaña Diseño.", DESIGN) == ""
    assert _defect("Ya estoy en la pestaña Diseño; si quieres, selecciono Títulos.", DESIGN) == ""
    assert _defect("I'm in Alarm now.", ALARM, said) == ""


@pytest.mark.parametrize("draft", [
    "Ya estoy en Alarma y veo la de las 7:00.",
    "Listo, seleccioné la pestaña Alarma.",
    "Elegí «Alarma» en el Reloj.",
    "Ya estoy en Alarma; no elegí ninguna alarma.",
])
def test_a_navigation_may_say_the_place_it_picked(draft: str) -> None:
    assert _defect(draft, ALARM) == ""


def test_a_real_pick_still_passes() -> None:
    assert _defect("Listo, elegí el lápiz.", PENCIL) == ""
    assert _defect("Listo, elegí el lápiz en Paint.", PENCIL) == ""


def test_the_change_claims_of_r7_stay_vetoed() -> None:
    assert _defect("Listo, puse la alarma de las 7:00.", ALARM) == "extra_claim"
    assert _defect("Ya activé la alarma de las 7:00.", ALARM) == "extra_claim"


@pytest.mark.parametrize("case", TWINS["cases"], ids=lambda case: case["id"])
def test_the_twin_fixture_is_what_the_mind_says(case: dict) -> None:
    # The C# OperationFloor reads the same fixture (ComputerUseFloorTests.TheAppSaysWhatTheMindSays).
    assert llm._deterministic_final(case["situation"], {}, "", "es") == case["es"]
    assert llm._deterministic_final(case["situation"], {}, "", "en") == case["en"]


def test_the_floor_data_is_the_mind_s_own() -> None:
    data = operation_floor.floor_data()["computerUse"]
    # The App splits the question off the goal with the marker the mission reader writes.
    assert data["questionMark"] == missions.QUESTION_MARK
    assert computer_use._STOP_CAUSES is data["causes"]
    for said in data["causes"].values():
        assert set(said) == {"es", "en"} and "operaci" not in said["es"] and "operation" not in said["en"]


def test_a_value_the_window_marks_without_a_click_is_not_the_missions_pick() -> None:
    # Live v6: Word marks its default style «Títulos»; the mission only went to the tab «Diseño».
    marked = _mission("ir a la pestaña diseño", [("Documento en blanco", "ListItem"), ("Diseño", "TabItem")], {
        "title": "Documento1 - Word",
        "values": [{"name": "Diseño", "state": "selected"}, {"name": "Títulos", "state": "selected"}],
    }, "Word")
    assert _mission_defect("Ya estoy en la pestaña Diseño y ahora selecciono Títulos.", marked) == "extra_claim"
    assert _mission_defect("Ya elegí Títulos en Word.", marked) == "extra_claim"
    assert _mission_defect("Ya estoy en la pestaña Diseño.", marked) is None
