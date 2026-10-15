"""What a sub-goal and its check say as the readers wrote them: the control a goal names and its head, a place,
a colour, a question, the atoms of a check, and the names a goal's place is spelled with.
"""

from __future__ import annotations

import re
from typing import Iterable

from .semantic.colours import is_basic_colour
from .semantic.missions import QUESTION_MARK, fold
from .cu_vocabulary import _PARTS, _PLACE_GOAL, _evidence_rules, _floor_name
from .cu_view import _KIND_WORDS, _SWITCH_KINDS


REVEAL_GOAL = "mostrar "
FIELD_GOAL = "poner "


def _value_terms(success_check: str | None) -> list[list[tuple[str, str]]]:
    """The terms of a field's check that only read values («value:ancho=500&value:alto=500»), each as its pairs of
    field name and value, folded."""

    terms: list[list[tuple[str, str]]] = []
    for term in str(success_check or "").split("|"):
        pairs: list[tuple[str, str]] = []
        for atom in (atom.strip() for atom in term.split("&")):
            kind, _, rest = atom.partition(":")
            name, equals, value = rest.partition("=")
            if kind.strip().casefold() != "value" or not equals or not name.strip():
                pairs = []
                break
            pairs.append((fold(name).strip(), fold(value).strip()))
        if pairs:
            terms.append(pairs)
    return terms


# The goals that name a control, with the state each one wants (None: a place to go or a control to press).
_GOAL_HEADS: tuple[tuple[str, str | None], ...] = (
    ("ir a ", None), ("hacer clic en ", None), ("activar ", "on"), ("desactivar ", "off"), ("seleccionar ", "selected"),
)
# The heads of a goal that goes to a place or clicks it: only those descend a navigation tree (ronda 21, v3-26).
_GOING_HEADS = frozenset({"ir a ", "hacer clic en "})


def _goal_target(goal: str) -> tuple[str, str | None, str, str | None] | None:
    """(head, wanted state, target, kind) of a goal that names a control: «ir a la pestaña YouTube» → («ir a », None,
    «YouTube», «TabItem»); the kind said before the name narrows the controls to it (a tab's name is its whole title,
    «Never Gonna Give You Up - YouTube»). None for any other goal."""

    folded_goal = fold(goal)
    for head, wanted in _GOAL_HEADS:
        if not folded_goal.startswith(head):
            continue
        target = re.sub(r"^(?:el|la|los|las|the|al|a\s+la|a\s+los|a\s+las)\s+", "", goal[len(head):].strip(), flags=re.IGNORECASE)
        named_kind = re.match(r"(?P<word>[^\W\d_]+)\s+(?:(?:de|del|of)\s+)?(?P<name>\S.*)$", target)
        kind = _KIND_WORDS.get(fold(named_kind.group("word"))) if named_kind is not None else None
        if named_kind is not None and kind is not None:
            target = named_kind.group("name")
        return head, wanted, target, kind
    return None


# A goal that sets or chooses one named thing («activar modo programador», «seleccionar lapiz»): what it names, for a
# switch to be pressed only when it is that thing.
_SETTING_GOAL = re.compile(
    r"^(?:activar|desactivar|encender|apagar|seleccionar|elegir|turn\s+on|turn\s+off|enable|disable|select)\s+"
    r"(?:(?:el|la|los|las|the)\s+)?(?:(?:modo|mode)\s+)?(?P<what>\S.*)$"
)


# «ir a X»: the place a goal goes to; a control so named is the place («Tus me gusta», «Liked Songs»), not an act.
_PLACE_NAMED = re.compile(r"^ir\s+a\s+(?:(?:el|la|los|las|tu|tus|the|my|your)\s+)?(?P<place>\S.*)$")
_POSSESSIVE = re.compile(r"^(?:el|la|los|las|tu|tus|the|my|your)\s+")


def reading_goal(goal: str | None) -> bool:
    """Review of lectura-ruta (finding 2): a goal that only looks and answers (data «computerUse.evidence.readGoal»:
    «ver …», «leer …», the question's own look ``QUESTION_LOOK``, «tell me …») changes no setting on the way: «decime
    si el bluetooth está activado» never presses the Bluetooth switch. «check X» is no reading: in English it also
    ticks a box."""

    folded = fold(goal or "").strip()
    return bool(folded) and not folded.startswith("check ") and re.match(_evidence_rules()["readGoal"], folded) is not None


def _placing_goal(goal: str | None) -> bool:
    """A goal that places the person somewhere or presses a named thing, never one that sets something: «ir a …»,
    «buscar …», a reading (``reading_goal``), and «hacer clic en …» unless it names a switch's kind («la casilla …»)."""

    folded = fold(goal or "")
    if folded.startswith(("ir a ", "buscar ")) or reading_goal(goal):
        return True
    parsed = _goal_target(goal or "") if folded.startswith("hacer clic en ") else None
    return parsed is not None and parsed[3] not in _SWITCH_KINDS


def colour_goal(goal: str | None) -> str | None:
    """The basic colour a goal «seleccionar X» chooses («azul», «blue»), or None for any other goal."""

    parsed = _goal_target(goal or "")
    if parsed is None or parsed[1] != "selected" or parsed[3] is not None:
        return None
    return parsed[2] if is_basic_colour(parsed[2]) else None


# The states a ``control:`` atom may end with, as the C# check reads them (ComputerUseSuccessCheck, «control»).
_ATOM_STATES = frozenset({"selected", "current", "on", "off", "expanded", "focused", "collapsed"})


def _check_atoms(success_check: str | None) -> list[tuple[str, str]]:
    """The ``control:`` atoms of a check as (folded name, state), state empty when the atom names none. Read as the C#
    check reads them (review of the branch, finding 6): the state is what follows the last «:», and only when it is a
    state word, so a name with «:» in it («Opciones: Vídeo») stays whole; «=» and «==» before the name are its match
    marks, not part of it."""

    atoms: list[tuple[str, str]] = []
    for term in str(success_check or "").split("|"):
        for atom in term.split("&"):
            head, colon, rest = atom.strip().partition(":")
            if not colon or head.strip().casefold() != "control":
                continue
            name, state = rest, ""
            at = rest.rfind(":")
            if at > 0 and rest[at + 1:].strip().casefold() in _ATOM_STATES:
                name, state = rest[:at], rest[at + 1:].strip().casefold()
            name = name.strip().lstrip("=")
            if name.strip():
                atoms.append((fold(name), state))
    return atoms


# The atoms of a check that name what has to appear in the sub-goal (a container born, a control an act brought), never
# what is already on screen when it starts (revisión 3 de ronda 24).
_TO_APPEAR_ATOMS = frozenset({"born", "appeared"})


def _check_names(success_check: str | None, heads: Iterable[str] = ("control", *_TO_APPEAR_ATOMS)) -> list[str]:
    """The names a check's ``control:``, ``born:`` and ``appeared:`` atoms (those of ``heads``) say, folded, without
    their state."""

    heads = frozenset(heads)
    names: list[str] = []
    for term in str(success_check or "").split("|"):
        for atom in term.split("&"):
            head, colon, rest = atom.strip().partition(":")
            if not colon or head.strip().casefold() not in heads:
                continue
            at = rest.rfind(":")
            if at > 0 and rest[at + 1:].strip().casefold() in _ATOM_STATES:
                rest = rest[:at]
            name = fold(rest.strip().lstrip("=")).strip()
            if name:
                names.append(name)
    return names


def _destination(goal: str | None) -> str:
    """«ir a la biblioteca» → «biblioteca»: the place a go-to goal names, folded; empty for other goals."""

    folded = fold(goal or "")
    if not folded.startswith("ir a "):
        return ""
    return re.sub(r"^(?:el|la|los|las|the|al)\s+", "", folded[len("ir a "):]).strip()


def proved_on_disk(success_check: str | None) -> bool:
    """Review of lectura-ruta (finding 5): a check every term of which reads a file on disk (``file:``, a save at the
    path said): only that file proves the goal. The title the model cites names the file, never the folder the dialog
    put it in."""

    terms = [term for term in str(success_check or "").split("|") if term.strip()]
    return bool(terms) and all(
        any(atom.strip().casefold().startswith("file:") for atom in term.split("&")) for term in terms
    )


def check_searches(success_check: str | None) -> bool:
    """A check that a search proves (the App's ``ComputerUseSuccessCheck.SearchResultsProve``): one of its terms
    joins a step done (``stepdone:``) with a title or a text the search shows."""

    for term in str(success_check or "").split("|"):
        kinds = {atom.split(":", 1)[0].strip().lower() for atom in term.split("&") if ":" in atom}
        if "stepdone" in kinds and kinds & {"title", "text"}:
            return True
    return False


def _goal_names_control(goal: str | None, name: object) -> bool:
    """The goal names the control: every word of its name (of three letters or more) is a word of the goal, or two of
    them are (a long name: «Marcador de resaltado: Amarillo, 5 mm» for «seleccionar marcador amarillo»)."""

    words = {word for word in re.findall(r"[a-z0-9]+", fold(name)) if len(word) >= 3}
    said = set(re.findall(r"[a-z0-9]+", fold(goal or "")))
    shared = words & said
    return bool(words) and (shared == words or len(shared) >= 2)


# Lectura-ruta (r9 v3-61): the step's goal when opening the application is all the goal does before its question.
QUESTION_LOOK = "ver en la ventana: "


def question_step_goal(goal: str, application: str | None) -> str:
    """The goal a step works on: the part before the question («escribir hola; y responder: …» types «hola»), or,
    when that part only opens the mission's application (data «evidence.openGoal» and the application's name, nothing
    else: «abrir Seguridad de Windows; y responder: decime cuándo fue el último examen»), a reading of the question
    itself (``QUESTION_LOOK``): the datum may live on another page of the window, and an opened window is no answer
    (r9 v3-61 ended on the start page with 0 steps). Opening a file («abrir el archivo …») keeps its own goal."""

    head, _, question = str(goal or "").partition(QUESTION_MARK)
    question = question.strip()
    said = fold(head).strip()
    verb = re.match(_evidence_rules()["openGoal"], said)
    if question and verb and application and said[verb.end():].strip() == fold(application).strip():
        return QUESTION_LOOK + question
    return head


def done_needs_an_act(goal: str | None) -> bool:
    """A goal whose «done» needs an act of the mission: neither a place («ir a X», data «placeGoal», matched as the App's
    PlaceAsked does, whatever the case) nor a reading (data «computerUse.evidence.readGoal», or a goal carrying a
    question). Twin of ComputerUseSuccessCheck.DoneNeedsAnAct."""

    said = str(goal or "").strip()
    if not said or QUESTION_MARK in said:
        return False
    if _PLACE_GOAL.match(said):
        return False
    return re.match(_evidence_rules()["readGoal"], fold(said).strip()) is None


def _search_goal(goal: str | None) -> bool:
    return re.match(_evidence_rules()["searchGoal"], fold(goal or "").strip()) is not None


def _place_of(goal: object, names: list[str]) -> str:
    """The place a goal «ir a X» went to, spelled as the window wrote it when one of its names is X."""

    found = _PLACE_GOAL.match(str(goal or "").strip()) if isinstance(goal, str) and QUESTION_MARK not in goal else None
    if found is None:
        return ""
    asked = _floor_name(found.group(1))
    return _spelled(asked, names) or asked


def _spelled(asked: str, names: list[str]) -> str | None:
    name = next((name for name in names if fold(name) == fold(asked)), None)
    return None if name is None else _calm_caps(name)


def _calm_caps(name: str) -> str:
    """A name the window writes in capitals («TIENDA», read off the screen) told with only its first letter so; an
    acronym («VPN», «HDMI») keeps them."""

    letters = [char for char in name if char.isalpha()]
    words = re.findall(r"[^\W\d_]+", name)
    if not letters or any(not char.isupper() for char in letters):
        return name
    if not any(len(word) >= _PARTS["capsWord"] for word in words):
        return name
    return name[:1] + name[1:].lower()
