"""What the sub-goal's history says: the steps that acted, clicks and texts already tried, a lookup already
begun, the search keys spent, what appeared after a key, and what only opened a control.
"""

from __future__ import annotations

from contextvars import ContextVar

from .semantic.missions import fold
from .cu_vocabulary import _UNSEEN_EFFECT_KEYS
from .cu_view import _bare, _opener_name
from .cu_fields import _SEARCH_KEYS, _is_search_field
from .cu_window import _process_key


def _steps_ok(history: list[dict], operation: str, **match: str) -> list[dict]:
    found = []
    for step in history:
        if step.get("operation") != operation or step.get("ok") is not True:
            continue
        if all(fold(step.get(key)) == fold(value) for key, value in match.items()):
            found.append(step)
    return found


def _search_started(history: list[dict]) -> bool:
    """This sub-goal already began looking the place up (a text typed, a search key, a click on a search field or on
    the window's navigation): the literal search goes on as it began, never handed back to the model midway."""

    for step in history:
        if not isinstance(step, dict):
            continue
        operation = step.get("operation")
        if operation in ("input.text.type", "input.scroll"):
            return True
        if operation == "input.key.press" and step.get("key") in _SEARCH_KEYS:
            return True
        if operation == "input.visible.click" and (
            _is_search_field({"name": step.get("label")}) or _opener_name(step.get("label"))
        ):
            return True
    return False


def _typed_steps(history: list[dict]) -> list[dict]:
    return [
        step for step in history
        if isinstance(step, dict) and step.get("operation") == "input.text.type" and step.get("ok") is True
    ]


def _looked_up_as(history: list[dict], name: str) -> bool:
    """``name`` was already typed into a search in this sub-goal, or a search burst was launched with it."""

    return _typed_target(history, name) or any(
        isinstance(step, dict) and bool(step.get("search")) and fold(step.get("search")) == fold(name) for step in history
    )


def _click_failed(history: list[dict], label: str) -> bool:
    """A click on this label already failed in this sub-goal."""

    return bool(label) and any(
        step.get("operation") == "input.visible.click" and step.get("ok") is False and fold(step.get("label")) == fold(label)
        for step in history if isinstance(step, dict)
    )


def _manner_opened(history: list[dict]) -> list[dict]:
    return [
        step for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("manner") == "open"
    ]


def _name_click_not_found(history: list[dict]) -> bool:
    """Revision 2 (finding 1): a click by label alone (no index) of this sub-goal was answered that no control of the
    window carries that name."""

    return any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and step.get("error") == "visible_button_not_found" and not isinstance(step.get("index"), int)
        for step in history
    )


def _before_unfolding_misses(history: list[dict]) -> list[dict]:
    """Revision 2 (finding 1): the history without the clicks by label alone that found no control of that name and
    were followed by a node opened by its identity: they pressed nothing, and what the node showed since is a control
    the click never reached (v3-26: «sistema» not found by name, then «Registros de Windows» opened and «Sistema»
    shown)."""

    last_open = max((
        n for n, step in enumerate(history)
        if isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("manner") == "open"
        and step.get("ok") is True
    ), default=-1)
    return [
        step for n, step in enumerate(history)
        if not (
            n < last_open and isinstance(step, dict) and step.get("operation") == "input.visible.click"
            and step.get("error") == "visible_button_not_found" and not isinstance(step.get("index"), int)
        )
    ]


# The search keys that brought up something not sought earlier in the mission, by the window's process (``spent``
# steps the shell carries across sub-goals); set for one decision by ``decide_step``.
_SPENT_KEYS: ContextVar[tuple[tuple[str, str], ...]] = ContextVar("cu_spent_keys", default=())


def _spent_keys(view: dict) -> frozenset[str]:
    """The search keys spent on the window's application: a key the shell marked ``spent`` whose process is this
    view's (any process when the step or the view does not say it)."""

    process = _process_key((view.get("window") or {}).get("process")) if isinstance(view, dict) else ""
    return frozenset(key for key, where in _SPENT_KEYS.get() if not where or not process or where == process)


def spent_steps(history: list[dict]) -> tuple[list[dict], tuple[tuple[str, str], ...]]:
    """The sub-goal's own steps and, apart, the search keys an earlier sub-goal spent (the shell's ``spent`` items):
    those never count as this sub-goal's steps (the first look of a sub-goal has no history)."""

    own = [step for step in history if not (isinstance(step, dict) and step.get("spent") is True)]
    # Ronda 21 (revisión 1, hallazgo b): a key the App's guard refused on a document the mission may not touch
    # (``refused``, a step of this sub-goal) is spent as well: neither the rule nor the model presses it again there.
    spent = tuple(
        (str(step.get("key") or ""), _process_key(step.get("process")))
        for step in history
        if isinstance(step, dict) and (step.get("spent") is True or step.get("refused") is True) and step.get("key")
    )
    return own, spent


def _appeared(step: dict) -> frozenset[str]:
    """The names the shell saw appear in the first look after a key (``appeared``: in that look, in none of the look
    before the key), folded; empty when the shell did not say."""

    names = step.get("appeared")
    return frozenset(fold(name).strip() for name in names if isinstance(name, str)) if isinstance(names, list) else frozenset()


def _typed_target(history: list[dict], target: str) -> bool:
    return any(
        step.get("operation") == "input.text.type" and step.get("ok") is True and fold(step.get("text")) == fold(target)
        for step in history
    )


def key_without_effect(step: object) -> bool:
    """A key meant to bring something up (a search, a menu, a tab, a pane: never one of ``_UNSEEN_EFFECT_KEYS``)
    done and verified whose next look showed the window exactly as before (the App marks it ``sameView``: same title,
    controls, states and values). A typed text is never one: the field that took it may expose no value."""

    return (
        isinstance(step, dict) and step.get("ok") is True and step.get("sameView") is True
        and step.get("operation") == "input.key.press" and str(step.get("key") or "") not in _UNSEEN_EFFECT_KEYS
    )


def _wrote_or_sent(history: list[dict]) -> bool:
    """Ronda 24 (v3-30: closing a list made the window reset the search already sent): the sub-goal already typed a
    text or sent it with a verified key; nothing is opened blind after that."""

    return any(
        isinstance(step, dict) and step.get("ok") is True and (
            step.get("operation") == "input.text.type"
            or (step.get("operation") == "input.key.press" and fold(step.get("key")).strip() in {"enter", "return"})
        )
        for step in history
    )


def only_opened(step: dict) -> bool:
    """Goal v3 B3 (review of the closed menus, finding 4): a step that only opened a control's arrow, its list or its
    context menu pressed nothing; no check reads it as a click on that control. A double click is a press. Ronda 24
    (t-menu-3): opening a menu entry whose only action is to open is pressing it (_open_is_its_press). Twin of
    ComputerUseSuccessCheck.OnlyOpened."""

    return (
        step.get("operation") == "input.visible.click" and step.get("manner") in ("open", "menu")
        and not _open_is_its_press(step)
    )


def _open_is_its_press(step: dict) -> bool:
    """Ronda 24 (t-menu-3): an «open» on a control whose only action is to open, a menu entry (kind MenuItem) the
    receipt expanded (method «expand») and read open: the ordinary click on it does the very same. The arrow of a split
    button acts by itself and a combo box's list chooses nothing, so neither is a press. Twin of
    ComputerUseSuccessCheck.OpenIsItsPress; the history the App hands the mind carries that verdict as «openPress»."""

    if step.get("manner") != "open":
        return False
    return step.get("openPress") is True or (
        step.get("kind") == "MenuItem" and step.get("method") == "expand" and step.get("opened") is True
    )


def _clicks_on(history: list[dict] | None, name: object) -> list[dict]:
    wanted = _bare(name)
    return [
        step for step in history or ()
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
        and not only_opened(step) and _bare(step.get("label")) == wanted
    ]


def _acts_on(history: list[dict] | None, name: object) -> list[dict]:
    """Every click of the history on the control that may have acted on it (``_may_have_acted``): verified, or pressed
    with its effect uncertain (ronda 20b review, finding 1: a toggle whose sibling's mark never appeared). Twin of
    ComputerUseSuccessCheck.ActsOn."""

    wanted = _bare(name)
    return [
        step for step in history or ()
        if isinstance(step, dict) and step.get("operation") == "input.visible.click" and not only_opened(step)
        and _may_have_acted(step) and _bare(step.get("label")) == wanted
    ]


def _may_have_acted(step: object) -> bool:
    """Whether a step may have changed the screen: verified, or pressed with a post-read that did not hold
    («effectUncertain»: a slow page changed after the verification window). Opening the application is no act on the
    way to a place, unless it made the new document asked for (``newDocument``, review of cu-v3-documento-nuevo finding
    7) or opened a place of the application by its address (``placeOpened``, estabilización encargo C); a step refused
    before any press did nothing. Twin of the App's ComputerUseMission.MayHaveActed."""

    return (
        isinstance(step, dict)
        and (step.get("operation") != "app.open" or step.get("newDocument") is True or step.get("placeOpened") is True)
        and (step.get("ok") is True or step.get("effectUncertain") is True)
    )
