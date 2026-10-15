"""Encargo H1 (2026-10-12): finals that told what did not happen or denied what did, in both tandas on redpc over
fable/estab-fase3 0650deac3 (cu-v3/tandas_fin1_redpc, tandas_fin2_redpc). The situations are the real ones of each run
(tests/data/h1_finales_payloads.json, from compose_audit.jsonl); each fix is checked on both runs and has its contracase.

1. t4-c04 t3 «pon el modo oscuro» over a Configuración that already showed «Oscuro»: «Lo hice en la aplicación…».
2. t3-c18 t2 «elegí el modo Programador» after a click that only opened the navigation, «Programador» already chosen.
3. t2-c04 t4 «regresa la escala a 100» over «100% (recomendado)» already chosen: «la pantalla todavía no muestra…»;
   t2-c04 t3 «regresala como estaba» after a change that never happened: «no hay un control para revertir».
4. t2-c03 t2 the closed window named from the request («Configuración de Valorant»).
6. t3-c02 t1 Excel started by the mission and never said.
(5, t4-c06, is the App's: ComputerUseLoopTests.H1TheNewWorkbookNamedLikeARecentFileIsTheMissions.)
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use_finals, cu_finals, llm, operation_floor  # noqa: E402
from baxy_mind.cu_projection import describe_step, project_seen  # noqa: E402

CASES = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "h1_finales_payloads.json").read_text(encoding="utf-8"))["cases"]}
RUNS = ("fin1", "fin2")


def _case(name: str, run: str) -> dict:
    return copy.deepcopy(CASES[f"{name}-{run}"])


def _mission(situation: dict) -> dict:
    return situation if situation.get("operation") == "mission.computer.use" else situation["reason"]


# ------------------------------------------------------------------ 1-3. an option already chosen is told as it was


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("name", ["dark-mode-already", "programmer-already", "scale-already-100"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_an_option_no_act_chose_is_told_as_already_chosen(name: str, run: str, language: str) -> None:
    case = _case(name, run)
    situation = case["situation"]
    said = computer_use_finals._computer_use_floor_first(situation, language)
    assert said == case[language]
    # The last resort says the same, never the published «Lo hice…», «elegí…» or «todavía no muestra…».
    assert cu_finals.floor_sentence(situation["observed"], language == "en", True) == case[language]
    assert said != case["published"]


@pytest.mark.parametrize("run", RUNS)
def test_a_click_on_the_option_chose_it(run: str) -> None:
    """Contracase: a verified click on the option itself is an act that may have chosen it."""

    situation = _case("dark-mode-already", run)["situation"]
    situation["observed"]["steps"].append({
        "step": 2, "operation": "input.visible.click", "label": "Oscuro", "ok": True, "name": "Oscuro",
        "kind": "RadioButton", "changed": True,
    })
    assert "ya estaba" not in computer_use_finals._computer_use_floor_first(situation, "es")
    assert cu_finals._held_before_acting(situation["observed"]) == ""


@pytest.mark.parametrize("run", RUNS)
def test_a_click_that_did_not_bring_the_option_into_view_may_have_chosen_it(run: str) -> None:
    """Contracase: the navigation click is no reveal unless the option came into view with it."""

    observed = _case("programmer-already", run)["situation"]["observed"]
    observed["steps"][-1]["appeared"] = ["cerrar navegacion"]
    assert cu_finals._held_before_acting(observed) == ""
    # A click that switched or selected something chose it too.
    observed = _case("programmer-already", run)["situation"]["observed"]
    observed["steps"][-1]["selected"] = True
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_a_text_that_reached_the_field_may_have_chosen_the_value(run: str) -> None:
    """Contracase: the typing that failed (input_entry_not_found) chose nothing; one that went through may have."""

    observed = _case("scale-already-100", run)["situation"]["observed"]
    typed = next(step for step in observed["steps"] if step["operation"] == "input.text.type")
    typed.update(ok=True)
    typed.pop("error", None)
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_an_application_already_open_is_not_said_opened(run: str) -> None:
    situation = _case("dark-mode-already", run)["situation"]
    situation["observed"]["steps"][0]["alreadyRunning"] = True
    assert computer_use_finals._computer_use_floor_first(situation, "es") == "«Oscuro» ya estaba elegido en «Configuración»."


def test_a_failed_typing_is_told_as_tried() -> None:
    observed = _case("scale-already-100", "fin1")["situation"]["observed"]
    seen = project_seen(observed, "es")
    assert "intentó escribir «100»" in seen["stepsFailed"]
    assert not any("escribió «100»" == item for item in seen["stepsFailed"])
    # Contracase: a text whose keys went (effect uncertain) was typed.
    assert describe_step({"operation": "input.text.type", "ok": False, "effectUncertain": True, "text": "x"}, "es") == (
        "escribió «x»")


# ------------------------------------------------------------------ 6. the application the mission started is said


@pytest.mark.parametrize("run", RUNS)
def test_the_application_the_mission_started_is_said(run: str) -> None:
    case = _case("excel-opened-not-said", run)
    situation = case["situation"]
    seen = project_seen(_mission(situation)["observed"], "es")
    assert seen["stepsDone"] == ["abrió «Excel»"]
    # The published final left it out; a final that says it passes.
    assert computer_use_finals._claims_defect(case["published"], "error", situation) == "unstated_effect"
    told = "Abrí Excel, pero no pude seleccionar la fila 1: está en su pantalla de inicio, sin ningún documento abierto."
    assert computer_use_finals._claims_defect(told, "error", situation) == ""
    # The floor says it too, before what it could not do.
    floor = cu_finals.floor_sentence(_mission(situation)["observed"], False, False)
    assert floor.startswith("Abrí «Excel», pero no pude hacerlo: ")
    assert cu_finals.floor_sentence(_mission(situation)["observed"], True, False).startswith(
        "I opened «Excel», but I couldn't do it: ")


@pytest.mark.parametrize("run", RUNS)
def test_an_application_already_running_owes_no_opening(run: str) -> None:
    """Contracase: brought to the front, it was not opened; «Llegué a Excel…» says nothing false."""

    case = _case("excel-opened-not-said", run)
    situation = case["situation"]
    _mission(situation)["observed"]["steps"][0]["alreadyRunning"] = True
    assert project_seen(_mission(situation)["observed"], "es")["stepsDone"] == ["trajo la aplicación al frente"]
    assert computer_use_finals._claims_defect(case["published"], "error", situation) == ""
    assert cu_finals.floor_sentence(_mission(situation)["observed"], False, False).startswith("No pude hacerlo en «Excel»")


# ------------------------------------------------------------------ 4. the closed window named as Windows wrote it


def _with_closed_title(situation: dict, title: str | None) -> dict:
    steps = []
    for raw in situation["steps"]:
        step = json.loads(raw)
        if step["operation"] == "app.close" and title is not None:
            step["observed"]["title"] = title
        steps.append(json.dumps(step, ensure_ascii=False))
    return {**situation, "steps": steps}


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("language", ["es", "en"])
def test_a_verified_close_is_said_by_the_floor_with_the_closed_windows_title(run: str, language: str) -> None:
    case = _case("close-named-from-request", run)
    situation = _with_closed_title(case["situation"], "Configuración")
    assert operation_floor.tells_first(situation)
    said = operation_floor.floor_final(situation, language == "en")
    assert said == ("Cerré la ventana «Configuración»." if language == "es" else "I closed the window «Configuración».")
    assert "Valorant" not in said


@pytest.mark.parametrize("run", RUNS)
def test_a_close_whose_receipt_names_no_window_names_none(run: str) -> None:
    """Contracase: the receipt as it was (no title): the floor says the close, and nothing from the request."""

    situation = _case("close-named-from-request", run)["situation"]
    assert operation_floor.floor_final(situation, False) == "Cerré la ventana."


# ------------------------------------------------------------------ 3. an undo of a change that never happened


class _Writer(llm.LlmRuntime):
    """Any call to the model fails the test: the floor answers."""

    def __init__(self) -> None:  # noqa: D107
        self._gguf = None
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        return {"choices": [{"message": {"content": json.dumps(
            {"answer": "No la he hecho: no hay un control para revertir la escala en la pantalla actual."})},
            "finish_reason": "stop"}]}


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("language", ["es", "en"])
def test_an_undo_after_a_change_told_not_done_is_said_by_the_floor(run: str, language: str) -> None:
    case = _case("scale-failed-before-undo", run)
    history = [
        {"role": "user", "content": "abre configuracion y ve a pantalla"},
        {"role": "assistant", "content": "Listo, estoy en «pantalla»."},
        {"role": "user", "content": case["said"]},
        {"role": "assistant", "content": case["published"]},
    ]
    writer = _Writer()
    reply, _ = writer.chat(
        "no espera se ve muy grande, regresala como estaba", history=history, conversation_kind="knowledge",
        response_language=language, temperature=0.0,
    )
    assert reply == operation_floor.floor_data()["heldFact"][language]["undoUnapplied"]
    assert writer.sent == []
    assert "como estaba" not in reply and "as it was" not in reply


def test_an_undo_after_a_change_told_done_is_still_the_writers() -> None:
    """Contracase: after «Listo, puse la escala en 125 %.» the undo is no «nothing changed»."""

    writer = _Writer()
    history = [
        {"role": "user", "content": "ahi ponle la escala en 125"},
        {"role": "assistant", "content": "Listo, puse la escala en 125 %."},
    ]
    reply, _ = writer.chat(
        "no espera se ve muy grande, regresala como estaba", history=history, conversation_kind="knowledge",
        response_language="es", temperature=0.0,
    )
    assert writer.sent
    assert reply != operation_floor.floor_data()["heldFact"]["es"]["undoUnapplied"]


def test_a_text_the_look_read_cut_is_told_as_tried() -> None:
    """Encargo K (banco def1 x8): «125+75» typed by the keyboard, the Calculator got «25+75»; the App's look marks the
    step («arrived» false) and the final never says it was typed. Contracase: the same step without the mark."""

    step = {"operation": "input.text.type", "text": "125+75", "ok": True, "method": "keyboard",
            "appeared": ["la expresion es 25 +", "se muestra 75"]}
    whole = describe_step(dict(step), "es")
    step["arrived"] = False
    assert describe_step(step, "es") == "intentó escribir «125+75»"
    assert describe_step(step, "en") == "tried to type «125+75»"
    assert whole == "escribió «125+75»"
