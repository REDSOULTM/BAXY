"""What a creating goal made: a click that made the asked thing (by its effect or by the count and title the
window shows), the one command that creates it, and a creation the goal does not ask for refused.
"""

from __future__ import annotations

import re
from typing import Iterable

from .semantic.missions import fold
from .semantic import cu_tipos
from .cu_vocabulary import _commit_on_offer, _created_words, _evidence_rules
from .cu_view import _drawn, _focused, _viewed_control, view_contains
from .cu_fields import _search_box
from .cu_acts import _click, _none
from .cu_window import _without_vetoed
from .cu_unasked import _REMOVAL_NAME
from .cu_languages import _translation_clickable
from .cu_meaning import REASON_ARRIVED_BY_EFFECT
from .cu_first_look import _CITATION_MARKS, _new_part_by_identity, _seen_at_start, look_parts
from .cu_text_place import _PLACEHOLDER_LINE, _placeholder_field


# A goal that makes something new («creá una página nueva», «add a new note»): its words besides these name the thing.
_CREATION_GOAL = re.compile(r"\b(?:cre[ae]\w*|nuev[oa]s?|new|create\w*|add|agreg\w*|anad\w*|insert\w*)\b")
_CREATION_FILLER = re.compile(r"\b(?:cre[ae]\w*|nuev[oa]s?|new|create\w*|add|agreg\w*|anad\w*|insert\w*|una?|el|la|los|las|a|an|the|otr[oa])\b")
# The parts of a document (not of a form) a new thing shows empty, waiting for its text.
_DOCUMENT_PARTS = ("titulo", "title", "subtitulo", "subtitle", "cuerpo", "body", "encabezado", "heading", "header")


def _created_by_effect(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """v3 campo-texto (live v3-08, v3-11): a goal of making something new is reached when its last step was a verified
    click that changed the window on a control naming the thing («Agregar página» for «creá una página nueva») and the
    keyboard now sits on an empty document part named as one («Título de página» of the new page) that the sub-goal's
    first look did not show: the thing is there, waiting for its text. «done» citing that part, which the shell checks
    on screen. Never a form's field (an Edit: what a form makes exists only once saved), never with a control that
    saves or confirms on offer, never when the goal says more than the thing (a day, an hour, a number), never a search
    box or a message box, never a part that holds text, never when the clicked control has the focus."""

    folded = fold(goal)
    if not _CREATION_GOAL.search(folded):
        return None
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True:
        return None
    # The App passes the receipt's verdict as «changed» (HistoryForMind), never «surfaceChanged».
    if last.get("changed") is not True:
        return None
    clicked = fold(last.get("label"))
    pressed = set(re.findall(r"\w+", clicked))
    said = _CREATION_FILLER.sub(" ", folded).split()
    thing = {word for word in said if len(word) >= 4}
    if not thing or not thing & pressed:
        return None
    # Review r10 campo-texto, finding 2: «creá un evento nuevo el viernes a las 5» says more than the thing, and the
    # click on «Nuevo evento» made none of it. Every word of the goal past the filler is the clicked control's.
    if any(any(char.isdigit() for char in word) or (len(word) >= 3 and word not in pressed) for word in said):
        return None
    focused = _focused(view)
    if focused is None or focused.get("kind") != "Document" or fold(focused.get("name")) == clicked:
        return None
    controls = [item for item in (view.get("controls") or []) if isinstance(item, dict)]
    control = next((item for item in controls if item.get("i") == focused.get("i")), focused)
    name = str(control.get("name") or "").strip()
    if not name or str(focused.get("value") or control.get("value") or "").strip() or _search_box(view, control):
        return None
    folded_name = fold(name)
    if not _placeholder_field({**control, "kind": "Document"}) or not (
        _PLACEHOLDER_LINE.search(folded_name) or any(re.search(rf"\b{word}\b", folded_name) for word in _DOCUMENT_PARTS)
    ):
        return None
    if _commit_on_offer(controls):
        # A form still to be saved or confirmed: what it makes does not exist yet.
        return None
    if any(step.get("operation") == "input.visible.click" and fold(step.get("label")) == folded_name for step in history):
        return None
    if _seen_at_start(name, view) and not _new_part_by_identity(name, view, history, goal):
        # Review r10 campo-texto, finding 6: the part was on the first look (a page already there). The App refuses
        # that citation and ends the mission (seen_at_start), so the step is the model's. Ronda 20 P4 (v3-08): unless
        # the focused part is another one of the same name (its id is new), as the App's judge also reads it.
        return None
    return {"operation": "done", "arguments": {"evidence": name[:80]}, "reason": REASON_ARRIVED_BY_EFFECT}


REASON_CREATED_BY_DIFF = "lo pedido apareció con el último clic: la ventana cuenta uno más o tiene un documento nuevo"

# A count the window writes of its things («Diapositiva 2 de 2», «Slide 3 of 3», «Página 1 de 4»).
_THING_COUNTER = re.compile(r"\b(?P<thing>[a-z]+)\s+\d{1,4}\s+(?:de|of)\s+(?P<total>\d{1,4})\b")
# A control that makes a thing anew by what it says of it: blank, new, empty.
_BLANK_OR_NEW = re.compile(r"\b(?:en\s+blanco|blank|nuev[oa]s?|new|vaci[oa]|empty)\b")


def _asked_to_create(goal: str | None) -> set[str]:
    """The words of the one thing a creating goal asks for (data «creatingGoal», ``_created_words``); empty for any
    other goal, and for one that says how many (data «creatingQuantity»)."""

    rules = _evidence_rules()
    folded = fold(goal or "").strip()
    if not re.match(rules["creatingGoal"], folded) or re.search(rules["creatingQuantity"], folded):
        return set()
    return _created_words(re.sub(rules["creatingGoal"], "", folded, count=1))


# Words that say a thing is another one, never which thing («otra diapositiva», «another slide»).
_ANOTHER = re.compile(r"\b(?:otr[oa]s?|another)\b")
# A control that sends or confirms a form («Enviar», «Crear», «Aceptar», «Guardar y cerrar»): with one on offer, what
# the form makes does not exist yet. A bare «Guardar»/«Save» is left out: a document application always shows it, and
# its new document exists unsaved («Presentación1»).
_FORM_COMMIT = re.compile(
    r"^(?:(?:guardar|save)\s+(?:y|and|&)\s+(?:cerrar|close)|crear|create|aceptar|ok|listo|done|confirmar|confirm|"
    r"enviar|send|publicar|publish|submit|finalizar|finish|agregar|add|anadir)$"
)


def _thing_of(text: object) -> set[str]:
    """The words of the one thing a creating goal or a creating control names, without the creating verb (data
    «creatingGoal», «creatingCommand») nor the words that say blank, new or another (``_created_words``)."""

    rules = _evidence_rules()
    folded = fold(text).strip()
    if re.match(rules["creatingGoal"], folded):
        folded = re.sub(rules["creatingGoal"], "", folded, count=1)
    else:
        command = re.match(rules["creatingCommand"], folded)
        folded = command.group("object") if command is not None else folded
    return _created_words(_ANOTHER.sub(" ", _BLANK_OR_NEW.sub(" ", folded)))


def _creates_what_is_asked(goal: str, label: object) -> bool:
    """Review of sistema-cumplido, findings 2-4 (the guards _created_by_effect has had since review r10 campo-texto,
    finding 2): the clicked control makes the very thing the goal asks for and the goal says nothing more. The click
    makes one anew (a creating command, or one that says blank or new), the goal names no number, and the goal's thing
    and the control's thing are the same words («haz una presentación en blanco» and «Presentación en blanco»; «add a
    new slide» and «Nueva diapositiva», kin words read as one). «agrega una diapositiva con el título Ventas» asks a
    title too; «Nueva presentación de ventas» is a recent file, not a new one; «Negrita» makes nothing."""

    folded_label = fold(label).strip()
    if not folded_label or not (
        re.match(_evidence_rules()["creatingCommand"], folded_label) or _BLANK_OR_NEW.search(folded_label)
    ):
        return False
    if any(char.isdigit() for char in fold(goal)):
        return False
    asked = _thing_of(goal)
    return bool(asked) and asked == _thing_of(folded_label)


def _form_on_offer(view: dict) -> bool:
    """A control of the view sends or confirms a form (``_FORM_COMMIT``)."""

    return any(
        isinstance(item, dict) and item.get("kind") in {"Button", "SplitButton"}
        and _FORM_COMMIT.match(fold(item.get("name")).strip()) is not None
        for item in view.get("controls") or ()
    )


def _thing_counts(lines: Iterable[object], asked: set[str]) -> dict[str, int]:
    """The totals the lines count of the asked thing, by its word (kin groups read as one)."""

    found: dict[str, int] = {}
    for line in lines:
        for match in _THING_COUNTER.finditer(fold(line)):
            for word in _created_words(match.group("thing")) & asked:
                found.setdefault(word, int(match.group("total")))
    return found


def _created_by_diff(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Pasada r15b (A2: v3-03, v3-04): a goal of making one thing is reached when the sub-goal's last verified step is
    a click and the difference between the sub-goal's first look (the App's «firstLook») and what that click made
    appear proves the one thing made, never the mere presence of a name:

    - a count the window writes of that thing («Diapositiva 1 de 1» at the first look) now says one more
      («diapositiva 2 de 2» appeared after the click): «done» citing that line;
    - the click named the thing («Presentación en blanco» for «haz una presentación en blanco») and the window's title
      is now one the first look never had that names it too («Presentación1 - PowerPoint»; a document born in the
      window or a new window of the application): «done» citing the title;
    - the App recorded that the click made the document the title now shows, with no name yet (its «createdDocument»):
      «done» citing the title.

    The shell judges either citation on screen like any evidence (new since the first look, after a verified act)."""

    asked = _asked_to_create(goal)
    last = history[-1] if history and isinstance(history[-1], dict) else None
    first_look = view.get("firstLook") if isinstance(view, dict) else None
    if not asked or last is None or not isinstance(first_look, str) or not first_look.strip():
        return None
    if last.get("operation") != "input.visible.click" or last.get("ok") is not True or last.get("echo") is True:
        return None
    if not _creates_what_is_asked(goal, last.get("label")) or _form_on_offer(view):
        # Review of sistema-cumplido, findings 2-4: the last click made the asked thing and nothing more is asked (a
        # title, a name, a text); a form still to send or confirm («Enviar» of a new mail) made nothing yet.
        return None
    before = _thing_counts(first_look.split("\n"), asked)
    appeared = view.get("newTextAfterClick") if isinstance(view.get("newTextAfterClick"), list) else view.get("newText")
    for line in appeared if isinstance(appeared, list) else ():
        text = str(line).strip()
        counted = _thing_counts((text,), asked)
        if any(before.get(word) is not None and total == before[word] + 1 for word, total in counted.items()) and (
            view_contains(view, text)
        ):
            return {"operation": "done", "arguments": {"evidence": text[:80]}, "reason": REASON_CREATED_BY_DIFF}
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    title = str(window.get("title") or "").strip()
    folded_title = fold(title).strip()
    parts = {part.strip() for part in first_look.split("\n") if part.strip()}
    label = fold(last.get("label")).strip()
    # The click made a new one (``_creates_what_is_asked``), never opened one already made: a recent «Presentación
    # final» is the person's file, whose title also names a presentation, and a window titled by the clicked name
    # («Nueva presentación de ventas - PowerPoint») opened a file of that name.
    if (
        folded_title and not any(folded_title in part for part in parts) and label not in folded_title
        and _created_words(folded_title) & asked
    ):
        return {"operation": "done", "arguments": {"evidence": title[:80]}, "reason": REASON_CREATED_BY_DIFF}
    # Ronda 24 (pasada r23 v3-11): a title that turned into a document with no name yet («Sin título - OneNote» after
    # «Agregar página») never names the thing; the App's record that the click made that document proves the creation
    # (the click's «createdDocument», ComputerUseMissionWindow.NoteCreatedDocument). Encargo EX: the mind reads that one
    # record, never a twin of its rule (the first look, the count of «Sin título» before and after the click).
    recorded, shown = (
        " ".join(part for part in re.split(r"[^\w]+", re.split(r"\s+[-–—|•·]\s+", fold(text).strip())[0]) if part)
        for text in (last.get("createdDocument"), folded_title)
    )
    if folded_title and recorded and recorded == shown:
        return {"operation": "done", "arguments": {"evidence": title[:80]}, "reason": REASON_CREATED_BY_DIFF}
    return None


def _creating_object(control: object) -> str | None:
    """The object of a command that creates (data «creatingCommand»), by the control's own name; None for any other."""

    if not isinstance(control, dict):
        return None
    found = re.match(_evidence_rules()["creatingCommand"], fold(str(control.get("name") or "")).strip())
    return found.group("object") if found is not None else None


def _last_click_made_something(view: dict, history: list[dict] | None, name: str) -> bool:
    """Pasada r15b (A2, v3-03: «Nueva diapositiva» pressed four times, each one a slide more): the sub-goal's last
    verified step is a click on a control of this name and it made lines appear (the App's «newTextAfterClick»), with
    no menu open and nothing left expanded: it made something rather than opening a choice. Read where the App's
    «broughtNew» cannot tell (a window whose controls fill the listing, so a new one may not be listed)."""

    last = next((step for step in reversed(history or []) if isinstance(step, dict) and step.get("ok") is True), None)
    if last is None or last.get("operation") != "input.visible.click" or last.get("echo") is True:
        return False
    if fold(str(last.get("name") or last.get("label") or "")).strip() != fold(name).strip():
        return False
    appeared = view.get("newTextAfterClick") if isinstance(view, dict) else None
    if not isinstance(appeared, list) or not any(str(line).strip() for line in appeared):
        return False
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    return not any(
        control.get("kind") == "Menu" or "expanded" in str(control.get("state") or "").split() for control in controls
    )


def _brought_this_subgoal(control: dict, view: dict) -> bool:
    """Revisión 3 de P4: a control the sub-goal brought, never one that was already on screen (Office's «Guardar» of
    the quick access bar is on every look): its name is among the lines the last verified click made appear (the
    App's «newTextAfterClick»), or its part (the name, with its value) shows more times than on the sub-goal's first
    look (the App's «firstLook», parts as ``look_parts`` writes them). Without either look, nothing counts as brought.
    Twin of ComputerUseSuccessCheck.BroughtThisSubgoal."""

    name = fold(control.get("name")).strip()
    if not name or not isinstance(view, dict):
        return False
    appeared = view.get("newTextAfterClick")
    if isinstance(appeared, list) and any(isinstance(line, str) and fold(line).strip() == name for line in appeared):
        return True
    first_look = view.get("firstLook")
    if not isinstance(first_look, str) or not first_look.strip():
        return False
    value = fold(control.get("value"))
    part = (fold(control.get("name")) + ("\t" + value if value else "")).replace("\n", " ").replace("\r", " ")
    return look_parts(view).count(part) > first_look.split("\n").count(part)


def _form_button_cited(evidence: str, view: dict, goal: str | None) -> bool:
    """Revisión 2 de P4: a goal of creating something (data «creatingGoal») cites a button (Button, SplitButton) of a
    form still to save: the citation is the form's own control («Guardar», «Descartar»), never what the form makes,
    which does not exist yet. Revisión 3 de P4 (Word, PowerPoint and Paint keep «Guardar» on the quick access bar;
    Edge's favourite bubble shows «Listo»): the form is the one the sub-goal brought (``_brought_this_subgoal``), so
    the cited button and a button that saves or confirms (data «commitControl») both came with it, and the cited
    button names nothing of what the goal creates (its words, kin included: «Editar favorito para esta página» for
    «agrega esta página a favoritos» is the thing's own control, not the form's). Twin of
    ComputerUseSuccessCheck.FormButtonCited."""

    rules = _evidence_rules()
    folded_goal = fold(goal or "").strip()
    if not isinstance(view, dict) or not re.match(rules["creatingGoal"], folded_goal):
        return False
    cited = fold(evidence).strip(_CITATION_MARKS).strip()
    if not cited:
        return False
    brought = [
        item for item in (view.get("controls") or [])
        if isinstance(item, dict) and item.get("kind") in {"Button", "SplitButton"}
        and _brought_this_subgoal(item, view)
    ]
    if not any(re.search(rules["commitControl"], fold(item.get("name")).strip()) for item in brought):
        return False
    asked = _created_words(re.sub(rules["creatingGoal"], "", folded_goal, count=1))
    return not _created_words(cited) & asked and any(fold(item.get("name")).strip() == cited for item in brought)


def _creation_shown(view: dict, history: list[dict], goal: str | None) -> bool:
    """Revisión 2 de P4: the view proves that what a creating command made exists, so «ya creó lo pedido» may be said
    and «done» offered. Never with a button that saves or confirms on offer (data «commitControl»: a form still to
    save, «Nuevo evento» with «Guardar») nor with a menu open or a control expanded (a command that offers templates
    made nothing yet); then one of the creation proofs holds: the new document part (``_created_by_effect``), a count
    or a title one more (``_created_by_diff``) or the focused part new by identity (``_new_part_by_identity``)."""

    if not isinstance(view, dict):
        return False
    controls = [item for item in (view.get("controls") or []) if isinstance(item, dict)]
    if _commit_on_offer(controls) or any(
        item.get("kind") == "Menu" or "expanded" in str(item.get("state") or "").split() for item in controls
    ):
        return False
    if _created_by_effect(goal or "", view, history) is not None or _created_by_diff(goal or "", view, history) is not None:
        return True
    focused = _focused(view)
    return focused is not None and _new_part_by_identity(str(focused.get("name") or ""), view, history, goal)


REASON_CREATING = "el objetivo crea lo que dice el único mando de la vista que lo crea"
# Ronda 23 (v3-35): the kinds of a command that creates; a list or tree item named «Nueva nota» is someone's content.
_CREATING_COMMAND_KINDS = frozenset({"Button", "SplitButton", "MenuItem"})


def _creating_command_step(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Ronda 23 (v3-35: «crea una nota rapida nueva» with «Nueva nota» on screen and the encoder cold: the model alone
    said «none»): a goal that creates one thing (data «creatingGoal», no «creatingQuantity»: ``_asked_to_create``) and a
    view with exactly one command that creates (data «creatingCommand», a button or menu entry drawn and enabled) whose
    object shares a word with what is asked (``_created_words``, kin included) presses that command by its index, with
    no encoder. Never a removal, an account act or a new window the goal does not ask for (``_translation_clickable``),
    never the system menu nor the frame (``_without_vetoed``), never after a click of the sub-goal (so never a second
    time: ``_creation_refusal``'s creates_again needs a click before, and its creates_other a command that shares no
    word with what is asked). Revisión 1 de r23 (b): what is asked is the object the goal creates, read by
    ``cu_tipos.created_object`` (an indefinite object right after the verb, nothing after it): a goal that adds to,
    changes or names something that exists («agrega pan a la nota», «haz la nota morada») or says another place («crea
    una carpeta en el escritorio») never presses a creating command here. Revisión 2 de r23 (b): the command's own
    object is read with the same contract (``cu_tipos.creating_command_object``): a command that adds something that
    exists or puts it somewhere («Agregar esta página a favoritos (Ctrl+D)», «Agregar nota al contacto») is never the
    one that creates, and the step is the model's. Two such commands, or none: the model."""

    rules = _evidence_rules()
    thing = cu_tipos.created_object(fold(goal or "").strip(), rules["creatingGoal"], rules["creatingQuantity"])
    asked = _created_words(thing) if thing else set()
    if not asked or not isinstance(view, dict) or any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" for step in history
    ):
        return None
    commands = [
        control for control in _without_vetoed(view, goal).get("controls") or []
        if isinstance(control, dict) and isinstance(control.get("i"), int)
        and str(control.get("kind")) in _CREATING_COMMAND_KINDS
        and "disabled" not in str(control.get("state") or "").split() and _drawn(view, control)
        and (found := _creating_object(control)) is not None and _created_words(found) & asked
    ]
    if len(commands) != 1:
        return None
    name = str(commands[0].get("name") or "")
    if not _translation_clickable(goal, name) or _REMOVAL_NAME.search(fold(name)):
        return None
    if cu_tipos.creating_command_object(fold(name).strip(), rules["creatingCommand"]) is None:
        return None
    return _click(commands[0], REASON_CREATING)


def _creation_refusal(decision: dict, view: dict, history: list[dict] | None, goal: str | None) -> dict | None:
    """Lote r11 (v3-11): a press on a command that creates something (data «creatingCommand») that the creating goal
    does not name («Crear una nueva sección» for «crea una página nueva»), or one that already brought something new in
    this sub-goal and would create another (data «creatingQuantity»: unless the goal says how many). None when the
    press is no such command."""

    if decision.get("operation") != "input.visible.click":
        return None
    arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
    target = _viewed_control(view, arguments.get("index"))  # type: ignore[union-attr]
    name = str((target or {}).get("name") or arguments.get("label") or "").strip()  # type: ignore[union-attr]
    rules = _evidence_rules()
    command = re.match(rules["creatingCommand"], fold(name).strip())
    folded_goal = fold(goal or "").strip()
    if not name or command is None:
        return None
    asked = _created_words(re.sub(rules["creatingGoal"], "", folded_goal, count=1)) if re.match(
        rules["creatingGoal"], folded_goal) else set()
    # Review of finales-buscador (finding 1): only when another creating command of the view names what the goal asks
    # is this one the wrong thing; a goal whose words no command shares («create a new folder» beside «Nueva
    # carpeta» with no kin) leaves the press to the model, never a refusal with nothing else to press.
    others = (
        control for control in (view.get("controls") or () if isinstance(view, dict) else ())
        if isinstance(control, dict) and control is not target
        and fold(str(control.get("name") or "")).strip() != fold(name).strip()
    )
    if asked and not _created_words(command.group("object")) & asked and any(
        (found := _creating_object(control)) is not None and _created_words(found) & asked for control in others
    ):
        return _none(f"«{name[:40]}» crearía algo que el objetivo no pide; elegí el control que crea lo pedido",
                     code="creates_other")
    created_before = any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("ok") is True
        and step.get("broughtNew") is True
        and fold(str(step.get("name") or step.get("label") or "")).strip() == fold(name).strip()
        for step in history or ()
    ) or (asked and _last_click_made_something(view, history, name))
    if created_before and re.search(rules["creatingQuantity"], folded_goal) is None:
        if asked and _created_words(command.group("object")) & asked and _creation_shown(view, history or [], goal):
            # Ronda 20 P4 (v3-08): the command creates just what the goal asks, it already brought it and the view
            # proves the thing made (_creation_shown): the retry admits «done» with its evidence (the judge still
            # checks it). Revisión 2 de P4: without that proof (a form with «Guardar» still to save) the step goes on.
            return {**_none(f"«{name[:40]}» ya creó lo pedido; repetirlo crearía otro: si lo ves, done con la evidencia",
                            code="creates_again"), "admits_done": True}
        return _none(f"«{name[:40]}» ya creó algo nuevo y no llevó al objetivo; repetirlo crearía otro: seguí con lo "
                     "que apareció o elegí otra vía", code="creates_again")
    return None
