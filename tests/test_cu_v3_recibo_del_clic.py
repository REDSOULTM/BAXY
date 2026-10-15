"""Recibo del clic por estado (pasada r15b: v3-46, v3-52, v3-44). Un control que está en la vista no se busca a
ciegas: si su estado contradice lo que pide la comprobación (un elemento de árbol cerrado que debe abrirse), el acto es
abrirlo por su identidad; si un clic que debía elegirlo no lo eligió, se dice que no tuvo efecto. Y ningún paso de
regla pulsa la oferta de buscar en la ayuda o en la web. Gemelos con las vistas reales de la pasada y sus contracasos."""

from __future__ import annotations

import re
from pathlib import Path

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import cu_goals
from baxy_mind import cu_by_name
from baxy_mind import cu_rules


def _msinfo(state: str) -> dict:
    # The view of v3-46 (model_calls.jsonl, call 20): msinfo32 with «Componentes» chosen and still collapsed.
    return {
        "window": {"title": "Información del sistema", "process": "msinfo32", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1000, "h": 700}},
        "controls": [
            {"i": 0, "kind": "TreeItem", "name": "Resumen del sistema", "state": "expanded", "zone": "TL"},
            {"i": 1, "kind": "TreeItem", "name": "Recursos de hardware", "state": "collapsed", "zone": "TL"},
            {"i": 2, "kind": "TreeItem", "name": "Componentes", "state": state, "zone": "TL"},
            {"i": 3, "kind": "TreeItem", "name": "Entorno de software", "state": "collapsed", "zone": "TL"},
            {"i": 4, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "zone": "TL"},
            {"i": 5, "kind": "Button", "name": "Minimizar", "zone": "TR"},
            {"i": 6, "kind": "Button", "name": "Maximizar", "zone": "TR"},
            {"i": 7, "kind": "Button", "name": "Cerrar", "zone": "TR"},
            {"i": 8, "kind": "MenuItem", "name": "Archivo", "state": "collapsed", "zone": "TL"},
            {"i": 9, "kind": "MenuItem", "name": "Editar", "state": "collapsed", "zone": "TL"},
            {"i": 10, "kind": "MenuItem", "name": "Ver", "state": "collapsed", "zone": "TL"},
            {"i": 11, "kind": "MenuItem", "name": "Ayuda", "state": "collapsed", "zone": "TL"},
            {"i": 12, "kind": "Tree", "name": "Tree1", "zone": "L"},
            {"i": 13, "kind": "Edit", "name": "Buscar esto:", "zone": "B"},
        ],
        "text": {},
    }


V3_46_CHECK = "control:componentes:expanded|stepDone:input.visible.click:componentes&control:pantalla"
CLICKED_COMPONENTES = [{"step": 2, "operation": "input.visible.click", "label": "Componentes", "index": 2, "ok": True}]


def test_twin_v3_46_a_chosen_tree_item_still_collapsed_is_opened_never_looked_up() -> None:
    step = cu_rules.deterministic_step(
        goal="hacer clic en componentes", view=_msinfo("selected collapsed"), history=CLICKED_COMPONENTES,
        application="Información del sistema", success_check=V3_46_CHECK,
    )
    assert step is not None
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Componentes", "index": 2, "manner": "open"}


def test_v3_46_the_tree_item_is_opened_once_then_the_rule_leaves_it() -> None:
    opened = [*CLICKED_COMPONENTES, {"step": 3, "operation": "input.visible.click", "label": "Componentes", "index": 2,
                                     "manner": "open", "ok": True}]
    step = cu_rules.deterministic_step(
        goal="hacer clic en componentes", view=_msinfo("selected collapsed"), history=opened,
        application="Información del sistema", success_check=V3_46_CHECK,
    )
    assert step is None or step.get("arguments", {}).get("manner") != "open"


def test_contracase_a_tree_item_only_to_be_chosen_is_never_opened() -> None:
    # The check asks for it chosen and names nothing it holds: the select+expand is not applied.
    step = cu_rules.deterministic_step(
        goal="hacer clic en componentes", view=_msinfo("selected collapsed"), history=CLICKED_COMPONENTES,
        application="Información del sistema", success_check="control:componentes:selected",
    )
    assert step is None or step.get("arguments", {}).get("manner") != "open"


def test_contracase_an_expanded_tree_item_is_not_opened_again() -> None:
    step = cu_rules.deterministic_step(
        goal="hacer clic en componentes", view=_msinfo("selected expanded"), history=CLICKED_COMPONENTES,
        application="Información del sistema", success_check=V3_46_CHECK,
    )
    assert step is None or step.get("arguments", {}).get("manner") != "open"


def _obs_settings() -> dict:
    # The view of v3-52 (model_calls.jsonl, call 29): OBS's «Ajustes», «General» chosen, «Vídeo» not.
    names = ["General", "Apariencia", "Emisión", "Salida", "Audio", "Vídeo", "Atajos", "Accesibilidad", "Avanzado"]
    controls: list[dict] = [{"i": 0, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "zone": "TL"}]
    for offset, name in enumerate(names):
        controls.append({"i": 2 + offset, "kind": "ListItem", "name": name, "zone": "TL",
                         **({"state": "selected focused"} if name == "General" else {})})
    controls += [
        {"i": 11, "kind": "ComboBox", "name": "Idioma", "state": "collapsed", "value": "Español", "zone": "TR"},
        {"i": 12, "kind": "CheckBox", "name": "Abrir diálogo de estadísticas al inicio", "state": "off", "zone": "T"},
        {"i": 46, "kind": "MenuBar", "name": "Barra de menús del sistema", "state": "focused", "zone": "TL"},
    ]
    return {"window": {"title": "Ajustes", "process": "obs64", "focused": None,
                       "rect": {"x": 0, "y": 0, "w": 1100, "h": 800}},
            "controls": controls, "text": {"TL": ["Ajustes", "General", "Apariencia", "Vídeo"]}}


V3_52_FAILED = [{"step": 3, "operation": "input.visible.click", "label": "Vídeo", "index": 7, "ok": False,
                 "error": "visible_button_postread_unchanged"}]


def test_twin_v3_52_a_list_item_the_click_did_not_choose_is_said_never_ctrl_k() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a video", view=_obs_settings(), history=V3_52_FAILED, application="OBS Studio (64bit)",
        success_check="control:video:current|title:video|page:video|mark:video",
    )
    assert step is not None
    assert step["operation"] == "none"
    assert step["code"] == cu_rules.CLICK_WITHOUT_EFFECT
    assert "Vídeo" in step["reason"]


def test_contracase_v3_52_a_list_item_chosen_after_the_click_is_no_failure() -> None:
    view = _obs_settings()
    for control in view["controls"]:
        if control["name"] == "Vídeo":
            control["state"] = "selected"
        elif control["name"] == "General":
            control.pop("state", None)
    video = next(c for c in view["controls"] if c["name"] == "Vídeo")
    assert not cu_rules._choice_without_effect(video, V3_52_FAILED, view)


def test_contracase_a_button_whose_click_did_not_change_the_window_still_goes_the_old_way() -> None:
    # Only what is chosen when pressed reads «no tuvo efecto»: a button keeps the window's own lookup.
    button = {"i": 3, "kind": "Button", "name": "Vídeo"}
    assert not cu_rules._choice_without_effect(button, V3_52_FAILED, _obs_settings())


def test_contracase_a_list_that_marks_nothing_chosen_is_still_looked_up() -> None:
    # Discord's «Cotele» (test_computer_use): no item chosen anywhere, so the failed click proves no choice failed.
    view = _obs_settings()
    for control in view["controls"]:
        control.pop("state", None) if control["kind"] == "ListItem" else None
    video = next(c for c in view["controls"] if c["name"] == "Vídeo")
    assert not cu_rules._choice_without_effect(video, V3_52_FAILED, view)


def _control_panel() -> dict:
    # v3-44: Control Panel's search typed in the English name; its results offer the help's search (the OCR read the
    # line with a stray «O» before it) and no control carries the name.
    return {
        "window": {"title": "devices and printers - Panel de control", "process": "explorer", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1100, "h": 800}},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "devices and printers", "zone": "TR"},
            {"i": 1, "kind": "Button", "name": "Atrás", "zone": "TL"},
            {"i": 2, "kind": "Button", "name": "Adelante", "zone": "TL"},
        ],
        "text": {"C": ["O Buscar \"devices and printers\" en Ayuda y soporte técnico de Windows"]},
    }


def test_twin_v3_44_no_rule_step_presses_the_offer_to_search_the_help() -> None:
    history = [
        {"step": 2, "operation": "input.visible.click", "label": "Cuadro de búsqueda", "index": 0, "ok": True},
        {"step": 3, "operation": "input.text.type", "text": "devices and printers", "ok": True},
    ]
    objective = "in control panel go to devices and printers and tell me which printer is the default"
    for steps in (history, []):
        step = cu_rules.deterministic_step(
            goal="ir a devices and printers", view=_control_panel(), history=steps, application="Panel de control",
            objective=objective,
        )
        # Before: the typed search's result was the help's line, and with nothing typed the written name (the line that
        # holds it is the help's offer) was clicked by label.
        assert step is not None and step["operation"] != "none"
        if step["operation"] == "input.visible.click":
            label = str(step["arguments"].get("label") or "")
            assert "ayuda" not in missions_fold(label)
            assert missions_fold(label) != "devices and printers"


def test_v3_44_a_name_clicked_by_label_alone_never_is_the_help_offer() -> None:
    view = {"window": {"title": "Panel de control"}, "controls": [{"i": i, "kind": "Text", "name": f"x{i}"} for i in range(60)],
            "truncated": True, "text": {}}
    names = ("Buscar devices and printers en Ayuda y soporte técnico", "dispositivos e impresoras")
    step = cu_by_name._unlisted_name_click(view, [], names)
    assert step is None or step["arguments"]["label"] == "dispositivos e impresoras"


# Review of fable/cu-v3-recibo-del-clic-por-estado (finding 3): the real receipt of v3-52 held by the picture alone (ok,
# surfaceChanged, its own «selected» false; the focus moved). With «General» still chosen and «Vídeo» not, it reads «no
# tuvo efecto» too; before it went on to ctrl_k. Review r2 (finding 1): the step as the mind gets it, only the keys the
# App's HistoryForMind projects (surfaceChanged reaches the mind as «changed»).
V3_52_REAL = [{"step": 3, "operation": "input.visible.click", "label": "Vídeo", "index": 7, "ok": True,
               "kind": "ListItem", "changed": True, "selected": False}]


def _projected_keys() -> set[str]:
    """The keys the App's HistoryForMind passes from a step to the mind (ComputerUseMission.ForTheMind.cs)."""

    source = (Path(__file__).resolve().parents[1] / "src" / "Baxy.App" / "ComputerUseMission.ForTheMind.cs").read_text(encoding="utf-8")
    body = source[source.index("internal static JsonArray HistoryForMind("):]
    item = body[body.index("var item = new JsonObject"):]
    keys = re.findall(r'\["(\w+)"\]\s*=\s*step\[', item[:item.index("};")])
    listed = re.search(r"foreach \(string key in new\[\] \{([^}]*)\}\)", item)
    assert listed is not None
    return {*keys, *re.findall(r'"(\w+)"', listed.group(1))}


def test_the_twin_of_v3_52_holds_only_what_the_app_sends_the_mind() -> None:
    # Review r2 (finding 1): the twin passed with a «selected» the App never sent; each key it holds is projected.
    projected = _projected_keys()
    assert "selected" in projected and "manner" in projected
    assert set(V3_52_REAL[0]) <= projected


def test_twin_v3_52_the_real_receipt_held_by_the_picture_is_a_choice_without_effect() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a video", view=_obs_settings(), history=V3_52_REAL, application="OBS Studio (64bit)",
        success_check="control:video:current|title:video|page:video|mark:video",
    )
    assert step is not None
    assert step["operation"] == "none"
    assert step["code"] == cu_rules.CLICK_WITHOUT_EFFECT


def test_contracase_a_receipt_that_says_chosen_or_says_nothing_is_no_failure() -> None:
    video = next(c for c in _obs_settings()["controls"] if c["name"] == "Vídeo")
    chosen = [{**V3_52_REAL[0], "selected": True}]
    silent = [{key: value for key, value in V3_52_REAL[0].items() if key != "selected"}]
    assert not cu_rules._choice_without_effect(video, chosen, _obs_settings())
    assert not cu_rules._choice_without_effect(video, silent, _obs_settings())


def test_contracase_a_row_chosen_in_another_zones_list_is_not_of_its_list() -> None:
    view = _obs_settings()
    for control in view["controls"]:
        if control["name"] == "General":
            control["zone"] = "C"
    video = next(c for c in view["controls"] if c["name"] == "Vídeo")
    assert not cu_rules._choice_without_effect(video, V3_52_REAL, view)


# Review of the branch (finding 6): the check's atoms are read as the C# check reads them, and a tree item the check
# asks for chosen is never opened, whatever else the check names.
def test_check_atoms_take_the_state_after_the_last_colon_and_keep_a_name_with_colons() -> None:
    assert cu_goals._check_atoms("control:Opciones: Vídeo:expanded") == [("opciones: video", "expanded")]
    assert cu_goals._check_atoms("control:Opciones: Vídeo") == [("opciones: video", "")]
    assert cu_goals._check_atoms("control:=informe:selected|title:x") == [("informe", "selected")]


def test_contracase_a_tree_item_the_check_wants_chosen_is_not_opened_for_another_missing_name() -> None:
    step = cu_rules.deterministic_step(
        goal="hacer clic en componentes", view=_msinfo("selected collapsed"), history=CLICKED_COMPONENTES,
        application="Información del sistema", success_check="control:componentes:selected&control:aceptar",
    )
    assert step is None or step.get("arguments", {}).get("manner") != "open"
