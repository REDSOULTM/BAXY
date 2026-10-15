"""Teclas y clics sin efecto (pasada r9 v3: v3-37, v3-39, v3-16, v3-41, v3-44) con vistas reales congeladas.

Medido: en la Terminal (v3-37, v3-39) y en Fotos (v3-16) la rutina buscó el destino con Ctrl+K; la vista quedó
igual, la rutina siguió con Escape (y Ctrl+F) y la misión paró por «la pantalla dejó de cambiar» sin que el modelo
viera nunca «Nueva pestaña» ni «Editar»; en Fotos el Escape cerró el visor. En v3-37, además, el clic del modelo en
«Nueva pestaña» se rechazó porque el objetivo derivado («ir a nueva de simbolo del sistema») perdió la palabra
«pestaña» que el pedido sí decía. En el Panel de control (v3-41, v3-44) la rutina escribió el nombre en la búsqueda y
pulsó, como «resultado que lo nombra», el enlace «Buscar "…" en Ayuda y soporte técnico de Windows»: la misión acabó
en la ayuda dentro de un navegador. En Recortes (v3-32) el recibo de un clic en una lista dijo «sin cambios» aunque la
vista siguiente la mostraba desplegada, y el modelo repitió el clic fallido sobre «Sin retraso».
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from baxy_mind import computer_use
from baxy_mind import cu_history
from baxy_mind import cu_unasked
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_diagnosis
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt

_DATA = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_teclas.json").read_text(encoding="utf-8"))
APPS = ("Terminal", "Fotos", "Panel de control")


def _view(name: str) -> dict:
    return copy.deepcopy(_DATA[name]["vista"])


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


def _key(step: int, key: str, *, same_view: bool | None = True) -> dict:
    entry = {"step": step, "operation": "input.key.press", "key": key, "ok": True, "changed": True}
    if same_view is not None:
        entry["sameView"] = same_view
    return entry


class _Model:
    """A local model that answers the step with the given acts, in order, and records what it was asked."""

    def __init__(self, *acts: dict) -> None:
        self.acts = list(acts)
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] != cu_step_prompt.STEP_PROMPT:
            return {"es": [], "en": []}
        self.payloads.append(copy.deepcopy(payload))
        return self.acts.pop(0) if self.acts else {"act": "none"}


# ---------------------------------------------------------------- (1) una tecla sin efecto no se sigue con otra


def test_v3_37_a_search_key_that_left_the_terminal_as_it_was_hands_the_step_to_a_visible_control() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    history = [_opened("Terminal"), _key(2, "ctrl_k")]
    step = cu_rules.deterministic_step(goal="ir a nueva de simbolo del sistema", view=terminal, history=history)
    # No Escape and no Ctrl+F after a shortcut that changed nothing: the model chooses among the controls.
    assert step is None


def test_counter_case_a_search_key_whose_effect_is_unknown_keeps_the_old_way() -> None:
    # A receipt without the App's mark (an older shell, or a look taken with the window behind): unchanged behaviour.
    terminal = _view("terminal_tras_ctrl_k")
    history = [_opened("Terminal"), _key(2, "ctrl_k", same_view=None)]
    step = cu_rules.deterministic_step(goal="ir a nueva de simbolo del sistema", view=terminal, history=history)
    assert step is not None and step["operation"] == "input.key.press"


def test_v3_16_photos_viewer_never_gets_escape_nor_ctrl_f_after_a_dead_shortcut() -> None:
    photos = _view("fotos_paisaje_tras_ctrl_k")
    goal = "ir a editor de la imagen que tengo abierta"
    step = cu_rules.deterministic_step(goal=goal, view=photos, history=[_opened("Fotos"), _key(2, "ctrl_k")])
    # The target looked up by its name in the whole window, a click: never another key.
    assert step is not None and step["operation"] == "input.visible.click"
    # The lookup itself: with the receipt the App sent in r9 (no mark) it went on with Ctrl+F (then Escape, which closed
    # the viewer); with the mark it hands the step on.
    target = "editor de la imagen que tengo abierta"
    old = cu_lookup._find_step(target, photos, [_opened("Fotos"), _key(2, "ctrl_k", same_view=None)])
    assert old is not None and old["operation"] == "input.key.press"
    assert cu_lookup._find_step(target, photos, [_opened("Fotos"), _key(2, "ctrl_k")]) is None


def test_v3_37_the_model_after_a_dead_shortcut_presses_new_tab_instead_of_another_key() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    history = [_opened("Terminal"), _key(2, "ctrl_k")]
    model = _Model({"act": "key", "key": "escape"}, {"act": "click", "i": 2})
    decision = computer_use.decide_step(
        model, objective="abrí la terminal y abrí una pestaña nueva de símbolo del sistema",
        goal="ir a nueva de simbolo del sistema", application="Terminal", success_check=None, view=terminal,
        history=history, budget_left=10, application_names=APPS,
    )
    # The model's Escape is refused (the same blind guess); the retry presses the visible «Nueva pestaña», which the
    # request asks for although the derived goal lost the word «pestaña».
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Nueva pestaña", "index": 2}
    first, retry = model.payloads
    assert "(sin efecto: la ventana quedó igual)" in first["messages"][1]["content"]
    assert "no cambió nada" in retry["messages"][-1]["content"]


def test_a_dead_key_refuses_another_key_and_a_blind_text_but_not_a_control_nor_a_named_field() -> None:
    photos = _view("fotos_paisaje_tras_ctrl_k")
    history = [_opened("Fotos"), _key(2, "ctrl_k")]
    for raw in ({"act": "key", "key": "ctrl_k"}, {"act": "key", "key": "enter"}, {"act": "type", "text": "editar"}):
        refused = cu_validate.validate_decision(
            raw, view=photos, last_failed=None, application_names=APPS, history=history, goal="ir a editor",
        )
        assert refused["operation"] == "none" and refused["code"] == "key_without_effect"
    assert "key_without_effect" in computer_use._RETRIED
    clicked = cu_validate.validate_decision(
        {"act": "click", "i": 13}, view=photos, last_failed=None, application_names=APPS, history=history, goal="ir a editor",
    )
    assert clicked["operation"] == "input.visible.click"
    # Counter-case: a key that did change the window may be followed by another one.
    changed = [_opened("Fotos"), _key(2, "ctrl_k", same_view=False)]
    key = cu_validate.validate_decision(
        {"act": "key", "key": "escape"}, view=photos, last_failed=None, application_names=APPS, history=changed, goal="ir a editor",
    )
    assert key["operation"] == "input.key.press"


def test_a_dead_shortcut_is_never_followed_later_by_the_other_blind_shortcut() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    history = [
        _opened("Terminal"), _key(2, "ctrl_k"),
        {"step": 3, "operation": "input.visible.click", "label": "Windows PowerShell", "index": 0, "ok": True, "changed": True},
    ]
    step = cu_lookup._find_step("simbolo del sistema", terminal, history)
    assert step is not None and step["operation"] == "input.scroll"
    # Counter-case: with the receipt unmarked the other shortcut is still tried.
    unmarked = [history[0], _key(2, "ctrl_k", same_view=None), history[2]]
    assert cu_lookup._find_step("simbolo del sistema", terminal, unmarked) == {
        "operation": "input.key.press", "arguments": {"key": "ctrl_f"}, "reason": step["reason"],
    }


# ------------------------------------------------- (v3-37) el pedido pide la pestaña nueva aunque el objetivo no


def test_v3_37_the_request_asking_for_a_new_tab_lets_the_model_press_new_tab() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    history = [_opened("Terminal")]
    asked = cu_validate.validate_decision(
        {"act": "click", "i": 2}, view=terminal, last_failed=None, application_names=APPS, history=history,
        goal="ir a nueva de simbolo del sistema", objective="abrí la terminal y abrí una pestaña nueva de símbolo del sistema",
    )
    assert asked["operation"] == "input.visible.click" and asked["arguments"] == {"label": "Nueva pestaña", "index": 2}


def test_counter_case_a_request_without_a_new_tab_or_one_already_opened_still_refuses_it() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    not_asked = cu_validate.validate_decision(
        {"act": "click", "i": 2}, view=terminal, last_failed=None, application_names=APPS, history=[_opened("Terminal")],
        goal="ir a configuracion", objective="windows terminal: open settings and tell me which profile is the default",
    )
    # Ronda 20b, palanca 6: the refused press on the split button opens its list instead; its action is never pressed.
    assert not_asked["operation"] == "input.visible.click" and not_asked["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    opened = [
        _opened("Terminal"),
        {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "ok": True, "changed": True},
    ]
    again = cu_validate.validate_decision(
        {"act": "click", "i": 2}, view=terminal, last_failed=None, application_names=APPS, history=opened,
        goal="ir a nueva de simbolo del sistema", objective="abrí la terminal y abrí una pestaña nueva de símbolo del sistema",
    )
    assert again["operation"] == "input.visible.click" and again["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}


# ------------------------------------------------------------- (4) nunca la ayuda ni la web desde una app de escritorio


def _typed(step: int, text: str) -> dict:
    return {"step": step, "operation": "input.text.type", "text": text, "ok": True, "changed": True}


def test_v3_44_the_help_offer_is_never_the_search_result_that_names_the_place() -> None:
    panel = _view("panel_ayuda_devices")
    history = [
        _opened("Panel de control"),
        {"step": 2, "operation": "input.visible.click", "label": "Ver dispositivos e impresoras", "ok": True, "changed": True},
        {"step": 3, "operation": "input.visible.click", "label": "Cuadro de búsqueda", "index": 7, "ok": True, "changed": True},
        _typed(4, "devices and printers"),
    ]
    step = cu_rules.deterministic_step(goal="ir a devices and printers", view=panel, history=history)
    assert step is not None and "Ayuda" not in str((step.get("arguments") or {}).get("label") or "")
    # Without the (stale) window text the only control naming the place is the help offer: no result at all.
    bare = {**panel, "text": {}}
    assert cu_lookup._result_naming(bare, "devices and printers", history) is None


def test_v3_41_the_help_offer_is_never_pressed_after_typing_an_option() -> None:
    panel = _view("panel_ayuda_iconos")
    history = [_opened("Panel de control"), _typed(2, "iconos grandes")]
    step = cu_rules.deterministic_step(goal="ir a iconos grandes", view=panel, history=history)
    assert step is not None and "Ayuda" not in str((step.get("arguments") or {}).get("label") or "")
    assert cu_lookup._result_naming({**panel, "text": {}}, "iconos grandes", history) is None
    # Estabilización R18: the model's own click on the help offer is no longer vetoed («opens_help» fired 0 times in
    # every model call of cu-v3): the prompt says it («nunca la ayuda ni la web si el pedido no las pide») and the rules
    # above, which act without the model, still never press it.
    assert "nunca la ayuda ni la web si el pedido no las pide" in cu_step_prompt.STEP_PROMPT
    model = cu_validate.validate_decision(
        {"act": "click", "i": 10}, view=panel, last_failed=None, application_names=APPS, history=history,
        goal="activar vista de iconos grandes", objective="abre el panel de control y ponlo en vista de iconos grandes",
    )
    assert model["operation"] == "input.visible.click"
    assert "opens_help" not in computer_use._RETRIED


def test_counter_case_a_request_that_asks_for_help_may_open_it() -> None:
    panel = _view("panel_ayuda_iconos")
    history = [_opened("Panel de control"), _typed(2, "iconos grandes")]
    allowed = cu_validate.validate_decision(
        {"act": "click", "i": 10}, view=panel, last_failed=None, application_names=APPS, history=history,
        goal="buscar iconos grandes en la ayuda", objective="en el panel de control buscá ayuda sobre iconos grandes",
    )
    assert allowed["operation"] == "input.visible.click"
    assert not cu_unasked.opens_help("Redes e Internet", panel, "ir a redes e internet")
    assert not cu_unasked.opens_help("Hardware y sonido", panel, "ir a hardware")


def test_the_step_prompt_says_the_four_rules() -> None:
    prompt = cu_step_prompt.STEP_PROMPT
    assert "«sin efecto» no se repite" in prompt and "nunca el mismo clic" in prompt
    assert "nunca la ayuda ni la web" in prompt and "nunca una parecida" in prompt


# ------------------------------------------- (2) un clic ok=false se diagnostica y nunca se repite igual (v3-32)


def _failed_click(step: int, label: str, error: str, index: int | None = None) -> dict:
    entry = {"step": step, "operation": "input.visible.click", "label": label, "ok": False, "error": error}
    if index is not None:
        entry["index"] = index
    return entry


def test_v3_32_a_list_its_receipt_called_unchanged_but_now_shows_expanded_is_read_as_opened() -> None:
    snipping = _view("recortes_desplegado")
    history = [
        _opened("Herramienta Recortes"),
        _failed_click(2, "Sin retraso", "visible_button_postread_unchanged"),
        _failed_click(3, "Menú desplegable del área de grabación", "visible_button_postread_unchanged", 0),
    ]
    assert "desplegó" in cu_diagnosis.failed_click_diagnosis(history[-1], snipping)
    model = _Model({"act": "click", "i": 0}, {"act": "click", "i": 2})
    decision = computer_use.decide_step(
        model, objective="open snipping tool and set the delay to 5 seconds",
        goal="open snipping tool and set the delay to 5 seconds", application="Herramienta Recortes", success_check=None,
        view=snipping, history=history, budget_left=8, application_names=APPS,
    )
    first, retry = model.payloads
    assert "el clic sí lo desplegó" in first["messages"][1]["content"]
    # The same click once more is refused with its diagnosis and retried, never the end of the mission.
    assert "repetiría el paso que acaba de fallar: el clic sí lo desplegó" in retry["messages"][-1]["content"]
    assert decision["operation"] == "input.visible.click" and decision["arguments"]["label"] == "Ventana"


def test_v3_32_the_value_a_closed_list_shows_points_to_that_list() -> None:
    snipping = _view("recortes_desplegado")
    # Counter-view: the same item drawn inside a collapsed list (the screenshot mode's delay list).
    closed = copy.deepcopy(snipping)
    closed["controls"].append({
        "i": 30, "kind": "ComboBox", "name": "Menú desplegable Retrasar recorte", "state": "collapsed",
        "rect": {"x": 990, "y": 420, "w": 70, "h": 50},
    })
    failed = _failed_click(4, "Sin retraso", "visible_button_not_invokable", 3)
    said = cu_diagnosis.failed_click_diagnosis(failed, closed)
    assert "[30]" in said and "Retrasar recorte" in said
    # Without a list around it, the receipt's own cause is said.
    assert "no se pulsa" in cu_diagnosis.failed_click_diagnosis(failed, snipping)
    # A step that did not fail has no diagnosis.
    assert cu_diagnosis.failed_click_diagnosis({**failed, "ok": True}, snipping) == ""


# ------------------------- contracasos de la revisión adversarial: lo que la firma de la vista no ve no es «sin efecto»


def _check(raw: dict, view: dict, history: list[dict], goal: str, objective: str | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=APPS, history=history, goal=goal, objective=objective,
    )


def test_counter_case_enter_after_a_typed_command_in_a_window_whose_text_is_no_control_value() -> None:
    # The Terminal's frozen view: 14 controls, the console text no control's value, so typing a command keeps the
    # signature and the App marks the type sameView. «type completo y después key enter» stays the way.
    terminal = _view("terminal_tras_ctrl_k")
    typed = {**_typed(2, "ipconfig"), "sameView": True}
    history = [_opened("Terminal"), typed]
    objective = "abrí la terminal y ejecutá ipconfig"
    enter = _check({"act": "key", "key": "enter"}, terminal, history, "ejecutar ipconfig", objective)
    assert enter["operation"] == "input.key.press" and enter["arguments"]["key"] == "enter"
    assert not cu_history.key_without_effect(typed)
    assert "sin efecto" not in cu_step_prompt._history_line(typed)
    # The Enter that ran it keeps the signature too: the next command is no blind guess either.
    ran = [*history, _key(3, "enter")]
    assert not cu_history.key_without_effect(ran[-1])
    assert _check({"act": "type", "text": "whoami"}, terminal, ran, "ejecutar whoami", objective).get("code") != "key_without_effect"


def test_counter_case_selection_and_clipboard_keys_chain_although_the_signature_kept() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    for first, second in (("ctrl_a", "delete"), ("ctrl_c", "ctrl_v"), ("ctrl_a", "ctrl_c"), ("ctrl_x", "ctrl_v")):
        history = [_opened("Terminal"), _key(2, first)]
        chained = _check({"act": "key", "key": second}, terminal, history, "borrar el texto")
        assert chained["operation"] == "input.key.press", (first, second, chained)
    # The measured dead shortcut still refuses the next blind key.
    dead = _check({"act": "key", "key": "escape"}, terminal, [_opened("Terminal"), _key(2, "ctrl_k")], "ir a configuracion")
    assert dead["code"] == "key_without_effect"


def _with_help_menu(name: str) -> dict:
    terminal = _view("terminal_tras_ctrl_k")
    terminal["controls"].append({
        "i": 14, "kind": "MenuItem", "name": name, "state": "collapsed", "rect": {"x": 160, "y": 137, "w": 60, "h": 28},
    })
    return terminal


def test_counter_case_the_help_menu_only_opens_a_menu_and_is_pressed() -> None:
    for name, goal, objective in (
        ("Ayuda", "ir a acerca de", "abrí la terminal y mostrame la versión en acerca de"),
        ("Help", "go to check for updates", "open the app and check for updates"),
    ):
        clicked = _check({"act": "click", "i": 14}, _with_help_menu(name), [_opened("Terminal")], goal, objective)
        assert clicked["operation"] == "input.visible.click" and clicked["arguments"]["index"] == 14, (name, clicked)
    for name in ("Ayuda", "Help", "Contenido de la Ayuda", "Get Help", "Asistente de ayuda rápida"):
        assert not cu_unasked.opens_help(name, None, "ir a acerca de"), name
    # The measured offers stay refused, and so does a search on the web.
    for offer in (
        'Buscar "iconos grandes" en Ayuda y soporte técnico de Windows', "Obtener ayuda sobre iconos grandes",
        "Search the web for large icons", "Buscar en línea", "Ayuda y soporte técnico",
    ):
        assert cu_unasked.opens_help(offer, None, "ir a iconos grandes"), offer


def test_counter_case_a_name_holding_web_or_internet_asks_for_no_help() -> None:
    offer = 'Buscar "cámara web" en Ayuda y soporte técnico de Windows'
    for said in ("ir a camara web", "configurá la cámara web", "abrí opciones de internet", "abrí whatsapp web"):
        assert cu_unasked.opens_help(offer, None, said), said
    for said in ("buscá la cámara en internet", "buscá ayuda sobre la cámara", "search it on the web"):
        assert not cu_unasked.opens_help(offer, None, said), said


def test_counter_case_a_new_tab_the_request_closes_or_another_sub_goal_does_not_get() -> None:
    terminal = _view("terminal_tras_ctrl_k")
    opened = [_opened("Terminal")]
    closing = _check({"act": "click", "i": 2}, terminal, opened, "ir a configuracion", "cerrá la pestaña nueva y abrí la configuración")
    assert closing["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}  # ronda 20b, palanca 6: its list, never its action
    chain = "abrí una pestaña nueva de símbolo del sistema y después abrí la configuración"
    other = _check({"act": "click", "i": 2}, terminal, opened, "ir a configuracion", chain)
    assert other["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    own = _check({"act": "click", "i": 2}, terminal, opened, "ir a nueva de simbolo del sistema", chain)
    assert own["operation"] == "input.visible.click"
    # A Ctrl+T that changed the window already opened it; one that changed nothing did not.
    by_key = [*opened, _key(2, "ctrl_t", same_view=False)]
    assert _check({"act": "click", "i": 2}, terminal, by_key, "ir a nueva de simbolo del sistema", chain)["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    dead_key = [
        *opened, _key(2, "ctrl_t"),
        {"step": 3, "operation": "input.visible.click", "label": "Windows PowerShell", "index": 0, "ok": True, "changed": True},
    ]
    assert _check({"act": "click", "i": 2}, terminal, dead_key, "ir a nueva de simbolo del sistema", chain)["operation"] == "input.visible.click"


def test_counter_case_the_diagnosis_of_a_twin_name_and_of_a_big_button_under_an_option() -> None:
    snipping = _view("recortes_desplegado")
    twins = copy.deepcopy(snipping)
    for i, x in ((18, 700), (19, 800)):
        twins["controls"].append({"i": i, "kind": "Button", "name": "Aceptar", "rect": {"x": x, "y": 560, "w": 80, "h": 30}})
    said = cu_diagnosis.failed_click_diagnosis(_failed_click(5, "Aceptar", "visible_button_postread_unchanged"), twins)
    assert "varios" in said and "[18]" in said and "[19]" in said
    # A big collapsed button the option merely lies on is no list showing it.
    big = copy.deepcopy(snipping)
    big["controls"].append({
        "i": 18, "kind": "Button", "name": "Panel de opciones", "state": "collapsed", "rect": {"x": 650, "y": 416, "w": 600, "h": 190},
    })
    said = cu_diagnosis.failed_click_diagnosis(_failed_click(4, "Sin retraso", "visible_button_not_invokable", 3), big)
    assert "abrí ese" not in said and "no se pulsa" in said
