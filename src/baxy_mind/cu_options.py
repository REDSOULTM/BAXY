"""Values of a list or a view's option: a list set to a number by its entry, the control that shows a view's
current option, and the value a goal sets a combo box to.
"""

from __future__ import annotations

import re

from .semantic.cu_buscar import goal_is_only_the_number, parameter_goal, sets_a_value
from .semantic.missions import fold, view_option_family
from .cu_vocabulary import _named_by_list, _screen_lists
from .cu_view import _ARROW_KINDS, _has_arrow, find_control
from .cu_goals import _goal_names_control
from .cu_acts import _click
from .cu_history import _clicks_on


# Ronda 22 (motor-listas-abiertas, r18 t2-c04: «ponle la escala en 125» with the list «Escala» open and «125%
# (recomendado)» selected; the model pressed the box again, typed into it and stopped): a number of the goal is one of
# a list's entries when it is a whole number of the entry's name, never part of a longer one («150» is not «1500»,
# «12» is not «125»).
_WHOLE_NUMBER = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?(?![\d])")
# The entries a list shows, and the controls that hold a list of entries: a box that shows its value (open or not) or
# another control the view marks expanded (its list hangs right after it in the tree).
_LIST_ENTRY_KINDS = frozenset({"ListItem", "DataItem"})
_LIST_HOLDER_KINDS = frozenset({"ComboBox", "SplitButton", "Button", "List"})
REASON_LIST_ENTRY = "la lista abierta muestra la entrada con el número que pide el objetivo"
REASON_LIST_VALUE = "la lista ya muestra elegido el número que pide el objetivo"


def _whole_numbers(text: object) -> set[str]:
    return {number.replace(",", ".") for number in _WHOLE_NUMBER.findall(fold(text))}


def _goal_number(goal: str | None) -> str | None:
    """The one number a goal says («activar escala de la pantalla en 125»), or None when it says none or several."""

    numbers = _whole_numbers(goal)
    return next(iter(numbers)) if len(numbers) == 1 else None


def _lists_of_view(view: dict) -> list[tuple[dict, list[dict], bool]]:
    """The lists the view shows, in its tree order: (holder, entries, open). An open list is a holder marked expanded
    and the entries (ListItem, DataItem) listed right after it; a closed box shows only the entry it holds, selected,
    right after it (Settings' «Escala» collapsed with «125% (recomendado)» selected). Nothing else is read as a list
    (a Text that says a number is no entry)."""

    controls = [control for control in (view.get("controls") if isinstance(view, dict) else None) or () if isinstance(control, dict)]
    lists: list[tuple[dict, list[dict], bool]] = []
    for at, control in enumerate(controls):
        kind = str(control.get("kind") or "")
        states = set(str(control.get("state") or "").split())
        is_open = "expanded" in states
        if kind not in _LIST_HOLDER_KINDS or not (is_open or (kind == "ComboBox" and "collapsed" in states)):
            continue
        entries: list[dict] = []
        for following in controls[at + 1:]:
            if str(following.get("kind") or "") not in _LIST_ENTRY_KINDS:
                break
            entries.append(following)
        if not is_open:
            entries = entries[:1] if entries and "selected" in str(entries[0].get("state") or "").split() else []
        if entries:
            lists.append((control, entries, is_open))
    return lists


def _numbered_list_step(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Ronda 22 (r18 t2-c04 t2 and t4): a goal that sets a list the view shows to a number («ponle la escala en 125»,
    «regresa la escala a 100»): the list is named by the goal (``_goal_names_control``) and exactly one of its entries
    has that number as a whole number of its name («125% (recomendado)» for 125).

    - The list is open and that entry is not selected: the entry is clicked (by its index), never the box again nor a
      text typed into it.
    - The entry is the one selected: «done» citing it, «already» when no act of
      the sub-goal pressed it nor typed (opening the list is no choice): the shell's AlreadyChosen judges it and the
      final says it was so.

    None when the goal does not set a value or choose (``sets_a_value``: never «escribir», «desactivar», «quitar»,
    «ir a», «hacer clic en»), says no number or several, names no list the view shows, two lists could take it, or no entry
    or more than one has the number (the model decides with the view). A failed click on that entry is not repeated."""

    number = _goal_number(goal)
    if number is None or parameter_goal(goal) or not sets_a_value(goal):
        # Review 1, finding 1: only a goal that sets a value or chooses an entry (``sets_a_value``); «desactivar …»,
        # «quitar …», «ir a …» or «hacer clic en …» with the entry seen selected is not reached by it.
        return None
    named = [entry for entry in _lists_of_view(view) if _goal_names_control(goal, entry[0].get("name"))]
    if len(named) != 1:
        return None
    holder, entries, is_open = named[0]
    matching = [entry for entry in entries if number in _whole_numbers(entry.get("name"))]
    if len(matching) != 1:
        return None
    entry = matching[0]
    if not goal_is_only_the_number(goal, holder.get("name"), entry.get("name"), number):
        # Review 3, findings 1 and 2: «pon la escala en 125 y la orientación en vertical» asks more than the entry, and
        # «2 horas» is never the entry «2 minutos» (the number's unit must be in its name); the model judges.
        return None
    if is_open and "selected" not in str(entry.get("state") or "").split():
        last = history[-1] if history and isinstance(history[-1], dict) else None
        name = str(entry.get("name") or "")
        if last is not None and last.get("ok") is not True and last.get("operation") == "input.visible.click" and (
            fold(last.get("label")).strip() == fold(name).strip()
        ):
            return None
        arguments: dict[str, object] = {"label": name}
        if isinstance(entry.get("i"), int):
            arguments["index"] = entry["i"]
        return {"operation": "input.visible.click", "arguments": arguments, "reason": REASON_LIST_ENTRY}
    if "selected" not in str(entry.get("state") or "").split():
        return None
    cited = str(entry.get("name") or "").strip()
    if not cited:
        return None
    if any(
        isinstance(step, dict) and step.get("ok") is True and step.get("operation") in {"input.key.press", "input.text.type"}
        for step in history
    ):
        # A key or a text sent may have set it: the model judges with the view.
        return None
    chosen = bool(_clicks_on(history, cited))
    arguments = {"evidence": cited[:80]}
    if not chosen:
        arguments["already"] = True
    return {"operation": "done", "arguments": arguments, "reason": REASON_LIST_VALUE}


REASON_VIEW_OPTION = "la opción de la vista está en el control que muestra la actual: lo abro"
# The kinds the control that shows a view's current option is drawn as.
_VIEW_OPTION_KINDS = frozenset({"Button", "SplitButton", "ComboBox", "MenuItem"})


def _view_option_control(view: dict, *, open_too: bool = False, family: str | None = None) -> dict | None:
    """The control that shows the current option of the window's view or order: a button, a split button, a list or a
    menu, collapsed or read-only, labelled by one of the data's labels (``viewOptionLabels``: «Ver por», «Sort by»): in
    its own name («Ver por: Categoría»), by the text control listed right before it, or by the line of text written
    right before its name in its zone (the Control Panel draws «Ver por:» as text beside its «Categoría» button).
    ``open_too``: one whose menu is already open (expanded) counts as well (``_view_option_shown``).
    Review 3 of palanca 6 (finding 2): ``family`` («view», «sort», «group»: ``view_option_family``) keeps only the labels
    of that family («viewOptionLabels.sort»): a «vista de X» is never shown by an «Ordenar por:» list, whose opening
    would be the person's order of their content and no step toward the goal."""

    labels = f"viewOptionLabels.{family}" if family else "viewOptionLabels"
    controls = [item for item in (view.get("controls") or []) if isinstance(item, dict)] if isinstance(view, dict) else []
    text = view.get("text") if isinstance(view, dict) and isinstance(view.get("text"), dict) else {}
    for position, control in enumerate(controls):
        kind = str(control.get("kind") or "")
        states = set(str(control.get("state") or "").split())
        name = str(control.get("name") or "").strip()
        shown = {"collapsed", "readonly"} | ({"expanded"} if open_too else set())
        if kind not in _VIEW_OPTION_KINDS or not name or not (shown & states or kind in _ARROW_KINDS):
            continue
        if ("expanded" in states and not open_too) or not isinstance(control.get("i"), int):
            continue
        if _named_by_list(name, labels) and fold(name).strip() not in _screen_lists().get(labels, ()):
            return control
        before = controls[position - 1] if position > 0 else None
        if before is not None and str(before.get("kind") or "") == "Text" and _named_by_list(before.get("name"), labels):
            return control
        lines = text.get(str(control.get("zone") or "")) if control.get("zone") else None
        if isinstance(lines, list):
            for previous, line in zip(lines, lines[1:]):
                if fold(line).strip() == fold(name).strip() and fold(previous).strip(" :") in _screen_lists().get(
                    labels, ()
                ):
                    return control
    return None


def _view_option_shown(view: dict, target: str | None = None) -> bool:
    """Review 2 of palanca 6 (finding 2): the window shows the control of its view's option (``_view_option_control``,
    by the data's labels), collapsed or with its menu already open. Only then is a goal said as an option of the view
    («vista de X», «ordenar por X») kept out of the search of the content; elsewhere it may be a real place whose name
    starts so («vista de tareas» in a settings window), looked up as any other place.
    Review 3 (finding 2): with the goal's ``target``, only the control of its option's family counts («Ordenar por:»
    never holds a «vista de X»)."""

    family = view_option_family(target) if target else None
    return _view_option_control(view, open_too=True, family=family) is not None


def _view_option_step(
    option: str, view: dict, history: list[dict], goal: str, family: str | None = None
) -> dict[str, object] | None:
    """The step toward an option of the view: None when the option itself is on screen (the goal's own step clicks
    it) or its control was already opened in this sub-goal; else the control that shows the current option, opened
    by its identity when it has an arrow, else pressed (a read-only button that drops its menu)."""

    if find_control(view, option) is not None:
        return None
    control = _view_option_control(view, family=family)
    if control is None:
        return None
    name = str(control.get("name") or "")
    if any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("ok") is True
        and (step.get("index") == control.get("i") or fold(step.get("label")).strip() == fold(name).strip())
        for step in history
    ):
        return None
    if _has_arrow(control):
        return {"operation": "input.visible.click", "arguments": {"label": name, "index": control["i"], "manner": "open"},
                "reason": REASON_VIEW_OPTION}
    return _click(control, REASON_VIEW_OPTION)


# D1 (pasada r15b, v3-28): the words that join a combo box's name to the value a goal sets it to («la fuente a X»,
# «the font to X», «el tamaño en 12»), and the article that may follow them.
_COMBO_LINKS = frozenset({"a", "al", "en", "to", "como", "as", "por", "=", ":"})
_COMBO_ARTICLES = frozenset({"la", "el", "los", "las", "the"})
_COMBO_VALUE_WORDS = 3
# Revisión de la rama (hallazgo 1): a value is a name, said last. Words that join another clause or place the change
# («Arial en el documento», «12 y escribe hola», «Arial and type hello») or describe a value instead of naming it («una
# más grande», «another one») mean the goal says more than a value: no value is read. The read is only a guess either
# way: the box takes it only as one of its own entries (``entry``), never as free text.
_COMBO_NOT_A_VALUE = frozenset({
    "y", "e", "and", "then", "luego", "despues", "en", "in", "on", "con", "with", "de", "del", "of", "para", "for",
    "que", "that", "pero", "but", "o", "or", "un", "una", "a", "an", "otra", "otro", "another", "mas", "more", "menos",
    "less",
})


def _word_folds(words: list[str]) -> list[str]:
    return [fold(word).strip(".,;:!?¡¿«»\"'()") for word in words]


def combo_value(goal: str | None, objective: str | None, name: object) -> str | None:
    """The value a goal sets a combo box to, said right after the box's name and a linking word («cambia la fuente a
    Wingdings» on «Fuente:», «set the font to Wingdings» on «Font:»), in the request's own spelling when the request says
    it (the planner may lower-case the goal). None when the goal does not name the box or no value follows it."""

    label = [word for word in _word_folds(str(name or "").split()) if word]
    words = str(goal or "").split()
    folded = _word_folds(words)
    if not label:
        return None
    for start in range(len(folded) - len(label) + 1):
        if folded[start:start + len(label)] != label:
            continue
        rest, rest_folded = words[start + len(label):], folded[start + len(label):]
        if not rest_folded or rest_folded[0] not in _COMBO_LINKS:
            continue
        skip = 2 if len(rest_folded) > 1 and rest_folded[1] in _COMBO_ARTICLES else 1
        if any(word.endswith((",", ";")) for word in rest[skip:-1]):
            return None
        value = [word.strip(".,;!?¡¿«»\"'") for word in rest[skip:]]
        value = [word for word in value if word]
        if not value or len(value) > _COMBO_VALUE_WORDS:
            return None
        wanted = _word_folds(value)
        if any(word in _COMBO_NOT_A_VALUE for word in wanted):
            return None
        said = str(objective or "").split()
        said_folded = _word_folds(said)
        for at in range(len(said_folded) - len(wanted) + 1):
            if said_folded[at:at + len(wanted)] == wanted:
                return " ".join(word.strip(".,;!?¡¿«»\"'") for word in said[at:at + len(wanted)])
        return " ".join(value)
    return None
