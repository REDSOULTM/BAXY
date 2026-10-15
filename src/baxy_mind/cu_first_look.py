"""What the sub-goal's first look already showed: the parts of a look, a citation shown anew, and a new part
told by its identity.
"""

from __future__ import annotations

import re

from .semantic.missions import fold
from .cu_vocabulary import _commit_on_offer, _created_words, _evidence_rules
from .cu_view import _focused, _view_lines


# The marks a citation is trimmed of, as the App's QuoteMarks.
_CITATION_MARKS = " «»\"'“”‘’"


def look_parts(view: dict) -> list[str]:
    """The folded parts a look shows: the window's title, each control's name (a tab and its value when it has one)
    and each written line. Twin of ComputerUseSuccessCheck.LookText: a control listed only for the goal's words (the
    App's «reserved», revisión 2 de la ronda 21) is no part of it, since the sub-goal's first look carried no words."""

    window = view.get("window") if isinstance(view, dict) else None
    parts = [fold(window.get("title") if isinstance(window, dict) else "")]
    for control in (view.get("controls") if isinstance(view, dict) else None) or []:
        if isinstance(control, dict) and control.get("reserved") is not True:
            value = fold(control.get("value"))
            parts.append(fold(control.get("name")) + ("\t" + value if value else ""))
    parts.extend(fold(line) for line in _view_lines(view))
    return [part.replace("\n", " ").replace("\r", " ") for part in parts]


def shows_anew(citation: str, view: dict, first_look: str) -> bool:
    """The look shows the citation in a part the first look did not have, part by part and counting repeats; a part
    that only grew around a first-look part holding it shows nothing new of it. Twin of ComputerUseSuccessCheck.ShowsAnew."""

    before: dict[str, int] = {}
    for part in first_look.split("\n"):
        if part:
            before[part] = before.get(part, 0) + 1
    now: dict[str, int] = {}
    for part in look_parts(view):
        if part:
            now[part] = now.get(part, 0) + 1
    held_before = [part for part in before if citation in part]
    held = False
    for part, count in now.items():
        if citation not in part:
            continue
        held = True
        if count > before.get(part, 0) and (part in before or not any(old in part for old in held_before)):
            return True
    return not held


def _new_part_by_identity(evidence: str, view: dict, history: list[dict], goal: str | None) -> bool:
    """Ronda 20 P4 (v3-08: «Agregar página» made a page, the keyboard sat on its empty «Título de página», and the
    citation was refused as seen at start because the page already there had an empty title of the same name). The
    cited part is new by identity, though its name showed on the first look, when: the goal creates one thing (data
    «creatingGoal», no «creatingQuantity»); the sub-goal's last step is a verified click that brought something new
    («broughtNew») on a command that creates what the goal names (data «creatingCommand», its object sharing the
    goal's words, kin included); the cited part is the focused Document or Edit, empty, whose id (the App's
    «focusedId») the first look's empty and focused parts (the App's «firstIds») did not have; and no menu is open (a
    command that offers templates made nothing yet); and no button that saves or confirms is on offer (data
    «commitControl»; revisión 1 de P4: «Nuevo evento» opened a form with «Guardar» whose empty «Agregar un título»
    belongs to nothing made yet). Twin of ComputerUseSuccessCheck.NewPartByIdentity."""

    first_ids = view.get("firstIds") if isinstance(view, dict) else None
    focused_id = view.get("focusedId") if isinstance(view, dict) else None
    if not isinstance(first_ids, list) or not isinstance(focused_id, str) or not focused_id or focused_id in first_ids:
        return False
    rules = _evidence_rules()
    folded = fold(goal or "").strip()
    if not re.match(rules["creatingGoal"], folded) or re.search(rules["creatingQuantity"], folded):
        return False
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if (
        last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True
        or last.get("broughtNew") is not True
    ):
        return False
    command = re.match(rules["creatingCommand"], fold(str(last.get("label") or last.get("name") or "")).strip())
    asked = _created_words(re.sub(rules["creatingGoal"], "", folded, count=1))
    if command is None or not asked or not _created_words(command.group("object")) & asked:
        return False
    focused = _focused(view)
    controls = [item for item in (view.get("controls") or []) if isinstance(item, dict)]
    part = next((item for item in controls if focused is not None and item.get("i") == focused.get("i")), None)
    if (
        part is None or part.get("reserved") is True or part.get("kind") not in {"Document", "Edit"}
        or fold(part.get("name")).strip() != fold(evidence).strip(_CITATION_MARKS)
        or str(part.get("value") or "").strip()
    ):
        return False
    if _commit_on_offer(controls):
        return False
    return not any(
        item.get("kind") == "Menu" or "expanded" in str(item.get("state") or "").split() for item in controls
    )


def _seen_at_start(evidence: str, view: dict) -> bool:
    """The citation already showed on the application's first look of this sub-goal (the App's «firstLook»), unless a
    title names it only now. Mirror of EvidenceRefusal's «seen_at_start»."""

    first_look = view.get("firstLook") if isinstance(view, dict) else None
    cited = fold(evidence).strip(_CITATION_MARKS)
    if not isinstance(first_look, str) or not first_look or not cited:
        return False
    window = view.get("window") if isinstance(view, dict) else None
    title = fold(window.get("title") if isinstance(window, dict) else "")
    if cited in title and cited not in first_look.split("\n", 1)[0]:
        return False
    return not shows_anew(cited, view, first_look)
