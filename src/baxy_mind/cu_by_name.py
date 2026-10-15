"""What the listing does not carry: a click by the goal's name alone on a view that lists only part of the
window, and a colour chosen by its swatch or its nearest shade.
"""

from __future__ import annotations

from typing import Iterable

from .semantic.colours import changes_the_tool, colour_shades, screen_language
from .semantic.cu_buscar import OPENS_ELSEWHERE
from .semantic.missions import fold
from .cu_view import _shown_as_words, _view_lines, _view_words
from .cu_acts import _click
from .cu_history import _steps_ok
from .cu_unasked import _REMOVAL_NAME, opens_help
from .cu_languages import _in_window_language
from .cu_address import _PATH_NAME
from .cu_lookup import REASON_BY_NAME


# How many controls the App lists in a view (its ``limit``); a view without ``controlCount`` that lists this many may
# leave out the rest of the window's tree.
_LISTED_CONTROLS = 60

REASON_SHADE = "la ventana no tiene ese color por su nombre: elijo su tono más cercano"


def _swatch(view: dict, names: Iterable[str]) -> dict | None:
    """The one listed control whose whole name is one of ``names`` (a colour's swatch), never a tool that picks
    colours; None when there is none or more than one."""

    wanted = {fold(name) for name in names if fold(name)}
    controls = view.get("controls") if isinstance(view, dict) else None
    found = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and fold(control.get("name")) in wanted and not changes_the_tool(control.get("name"))
    ]
    return found[0] if len(found) == 1 else None


def _colour_step(view: dict, history: list[dict], names: tuple[str, ...], target: str, tried: Iterable[str]) -> dict[str, object] | None:
    """A colour the listing does not carry by its name: the name by label alone first (beyond the listed controls),
    then the closest of its shades the view lists, then each of its shades by label alone, closest first, in the
    window's language when its names tell it (measured on Paint: no «Azul», «Añil» is the blue of the palette). Each
    label once per sub-goal; the label keeps the written spelling, which the click matches whole."""

    lines = {fold(line) for line in _view_lines(view)}
    written = next((name for name in names if fold(name) in lines), None)
    if written is not None and not _steps_ok(history, "input.visible.click", label=written):
        # Written on screen whole, outside the accessible tree: its label, which the click's cascade finds.
        return {"operation": "input.visible.click", "arguments": {"label": written}, "reason": "el objetivo lo dice"}
    by_name = _unlisted_name_click(view, history, names, tried)
    if by_name is not None:
        return by_name
    clicked = {
        str(step.get("label") or "").casefold() for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    } | {str(label).casefold() for label in tried}
    controls = view.get("controls") if isinstance(view, dict) else None
    listed = [str(control.get("name") or "") for control in controls if isinstance(control, dict)] if isinstance(controls, list) else []
    language = screen_language([*listed, *_view_lines(view)])
    shades = [shade for shade in colour_shades(target, language) if shade.casefold() not in clicked]
    for shade in shades:
        swatch = _swatch(view, (shade,))
        if swatch is not None and str(swatch.get("name") or "").casefold() not in clicked:
            if "selected" in str(swatch.get("state") or "").split():
                return None
            return _click(swatch, REASON_SHADE)
    if not _lists_part_of_the_tree(view) or not shades:
        return None
    return {"operation": "input.visible.click", "arguments": {"label": shades[0]}, "reason": REASON_SHADE}


def _lists_part_of_the_tree(view: dict) -> bool:
    """The view lists only part of the window's controls: ``controlCount`` (all the tree holds) above the listed ones,
    or, without it, the listing full at the App's limit."""

    controls = view.get("controls") if isinstance(view, dict) else None
    listed = len(controls) if isinstance(controls, list) else 0
    count = view.get("controlCount") if isinstance(view, dict) else None
    if isinstance(count, int) and not isinstance(count, bool):
        return count > listed
    return listed >= _LISTED_CONTROLS


# At most this many of a goal's names are looked up blind (by label alone, against the whole tree) in a sub-goal.
_BLIND_NAMES = 2


def _unlisted_name_click(
    view: dict, history: list[dict], names: Iterable[str], tried: Iterable[str] = (), objective: str | None = None,
) -> dict[str, object] | None:
    """A click by label alone (no index) on the goal's own name, the person's word first and then its other names,
    when the view lists only part of the window and neither a listed control nor a written line carries it: the
    click resolves the label against the whole tree (measured on Paint: the palette's colours lie beyond the 60
    listed controls, and the model clicked the colour picker tool and a shape instead). Each name once per sub-goal,
    failed or not; never a name that removes something."""

    if not _lists_part_of_the_tree(view):
        return None
    clicked = {
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    } | {fold(label) for label in tried}
    names = tuple(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if any(_REMOVAL_NAME.search(fold(name)) or OPENS_ELSEWHERE.search(fold(name)) for name in names):
        return None
    # A path is an address, never a control's name (t-scroll-4: «c:\windows\system32» clicked by label and not found).
    names = tuple(name for name in names if not _PATH_NAME.search(name))
    # The whole tree searched for two of the goal's names and neither there: its other names are synonyms the window
    # does not hold either (pasada r7, v3-58: «configuracion», «ajustes», «preferences», «preferencias», «settings»,
    # each a step of ~1.7 s, twice). The place is looked up the way the window offers, or the model decides.
    not_found = {
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and step.get("error") == "visible_button_not_found" and not isinstance(step.get("index"), int)
    } | {fold(label) for label in tried}
    if len(not_found & {fold(name) for name in names}) >= _BLIND_NAMES:
        return None
    # The name the window itself writes somewhere (a word of a listed control or a line on screen) goes first: it is
    # the window's language, and a click on the other language's name costs one of the sub-goal's steps.
    shown = _view_words(view)
    # Then the window's language, when it and the request's are told apart (t-scroll-3, r9: «fonts» was clicked before
    # «fuentes» on a Spanish Settings).
    ordered = _in_window_language(names[0], names[1:], view, objective) if names else names
    names = tuple(sorted(ordered, key=lambda name: not _shown_as_words(fold(name), shown)))
    for name in names:
        # Never the offer to look the name up in the help or the web (r15b v3-44), as any other rule's press.
        if fold(name) in clicked or opens_help(name, view, objective):
            continue
        return {"operation": "input.visible.click", "arguments": {"label": name}, "reason": REASON_BY_NAME}
    return None
