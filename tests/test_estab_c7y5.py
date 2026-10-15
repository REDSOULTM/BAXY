"""Encargo C7Y5 (banco final fp, fable/estab-fase3 32dd2d02b).

c7 (Normal): «en Discord andá al canal Cotele y después en Steam andá a la tienda» → la pregunta por entrar al canal
de voz → «no» → «No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló.», y la misión entera se canceló
sin decir que la tienda de Steam quedó sin ir. La cancelación se mantiene; el final dice también los sub-objetivos que
dejó sin hacer (``cancelledGoals``, datos ``cancelledFloor.rest``).

y5 fp3: «Imágenes» del árbol del Explorador pulsado por Invoke quedó elegido sin navegar, el recibo midió el lugar como
movido (``placeMoved`` true) y la mente buscó «imagenes» dentro de Downloads; el final dijo «no vi el control». Un nodo
elegido sin llegada recibe una pulsación más y, si sigue sin llegar, se dice como clic sin efecto. Las vistas y el
recibo son los del journal de ``evidencia_fp3/v2-y5``.
"""

from __future__ import annotations

import copy
import json

from baxy_mind import cu_rules
from baxy_mind import operation_floor
from baxy_mind.llm import LlmRuntime

C7 = "en Discord andá al canal Cotele y después en Steam andá a la tienda"
COTELE = {
    "operation": "input.visible.click", "purpose": "Cumplir exactamente el efecto solicitado.",
    "arguments": {"label": "Cotele!!!😎, Canal de voz, Choche", "index": 60, "window": 919326},
    "worldAct": "call", "actName": "Cotele!!!😎",
}


def _cancelled(goals: list[dict] | None = None) -> dict:
    situation = {
        "kind": "status", "polarity": "success", "cause": "remaining_steps_cancelled", "steps": [],
        "cancelledRequest": C7, "cancelledAction": COTELE,
    }
    return {**situation, "cancelledGoals": goals} if goals is not None else situation


class _Writer(LlmRuntime):
    def __init__(self) -> None:
        self._gguf = None
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        raise TimeoutError("sin presupuesto")


def test_banco_c7_the_cancelled_chain_says_the_store_left_undone() -> None:
    situation = _cancelled([{"goal": "ir a la tienda", "application": "Steam"}])
    assert operation_floor.cancelled_final(situation, False) == (
        "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló y no fui a «tienda» en Steam."
    )
    assert operation_floor.cancelled_final(situation, True) == (
        "I didn't click the button «Cotele!!!😎» because it was cancelled and I didn't go to «tienda» in Steam."
    )
    writer = _Writer()
    composed = writer.compose_user_message("no", "status", {"situation": json.dumps(situation, ensure_ascii=False)})
    assert composed == operation_floor.cancelled_final(situation, False)
    assert writer.requests == []


def test_a_goal_that_is_no_place_is_quoted_and_an_app_its_name_says_is_not_repeated() -> None:
    situation = _cancelled([
        {"goal": "escribir hola en el buscador", "application": "Steam"},
        {"goal": "ir a la tienda de Steam", "application": "Steam"},
    ])
    assert operation_floor.cancelled_final(situation, False) == (
        "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló y no seguí con «escribir hola en el"
        " buscador» en Steam y no fui a «tienda de Steam»."
    )


def test_contracase_a_single_act_chain_is_said_as_before() -> None:
    expected = "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló."
    assert operation_floor.cancelled_final(_cancelled(), False) == expected
    assert operation_floor.cancelled_final(_cancelled([]), False) == expected
    assert operation_floor.cancelled_final(_cancelled([{"goal": "", "application": "Steam"}]), False) == expected


def _downloads_view(images_state: str) -> dict:
    # Journal of evidencia_fp3/v2-y5, 10:38:44.759: Explorer still on «Downloads», the tree's «Imágenes» chosen.
    return {
        "window": {"title": "Downloads - Explorador de archivos", "process": "explorer", "foreground": True,
                   "focused": None, "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [
            {"i": 0, "kind": "RadioButton", "name": "Detalles", "state": "selected readonly", "zone": "BR"},
            {"i": 1, "kind": "TreeItem", "name": "Inicio", "value": "Inicio", "zone": "L"},
            {"i": 2, "kind": "TreeItem", "name": "Galería", "value": "Galería", "zone": "L"},
            {"i": 3, "kind": "TreeItem", "name": "Downloads", "value": "Downloads", "zone": "L"},
            {"i": 4, "kind": "TreeItem", "name": "Documentos", "value": "Documentos", "zone": "L"},
            {"i": 5, "kind": "TreeItem", "name": "Imágenes", "value": "Imágenes", "state": images_state, "zone": "L"},
            {"i": 6, "kind": "TreeItem", "name": "Este equipo", "value": "Este equipo", "state": "expanded", "zone": "L"},
            {"i": 7, "kind": "ListItem", "name": "BAXY-traspaso-2026-09-21", "zone": "C"},
            {"i": 8, "kind": "TabItem", "name": "Downloads", "state": "selected", "zone": "T"},
            {"i": 9, "kind": "SplitButton", "name": "Downloads", "zone": "T"},
            {"i": 10, "kind": "Edit", "name": "Buscar en Downloads", "zone": "TR"},
        ],
        "text": {},
    }


# The receipt of fp3's click (journal 10:38:44.206), as HistoryForMind projects it.
FP3_CLICK = {"step": 2, "operation": "input.visible.click", "label": "Imágenes", "index": 5, "ok": True,
             "kind": "TreeItem", "changed": True, "selected": True, "surfaceChanged": False, "placeMoved": True,
             "method": "invoke"}


def _y5_step(history: list[dict], state: str = "selected focused") -> dict | None:
    return cu_rules.deterministic_step(
        goal="ir a imágenes", view=_downloads_view(state), history=history, application="Explorador de archivos",
        objective="en el Explorador de archivos andá a Descargas y después a Imágenes",
    )


def _looks_up(step: dict | None) -> bool:
    if step is None:
        return False
    label = str((step.get("arguments") or {}).get("label") or "").casefold()
    return step.get("operation") in ("input.text.type", "input.key.press", "input.scroll") or "buscar" in label


def test_banco_fp3_y5_a_chosen_node_measured_as_moved_but_not_arrived_is_pressed_again_never_searched() -> None:
    step = _y5_step([FP3_CLICK])
    assert step is not None and step["operation"] == "input.visible.click", step
    assert step["arguments"]["label"] == "Imágenes" and step["arguments"].get("index") == 5, step
    assert not _looks_up(step)


def test_banco_fp3_y5_pressed_twice_and_still_not_there_is_a_click_without_effect() -> None:
    # The second press on the chosen node gives no place measure (it was chosen already).
    again = {**FP3_CLICK, "step": 3}
    again.pop("placeMoved")
    step = _y5_step([FP3_CLICK, again])
    assert step is not None and step["operation"] == "none" and step["code"] == cu_rules.CLICK_WITHOUT_EFFECT, step


def test_contracases_y5_unmeasured_once_is_the_models_a_node_not_chosen_or_a_surface_change_are_not_pressed_again() -> None:
    unmeasured = {key: value for key, value in FP3_CLICK.items() if key != "placeMoved"}
    assert _y5_step([unmeasured]) is None
    # The node not shown chosen: the arrival's judge never holds it as a chosen place.
    assert cu_rules._chosen_place_click(_downloads_view("")["controls"][5], [FP3_CLICK], _downloads_view(""))[0] is None
    # A press whose surface changed is no held choice either.
    changed = {**FP3_CLICK, "surfaceChanged": True}
    assert cu_rules._chosen_place_click(
        _downloads_view("selected")["controls"][5], [changed], _downloads_view("selected"),
    )[0] is None
