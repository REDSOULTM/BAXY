"""The model's act checked without any model (contract §4.4): ``validate_decision`` and the checks of each act
(a click, a text, a key, the manner of an opening), with the act sent instead when one exists.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from . import effect_intent
from .semantic.account_acts import SESSION_ACTS, aborts_unasked, account_act, act_says, goal_asks_for
from .semantic.colours import changes_the_tool
from .semantic.cu_buscar import OPENS_ELSEWHERE, asks_to_scroll, caption_verb, parameter_goal, text_slot
from .semantic.missions import KEYS, application_named_in, fold, names_a_file, quotes_the_text
from .cu_vocabulary import _evidence_rules
from .cu_view import (
    _FIELD_KINDS, _LIST_KINDS, _ONE_LINE_HEIGHT, _area, _bare, _chosen, _focused,
    _focused_is_password, _has_arrow, _is_switch, _scroll_part, _shown_whole, _state_unknown_switch, _text_line_with,
    _viewed_control, effect_intent_actionable_kinds, find_control, is_content_item, label_names, view_contains,
)
from .cu_goals import (
    _PLACE_NAMED, _POSSESSIVE, _SETTING_GOAL, _destination, _goal_names_control, _goal_target, _place_of,
    _placing_goal, _search_goal, check_searches, colour_goal, done_needs_an_act, proved_on_disk,
)
from .cu_fields import (
    _COMPOSER_NAME, _EDITABLE_KINDS, _PRESSED_KINDS, _focused_controls, _is_search_field, _keyboard_on_address_field,
    _search_box, _writable, key_arguments,
)
from .cu_acts import _ACT_KEYS, _form_field_arguments, _guard_repeat, _none, _reveal_arguments, typed_text
from .cu_window import _system_menu_off_goal
from .cu_history import _clicks_on, _may_have_acted, _spent_keys, _steps_ok, key_without_effect
from .cu_unasked import (
    _DISCARD_NAME, _ELSEWHERE_WORDS, _REMOVAL_NAME, _request_opens_one, unasked_act, unasked_text,
)
from .cu_languages import _said_in_other_language
from .cu_meaning import SemanticMatcher
from .cu_forms import _FORM_FIELD_KINDS, _editor_body, _field_named, _field_of_label
from .cu_text_place import (
    _TYPED_CHORD, _into_the_focused_part, _named_field, _part_kept_from_the_text, _part_of_the_document,
    _placeholder_field, _pressed_instead, _slot_destination, _slot_or_refusal, _typing_without_arrival,
)
from .cu_creation import _creation_refusal, _form_button_cited
from .cu_gates import _gate_holds, _gate_stop
from .cu_options import combo_value
from .cu_navigation import (
    _is_container, _navigation_item, _navigation_tree_nodes, _offers_uninstall, _openable_tree_node, _runs_when_opened,
)
from .cu_lookup import (
    _command_box, _content_search_instead, _is_the_place, _keyboard_on_another_field, _search_line_appeared,
    own_place_button,
)
from .cu_evidence import (
    _cited_control_name, _echoes_typing, _entry_shown, _evidence_names_a_press, _holds_typing, _mission_proof,
    _option_not_product, _proved_done, _seen_at_start_all, _slot_written, _unrelated_evidence, acted_with_effect,
)
from .cu_diagnosis import failed_click_diagnosis


# The refusals the model gets one more try at, with the refusal in front of it (contract §4.4).
NOT_THE_OWN_BUTTON = "not_the_own_button"


def _types_the_place(arguments: object, goal: str | None, success_check: str | None, view: dict | None = None) -> bool:
    """The text the model types is the place a goal «ir a X» names (its whole name, with or without its article),
    the sub-goal's check is no search's, the view lists a control named as the place (a click leads there, as
    «Inicio» on a player's side bar), and the keyboard is not on an address field (review r4: a browser's address
    bar holding a page takes a site's name, and nothing else on screen leads there)."""

    place = _destination(goal)
    if not place or check_searches(success_check) or not isinstance(arguments, dict):
        return False
    typed = _POSSESSIVE.sub("", fold(arguments.get("text")).strip(" «»\"'")).strip()
    bare = _POSSESSIVE.sub("", place).strip()
    if not typed or not _is_the_place(typed, place) or not isinstance(view, dict) or _keyboard_on_address_field(view):
        return False
    controls = view.get("controls")
    # Revisión S, H2: the place's own button («Abre Tu biblioteca») leads there too.
    return own_place_button(view, place) is not None or isinstance(controls, list) and any(
        isinstance(control, dict) and str(control.get("kind")) not in _EDITABLE_KINDS
        and _POSSESSIVE.sub("", fold(control.get("name")).strip()).strip() == bare
        for control in controls
    )


# A control this much of its window is the window's body (a document, a web view, a canvas), not a place to go.
_COVERS_WINDOW = 0.8


def validate_decision(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    history: list[dict] | None = None,
    goal: str | None = None,
    objective: str | None = None,
    success_check: str | None = None,
    application: str | None = None,
    semantic: SemanticMatcher | None = None,
) -> dict[str, object]:
    """The model's act, checked against the view without any model (contract §4.4): a click on a control that
    covers the window, an act that repeats the last two that changed nothing, or the place's own name typed in a
    goal of going there whose check is no search's, is refused too."""

    decision = _checked_act(
        raw, view=view, last_failed=last_failed, application_names=application_names, history=history, goal=goal,
        objective=objective, application=application, semantic=semantic,
    )
    pressed = decision.pop("press", None)
    if pressed is not None:
        # Pasada r7 (t-long-2): «creá un documento en blanco» said done citing «Documento en blanco», the gallery's
        # item that does it, before any step; refused, the model answered none and the mission stopped. The control
        # the done cites, when the goal names it, is the act it skipped: pressed, under every check of a click.
        decision = _checked_act(
            {"act": "click", "text": pressed, "why": str(raw.get("why") or "") if isinstance(raw, dict) else ""}, view=view,
            last_failed=last_failed, application_names=application_names, history=history, goal=goal,
            objective=objective, application=application, semantic=semantic,
        )
    elif decision["operation"] == "done" and success_check and not any(_may_have_acted(step) for step in history or ()):
        # Review r10a finding 1: a goal «ir a X» whose check did not hold on the first look, said done by the model
        # before any act (Steam on its store, «ir a la biblioteca», done citing «Destacados»), is no arrival: the
        # place's own name on screen is pressed, and the click tells whether the window was there already
        # (ClickedPlaceLeftTreeAsIs) or goes there.
        named = _place_to_press(goal, view)
        if named is not None:
            decision = _checked_act(
                {"act": "click", "text": named, "why": str(raw.get("why") or "") if isinstance(raw, dict) else ""},
                view=view, last_failed=last_failed, application_names=application_names, history=history, goal=goal,
                objective=objective, application=application, semantic=semantic,
            )
    if _search_goal(goal) and decision["operation"] in {"input.visible.click", "input.text.type"}:
        # Lote r11 (v3-10): a search of content aimed at the box of the application's commands and help goes to the
        # view's other search field; with none, the model is told what that box is.
        arguments = decision["arguments"] if isinstance(decision.get("arguments"), dict) else {}
        target = _viewed_control(view, arguments.get("index"))  # type: ignore[union-attr]
        if target is None and decision["operation"] == "input.text.type":
            # Review of finales-buscador (finding 3): a «type» with «field» goes to the field it names (as the App
            # sends it, and as _typing_without_arrival reads it), never judged by the focus; without one, the focus.
            field = str(arguments.get("field") or "").strip()  # type: ignore[union-attr]
            target = (_field_named(view, (field,)) or {"name": field}) if field else _focused(view)
        if _command_box(target):
            instead = _content_search_instead(view, history, target)
            if instead is None:
                return _none(
                    "ese cuadro busca comandos y ayuda de la aplicación, no su contenido; usá el buscador del contenido "
                    "(su lupa, «Buscar en…» o el atajo que muestre) o decí que no lo ves",
                    code="command_box",
                )
            decision = _checked_act(
                {"act": "click", "text": str(instead.get("name") or ""), "i": instead.get("i"),
                 "why": str(raw.get("why") or "") if isinstance(raw, dict) else ""},
                view=view, last_failed=last_failed, application_names=application_names, history=history, goal=goal,
                objective=objective, application=application, semantic=semantic,
            )
    if decision["operation"] == "done" and proved_on_disk(success_check):
        # Review of lectura-ruta (finding 5): the shell asks the model only while the file is not at the path said; a
        # title naming it then proves a save in another folder (the dialog's own), never the one asked.
        return _none("lo guardado lo prueba el archivo en la carpeta pedida y todavía no está; hacé el paso que falta",
                     code="file_not_written")
    if decision["operation"] == "input.visible.click":
        # Pasada v3 r9 (v3-02): a click again on the option the goal names that an earlier click of the sub-goal left
        # chosen changes nothing: the goal is there (or was already), said with that option instead of a third click.
        arguments = decision["arguments"]
        target = _viewed_control(view, arguments.get("index")) if isinstance(arguments, dict) else None
        name = str(target.get("name") or "") if target is not None else ""
        # Review of cierre-de-subobjetivos (finding 1): every goal that names the option, whatever its verb («centrar»,
        # «encender», «habilitar»…), never a list of verbs that would send the click again and undo what the first did.
        if name and _chosen(target) and _clicks_on(history, name) and _goal_names_control(goal, name):
            proved = _proved_done(view, history, goal, decision.get("reason") or "")
            if proved is not None and fold(proved["arguments"]["evidence"]).strip() == fold(name).strip():  # type: ignore[index]
                # Pasada r15b: the done made of it passes every check of the model's own done (an act of the
                # sub-goal, …); refused, the refusal is the model's retry.
                checked = _checked_act(
                    {"act": "done", "evidence": name, "why": proved["reason"]}, view=view, last_failed=last_failed,
                    application_names=application_names, history=history, goal=goal, objective=objective,
                    application=application, semantic=semantic,
                )
                checked.pop("press", None)
                return checked
    if decision.get("code") == "repeated_step":
        # Rule 2 of «teclas sin efecto»: the click that just failed is never pressed again; the retry says why it failed.
        why_failed = failed_click_diagnosis(last_failed, view)
        if why_failed:
            decision = {**decision, "reason": f"{decision['reason']}: {why_failed}"}
    if decision["operation"] == "input.text.type" and _types_the_place(decision["arguments"], goal, success_check, view):
        # Regresiones r2 M3 (live v8): going to «Inicio» on a music player the model typed «inicio» in its search, a
        # side effect left on screen that brings no place. Typing the name is the routine's way only where the window
        # searches its places (``_find_step``); the model's typing is refused unless the check is a search's.
        return _none("ir a un lugar no es buscar su nombre; elegí el control que lleva ahí", code="types_the_place")
    if decision["operation"] == "input.visible.click" and _presses_system_menu(view, decision["arguments"], goal):
        return _none("ése es el menú de sistema de la ventana (mover, minimizar, cerrar), no un lugar del objetivo; "
                     "elegí un control de la ventana", code="system_menu")
    if decision["operation"] == "input.visible.click" and _covers_window(view, decision["arguments"]):
        return _none("ese control ocupa casi toda la ventana; elegí uno concreto", code="control_covers_window")
    if _repeats_without_progress(decision, history or [], view):
        return _none("repetiría por tercera vez un paso que no hizo aparecer nada", code="no_progress")
    return _creation_refusal(decision, view, history, goal) or decision


def _place_to_press(goal: str | None, view: dict) -> str | None:
    """The one control, or else the one line of the window's text, named exactly as the place a goal «ir a X» names:
    what a done before any act skipped (review r10a finding 1). None for another goal or when nothing names it."""

    place = _destination(goal) or fold(_place_of(goal, [])).strip()
    if not place:
        return None
    controls = view.get("controls") if isinstance(view, dict) else None
    named = {
        str(control.get("name") or "").strip() for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and fold(control.get("name")).strip() == place and not _scroll_part(control, view)
    }
    if len(named) == 1:
        return next(iter(named))
    if named:
        return None
    text = view.get("text") if isinstance(view, dict) else None
    lines = {
        str(line).strip() for zone in (text.values() if isinstance(text, dict) else ()) if isinstance(zone, list)
        for line in zone if fold(str(line)).strip() == place
    }
    return next(iter(lines)) if len(lines) == 1 else None


def _presses_system_menu(view: dict, arguments: object, goal: str | None) -> bool:
    """A click on the window's system menu that the goal does not ask for (``_system_menu_off_goal``): by the index
    the view handed out, else by its whole label."""

    if not isinstance(arguments, dict):
        return False
    control = _viewed_control(view, arguments.get("index"))
    if control is None:
        label = fold(arguments.get("label")).strip()
        controls = view.get("controls") if isinstance(view, dict) else None
        control = next((
            item for item in controls or [] if isinstance(item, dict) and label and fold(item.get("name")).strip() == label
        ), None)
    return _system_menu_off_goal(view, control, goal)


def _covers_window(view: dict, arguments: object) -> bool:
    window = view.get("window") if isinstance(view, dict) else None
    controls = view.get("controls") if isinstance(view, dict) else None
    index = arguments.get("index") if isinstance(arguments, dict) else None
    label = str(arguments.get("label") or "") if isinstance(arguments, dict) else ""
    if not isinstance(window, dict) or not isinstance(controls, list):
        return False
    if isinstance(index, int):
        control = next((item for item in controls if isinstance(item, dict) and item.get("i") == index), None)
    else:
        # A click by label alone on the name of the window's body (measured on a web view: «Chrome Legacy Window»,
        # the only control of the tree) is the same click.
        control = next((item for item in controls if isinstance(item, dict) and label and fold(item.get("name")) == fold(label)), None)
        if control is not None and control.get("kind") not in {"Pane", "Document", "Window", "Custom", "Group"}:
            return False
    outer, inner = window.get("rect"), control.get("rect") if control is not None else None
    if not isinstance(outer, dict) or not isinstance(inner, dict):
        return False
    try:
        window_area = float(outer["w"]) * float(outer["h"])
        width = min(float(inner["x"]) + float(inner["w"]), float(outer["x"]) + float(outer["w"])) - max(float(inner["x"]), float(outer["x"]))
        height = min(float(inner["y"]) + float(inner["h"]), float(outer["y"]) + float(outer["h"])) - max(float(inner["y"]), float(outer["y"]))
    except (KeyError, TypeError, ValueError):
        return False
    return window_area > 0 and width > 0 and height > 0 and width * height >= _COVERS_WINDOW * window_area


def _repeats_without_progress(decision: dict[str, object], history: list[dict], view: dict) -> bool:
    """The act equals the last two steps, both done, and nothing new appeared on screen after them."""

    if decision["operation"] in {"none", "done"} or len(history) < 2 or view.get("newText"):
        return False
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    return all(
        isinstance(step, dict) and step.get("ok") is True and step.get("operation") == decision["operation"]
        and all(fold(step.get(key)) == fold(arguments.get(key)) for key in _ACT_KEYS)
        for step in history[-2:]
    )


def _checked_act(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    history: list[dict] | None,
    goal: str | None,
    objective: str | None = None,
    application: str | None = None,
    semantic: SemanticMatcher | None = None,
) -> dict[str, object]:
    if not isinstance(raw, dict):
        return _none("respuesta inválida del modelo")
    act = str(raw.get("act") or "")
    why = str(raw.get("why") or "")[:160]
    if act == "done":
        evidence = _cited_control_name(str(raw.get("evidence") or "").strip(), view)
        destination = _destination(goal)
        lists = {fold(item.get("name")).strip() for item in view.get("controls") or () if item.get("kind") in _LIST_KINDS}
        if destination and fold(evidence).strip(" «»\"'") in {destination, f"la {destination}", f"el {destination}"} - lists:
            # Measured on Steam: «BIBLIOTECA» is on screen before and after the click (it opened a menu); the label of
            # the destination proves nothing. A list, grid or tree of that name is the place shown (banco r23b u1).
            return _none("el nombre del destino ya estaba en pantalla antes; citá algo de lo que se ve al llegar",
                         code="evidence_not_visible")
        # Review of the branch (finding 4): an entry of a list chosen by pattern («entry») is no typing that echoes: the
        # box showing that entry as its value is the change itself (the font of a character map has no other proof).
        chosen_entry = bool(evidence) and _entry_shown(evidence, view, history or [])
        # Ronda 24 (pasada r23, v3-08): the text a goal puts in a part it names («ponele de título Lista del super»),
        # typed into the field that names that part and shown as its value, is the act done, never an echo.
        slot_written = bool(evidence) and _slot_written(evidence, view, history or [], goal)
        if evidence and not chosen_entry and not slot_written and _echoes_typing(evidence, history or [], contained=not fold(goal or "").startswith("escribir ")):
            # What was typed is on screen because it was typed (the search box's echo, a title that repeats the
            # search: «imagenes - Resultados de la búsqueda en ETC»), never proof of arriving.
            return _none("lo que escribí se ve porque lo escribí; citá algo del resultado", code="evidence_not_visible")
        gate = _gate_holds(view, history or [], objective, goal)
        if gate is not None:
            # v3 limits (live v3-34: a success told over a notes app updating itself): nothing is reached on a gate
            # that stops this goal; the same rule as the step's (a goal about the gate or pressing its control is not).
            return _gate_stop(gate, history or [])
        session_act = account_act(evidence) if evidence else None
        if session_act in SESSION_ACTS and done_needs_an_act(goal) and not goal_asks_for(goal or "", session_act):
            # Pasada v3 r9 (v3-34): «Iniciando sesión...» was cited as the note created. The account's session (signing
            # in or out, an account created or changed) is never the proof of another act, on any screen.
            return _none("eso es la sesión de tu cuenta, no lo que pide el objetivo", code="evidence_not_visible")
        if evidence and done_needs_an_act(goal) and re.search(_evidence_rules()["failureText"], fold(evidence)):
            # Pasada v3 r9 (v3-11): a warning that something failed («Ya existe una sección con ese nombre») is never
            # the proof of doing it. Twin of EvidenceRefusal's «failure_shown».
            return _none("eso es un aviso de que algo falló, no la prueba de hacerlo", code="evidence_not_visible")
        if evidence and _form_button_cited(evidence, view, goal):
            # Revisión 2 de P4 (twin of EvidenceRefusal's «unsaved_form»): «Guardar» or «Descartar» of a form still to
            # save is no proof of what the form makes; it exists only once saved or confirmed.
            return _none("eso es un botón de un formulario sin guardar; lo que crea no existe hasta guardarlo o "
                         "confirmarlo", code="evidence_not_visible")
        if evidence and done_needs_an_act(goal):
            # Falsos éxitos v3 M1 (the one judge of the done: its App twin went with estabilización R16): a goal of doing
            # something is proved by a verified act of its own, never by what the screen already showed (v3-17:
            # «recórtala» said done with no step) nor by a text BAXY typed glued to another word (v3-35: «moradosu»).
            if not acted_with_effect(history or [], goal):
                refused = _none("todavía no hice nada para este objetivo; hacé el paso que lo cumple", code="evidence_not_visible")
                pressed = _evidence_names_a_press(evidence, view, goal)
                # The control the done cites is the act it skipped (``validate_decision`` presses it, checked).
                return {**refused, "press": pressed} if pressed is not None else refused
            unmade = _option_not_product(evidence, view, history or [], goal)
            if unmade is not None:
                # Ronda 24 (pasada r23 v3-33; twin of EvidenceRefusal's «option_not_product»): the mode chosen for a
                # capture is no capture; the product exists only once the control that makes it is pressed.
                return _none(unmade, code="option_not_product")
            if _seen_at_start_all(evidence, view, history, goal):
                # A control the act chose (a tab, an option now selected) is new though its name showed before.
                return _proved_done(view, history, goal, why) or _none(
                    "eso ya se veía antes de hacer nada; citá lo que cambió con el paso", code="evidence_not_visible")
            if not chosen_entry and not slot_written and _holds_typing(evidence, history or [], view, goal):
                return _proved_done(view, history, goal, why) or _none(
                    "eso lo escribí yo; citá algo que muestre el resultado", code="evidence_not_visible")
            if _unrelated_evidence(evidence, view, history, goal):
                # Ronda 22 (pasada r18, t4-c06, t4-c13; twin of EvidenceRefusal's «unrelated»): what is new on screen
                # proves the goal only when it says something of it (a word of the goal, or its alias in data), never a
                # notice of the window's own state (read only, a recovered file).
                return _proved_done(view, history, goal, why) or _none(
                    "eso no muestra el resultado del objetivo; citá lo que cambió y lo muestra", code="evidence_not_visible")
        if evidence and view_contains(view, evidence):
            arguments: dict[str, object] = {"evidence": evidence}
            proof = _mission_proof(view, history, goal)
            if proof is not None and proof[1] and _bare(proof[0]) == _bare(evidence):
                # The option cited was chosen before any act of the sub-goal touched it: said as it was, never as done.
                arguments["already"] = True
            if slot_written:
                # Revisión 1 de r24 (B2): «written» tells the App the citation is the text the goal put in the part it
                # names, never the echo of a typing (ComputerUseSuccessCheck.SlotWritten checks the view and the steps).
                arguments["written"] = True
            return {"operation": "done", "arguments": arguments, "reason": why}
        # Pasada v3 r9 (v3-09, v3-10): a citation the view does not hold (a joined line, an invented form) leaves the
        # screen's own proof, when there is one: the option the goal names chosen by the act, the field BAXY wrote.
        return _proved_done(view, history, goal, why) or _none("la evidencia citada no está en la vista", code="evidence_not_visible")
    if act == "click":
        label = str(raw.get("label") or raw.get("text") or "").strip()
        index = raw.get("i") if isinstance(raw.get("i"), int) and not isinstance(raw.get("i"), bool) else None
        if not label and index is not None:
            controls = view.get("controls") if isinstance(view, dict) else None
            if isinstance(controls, list) and 0 <= index < len(controls) and isinstance(controls[index], dict):
                label = str(controls[index].get("name") or "")
        if not label:
            return _none("el clic no nombra ningún control")
        control = find_control(view, label, index)
        if control is None and index is None:
            # Ronda 21 (v3-24): two controls named exactly so (the actions pane's button and the tree's node) are no
            # absence: the one navigation item among them is the place; otherwise the model is told the truth and
            # chooses one by its index. Only controls that take a press count: a row and its written label
            # (r9 v3-47: «Procesador» as a DataItem and a Text) stay the click by label they were.
            exact = [
                item for item in ((view.get("controls") or []) if isinstance(view, dict) else [])
                if isinstance(item, dict) and fold(item.get("name")) == fold(label)
                and str(item.get("kind")) in effect_intent_actionable_kinds()
            ]
            if len(exact) >= 2:
                navigation = [item for item in exact if _navigation_item(item, view)]
                rows = [item for item in exact if is_content_item(item, view)]
                if fold(goal or "").startswith("hacer clic en ") and len(rows) == 1:
                    # Revision 1 (finding 2): a click on a name the content shows as a row (a folder of a file window
                    # beside its node in the opened tree) presses the row, which chooses it; only going there enters it.
                    control = rows[0]
                elif len(navigation) != 1:
                    return _none(f"hay {len(exact)} controles llamados «{label[:40]}»: usá i", code="label_ambiguous")
                else:
                    control = navigation[0]
        labelled = _field_of_label(control, view)
        if labelled is not None:
            # Pasada r15b (v3-27): the click on a form's label («Caracteres para copiar:», a Text) meant its field;
            # the label takes no keyboard and its click does nothing. The field, under every check of a click.
            control, label = labelled, str(labelled.get("name") or label)
        clicked = str(control.get("name") or label) if control is not None else label
        elsewhere = bool(OPENS_ELSEWHERE.search(fold(clicked))) and not _ELSEWHERE_WORDS.search(fold(goal)) and not (
            _request_opens_one(objective, history or [], goal or "")
        )
        if elsewhere:
            if control is not None and _opens_its_list_instead(control, last_failed):
                # Ronda 20b, palanca 6 (v3-38, v3-39: «Configuración» lives in the list of the split button «Nueva
                # pestaña»): the press its guard refuses is its own action; its arrow or its list opens without it, and
                # what is chosen inside goes through every check of a click.
                return _checked_manner({"i": control["i"]}, "open", view=view, goal=goal, objective=objective,
                                       history=history, why=REASON_OPEN_LIST, last_failed=last_failed)
            return _none(f"«{clicked[:40]}» abre otra pestaña o ventana y el objetivo no lo pide", code="opens_elsewhere")
        named_explicitly = fold(goal or "").startswith("hacer clic en ") and (
            label_names(_goal_target(goal or "")[2] if _goal_target(goal or "") else "", clicked)
        )
        if control is not None and _current_node_elsewhere(control, view, goal, objective):
            # Ronda 21 (v3-26: «Visor de eventos (local)», already the window's place, pressed twice while going to
            # «Sistema»): the node the window is in is no step towards another place; what is not in the view lives
            # inside a collapsed node, opened by its identity.
            closed = any(_openable_tree_node(node, view) for node in _navigation_tree_nodes(view))
            return _none(
                f"«{clicked[:40]}» ya es el lugar actual" + ("; el destino está dentro de un nodo cerrado: open" if closed else ""),
                code="already_current",
            )
        place = _PLACE_NAMED.match(fold(goal or ""))
        own = own_place_button(view, place.group("place")) if place is not None and control is not None else None
        if own is not None and control is not own[0] and _is_the_place(clicked, place.group("place")):
            # Revisión S, H2 (e2 u1: a stranger's list «Tu biblioteca» opened from a search): a place with its own
            # button is that button's; another control called like it is content named so.
            return _none(f"«{clicked[:40]}» se llama como el lugar, pero su botón es «{own[0].get('name')}»",
                         code=NOT_THE_OWN_BUTTON)
        changes_the_account = unasked_act(clicked, goal, objective)
        if changes_the_account is not None:
            # Live z7 (going to «Tu biblioteca» on a music app): the model followed a profile and saved a playlist in
            # the person's account. Following, saving, liking, subscribing, installing or playing is theirs to ask for.
            return _none(f"«{clicked[:40]}» {act_says(changes_the_account)} y el objetivo no lo pide",
                         code="changes_the_account")
        if control is not None and _shows_progress(view) and aborts_unasked(clicked, goal, objective):
            # Encargo CS (banco fz1 s12): the only control of Steam's updater, «Cancelar», was pressed by the model's
            # «open» and the start the mission itself launched was cancelled. What a window shows in progress is
            # stopped only when asked («cancelá la descarga»).
            return _none(f"«{clicked[:40]}» detiene lo que está en curso y el objetivo no lo pide", code="aborts_in_progress")
        if colour_goal(goal) is not None and changes_the_tool(clicked):
            # Choosing a colour never picks a tool (live e2: the model clicked «Selector de colores», the eyedropper,
            # and the canvas's next click would have picked a colour from the drawing instead).
            return _none(f"«{clicked[:40]}» cambia de herramienta y el objetivo es elegir un color", code="changes_the_tool")
        if control is not None and _scroll_part(control, view) and not asks_to_scroll(goal):
            # A scroll bar's line or page button only scrolls: never the place a goal names by a shared word (measured
            # on v3-40: «split the pane vertical» pressed «Aumento grande vertical»).
            return _none(f"«{clicked[:40]}» sólo desplaza la vista; para desplazar, scroll", code="scroll_part")
        if control is not None and _placing_goal(goal) and _is_switch(control) and not named_explicitly:
            # Going somewhere never changes a setting on the way (measured on Settings: looking for «Colores» the
            # model clicked «Invertir colores» of the Magnifier).
            return _none(f"«{clicked[:40]}» cambia un ajuste y el objetivo no pide cambiar ninguno", code="changes_a_setting")
        setting = _SETTING_GOAL.match(fold(goal or ""))
        if control is not None and setting is not None and _state_unknown_switch(control) and not named_explicitly:
            # Revision 3 of ronda 20b (B-B): a closed menu's entry that toggles a setting shows no state of now; pressed
            # to set it on or off it may set it the other way. Its menu opened shows the entry with its state.
            return _none(
                f"«{clicked[:40]}» conmuta un ajuste cuyo estado no se ve; abrí su menú para verlo", code="changes_a_setting"
            )
        if control is not None and setting is not None and _is_switch(control) and not named_explicitly and not (
            label_names(setting.group("what"), clicked) or label_names(clicked, setting.group("what"))
        ):
            # Setting or choosing one thing never flips another switch on the way (live y1: for «activar modo
            # programador» the model clicked the Calculator's «Alternar grados» and left it in radians).
            return _none(f"«{clicked[:40]}» cambia otro ajuste que el objetivo no nombra", code="changes_a_setting")
        entry_act = _combo_entry_act(control, label, goal, objective, last_failed, why)
        if entry_act is not None:
            return _checked_act(
                entry_act, view=view, last_failed=last_failed, application_names=application_names, history=history,
                goal=goal, objective=objective, application=application, semantic=semantic,
            )
        if control is not None:
            arguments: dict[str, object] = {"label": str(control.get("name") or label)}
            if isinstance(control.get("i"), int):
                arguments["index"] = control["i"]
            return _guard_repeat({"operation": "input.visible.click", "arguments": arguments, "reason": why}, last_failed)
        line = _text_line_with(view, label)
        if line is not None:
            return _guard_repeat({"operation": "input.visible.click", "arguments": {"label": label}, "reason": why}, last_failed)
        return _none(f"«{label[:40]}» no está en la vista", code="label_not_visible")
    if act in ("key", "type") and not (act == "type" and str(raw.get("field") or "").strip()):
        stale = history[-1] if history else None
        if key_without_effect(stale):
            # Teclas sin efecto (r9: v3-37, v3-39, v3-16): the last key left the window as it was; another key or a
            # text sent blind after it is the same guess again. The next step is a control the view shows.
            said = str((stale or {}).get("key") or (stale or {}).get("operation") or "")
            return _none(f"la tecla «{said}» no cambió nada en la ventana; elegí un control visible", code="key_without_effect")
    if act == "type":
        text = typed_text(str(raw.get("text") or ""))
        if not text.strip():
            return _none("no hay texto que escribir")
        if _TYPED_CHORD.search(fold(text)) is not None and not quotes_the_text(text, goal, objective):
            # Ronda 22 (pasada r18, t4-c13): «Ctrl+B» typed as text over the person's selection, twice. The name of a
            # key combination is never typed; the visible control that does it, or the catalog's key, does it.
            return _none(
                f"«{text[:20]}» es una combinación de teclas, no un texto; usá el control visible que lo hace o la tecla "
                "del catálogo", code="typed_chord",
            )
        if _focused_is_password(view):
            return _none("el campo enfocado es una contraseña", code="password_field")
        unasked = unasked_text(text, goal, objective)
        if unasked is not None:
            # Live v3-11 («n» as a section's name) and estabilización G2 (t2-c03: an OCR'd date typed in Settings'
            # search while going to «pantalla»): what is typed, in a field or at the focus, comes from the request.
            return _none(f"«{text[:30]}» no sale del pedido; lo que se escribe sale del pedido o del objetivo",
                         code=unasked)
        named = _named_field(str(raw.get("field") or ""))[0]
        # v3 campo-texto: a goal that names the part its text goes to («de título», «en el asunto») is typed there.
        slot = text_slot(goal)

        def press(label: str) -> dict[str, object]:
            # A placeholder line pressed so its part takes the keyboard goes through every check of a click (review
            # r10 campo-texto, finding 8).
            return _checked_act(
                {"act": "click", "text": label, "why": "pulso el marcador del campo donde va el texto"}, view=view,
                last_failed=last_failed, application_names=application_names, history=history, goal=goal,
                objective=objective, application=application, semantic=semantic,
            )

        if named:
            # Goal v3 point 2 (forms): the value goes to the one field of the view the label names and replaces what
            # it held; never a password, a document (the person's work) or a control that takes no text.
            field = _field_named(view, (named,))
            placeholder = None
            if field is None:
                # A document's empty part named as such («Título de página», «Haga clic para agregar título») or its
                # body the view read empty («empty», never an unread one: r25, c1) takes the text too: no one's work.
                placeholder = next((
                    control for control in (view.get("controls") or []) if isinstance(control, dict)
                    and fold(control.get("name")).strip(" :") == fold(named)
                    # Ronda 20 P1: a request that names no part never takes an empty part the first look already showed.
                    and (_placeholder_field(control, view if slot is None and text_slot(objective) is None else None)
                         or (control.get("empty") is True and control.get("kind") == "Document" and _writable(control)
                             and not _search_box(view, control) and not _part_of_the_document(control, view)))
                ), None) if isinstance(view, dict) else None
                field = placeholder
            if field is None:
                # Ronda 20 (P7, v3-10): the field named by the example text the prompt shows as its value.
                field = _field_by_value(view, named)
            if field is None:
                pressed = find_control(view, named)
                if pressed is not None and str(pressed.get("kind") or "") in _PRESSED_KINDS:
                    # Live v3-01: the title typed «into» the gallery's item «Presentación en blanco». Writing on a
                    # button or an item is no writing: the press the goal names, under every check of a click, or no step.
                    act = _pressed_instead(named, pressed, goal)
                    if act is not None:
                        return _checked_act(
                            {**act, "why": why}, view=view, last_failed=last_failed, application_names=application_names,
                            history=history, goal=goal, objective=objective, application=application, semantic=semantic,
                        )
                    return _none(f"«{named[:40]}» se pulsa, no recibe texto; para pulsarlo, click", code="not_a_field")
                keyboard = _keyboard_field_name(view)
                if keyboard is not None and fold(keyboard).strip(" :") != fold(named).strip(" :"):
                    # Ronda 20 (P7): the refusal names the field that has the keyboard, so the retry names it right.
                    return _none(f"«{named[:40]}» no es un campo de la vista; el campo con el teclado se llama «{keyboard[:60]}»",
                                 code="label_not_visible")
                return _none(f"«{named[:40]}» no es un campo de la vista", code="label_not_visible")
            states = str(field.get("state") or "").split()
            # An entry of a closed list rewritten from a click (``combo_value``) is chosen, not written: a list-only box
            # (its value read-only) takes it; a password never.
            entry = raw.get("_entry") is True and str(field.get("kind")) == "ComboBox"
            if raw.get("_entry") is True and not entry:
                # The label of the box the click named resolves to another control: no text goes there.
                return _none(f"«{named[:40]}» no es la lista que se pulsó", code="not_a_field")
            if "password" in states or ("readonly" in states and not entry):
                return _none("ese campo no se escribe", code="password_field")
            if slot is not None and not entry and _search_box(view, field):
                # Live v3-04: «ponle 'Proyecto final' de título» went six times into the window's search box. The
                # search box takes only a search; the text goes to the part the goal names.
                return _slot_or_refusal(view, slot, text, history or [], semantic, why, last_failed, press)
            arguments = _form_field_arguments(field, named, text)
            if (placeholder is not None and field.get("kind") == "Document") or _editor_body(field, view):
                arguments.pop("replace", None)
            if entry:
                # Only one of the list's own entries of that name, chosen by pattern; none of that name, nothing changes.
                arguments["entry"] = True
            decision = _guard_repeat({"operation": "input.text.type", "arguments": arguments, "reason": why}, last_failed)
            return _typing_without_arrival(decision, history or [], view)
        if slot is not None:
            # The keyboard on a field that takes text and is no search stays the model's choice (a rename box need not
            # say «nombre»); on a search box, or on nothing that takes text, the part the goal names is the place.
            focused = next((control for control in _focused_controls(view) if control.get("kind") in _EDITABLE_KINDS), None)
            if focused is None or _search_box(view, focused) or not _writable(focused):
                destination = _slot_destination(view, slot, text, history or [], semantic, why, press)
                if destination is not None:
                    return _typing_without_arrival(_guard_repeat(destination, last_failed), history or [], view)
                if focused is not None and _search_box(view, focused):
                    return _none(
                        "el cuadro de búsqueda sólo recibe búsquedas; el texto va al campo que el objetivo nombra",
                        code="search_box_not_target",
                    )
        if fold(goal or "").startswith("buscar ") and _keyboard_on_another_field(view):
            # A search's name never goes into a message box or another field that has the keyboard.
            return _none("el teclado está en un campo que no es la búsqueda", code="search_focus_unproven")
        part = _part_kept_from_the_text(view, goal, objective)
        if part is not None:
            # Review of r20 P1 (finding 1, v3-11 t2): the keyboard is on a part of a document (the title of the page
            # «Sin título») that the request does not name and that is no vacancy of this sub-goal (the first look
            # already showed it, or it holds text): a text at the caret would rename the person's page. The model
            # puts the caret in the body first; a part new in this sub-goal, one the request names, or a placeholder
            # line («Haga clic para agregar título», no one's text) takes it.
            return _none(
                f"el teclado está en «{str(part.get('name') or '')[:40]}», una parte del documento que el pedido no "
                "nombra; poné el cursor en el cuerpo primero",
                code="part_not_named",
            )
        if not _keyboard_takes_the_text(view, goal):
            return _none("el teclado no está en un campo que reciba ese texto; primero el campo", code="no_text_field")
        arguments = _into_the_focused_part({"text": text[:4096]}, view)
        decision = _guard_repeat({"operation": "input.text.type", "arguments": arguments, "reason": why}, last_failed)
        return _typing_without_arrival(decision, history or [], view)
    if act == "key":
        key = str(raw.get("key") or "")
        if key not in KEYS:
            return _none("tecla fuera del catálogo")
        if key in _spent_keys(view):
            # Review finding 3: a search key that brought up something not sought earlier in the mission, on this
            # application, is the model's no more than the routine's.
            return _none(f"la tecla «{key}» ya abrió algo que no se buscaba en esta aplicación; elegí un control visible",
                         code="key_spent")
        # A calculation's Enter after typing the expression is the calculator's (no message box there).
        typed = None if fold(goal or "").startswith("calcular ") else history
        return _guard_repeat({"operation": "input.key.press", "arguments": key_arguments(key, view, typed), "reason": why}, last_failed)
    if act == "scroll":
        direction = str(raw.get("direction") or "down")
        if direction not in {"down", "up"}:
            direction = "down"
        return _guard_repeat({"operation": "input.scroll", "arguments": {"direction": direction, "amount": 3}, "reason": why}, last_failed)
    if act == "reveal":
        # Goal v3 point 2: an element of a long list brought into view by name (input.scroll with label), no wheel.
        name = str(raw.get("text") or raw.get("label") or "").strip()
        if not name:
            return _none("no hay nada que traer a la vista")
        if _shown_whole(view, name):
            # Lectura-ruta (r9 v3-47): «AMD Ryzen 7 5800H…» was asked to be revealed while the view already showed it;
            # the reveal found no item of that name and the list scrolled it out of the view. What the view shows needs
            # no reveal: the model is asked again for the goal's step on it.
            folding = _collapsed_shown(view, name)
            if folding is not None:
                # Ronda 21 (v3-67: «reveal Microsoft» on the collapsed tree node «Microsoft»): what the model wants to
                # see is what the control holds; it is opened by its identity, never refused as already in view.
                return _checked_manner({"i": folding["i"]}, "open", view=view, goal=goal, objective=objective,
                                       history=history, why=why, last_failed=last_failed)
            return _none(f"«{name[:40]}» ya está en la vista; hacé el paso del objetivo sobre él", code="already_in_view")
        return _guard_repeat({"operation": "input.scroll", "arguments": _reveal_arguments(name), "reason": why}, last_failed)
    if act == "open" and "application" not in raw and raw.get("i") is not None:
        pressed = _pressed_not_opened(view, raw.get("i"))
        if pressed is not None:
            # Ronda 24b (banco r23 n6: «open» on the button «Pestaña Archivo», which has no arrow nor list, refused five
            # times with cannot_open while the retry offered a lookalike): the act meant is its press, under every
            # check of a click.
            return _checked_act(
                {"act": "click", "label": str(pressed[1].get("name") or ""), "i": pressed[0], "why": why},
                view=view, last_failed=last_failed, application_names=application_names, history=history, goal=goal,
                objective=objective, application=application, semantic=semantic,
            )
    if act in ("menu", "double") or (act == "open" and "application" not in raw and raw.get("i") is not None):
        if act in ("open", "menu"):
            # Ronda 20 (P7, v3-28): D1 by the destination, not by the verb. The arrow of a closed list whose value the
            # goal names opens a list that lives only while its window is active; the box is set by its entry instead,
            # exactly as for a click on it (_combo_entry_act).
            entry_act = _combo_entry_act(_viewed_control(view, raw.get("i")), "", goal, objective, last_failed, why)
            if entry_act is not None:
                return _checked_act(
                    entry_act, view=view, last_failed=last_failed, application_names=application_names,
                    history=history, goal=goal, objective=objective, application=application, semantic=semantic,
                )
        return _checked_manner(raw, act, view=view, goal=goal, objective=objective, history=history, why=why,
                               last_failed=last_failed)
    if act == "open":
        asked = str(raw.get("application") or "").strip()
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {asked}", application_names) if asked else None
        if app_id is None:
            return _none("la aplicación no está en el catálogo", code="application_unknown")
        if objective and not application_named_in(app_id, (objective, goal), application_names, application):
            # Banco r6 (t-drag-3): «… llevala a la esquina de arriba a la derecha de la pantalla» made the model open
            # «Teclado en pantalla», a window always on top that then covered every later case. The model opens only
            # an application the person's request names (by its name or an alias of it), never one it guessed.
            return _none("esa aplicación no la nombra el pedido", code="application_not_requested")
        if history and _steps_ok(history, "app.open", appId=app_id):
            return _none("esa aplicación ya está abierta", code="already_open")
        return _guard_repeat({"operation": "app.open", "arguments": {"appId": app_id}, "reason": why}, last_failed)
    return _none(why or "el modelo no ve por dónde seguir")


def _combo_entry_act(
    control: dict | None, label: str, goal: str | None, objective: str | None, last_failed: dict | None, why: str,
) -> dict | None:
    """D1 (pasada r15b, v3-28): a closed list clicked or opened by its arrow lives only while its window is active, and
    the person's window took the front back before the next decision (the list closed, Arial stayed). When the goal names
    the value, the box is set to it by its field (its entry chosen by pattern, no front needed), under every check of a
    text aimed at a field. Ronda 20 (P7): decided by the control the act goes to (a combo box that says it is collapsed),
    never by the act's verb, so a click, an arrow (open) or a context menu (menu) on it are the same pick.

    Review of the branch (findings 1, 2): the value read from the goal is only taken as one of the box's own entries
    («entry»: chosen by pattern, never written as text), so a misread goal changes nothing; a list-only box (its value
    read-only) is the one this is for. After that pick failed on this box, the act is the model's step as it was (the
    list opened), never the same guess again. A split button or a menu with a submenu is no combo box and stays the
    model's act; a goal that names no value («abrí la lista de fuentes») too."""

    if not isinstance(control, dict) or str(control.get("kind")) != "ComboBox":
        return None
    if "collapsed" not in str(control.get("state") or "").split():
        return None
    value = combo_value(goal, objective, control.get("name"))
    picked_before = isinstance(last_failed, dict) and last_failed.get("operation") == "input.text.type" and fold(
        str(last_failed.get("field") or "")).strip(" :") == fold(str(control.get("name") or "")).strip(" :")
    if not value or fold(value) == fold(control.get("value") or "") or picked_before:
        return None
    return {"act": "type", "text": value, "field": str(control.get("name") or label), "why": why, "_entry": True}


def _field_by_value(view: dict, named: str) -> dict | None:
    """Ronda 20 (P7, v3-10): a field the model named by what the prompt shows as its value (valor=«Buscar blocs de notas»,
    a search box's example text) when no field is called that. Only the one writable field (never a password, a
    read-only box nor a message box: ``_writable``) whose value is exactly that name and that has the keyboard or is the
    window's search box; never a field without the keyboard holding the person's text, nor one of two that hold it.
    Revisión 2: never an editor's body either, whose value is the person's work and would be replaced whole (a
    Document with text, an Edit in the zone of the focused Document, an Edit with the keyboard the view does not show
    as a one-line field: the body of a plain-text editor). A search box (``_search_box``) is no one's work; a field with
    the keyboard that is no search box goes by its value only when it is a form's field (``_FORM_FIELD_KINDS``)."""

    wanted = fold(named).strip(" :")
    if not wanted or not isinstance(view, dict):
        return None
    focused = _focused_controls(view)
    candidates = [
        control for control in [*focused, *(view.get("controls") or [])]
        if isinstance(control, dict) and _writable(control) and str(control.get("value") or "").strip()
        and fold(control.get("value")).strip(" :") == wanted and not _in_focused_document(view, control)
        and (_search_box(view, control) or (control in focused and _form_field_not_body(view, control)))
    ]
    unique: list[dict] = []
    for control in candidates:
        if not any(fold(seen.get("name")) == fold(control.get("name")) and seen.get("kind") == control.get("kind")
                   for seen in unique):
            unique.append(control)
    return unique[0] if len(unique) == 1 else None


def _in_focused_document(view: dict, control: dict) -> bool:
    """An Edit in the zone of the focused Document: a part of an editor's body (Revisión 2 of P7)."""

    return control.get("kind") == "Edit" and bool(control.get("zone")) and any(
        other.get("kind") == "Document" and other.get("zone") == control.get("zone") for other in _focused_controls(view)
    )


def _form_field_not_body(view: dict, control: dict) -> bool:
    """A form's field with the keyboard and not an editor's body (Revisión 2 of P7): a ComboBox or a Spinner, or an
    Edit the view shows as a one-line field (its rectangle, or that of the listed control of its name and kind).
    An Edit without a rectangle may be a plain-text editor's whole body: never resolved by what it holds."""

    kind = control.get("kind")
    if kind not in _FORM_FIELD_KINDS:
        return False
    if kind != "Edit":
        return True
    listed = [control, *(
        item for item in (view.get("controls") or []) if isinstance(item, dict) and item.get("kind") == "Edit"
        and fold(item.get("name")) == fold(control.get("name"))
    )]
    rect = next((item.get("rect") for item in listed if _area(item.get("rect")) > 0), None)
    return rect is not None and float(rect.get("h") or 0) <= _ONE_LINE_HEIGHT


def _keyboard_field_name(view: dict) -> str | None:
    """The name of the writable field that has the keyboard, to say it in a refusal (the retry names it right)."""

    focused = next((control for control in _focused_controls(view) if _writable(control)), None)
    name = str((focused or {}).get("name") or "").strip()
    return name or None


# Goal v3 B3: what an act other than the click is sent as (``input.visible.click`` «manner»).
_MANNERS = {"open": "open", "menu": "menu", "double": "double"}
# Ronda 20b, palanca 6: a refused press rewritten as the opening of the control's own list.
REASON_OPEN_LIST = "abro su lista sin pulsarlo"


def _opens_its_list_instead(control: dict, last_failed: dict | None) -> bool:
    """A press a guard refuses on a control with an arrow is sent as the opening of its list, unless that opening just
    failed on it (``cannot_open``: a split button without ExpandCollapse): then the model has its retry, and the
    control's action is never pressed."""

    if not _has_arrow(control):
        return False
    return not (
        isinstance(last_failed, dict) and last_failed.get("operation") == "input.visible.click"
        and last_failed.get("manner") == "open" and (
            last_failed.get("index") == control.get("i")
            or fold(last_failed.get("label")).strip() == fold(control.get("name")).strip()
        )
    )


# The controls a double click would open as content: an item of a list, a grid or a tree.
_ITEM_KINDS_OPENED = frozenset({"ListItem", "DataItem", "TreeItem"})
# Review of B3, finding 2: the only controls a double click goes to. On a button, a link, a menu's item or a split button
# a double click is two activations (two BN_CLICKED of a Win32 button, two click events on a rendered page: «Enviar»
# sent twice under one confirmation); on a written text of a page it may be a link drawn as text. An item opens (a
# folder, a drive, a document, under the rule of Enter on an item), a tab is chosen twice (a console renames it: v3-40)
# and a document selects a word. The worker refuses the rest too (DesktopUiaWorker.ps1, $script:DoubleKinds).
_DOUBLE_KINDS = _ITEM_KINDS_OPENED | {"TabItem", "Document"}


_FOLDING_KINDS = frozenset({"TreeItem", "MenuItem", "ComboBox"})


def _collapsed_shown(view: dict, name: str) -> dict | None:
    """Ronda 21 (v3-67): the one control of the view named exactly ``name`` that holds more inside and shows it closed
    (a tree node, a menu or a drop-down marked collapsed); None otherwise."""

    controls = view.get("controls") if isinstance(view, dict) else None
    found = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and fold(control.get("name")).strip() == fold(name).strip()
        and str(control.get("kind") or "") in _FOLDING_KINDS and isinstance(control.get("i"), int)
        and "collapsed" in str(control.get("state") or "").split()
    ]
    return found[0] if len(found) == 1 else None


def _current_node_elsewhere(control: dict, view: dict, goal: str | None, objective: str | None) -> bool:
    """Ronda 21 (v3-26): the control is the navigation tree's node the window is already in (selected) while the goal
    names another place, and neither the goal nor the request names this node («hacé clic en Visor de eventos (local)»
    is pressed)."""

    if control.get("kind") != "TreeItem" or "selected" not in str(control.get("state") or "").split():
        return False
    if not _navigation_item(control, view):
        return False
    parsed = _goal_target(goal or "")
    if parsed is None or not str(parsed[2] or "").strip():
        return False
    name = str(control.get("name") or "")
    target = parsed[2]
    if label_names(target, name) or label_names(name, target):
        return False
    if _said_in_other_language(target, view, objective):
        # «hacer clic en library» on «Biblioteca del Programador de tareas» (v3-67): a place said in another language
        # than the window's may be this very node; only its meaning tells, and that is the model's.
        return False
    return fold(name).strip() not in fold(objective or "")


def _shows_progress(view: dict) -> bool:
    """Encargo CS: the view shows something in progress (a progress bar of any name)."""

    return any(isinstance(control, dict) and control.get("kind") == "ProgressBar" for control in view.get("controls") or [])


def _opens_a_list(control: dict) -> bool:
    """What «open» opens without pressing: a control collapsed or expanded, a drop-down or a split button."""

    return bool({"collapsed", "expanded"} & set(str(control.get("state") or "").split())) or control.get("kind") in {
        "ComboBox", "SplitButton"}


def _pressed_not_opened(view: dict, index: object) -> tuple[int, dict] | None:
    """Ronda 24b (n6): (its position in the view, the control) when control ``index`` has nothing to open
    (``_opens_a_list``) and is no frame button: «open» on it means its click, under every check of a click. A
    drop-down, a split button or a node keeps its own «open» (v3-37, v3-38). Estabilización R19: of every kind (an
    Edit, a list's item, a group, a link: g1, v3-03, v3-10, v3-32 were refused «cannot_open» on them, and the refusal
    itself said «para pulsarlo, click»), not only buttons, tabs and menu entries."""

    control = _viewed_control(view, index)
    if control is None or _opens_a_list(control) or not str(control.get("name") or "").strip():
        return None
    if caption_verb(control.get("name")):
        # A frame button (minimize, maximize, close) opens nothing and its press acts on the window: never read as one.
        return None
    controls = view.get("controls") or []
    position = next((at for at, item in enumerate(controls) if item is control), None)
    return None if position is None else (position, control)


def _checked_manner(
    raw: dict, act: str, *, view: dict, goal: str | None, objective: str | None, history: list[dict] | None, why: str,
    last_failed: dict | None,
) -> dict[str, object]:
    """Goal v3 B3 (orders that live in closed menus): «open» opens only the arrow or the list of control N (a split
    button, a drop-down, a collapsed menu), never its own action (measured v3-37: the click on «Nueva pestaña» opened
    another tab instead of its list); «menu» opens its context menu; «double» double-clicks it. Each names a control of
    the view by its index and goes through the guards of a click: a scroll bar's part never; a double click never on an
    item that runs (an installer, a program, a shortcut) nor in a list that offers to remove what is chosen, and never
    on what removes, discards or changes the account when the goal does not ask for it; nor on what opens another tab or
    window (the help or the web the prompt itself forbids, estabilización R18). Opening a list or a menu presses nothing: what is chosen in it is a click, checked as one, and
    the Kernel asks before a removal or a purchase (RiskPolicy reads the label)."""

    index = raw.get("i")
    control = _viewed_control(view, index)
    if control is None:
        return _none("ese índice no es un control de la vista", code="label_not_visible")
    name = str(control.get("name") or "").strip()
    if not name:
        return _none("ese control no tiene nombre en la vista", code="label_not_visible")
    folded = fold(name)
    if _scroll_part(control, view) and not asks_to_scroll(goal):
        return _none(f"«{name[:40]}» sólo desplaza la vista; para desplazar, scroll", code="scroll_part")
    if act == "open" and not _opens_a_list(control):
        # The model's «open» on such a control is its click (``_pressed_not_opened``); here only a frame button, or a
        # rule unfolding what may hold the goal (``_unfold_before_giving_up``), which skips what opens nothing.
        return _none(f"«{name[:40]}» no tiene flecha ni lista que abrir; para pulsarlo, click", code="cannot_open")
    if act == "double":
        changes_the_account = unasked_act(name, goal, objective)
        if changes_the_account is not None:
            return _none(f"«{name[:40]}» {act_says(changes_the_account)} y el objetivo no lo pide",
                         code="changes_the_account")
        if (_REMOVAL_NAME.search(folded) or _DISCARD_NAME.search(folded)) and not _REMOVAL_NAME.search(fold(goal)):
            return _none(f"«{name[:40]}» quita algo y el objetivo no lo pide", code="removes_unasked")
        if OPENS_ELSEWHERE.search(folded) and not _ELSEWHERE_WORDS.search(fold(goal)) and not _request_opens_one(
            objective, history or [], goal or ""
        ):
            return _none(f"«{name[:40]}» abre otra pestaña o ventana y el objetivo no lo pide", code="opens_elsewhere")
        if str(control.get("kind") or "") not in _DOUBLE_KINDS:
            return _none(f"«{name[:40]}» no se abre con doble clic: dos clics serían dos pulsaciones; para pulsarlo, click",
                         code="cannot_double")
        if str(control.get("kind") or "") in _ITEM_KINDS_OPENED and (
            _runs_when_opened(control) or _offers_uninstall(view)
            or not (_is_container(control, view) or (names_a_file(name) and not _runs_when_opened(control)))
        ):
            # The same rule as Enter on an item: only a folder, a drive or a document opens; an application, a
            # shortcut, an installer or an item of a list of programs runs something.
            return _none(f"«{name[:40]}» se ejecutaría al abrirlo; nunca un programa ni un instalador", code="runs_when_opened")
        if _covers_window(view, {"index": control.get("i")}):
            return _none("ese control ocupa casi toda la ventana; elegí uno concreto", code="control_covers_window")
    arguments: dict[str, object] = {"label": name, "index": control["i"], "manner": _MANNERS[act]}
    return _guard_repeat({"operation": "input.visible.click", "arguments": arguments, "reason": why}, last_failed)


def _keyboard_takes_the_text(view: dict, goal: str | None) -> bool:
    """A text the model types without naming a field goes where the keyboard is, as a person's keys would (a cell, a
    calculator's key, a file list that jumps to a name, the document). A parameter (a new name or a search:
    ``parameter_goal``, read from the verb that heads the sub-goal) goes only to a focused text field that is no message
    box: never a tab, a button, the document nor a window whose focus cannot be read (a console, measured on v3-40:
    «pruebas» went to the console with the focus on a tab and the rename was told as done), unless a search prompt just
    appeared there (a written search box with the caret)."""

    if not parameter_goal(goal):
        return True
    focused = _focused_controls(view)
    fields = [
        control for control in focused
        if control.get("kind") in _FIELD_KINDS and not (_COMPOSER_NAME.search(fold(control.get("name"))) and not _is_search_field(control))
    ]
    return bool(fields) or (not focused and _search_line_appeared(view) is not None)
