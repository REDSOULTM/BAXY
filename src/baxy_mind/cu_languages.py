"""A place said in another language than the window's: the translations that may name it, a control found by
one, and the name a lookup types.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .semantic.account_acts import unasked_world_act
from .semantic.colours import changes_the_tool, screen_language
from .semantic.cu_buscar import OPENS_ELSEWHERE
from .semantic.missions import fold, label_alternatives
from .semantic.request import evident_language, name_language
from .cu_view import _short_name, _shown_as_words, _view_lines, is_content_item
from .cu_goals import colour_goal
from .cu_fields import _message_window
from .cu_history import _looked_up_as
from .cu_unasked import _ELSEWHERE_WORDS, _REMOVAL_NAME, unasked_act


def _lookup_translations(target: str, translate: Callable[[str], tuple[str, ...]] | None) -> tuple[str, ...]:
    """The other language's names of the place (``LabelTranslator``) a lookup may type, as the first lookup takes them:
    never one of the names already said, never one that does not fit the place (``_translation_fits``)."""

    if translate is None or not str(target or "").strip():
        return ()
    said = {fold(name) for name in (target, *label_alternatives(target))}
    return tuple(name for name in translate(target) if fold(name) not in said and _translation_fits(target, name))


# The kinds whose name may carry a translated place inside a few more words, the way the worker's ``Test-NameHolds``
# holds a label: a link «Ver dispositivos e impresoras» is the place «devices and printers» (measured on v3-44: the
# whole-name rule missed it on screen and the English name was typed into the window's search).
_CONTAINED_TRANSLATION_KINDS = frozenset({"Hyperlink", "MenuItem", "TreeItem", "ListItem"})


def _names_by_translation(control: dict, name: str) -> bool:
    """The control is the place a translated ``name`` names: its whole name, or (a link, a menu, tree or list item) a
    short name that holds the translation as whole words. ``find_control`` already made it the only one."""

    own, wanted = fold(control.get("name")).strip(), fold(name).strip()
    if own == wanted:
        return True
    return (
        str(control.get("kind")) in _CONTAINED_TRANSLATION_KINDS and _shown_as_words(wanted, own)
        and _short_name(own, wanted) and len(own.split()) <= len(wanted.split()) + 2
    )


def _translation_fits(said: str, translation: str) -> bool:
    """A translation the table does not know as another place's name: «Diseño» is the table's «design», so it is
    never what «layout» is called, whatever the model says (the table goes first, contract §4.4.1)."""

    known = label_alternatives(translation)
    return not known or fold(said).strip() in {fold(name).strip() for name in known}


def _translation_clickable(goal: str, name: str) -> bool:
    """A control found by a translation is clicked only when it is no act the goal does not ask for: the name came from
    the model, not from the person, so the guards the model's own clicks pass (``_validated_step``) apply to it: an
    account act («Siguiendo», «Guardar en tu biblioteca»), a removal, a control that opens another tab or window, a
    tool while choosing a colour; nor an act that goes out to the world («Iniciar Transmisión», «Compartir») that the
    goal does not name (``unasked_world_act``): neither pressed nor shown as like the goal."""

    folded = fold(name)
    return not (
        unasked_act(name, goal) is not None
        # Ronda 29 (v3-53: «Iniciar Transmisión» named as like «vuelve a activarlo»): nor what goes out to the world.
        or unasked_world_act(goal, name)
        or _REMOVAL_NAME.search(folded)
        or (OPENS_ELSEWHERE.search(folded) and not _ELSEWHERE_WORDS.search(fold(goal)))
        or (colour_goal(goal) is not None and changes_the_tool(name))
    )


# The kinds of a window's interface that a translation may name: tabs, menus, buttons, links, headings and the
# window's navigation; never a content item (a file, a result, a chat, a contact).
_TRANSLATED_ITEM_KINDS = frozenset({"ListItem", "TreeItem"})


def _interface_control(control: dict, view: dict) -> bool:
    """A control of the window's interface, where a translated name may land: no DataItem, no item of a content view,
    and no list or tree item of a window that writes to people (a chat's list holds conversations and contacts)."""

    kind = str(control.get("kind") or "")
    if kind == "DataItem" or is_content_item(control, view):
        return False
    return kind not in _TRANSLATED_ITEM_KINDS or not _message_window(view)


def _said_in_other_language(target: str, view: dict, objective: str | None) -> bool:
    """The place was said in a language other than the window's: the window's own names tell its language
    (``screen_language``), the request's words tell another (``evident_language``), and the name as said does not
    spell itself in the window's language (``name_language``: «andá a fonts» on an English Settings names the place
    as the window shows it, inside a Spanish sentence)."""

    if not objective or not str(target or "").strip():
        return False
    controls = view.get("controls") if isinstance(view, dict) else None
    listed = [str(control.get("name") or "") for control in controls if isinstance(control, dict)] if isinstance(controls, list) else []
    screen = screen_language([*listed, *_view_lines(view)])
    said = evident_language(objective)
    if screen is None or said is None or screen == said:
        return False
    return name_language(target) != screen


def _in_window_language(target: str, others: Iterable[str], view: dict, objective: str | None) -> tuple[str, ...]:
    """The place's names (``target`` as said, then ``others``: the table's or the translator's), the window's language
    first when the place was said in another (``_said_in_other_language``): the name as said goes last and, among the
    others, the ones that share no word with it go first (t-scroll-3, r9: «fonts» typed into a Spanish Settings whose
    page is «Fuentes»). Otherwise the order as said."""

    names = tuple(dict.fromkeys(str(name).strip() for name in (target, *others) if str(name).strip()))
    if len(names) < 2 or not _said_in_other_language(names[0], view, objective):
        return names
    own = set(fold(names[0]).split())
    rest = sorted(names[1:], key=lambda name: bool(set(fold(name).split()) & own))
    return (*rest, names[0])


def _name_to_look_up(target: str, others: Iterable[str], view: dict, history: list[dict], objective: str | None) -> str:
    """The name a place is looked up by in the window's search: the one already typed (or launched in a burst) in this
    sub-goal, whatever the view now tells of its language, else the window's language's (``_in_window_language``, from
    the table's names of the place and the translator's)."""

    names = _in_window_language(target, (*label_alternatives(target), *others), view, objective)
    used = next((name for name in names if _looked_up_as(history, name)), None)
    if used is None:
        # A burst of this sub-goal launched with a name the re-entries do not carry (the translator's, chosen at the
        # step that launched it): the place is still looked up by that name, never a second way beside it.
        used = next((str(step["search"]).strip() for step in reversed(history) if isinstance(step, dict)
                     and step.get("searchBurst") is True and str(step.get("search") or "").strip()), None)
    return used if used is not None else (names[0] if names else target)
