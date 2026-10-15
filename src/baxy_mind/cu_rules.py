"""The step a goal dictates without the model (contract §4.2): ``deterministic_step`` and the rules only it
uses (a state a check asks for, an item chosen, a click that needs the person's confirmation).
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from .semantic.account_acts import unasked_world_act, world_act
from .semantic.colours import is_basic_colour, names_a_colour, names_the_colour_kind
from .semantic.missions import (
    BROWSER_CATEGORY, CONTEXT_MENU_GOAL, _key_from_words, fold, gender_twin, label_alternatives,
    mode_named as _mode_named, view_option_family, view_option_named, is_search_place,
)
from .cu_view import (
    _FIELD_KINDS, _focused_is_password, _is_switch, _state_unknown_switch, _text_line_with, _without_row_cells,
    _without_state_unknown_switches, find_control, is_content_item, label_names,
)
from .cu_goals import FIELD_GOAL, REVEAL_GOAL, _GOING_HEADS, _check_atoms, _goal_target
from .cu_fields import (
    _ADDRESS_NAME, _EDITABLE_KINDS, _composer_with_text, _focus_unreadable, _focused_controls, _focused_field,
    _focused_is_text_field, _is_search_field, _keyboard_on_a_search, _keyboard_on_address_field, _message_window,
    _typed_into_plain_field, _writable, key_arguments,
)
from .cu_acts import _REASON_FIND, _click, _form_field_arguments, _none, typed_text
from .cu_window import _named_exactly, _vetoed_controls, _window_fold, _without_vetoed, application_is_in_front
from .cu_history import (
    _before_unfolding_misses, _click_failed, _name_click_not_found, _search_started, _steps_ok, _typed_target,
)
from .cu_unasked import _REMOVAL_NAME, opens_help
from .cu_languages import (
    _interface_control, _lookup_translations, _names_by_translation, _said_in_other_language, _translation_clickable,
    _translation_fits,
)
from .cu_meaning import SemanticMatcher, _collapsed_to_open, _free_goal_label, _semantic_step
from .cu_forms import _field_step, _form_confirm_step, _form_unit_step
from .cu_text_place import (
    _MODEL_DECIDES, _body_click, _focused_slot_step, _into_the_focused_part, _off_the_search, _part_kept_from_the_text,
    _part_of_the_document, _place_to_type, _typing_place_step,
)
from .cu_creation import _creating_command_step
from .cu_documents import _start_page_step
from .cu_options import _view_option_shown, _view_option_step
from .cu_navigation import (
    _content_item_chosen, _current_node_first, _is_container, _names_a_switch, _navigation_item, _offers_uninstall,
    _reveal_step, _runs_when_opened, _tree_descent_step, _without_name,
)
from .cu_menus import _context_menu_step, _menu_opened_by
from .cu_address import _address_path, _address_step
from .cu_lookup import (
    _find_step, _held_for_the_encoder, _layer_holds_the_keyboard, _navigation_opener, _pressed_own_button,
    _searches_content, _typed_into_written_search, own_place_button,
)
from .cu_by_name import _colour_step, _lists_part_of_the_tree, _swatch, _unlisted_name_click


_CALC_TRANSLATE = str.maketrans({"×": "*", "x": "*", "X": "*", "÷": "/", "−": "-", ",": "."})


def _expression_for_typing(expression: str) -> str:
    return "".join(expression.translate(_CALC_TRANSLATE).split())


# «activar modo X»: the reader's goal for «poné el modo X», which is a switch only where the window has one so named.
_MODE_SWITCH_GOAL = re.compile(r"^activar\s+modo\s+(?P<what>\S.*)$")


def _switch_named(view: dict, what: str) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _is_switch(control)
        and (label_names(what, str(control.get("name") or "")) or label_names(f"modo {what}", str(control.get("name") or "")))
        for control in controls or ()
    )


def deterministic_step(
    *,
    goal: str,
    view: dict,
    history: list[dict],
    application: str | None = None,
    objective: str | None = None,
    translate: Callable[[str], tuple[str, ...]] | None = None,
    semantic: SemanticMatcher | None = None,
    success_check: str | None = None,
    _tried: tuple[str, ...] = (),
    form_check: str | None = None,
) -> dict[str, object] | None:
    """The step the goal itself dictates when the view shows it (contract §4.2):
    a key to press, a text or an expression to type, a named control to click
    or to switch, a tab to close while more than one is open. No model, no
    application knowledge; anything else, or a step that just failed, goes to
    the model. ``translate`` (a ``LabelTranslator``) gives the other language's
    names of a place no known name finds; a click on one of them carries
    ``alias`` {from, to} for the shell's check (contract §4.4.1)."""

    folded_goal = fold(goal)
    mode = _MODE_SWITCH_GOAL.match(folded_goal)
    if mode is not None and not _switch_named(view, mode.group("what")):
        # «poné el modo programador» on a window with no switch of that name: the mode is one of the window's places,
        # chosen the way «cambiá a programador» chooses it (live y1: the model wandered and flipped «Alternar grados»).
        return deterministic_step(
            goal=f"ir a {mode.group('what')}", view=view, history=history, application=application,
            objective=objective, _tried=_tried,
        )
    if folded_goal.startswith("escribir ") and _layer_holds_the_keyboard(view, history):
        # Estabilización S2 (banco f3 c6: a chat client's quick switcher, a layer of its own window, kept the keyboard;
        # the text was refused as not reaching the message box and the model saw no step): one Escape closes that
        # layer, and the writing goes on as it would.
        return {"operation": "input.key.press", "arguments": key_arguments("escape", view, history),
                "reason": "una capa de la ventana tiene el teclado y el texto no llega: Escape la cierra"}
    if folded_goal.startswith("ir a ") and _pressed_own_button(history, goal[len("ir a "):]):
        # Encargo S (banco e1 y8: the press on «Abre Tu biblioteca» held and the panel was still being drawn; e2 u1, y8:
        # its post-read did not hold): the place's own button is pressed once in the sub-goal at most (a second press
        # closes what the first opened). Arriving is then the check's, and the step the model's: no other control named
        # like the place, no lookup by its name and no search.
        return None
    last = history[-1] if history and isinstance(history[-1], dict) else None
    # A list whose patterns could not bring the element by its name goes on with the wheel, and a wheel that no longer
    # moves it is the long list limit (_reveal_step; estabilización L4).
    revealing = folded_goal.startswith(REVEAL_GOAL) and last is not None and last.get("operation") == "input.scroll"
    if last is not None and last.get("searchBurst") is True and last.get("ok") is not True:
        # A search burst that stopped before its last sub-act (goal v3 point 0, fix 3): the routine that sent it goes
        # on from its whole history (``_find_step``), never by retrying the sub-act alone.
        parsed = _goal_target(goal)
        if parsed is None or parsed[1] is not None or parsed[3] is not None:
            return None
        return _find_step(parsed[2], view, history, navigate=parsed[0] == "ir a ", objective=objective,
                          others=_lookup_translations(parsed[2], translate))
    if last is not None and last.get("ok") is not True and not revealing:
        # An opening that could not be verified but left the application in
        # front (measured: the Calculator's hosted window is invisible to the
        # opener's inventory) does not stop what the goal dictates.
        if not (last.get("operation") == "app.open" and application_is_in_front(view, application)):
            if folded_goal.startswith(CONTEXT_MENU_GOAL) and last.get("manner") == "menu":
                # Ronda 21 (t-menu-1): the context menu's own act failed: its fallback (choose, then the key) from the
                # whole history, never the same act once more.
                return _context_menu_step(goal[len(CONTEXT_MENU_GOAL):].strip(), view, history)
            if last.get("operation") == "input.visible.click" and last.get("error") == NEEDS_CONFIRMATION_REFUSAL:
                return _named_for_confirmation(view, last, goal)
            # A failed click while the menu the place's own click opened is still on screen: its entry is the step.
            place = folded_goal[len("ir a "):].strip() if folded_goal.startswith("ir a ") else ""
            entry = _menu_opened_by(view, history, place, goal) if place and last.get("operation") == "input.visible.click" else None
            if entry is not None:
                return {"operation": "input.visible.click", "arguments": {"label": entry}, "reason": "el clic abrió un menú"}
            if last.get("operation") != "input.visible.click":
                return None
            if CONTAINER_REFUSAL in str(last.get("error") or ""):
                # Ronda 24b, revisión 3 (D): the worker refused the press on a list, tree, grid or table (its pointer
                # would have chosen whatever row lay at its centre). The goal's own name is still that container, so
                # no rule's retry finds anything else to press but the window's search, and that lookup is blind (it
                # typed «search» into the person's search box on u9). The model decides, told it was a container.
                return None
            # A click that failed (a learned label now ambiguous or gone, measured on Settings after a replay) leaves
            # the goal's own step to be found again on this view, by identity, never the same act once more.
            # Without the failed step its look is not the last one: what the last verified click made appear is the
            # App's newTextAfterClick, never the failed look's newText (stale or empty).
            after_click = view.get("newTextAfterClick")
            retry_view = {**view, "newText": after_click if isinstance(after_click, list) else []}
            # A click on the goal's own name by label alone that found nothing stays tried: the next name (the other
            # language's) is the step, never the same name once more.
            tried = (*_tried, str(last.get("label") or "")) if not isinstance(last.get("index"), int) else _tried
            retried = deterministic_step(
                goal=goal, view=retry_view, history=history[:-1], application=application, objective=objective,
                translate=translate, semantic=semantic, success_check=success_check, _tried=tried,
            )
            if retried is None or retried.get("operation") != "input.visible.click":
                return retried
            arguments = retried.get("arguments") or {}
            same_index = isinstance(arguments, dict) and arguments.get("index") is not None and arguments.get("index") == last.get("index")
            same_label = isinstance(arguments, dict) and arguments.get("index") is None and fold(arguments.get("label")) == fold(last.get("label"))
            if same_index or same_label:
                # Recibo del clic por estado (r15b v3-52, v3-46): the goal's own control is in the view; a state its
                # check asks for is acted on it, and a choice that did not take is said, never looked up blind.
                at = last.get("index") if isinstance(last.get("index"), int) else None
                failed_on = find_control(view, str(last.get("label") or ""), index=at)
                if failed_on is not None:
                    by_state = _state_step(failed_on, history, success_check, view)
                    if by_state is not None:
                        return by_state
                    if _choice_without_effect(failed_on, history, view):
                        return _none(f"el clic en «{str(failed_on.get('name') or '')[:40]}» no tuvo efecto",
                                     code=CLICK_WITHOUT_EFFECT)
                # The goal's own control is the one that failed (measured on Discord: «Cotele» clicked, nothing
                # changed): the place is looked up the way the window offers, as a person would; only a name said
                # without a kind is looked up («la pestaña de Gmail» is never searched as «pestaña de Gmail»).
                parsed = _goal_target(goal)
                if folded_goal.startswith("buscar ") and failed_on is not None and _writable(failed_on) and failed_on.get(
                        "kind") in _FIELD_KINDS and _is_search_field(failed_on) and at in (None, failed_on.get("i")):
                    # r30 (y9, 5 of 6 runs): the search's own field, clicked with no effect to read (a window behind
                    # the person's), takes the search by its label, or nothing does. It was the model's step, which
                    # gave it only when a loaded encoder named the field for its retry, and «none» while E5 loaded.
                    # Only the control at the index that failed: never one of that label elsewhere in the view.
                    text = typed_text(goal[len("buscar "):].strip())
                    return {"operation": "input.text.type", "arguments": _form_field_arguments(failed_on, "", text),
                            "reason": _REASON_FIND}
                if parsed is None or parsed[1] is not None or parsed[3] is not None:
                    return None
                # Ronda 20b, palanca 6 (v3-44: «devices and printers» typed into a Control Panel in Spanish): the
                # lookup after a failed click types the window's language's name, as the first lookup does.
                return _find_step(parsed[2], view, history, navigate=parsed[0] == "ir a ", objective=objective,
                                  others=_lookup_translations(parsed[2], translate))
            return retried
    reason = "el objetivo lo dice"
    focused_slot = _focused_slot_step(goal, view, history)
    if focused_slot is not None:
        return focused_slot
    if folded_goal == "enviar":
        # «… y mandalo»: sending what was written is Enter in the message box, always marked so RiskPolicy asks first
        # (measured: an unmarked Enter sent «prueba BAXY C6» without asking).
        if _steps_ok(history, "input.key.press", key="enter"):
            return None
        typed = view.get("lastTyped") if isinstance(view, dict) else None
        if isinstance(typed, dict) and typed.get("atCaret") is True and typed.get("intoSearch") is True \
                and _keyboard_on_a_search(view) is not None:
            # Ronda 24b (banco r23 c6): the text went where the keyboard was and that was the window's search, which
            # still has it: an Enter there submits a search, never sends a message; RiskPolicy is not asked to confirm
            # a send that is none.
            return _none("el texto quedó en el buscador, no en la caja de mensaje", code=TEXT_NOT_IN_COMPOSER)
        return {"operation": "input.key.press", "arguments": {"key": "enter", "target": "message_composer"},
                "reason": reason}
    if folded_goal.startswith("apretar "):
        key = _key_from_words(folded_goal[len("apretar "):])
        if key is not None and not _steps_ok(history, "input.key.press", key=key):
            return {"operation": "input.key.press", "arguments": key_arguments(key, view, history, blind_asks=True), "reason": reason}
        return None
    if folded_goal.startswith("calcular "):
        expression = _expression_for_typing(goal[len("calcular "):])
        if not expression:
            return None
        if not _steps_ok(history, "input.text.type"):
            return {"operation": "input.text.type", "arguments": {"text": expression}, "reason": reason}
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": key_arguments("enter", view), "reason": reason}
        return None
    if folded_goal.startswith("escribir "):
        text = typed_text(goal[len("escribir "):]).strip()
        if not text or _steps_ok(history, "input.text.type") or _focused_is_password(view):
            return None
        placed = _typing_place_step(text, view, history, reason)
        if placed is not None:
            return placed.get("step")
        if _part_kept_from_the_text(view, goal, objective) is not None:
            # Ronda 20 P1 (v3-11 t2: «escribe ahí» renamed the existing page «Sin título»): the keyboard is on a part
            # of a document the request does not name (its title, its heading). The text never goes there by rule: the
            # body beside it is clicked first; with no body to tell, the model decides with the view. Review 2 of r20
            # P1 (finding 2): the request, not only the sub-goal: «escribe «Compras» como título» reads as the
            # sub-goal «escribir compras», and its title is the objective's.
            return _body_click(view, history)
        off = _off_the_search(view, history)
        if off is not None:
            # Ronda 24b (banco r23 c6): the keyboard was on the window's search (a burst cut by the person left it
            # there) and «prueba BAXY C6» went into it while the message box stayed empty. A free text goes where text
            # is written: the message box is clicked first; with no single place to tell, the model decides.
            how, place = off
            if how == _MODEL_DECIDES or place is None:
                return None
            if how == "stuck":
                return _none(f"el campo «{str(place.get('name') or '')[:40]}» no tomó el teclado, que sigue en el buscador",
                             code=FIELD_NOT_FOCUSED)
            arguments = {"label": str(place.get("name") or "")}
            if isinstance(place.get("i"), int):
                arguments["index"] = place["i"]
            return {"operation": "input.visible.click", "arguments": arguments, "reason": "pongo el cursor donde se escribe"}
        field = _place_to_type(view, history)
        if field is None:
            if not _focused_is_text_field(view) and any(
                    isinstance(control, dict) and "password" in str(control.get("state") or "") for control in view.get("controls") or ()):
                return None  # no focus read on a text field and a password listed: the window's own focus may be it
            return {"operation": "input.text.type", "arguments": _into_the_focused_part({"text": text}, view), "reason": reason}
        on_it = {**view, "window": {**(view.get("window") or {}), "focused": field}}
        if _part_kept_from_the_text(on_it, goal, objective):
            return None  # the one field is a part of a document the request does not name (a note's title): never clicked
        # The keyboard is not on a text field: the field is clicked first, the way a person puts the cursor there
        # (measured: in Discord the text went to the message search instead of the message box). r26 (x5, y4): where the
        # view reads no focus at all (a window behind the person's: that click is never proven) the text names the one
        # field by its label, and the provider writes its value or its edit control or refuses before any effect. Never
        # a name two fields share, a field not written, a box whose Enter would be asked as a message, or a part.
        label = str(field.get("name") or "").rstrip(":： ").strip()
        same = sum(1 for control in view.get("controls") or () if isinstance(control, dict) and control.get("kind") in _EDITABLE_KINDS
                   and fold(str(control.get("name") or "").rstrip(":： ")) == fold(label))
        if _focused_controls(view) or not label or same != 1 or not _writable(field) or _composer_with_text(on_it) \
                or _part_of_the_document(field, view):
            return _click(field, "pongo el cursor donde se escribe")
        return {"operation": "input.text.type", "arguments": {"text": text, "field": label}, "reason": reason}
    if folded_goal.startswith("ir a la direccion "):
        # «andá a es.wikipedia.org»: the browser's address bar, the address, Delete, Enter. The bar completes what is
        # typed with a page of the history, selected after the caret (measured on Opera: «es.wikipedia.org» became
        # «…/wiki/Curicó» and Enter went there); Delete drops that completion and nothing else.
        address = typed_text(goal[len("ir a la direccion "):]).strip()
        if not _steps_ok(history, "input.key.press", key="ctrl_l"):
            return {"operation": "input.key.press", "arguments": {"key": "ctrl_l"}, "reason": reason}
        if not _steps_ok(history, "input.text.type"):
            return {"operation": "input.text.type", "arguments": {"text": address}, "reason": reason}
        if not _steps_ok(history, "input.key.press", key="delete"):
            # Delete erases characters only where the view shows the keyboard on the address field; anywhere else
            # (ctrl_l did not reach the bar, a page took the focus) it would delete what is selected: stop.
            if not _keyboard_on_address_field(view):
                return None
            return {"operation": "input.key.press", "arguments": key_arguments("delete", view), "reason": reason}
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": key_arguments("enter", view), "reason": reason}
        return None
    if folded_goal.startswith("buscar "):
        # «buscá Hades»: the window's own search (field, button or shortcut), the name, then Enter to submit it.
        target = goal[len("buscar "):].strip()
        if not _typed_target(history, target):
            # A search is the window's search, never its navigation menu.
            step = _find_step(target, view, history, navigate=False, choose=False)
            return None if step is None or step.get("operation") == "input.scroll" else step
        if not _steps_ok(history, "input.key.press", key="enter") and not _focused_is_password(view):
            # Enter submits the search only in a field the view shows is a search; anywhere else (a focus that cannot
            # be read, measured on WhatsApp with a chat open) the name may be in a message box and Enter would send
            # it, so RiskPolicy asks first.
            # A field of the view proven to hold the name (or clicked right before it) that is a search or form field
            # submits too, when nothing else in the view may send (r9: the Character Map's «Buscar:» read behind).
            field = _focused_field(view)
            searching = (
                (field is not None and _is_search_field(field)) or _typed_into_written_search(view, history)
                or (_focus_unreadable(view) and _typed_into_plain_field(view, history) is not None
                    and not _composer_with_text(view, history))
            )
            arguments = {"key": "enter"} if searching else {"key": "enter", "target": "message_composer"}
            return {"operation": "input.key.press", "arguments": arguments, "reason": reason}
        return None
    if folded_goal.startswith(REVEAL_GOAL):
        return _reveal_step(goal[len(REVEAL_GOAL):].strip(), view, history)
    if folded_goal.startswith(CONTEXT_MENU_GOAL):
        return _context_menu_step(goal[len(CONTEXT_MENU_GOAL):].strip(), view, history)
    if folded_goal.startswith(FIELD_GOAL):
        unit = _form_unit_step(goal, success_check, view, history, objective, form_check)
        return unit if unit is not None else _field_step(goal, view, history)
    if form_check and folded_goal.startswith("hacer clic en "):
        # Revisión 2 de la ronda 20b (bloqueante 1): the form is evaluated whole again before its button accepts it.
        confirm = _form_confirm_step(form_check, view, history, objective)
        if confirm is not None:
            return confirm
    parsed = _goal_target(goal)
    if parsed is None:
        # A free goal short enough to be a control's name («creá un documento en blanco» on a start page that offers
        # «Documento en blanco»): pressed by meaning once, only past the calibrated threshold and margin; anything
        # else is the model's step.
        creating = _creating_command_step(goal, view, history)
        if creating is not None:
            return creating
        label = _free_goal_label(goal)
        if label is None or semantic is None or any(
            isinstance(step, dict) and step.get("operation") == "input.visible.click" for step in history
        ):
            return None
        return _semantic_step(goal, label, view, history, None, None, (), semantic, _tried)[0]
    head, wanted, target, kind = parsed
    searching = wanted is None and kind is None
    # Going to a place (any «ir a», and a click on a name said without a kind) never changes a setting on the way.
    placing = wanted is None and (head == "ir a " or kind is None)
    navigate = head == "ir a "
    if navigate and searching:
        # A folder's path goes to the window's address field, never to its search (t-scroll-4, v3-48).
        addressed = _address_step(target, view, history)
        if addressed is not None:
            return addressed
        if _address_path(target) is not None:
            # Ronda 21 (pasada r18 t-scroll-4): a folder's path whose address field took nothing more (the click on it
            # landed elsewhere, the field left the view) is the model's to go on with, never the window's search.
            return None
    # The place typed by any of its names (the window's language's, ``_name_to_look_up``) was typed.
    typed = searching and any(_typed_target(history, name) for name in (target, *label_alternatives(target)))
    opened = None if typed else _menu_opened_by(view, history, target, goal)
    if opened is not None:
        # The click on the destination opened a short menu instead of going there (measured on Steam: «BIBLIOTECA»
        # → «Página principal · Colecciones · Descargas»): the entry the goal names, else the destination's own
        # page, else the first entry of a menu in the tree (``_menu_opened_by``).
        return {"operation": "input.visible.click", "arguments": {"label": opened}, "reason": "el clic abrió un menú"}
    if typed:
        # The name was typed into a search: what to click is the result that names it, never the field's echo.
        return _find_step(target, view, history, navigate=navigate, objective=objective)
    # Only a mode's name has two genders on screen; a place keeps the gender said («partido» is no «partida»),
    # neither as a second name nor as the one typo the loose match allows.
    is_mode = _mode_named(target) is not None
    twin = gender_twin(target) if searching and is_mode else None
    names = (target, *label_alternatives(target), *((twin,) if twin else ()))
    other_gender = None if is_mode else gender_twin(target)
    seen = _without_name(view, other_gender) if other_gender else view
    # Revisión 1 de r24b (B1, banco r23 x7): the place is the search itself and its control was already pressed: every
    # route below that would look it up (the find key, Escape on the field that key focused, the scroll) is the model's
    # instead, whatever the view shows now (the button and the field both named so, the button gone behind the field,
    # a navigation item and a button of the same name).
    search_pressed = searching and _search_place_pressed(target, names, history)
    # Ronda 23 (v3-23: «ir a sistema» resolved to the window's system menu «Sistema», the validator vetoed the press and
    # the whole rule went to the model with the encoder cold): what the validator refuses for this goal (the system
    # menu, the window's frame) is never a candidate, so it shadows no place of the same name. Revisión 1 de r23 (a): only
    # to choose among controls named exactly so; when the vetoed one is the only one so named, the step is the model's
    # (as after the veto before) and no control that merely carries the name («Bandeja del sistema») takes its place.
    if _only_vetoed_named(seen, goal, names):
        return None
    seen = _without_vetoed(seen, goal, names)
    if placing:
        seen = _without_fixed_fields(seen)
    chosen = _content_item_chosen(view, history, names) if head == "ir a " and kind is None else None
    if chosen is not None:
        # One click on an item of a content list chose it and opened nothing (measured on Explorer: «Descargas»
        # in the Home view); a person then presses Enter. Enter on a list item sends nothing to anyone, but on an
        # application, a shortcut or a file it may start something: pressed only where the view shows the item is
        # a folder or a drive (``_is_container``), never on a file that runs nor in a view that offers to remove
        # what is chosen (a list of programs); anything else is the model's step.
        if (
            _runs_when_opened(chosen) or _offers_uninstall(view) or _REMOVAL_NAME.search(fold(chosen.get("name")))
            or not _is_container(chosen, view)
        ):
            return None
        return {"operation": "input.key.press", "arguments": key_arguments("enter", view),
                "reason": "el clic sólo eligió el elemento: Enter lo abre"}
    # Going to a place looks among the controls that are not switches first («Bluetooth» as a switch and as the
    # navigation item: the item is the place).
    among = _without_switches(seen) if placing else seen
    if wanted in ("on", "off"):
        # Revision 3 of ronda 20b (B-B): a closed menu's entry that toggles a setting shows no state of now; pressed
        # for «activar» it may switch the setting off. It is never the control set; the same name drawn (the menu
        # opened, its item with its state) is.
        among = _without_state_unknown_switches(among)
    colour = wanted == "selected" and kind is None and is_basic_colour(target)
    if colour or (names_the_colour_kind(target) and names_a_colour(objective)):
        # A colour is its swatch's whole name: «azul» is never «Gris azulado», «rojo» never «Rojo oscuro» nor
        # «Color 1: Rojo» (live e2), and never a tool that picks colours from the canvas. Estabilización G3 (f2nb
        # t3-c19): the kind alone («hacer clic en color») of a colour the person names is only a control of that whole
        # name, never one that merely carries the word («Editar colores» opened a modal dialog); the colour named is
        # chosen by its own sub-goal (``missions``: a click on the kind before the colour is that one choice). «ir a
        # colores» with no colour named is a place (Settings' «Colores»), looked up as any other.
        control = _swatch(among, names)
        if control is None:
            return _colour_step(view, history, names, target, _tried) if colour else None
    else:
        control = next(
            (found for name in names if (found := find_control(among, name, kind=kind, placing=placing)) is not None), None,
        )
    own = own_place_button(seen, target) if navigate and kind is None and wanted is None else None
    if own is not None:
        # Encargo S (banco e2 u1, y8: a stranger's list «Tu biblioteca» on the home page was pressed for the player's
        # library): a place with its own button is that button's, never another control of the same name; never while
        # it says the place is open (arriving is then the check's, and the step the model's).
        if own[1]:
            return None
        control = own[0]
    if control is None and placing:
        control = next((found for name in names if (found := find_control(seen, name, kind=kind, placing=True)) is not None), None)
    alias: dict[str, str] | None = None
    translated: tuple[str, ...] = ()
    if (
        control is None and not colour and translate is not None and wanted in (None, "selected", "on", "off")
        and not _controls_carrying(seen, names, kind, placing)
        and not (kind is None and any(_text_line_with(seen, name, placing=placing) is not None for name in names))
    ):
        # No name the goal or the table gives is on screen: the other language's names (``LabelTranslator``), used
        # only where the view shows a control whose whole name is one of them, never a name the table knows as
        # another place's, never a switch while going somewhere, never the person's own content, and never an act
        # the goal does not ask for (``_translation_clickable``).
        translated = tuple(
            name for name in translate(target)
            if fold(name) not in {fold(known) for known in names} and _translation_fits(target, name)
        )
        for name in translated:
            found = find_control(among, name, kind=kind, placing=placing)
            if found is None and placing:
                found = find_control(seen, name, kind=kind, placing=True)
            if (
                found is not None and _names_by_translation(found, name)
                and not (placing and _is_switch(found)) and _interface_control(found, view)
                and _translation_clickable(goal, str(found.get("name") or ""))
            ):
                control = found
                alias = {"from": target, "to": str(found.get("name") or name)}
                break
    if control is None and wanted in ("on", "off") and any(
        _state_unknown_switch(find_control(seen, name, kind=kind)) for name in names
    ):
        # Revision 3 of ronda 20b (B-B): only a closed menu's entry carries the name, its state unknown: the model
        # decides (it opens the menu, where the entry shows on or off), never a blind press.
        return None
    if control is not None and placing and _is_switch(control):
        # Going somewhere never changes a setting on the way: a switch named like the place is not the place, and
        # neither is its written name; the place is looked up the way the window offers (never once the search itself
        # was pressed: B1 of r24b's first review).
        return _find_step(
            target, view, history, navigate=navigate, objective=objective, others=translated,
        ) if searching and not search_pressed else None
    option = view_option_named(target) if control is None else None
    if option is not None:
        # Ronda 20b, palanca 6 (v3-41: «iconos grandes» typed into the Control Panel's search): an option of the view or
        # of its order is chosen in the control that shows the current one, whatever the goal's verb («activar», «ir a»,
        # «hacer clic en»); never looked up as content (``_find_step`` refuses that for an option).
        opening = _view_option_step(option, view, history, goal, view_option_family(target))
        if opening is not None:
            return opening
    if control is None and (wanted in ("on", "selected") or head == "hacer clic en "):
        # «poné el modo científico» where no switch is called so: the mode is chosen like a place (the
        # Calculator's modes are items of its navigation). Uso real v3 tanda 3 c18 «ahora ponla en modo programador»,
        # restated «En la Calculadora, haz clic en «Programador»»: a mode clicked or selected by its name is chosen
        # the same way, never looked up by name behind a closed navigation (two clicks not found, then Ctrl+K, Esc,
        # Ctrl+F, Esc into the Calculator).
        mode = _mode_named(target)
        if mode is not None:
            # The mode's place, with what the goal's own step has: the matcher, the translator, the check and the request.
            stepped = deterministic_step(
                goal=f"ir a {mode}", view=view, history=history, application=application, objective=objective,
                translate=translate, semantic=semantic, success_check=success_check,
            )
            return (
                None if option is not None and _searches_content(stepped) and _view_option_shown(view, target) else stepped
            )
    if control is None and kind == "TabItem" and wanted is None and _window_fold(application) != _window_fold(BROWSER_CATEGORY):
        # A tab of an editor's workspace exists only with a document open; on the start page a person first creates
        # the blank one it offers (live v5/v6: Excel and Word opened on «Libro/Documento en blanco» and recent files).
        started = _start_page_step(view, history, objective, application)
        if started is not None:
            return started
    carrying = _controls_carrying(seen, names, kind, placing) if control is None and wanted is None else []
    if len(carrying) >= 2:
        # Two controls carry the name (measured on Discord: «Cotele» was a server and an activity card; on Explorer
        # «Descargas» is the side list's item and a tile of the Home view). The one navigation item among them (an
        # item of a list in the window's left column, not content) is the place; otherwise neither is surely it,
        # the written word is the same doubt, and the place is looked up instead.
        navigation = [found for found in carrying if _navigation_item(found, view)]
        nodes = [found for found in carrying if str(found.get("kind")) == "TreeItem"]
        if navigate and not navigation and len(nodes) == 1 and all(
            found is nodes[0] or is_content_item(found, view) for found in carrying
        ):
            # Ronda 23 (v3-23): going to a place that is a node of a tree and a row of the content that lists what the
            # current node holds: the tree's node is the place (the row only chooses), wherever the tree is drawn.
            navigation = nodes
        if len(navigation) == 1 and not _steps_ok(history, "input.visible.click", label=str(navigation[0].get("name") or "")):
            return _click(navigation[0], reason)
        if search_pressed:
            return None
        return _find_step(target, view, history, navigate=navigate, objective=objective, others=translated) if searching else None
    if control is None and search_pressed:
        return None
    if control is None:
        # A window drawn without an accessible tree (CEF, Electron, canvas: measured on Steam, one control and
        # the navigation only in the OCR lines): the word written on screen is clicked by its label, and the
        # click's cascade (UIA → OCR → vision) finds where it is. Never the written name of a switch.
        written = next(
            (name for name in names
             if (line := _text_line_with(seen, name, placing=placing)) is not None
             and not (placing and _names_a_switch(view, line)) and not opens_help(line, view, goal, objective)),
            None,
        ) if kind is None else None
        if written is None and kind is None and not _message_window(view):
            # A translation written on screen in a window without a tree: a line that is its whole name, never a
            # sentence that mentions it, a switch's name, an act the goal does not ask for, nor a conversation's
            # window (its lines are the person's content).
            written = next(
                (name for name in translated
                 if (line := _text_line_with(seen, name)) is not None and fold(line).strip() == fold(name).strip()
                 and not (placing and _names_a_switch(view, line)) and _translation_clickable(goal, line)
                 and not opens_help(line, view, goal, objective)),
                None,
            )
            alias = {"from": target, "to": written} if written is not None else None
        if wanted in (None, "selected") and written is not None and not _steps_ok(history, "input.visible.click", label=written):
            step = {"operation": "input.visible.click", "arguments": {"label": written}, "reason": reason}
            return {**step, "alias": alias} if alias else step
        # P1: no name of the goal is on screen, but a control may say it with other words («video library» is
        # «Biblioteca de videos», «firewall & network protection» is «Firewall y protección de red»): pressed without
        # the model only past the calibrated similarity and margin and the safety filters; a similar name below that
        # leaves the step to the model, which sees it ranked and named (P2), before any blind search.
        similar_click, similar = (None, ()) if colour or written is not None else _semantic_step(
            goal, target, view, history, wanted, kind, translated, semantic, _tried,
        )
        if similar_click is not None:
            return similar_click
        # A navigation button not opened yet goes first: right after a cold start a name clicked by label alone is
        # waited for as the application draws (live y1: «programador» took 39 s to be not found; it was behind
        # «Abrir navegación»).
        opener_first = navigate and _navigation_opener(view, history) is not None
        by_name = written is None and kind is None and wanted in (None, "selected") and not opener_first
        if (
            searching and written is None and not similar and head in _GOING_HEADS
            and not _said_in_other_language(target, view, objective)
        ):
            # Ronda 21 (v3-26): the place may live inside a collapsed node of the window's navigation tree; the nodes
            # open before any click by name off the view (a tree of hundreds of nodes takes the whole sub-goal's clock
            # to search: v3-25) and before any search. A place said in another language than the window's never shows
            # by its letters inside a node («windows logs» is «Registros de Windows», «library» is «Biblioteca…»): it
            # is the model's to read by its meaning (``_blind_lookup``), never opened for blind.
            # Revision 1 (finding 1): while the window's current node is not open, what the content pane shows is what
            # that node holds (a folder's files and folders, the commands on them), and a view that lists only part of
            # the window leaves most of it out: the click by name off the view resolves against the whole tree, the
            # content included, and goes first; the nodes open only once it found nothing.
            # Revision 2 (finding 1): with the current node open too (a console's root, «selected expanded»), the
            # commands of its actions pane are no place of the tree («Filtrar registro actual», «Crear tarea básica»)
            # and a partial view leaves them out as well: the click by name goes first whatever the node shows, and the
            # nodes open only once a click by name of this sub-goal found nothing (in the history, or the last step
            # retried here with its label tried).
            if by_name and _lists_part_of_the_tree(view) and not _tried and not _name_click_not_found(history):
                unlisted = _unlisted_name_click(view, history, names, _tried, objective)
                if unlisted is not None:
                    return unlisted
            descent = _tree_descent_step(target, view, history, semantic)
            if descent is not None:
                return descent
        if by_name:
            unlisted = _unlisted_name_click(view, history, names, _tried, objective)
            if unlisted is not None:
                return unlisted
        if semantic is not None and not _search_started(history) and searching:
            # P5: an option often lives inside a collapsed control (a «Ver por» list, a menu button): up to two of
            # them, the most similar to the goal first, are opened before any search.
            unfolded = _collapsed_to_open(goal, target, view, history, translated, semantic, similar)
            if unfolded is not None:
                return unfolded
        if similar and not _search_started(history):
            # The model decides among the similar names (the literal search stays its fallback, ``_decide_step``).
            return None
        if searching and written is None and _held_for_the_encoder(
            semantic, target, names, translated, translate, view, history, objective,
        ):
            # lat-e5, contracase v3-14: the encoder was still loading, the place has no other name (the
            # table's or the translator's) and was said in another language than the window's: the model decides first
            # with the view (it reads «Biblioteca de videos» for «video library»); the literal search stays its
            # fallback (``_decide_step``).
            return None
        # Not on screen: looked up the way any window offers (search field, quick switcher, find, the list).
        return _find_step(
            target, view, history, navigate=navigate, objective=objective, others=translated,
        ) if searching and written is None else None
    states = str(control.get("state") or "").split()
    if wanted is not None and (wanted in states or (wanted == "selected" and "on" in states)):
        # Already so; a tool or a colour chosen shows as selected or pressed.
        return None
    if _steps_ok(history, "input.visible.click", label=str(control.get("name") or "")) or _click_failed(
        _before_unfolding_misses(history), str(control.get("name") or "")
    ):
        # Recibo del clic por estado (r15b v3-46: «Componentes» chosen and still collapsed, the check asking for it
        # expanded, then «componentes» typed into «Buscar esto:», Escape, ctrl_k, ctrl_a, ctrl_f; v3-52: «Vídeo» pressed
        # and not chosen, then ctrl_k and ctrl_f): the control is in the view, so its state is what is acted on (opened,
        # by its identity) or a choice that did not take is said; looking it up is only for what is not on screen.
        by_state = _state_step(control, history, success_check, view)
        if by_state is not None:
            return by_state
        if _choice_without_effect(control, history, view):
            return _none(f"el clic en «{str(control.get('name') or '')[:40]}» no tuvo efecto", code=CLICK_WITHOUT_EFFECT)
        chosen_click, presses = _chosen_place_click(control, history, view)
        if chosen_click is not None:
            # Ronda 24b (banco r23 s04): a place's item (a tree node, a tab, a navigation item) the view shows chosen and
            # the sub-goal not arrived: never looked up blind (the search field typed «descargas» and turned the window
            # into an empty search). Its place measured as stayed (placeMoved false, after the worker's second Invoke),
            # or the item already pressed twice, is said as a click without effect (C7Y5, banco fp3 y5: never «no vi el
            # control»). C7Y5: a receipt whose place «moved» while the arrival is not seen (the measure saw the
            # Explorer's header redrawn and the folder stayed) gets the press the worker gives an unmoved one: once
            # more, on the chosen item, which opens it. Revisión 1 (B3): a receipt without the measure, pressed once,
            # leaves the step to the model (a tab chosen by Select alone may have changed).
            if chosen_click.get("placeMoved") is False or presses > 1:
                return _none(f"el clic en «{str(control.get('name') or '')[:40]}» no tuvo efecto", code=CLICK_WITHOUT_EFFECT)
            return _click(control, reason) if chosen_click.get("placeMoved") is True else None
        if search_pressed or is_search_place(target):
            # Ronda 24b (banco r23 x7): the place is the search itself and its own control was pressed: no find key, no
            # Escape on the field that key focused, no scroll. When the shell does not give the arrival, the model
            # decides with the view.
            return None
        # Clicked and not there yet (measured on Discord: the name was written in an activity card, not the
        # channel), or clicked and refused (measured 2026-10-07: a field that cannot be pressed was clicked four times
        # in one sub-goal): looked up the way the window offers, never clicked again.
        return _find_step(target, view, history, navigate=navigate, objective=objective, others=translated) if searching else None
    if searching and head == "ir a ":
        # Ronda 21 (v3-23 «andá a registros de windows, sistema»): going to a row of the content that only shows what
        # the collapsed current node holds. Revision 1 (finding 2): only going there; «hacer clic en» a visible row
        # presses that row (a folder listed in a file window is chosen, never entered through the tree).
        first = _current_node_first(control, view, history)
        if first is not None:
            return first
    arguments = {"label": str(control.get("name") or target)}
    if isinstance(control.get("i"), int):
        arguments["index"] = control["i"]
    step = {"operation": "input.visible.click", "arguments": arguments, "reason": reason}
    return {**step, "alias": alias} if alias else step


def _without_fixed_fields(view: dict) -> dict:
    """The view without the fields that only show a value (read-only, or a browser's address): going to a place never
    clicks one (measured 2026-10-07: «search» matched a web app's read-only «Address and search bar», whose clicks
    all failed)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [
        control for control in controls
        if not (
            isinstance(control, dict) and control.get("kind") in {"Edit", "ComboBox", "Document"}
            and ("readonly" in str(control.get("state") or "").split() or _ADDRESS_NAME.search(fold(control.get("name"))))
        )
    ]}


# Recibo del clic por estado (r15b): a click on a control that is in the view and did not take («el clic no tuvo
# efecto»), said instead of looking the control up blind.
CLICK_WITHOUT_EFFECT = "click_without_effect"
# Ronda 24b, revisión 3 (D): the worker's refusal of a press on a container (WindowsVisibleControlAdapter's code).
CONTAINER_REFUSAL = "visible_control_is_container"
# Encargo V (banco e2, c7): the worker's refusal of a control whose name asks for the person's word while the click's
# label did not («cotele» resolved to «Cotele!!!😎, Canal de voz, Choche»); the step records its «name».
NEEDS_CONFIRMATION_REFUSAL = "visible_control_needs_confirmation"
_REASON_NAMED_FOR_CONFIRMATION = "el control sale al mundo: lo nombro entero para que me pidan confirmación"
# What a list, a tree or tabs choose when pressed: their «selected» state says whether the press took.
_CHOSEN_KINDS = frozenset({"ListItem", "TreeItem", "TabItem", "DataItem"})


def _state_step(control: dict, history: list[dict], success_check: str | None, view: dict) -> dict[str, object] | None:
    """The act on the state of a control of the view its check asks for (r15b v3-46): a collapsed control the check
    wants expanded, or a collapsed tree item while the check names a control the view does not list (what it holds
    appears when it opens), is opened by its identity (``manner`` «open», goal v3 B3), once. A control the check only
    wants chosen is never opened; a check that names nothing of it changes nothing."""

    name = str(control.get("name") or "").strip()
    states = str(control.get("state") or "").split()
    if not name or "collapsed" not in states or not isinstance(control.get("i"), int):
        return None
    if any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("manner") == "open"
        and fold(step.get("label")) == fold(name)
        for step in history
    ):
        return None
    atoms = _check_atoms(success_check)
    wanted = any(atom == fold(name) and state == "expanded" for atom, state in atoms)
    # Review of the branch (finding 6): a check that asks this control for another state («selected») wants it chosen,
    # never opened, whatever else it names.
    own = {state for atom, state in atoms if atom == fold(name) and state}
    holds = control.get("kind") == "TreeItem" and not own and any(
        atom != fold(name) and find_control(view, atom) is None for atom, _ in atoms
    )
    if not (wanted or holds):
        return None
    return {"operation": "input.visible.click", "arguments": {"label": name, "index": control["i"], "manner": "open"},
            "reason": "el control sigue cerrado: lo abro"}


def _choice_without_effect(control: dict, history: list[dict], view: dict) -> bool:
    """A control that is chosen when pressed (an item of a list, a tree or tabs), still not chosen in the view while
    another item of its list is (its kind and, when both say one, its zone: the list shows where the window is; v3-52,
    «General» chosen, «Vídeo» not), whose last click did not choose it: failed because the window stayed the same (the
    worker's ``visible_button_postread_unchanged``, after every way it has to choose it), or answered with its receipt
    saying ``selected`` false while only the picture changed (the real v3-52 receipt: ok, surfaceChanged, selected
    false; the focus moved). The click had no effect, and that is said. A list that marks nothing chosen proves
    nothing (Discord's «Cotele» was a card's word, not the server: it is looked up)."""

    kind = control.get("kind")
    if kind not in _CHOSEN_KINDS or "selected" in str(control.get("state") or "").split():
        return False
    zone = control.get("zone") or None
    controls = view.get("controls") if isinstance(view, dict) else None
    if not any(
        isinstance(other, dict) and other is not control and other.get("kind") == kind
        and "selected" in str(other.get("state") or "").split()
        and (zone is None or not other.get("zone") or other.get("zone") == zone)
        for other in (controls if isinstance(controls, list) else [])
    ):
        return False
    name = fold(control.get("name"))
    clicks = [
        step for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click" and fold(step.get("label")) == name
    ]
    if not clicks:
        return False
    last = clicks[-1]
    if last.get("ok") is False:
        return last.get("error") == "visible_button_postread_unchanged"
    # Review of the branch (finding 3): the receipt that held by the picture alone, its own «selected» false.
    return last.get("ok") is True and last.get("selected") is False and not last.get("manner")


# Ronda 24b: what a click chooses as a place (a tree's node, a tab), whose receipt says whether the place moved.
_PLACE_ITEM_KINDS = frozenset({"TreeItem", "TabItem"})


def _place_item(control: dict, view: dict | None) -> bool:
    """Revisión 1 de r24b (B2): an item whose choice is a place: a tree's node, a tab, or an item of the window's
    navigation (``_navigation_item``: WinUI's NavigationView and many Electron side lists are ``ListItem`` in the left
    column). A content row that only chooses is not."""

    return control.get("kind") in _PLACE_ITEM_KINDS or (
        isinstance(view, dict) and control.get("kind") == "ListItem" and _navigation_item(control, view)
    )


def _chosen_without_arriving(control: dict, history: list[dict], view: dict | None = None) -> bool:
    """Ronda 24b (banco r23 s04: «Downloads» of Explorer's navigation tree chosen by Invoke, ``selected`` true and
    ``surfaceChanged`` false; the mind then typed «descargas» into the window's search): a place's item the view shows
    chosen whose last click held by the choice alone and whose receipt measured the place as not moved
    (``placeMoved`` false). Revisión 1 (B3): a receipt without the measure is no proof that the place stayed."""

    last, _ = _chosen_place_click(control, history, view)
    return last is not None and last.get("placeMoved") is False


def _search_place_pressed(target: str, names: tuple, history: list[dict]) -> bool:
    """Revisión 1 de r24b (B1): the goal's place is the search itself (``is_search_place``) and a click on a control
    named so (any of the goal's names, or any name of the search) went through in this sub-goal."""

    if not is_search_place(target):
        return False
    folded = {fold(name) for name in names}
    return any(
        fold(step.get("label")) in folded or is_search_place(step.get("label"))
        for step in _steps_ok(history, "input.visible.click")
    )


def _chosen_place_click(control: dict, history: list[dict], view: dict | None = None) -> tuple[dict | None, int]:
    """The last click on a place's item (``_place_item``) the view shows chosen, when it held by the choice (ok and
    selected, the receipt not saying that the surface changed), and how many such clicks the sub-goal took; None
    otherwise. A list's content row that only chooses is no place; a control not shown chosen (Discord's card word
    «Cotele») is not either; and a press whose surface changed is the arrival's to judge. Its place measured as moved
    (``placeMoved`` true) still holds: the caller is here because the arrival was not seen."""

    if not _place_item(control, view) or "selected" not in str(control.get("state") or "").split():
        return None, 0
    name = fold(control.get("name"))
    clicks = [
        step for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click" and fold(step.get("label")) == name
        and not step.get("manner")
    ]
    pressed = [step for step in clicks if step.get("ok") is True and step.get("surfaceChanged") is not True]
    held = bool(pressed) and clicks[-1] is pressed[-1] and (pressed[0].get("selected") is True)
    return (clicks[-1], len(pressed)) if held else (None, 0)


def _only_vetoed_named(view: dict, goal: str | None, names: Iterable[str]) -> bool:
    """Revisión 1 de r23 (a): the only controls named exactly as the goal's place are ones the validator vetoes for
    this goal (OBS «Ajustes»: the system menu «Sistema» beside the group «Bandeja del sistema»)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return False
    vetoed = _vetoed_controls(view, goal)
    names = tuple(names)
    return bool(vetoed) and _named_exactly(controls, names, vetoed, kept=False) and not _named_exactly(
        controls, names, vetoed, kept=True)


def _without_switches(view: dict) -> dict:
    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [control for control in controls if not (isinstance(control, dict) and _is_switch(control))]}


# What may follow a name at the start of a control's name that is still that name («Cotele (servidor)», «general ·
# Mi servidor», «Descargas - Anclado»); a name inside a sentence is not one.
_NAME_SEPARATORS = (" (", ",", " ·", " -", ":")


def _carries_name(control_name: str, name: str) -> bool:
    """A control's name is ``name``: equal folded, or ``name`` followed by a separator at its start."""

    folded, wanted = fold(control_name), fold(name)
    return bool(wanted) and (folded == wanted or any(folded.startswith(wanted + mark) for mark in _NAME_SEPARATORS))


def _controls_carrying(view: dict, names: Iterable[str], kind: str | None, placing: bool) -> list[dict]:
    """The controls (of ``kind`` when given; never a switch while going to a place) that carry one of the names as
    their own (``_carries_name``): a message that says «… en general …» does not make «general» two places."""

    names = tuple(names)
    controls = view.get("controls") if isinstance(view, dict) else None
    return [
        # Ronda 23 (v3-23): a row's own cell is the row, never a second carrier (``_row_cell``).
        control for control in (_without_row_cells(controls) if isinstance(controls, list) else [])
        if isinstance(control, dict) and (kind is None or control.get("kind") == kind)
        and not (placing and _is_switch(control))
        and any(_carries_name(str(control.get("name") or ""), name) for name in names)
    ]


def _controls_naming(view: dict, names: Iterable[str], kind: str | None, placing: bool) -> int:
    """How many controls carry one of the names as their own (``_controls_carrying``)."""

    return len(_controls_carrying(view, names, kind, placing))


FIELD_NOT_FOCUSED = "field_not_focused"
TEXT_NOT_IN_COMPOSER = "text_not_in_composer"


def _named_for_confirmation(view: dict, last: dict, goal: str) -> dict[str, object] | None:
    """The click the worker left unpressed because the control's name goes out to the world and the label did not say so
    (``NEEDS_CONFIRMATION_REFUSAL``): the same control, named whole, so RiskPolicy asks for this invocation (bypass
    presses it). Only a world act the goal names («ir a cotele» and «Cotele!!!😎, Canal de voz, Choche»); anything
    else (an act the goal does not name, a removal) is the model's, as before."""

    name = str(last.get("name") or "").strip()
    if not name or world_act(name) is None or unasked_world_act(goal, name):
        return None
    control = find_control(view, name)
    if control is not None and fold(control.get("name")) == fold(name):
        return _click(control, _REASON_NAMED_FOR_CONFIRMATION)
    return {"operation": "input.visible.click", "arguments": {"label": name}, "reason": _REASON_NAMED_FOR_CONFIRMATION}
