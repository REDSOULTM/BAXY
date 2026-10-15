"""Where a typed text goes: the part of a document it names or the one with the keyboard, a placeholder, the
field a place names, a text kept from a part nobody named, and a free text kept out of the search.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable

from . import operation_floor
from .semantic.account_acts import account_act
from .semantic.cu_buscar import SLOT_WORDS, names_an_item, slot_text, text_slot
from .semantic.missions import fold
from .semantic.cu_tipos import named_typing_place
from .semantic.cu_semejanza import CLICK_MARGIN, CLICK_SIMILARITY, runner_up
from .cu_view import _focused, _same_control, label_names
from .cu_fields import (
    _ADDRESS_NAME, _COMPOSER_NAME, _EDITABLE_KINDS, _PRESSED_KINDS, _SEARCH_NAME, _example_text, _focused_controls,
    _is_search_field, _keyboard_on_a_search, _search_box, _search_field_box, _search_words, _writable,
)
from .cu_acts import _click, _form_field_arguments, _guard_repeat, _none, typed_text
from .cu_window import _window_fold
from .cu_unasked import _DISCARD_NAME, _REMOVAL_NAME
from .cu_meaning import SemanticMatcher
from .cu_first_look import _seen_at_start
from .cu_forms import _FORM_FIELD_KINDS, _field_named


# The part of a document or a form a goal names as where its text goes (``semantic.cu_buscar.text_slot`` reads it
# from the goal; ``SLOT_WORDS`` are its names). The same part said in the other language of the tables (data: the
# encoder covers the rest by meaning).
_SLOT_OTHER = {
    "titulo": "title", "title": "titulo", "subtitulo": "subtitle", "subtitle": "subtitulo", "cuerpo": "body",
    "body": "cuerpo", "asunto": "subject", "subject": "asunto", "nombre": "name", "name": "nombre", "notas": "notes",
    "notes": "notas", "nota": "note", "note": "nota", "descripcion": "description", "description": "descripcion",
    "comentario": "comment", "comment": "comentario", "encabezado": "heading", "heading": "encabezado",
    "header": "encabezado",
}
# A document's placeholder that takes the text once pressed («Haga clic para agregar título», «Click to add title»).
_PLACEHOLDER_LINE = re.compile(
    r"\b(?:haga|haz|hace|pulse|pulsa|toque|toca|click|clic|tap)\b.{0,12}\b(?:para|to)\s+(?:agregar|anadir|escribir|add|type)\b"
)
# What the model may name as the field («ListItem «Presentación en blanco»»): the view's own «kind «name»» line.
_KIND_AND_NAME = re.compile(r"^\s*(?P<kind>[A-Za-z]+)\s*[«\"“](?P<name>.+?)[»\"”]\s*$")

# A text that did not reach its place this many times is not sent there again.
_SAME_TEXT_TRIES = 2


def _names_slot(name: object, slot: str) -> bool:
    folded = fold(name)
    return any(re.search(rf"\b{word}\b", folded) for word in (slot, _SLOT_OTHER.get(slot, slot)))


def _placeholder_field(control: dict, view: dict | None = None) -> bool:
    """A document's part waiting for its text: a field or document named as a placeholder («Haga clic para agregar
    título»), or one that names a part («Título de página», «Título 1») and holds nothing yet. Never the person's work:
    a document that holds text is no placeholder. With ``view`` (a goal that does not name the part), an empty part the
    sub-goal's first look already showed is no vacancy either (ronda 20 P1, v3-11: the empty title of a page that was
    already there is the person's page)."""

    if not _writable(control):
        return False
    name = fold(control.get("name"))
    if view is not None and str(control.get("name") or "").strip() and _seen_at_start(str(control.get("name")), view):
        return False
    if _PLACEHOLDER_LINE.search(name):
        return True
    return not str(control.get("value") or "").strip() and any(re.search(rf"\b{word}\b", name) for word in SLOT_WORDS)


# The parts of a document that are not its body (ronda 20 P1): a text the goal does not aim at one never goes there.
# Data shared with the App (operation_floor.v1.json «computerUse.documentPart»): the negated forms («sin título»,
# «no title», like «untitled») name a whole document that has none, never its title part (review of r20 P1, finding 3).
_DOCUMENT_PART = re.compile(operation_floor.floor_data()["computerUse"]["documentPart"])
# Ronda 22 (data «computerUse.typedChord»): a text whose whole folded form is a key combination.
_TYPED_CHORD = re.compile(operation_floor.floor_data()["computerUse"]["typedChord"])


def _names_a_part(name: object) -> bool:
    """The name names a part of a document other than its body by its words («Título de página», «Título 1»,
    «Encabezado», a placeholder line «Haga clic para agregar título»); never a document without a title («Sin título»,
    «Documento sin título - …», «Untitled»)."""

    return _DOCUMENT_PART.search(" ".join(fold(name).split())) is not None


# The window's title names its document: a name it shows at its start or after a separator, then perhaps the file's
# extension and a separator or the end («Proyecto de título.docx - Word», «Sin título: Bloc de notas»).
_TITLE_SEPARATOR = r"\s*[-–—|:]\s"


def _names_the_window(name: object, title: object) -> bool:
    """Review 3 of r20 P1 (B1): the control's name is the name the window's title gives its document («Proyecto de
    título» in «Proyecto de título - Word»): the document itself, never a part of it, whatever words its name holds (a
    person's file called «Seminario de Título», «Cover letter header»). Twin of OperationFloor.NamesTheWindow."""

    folded = " ".join(_window_fold(name).split()).strip()
    whole = " ".join(_window_fold(title).split()).strip()
    if not folded or not whole:
        return False
    return re.search(
        rf"(?:^|{_TITLE_SEPARATOR}){re.escape(folded)}(?:\.\w{{1,5}})?(?:{_TITLE_SEPARATOR}|\s*$)", whole
    ) is not None


def _part_of_the_document(control: dict, view: dict) -> bool:
    """A part of a document other than its body by its name (``_names_a_part``), unless that name is the one the
    window's title gives the document itself (``_names_the_window``, review 3 of r20 P1, B1)."""

    window = view.get("window") if isinstance(view, dict) else None
    title = window.get("title") if isinstance(window, dict) else None
    return _names_a_part(control.get("name")) and not _names_the_window(control.get("name"), title)


def _unnamed_part_in_focus(view: dict) -> dict | None:
    """The Document or Edit that has the keyboard when it is a part of a document other than its body (by its name):
    the place a text no goal aimed at must not go."""

    for control in _focused_controls(view):
        if control.get("kind") in {"Document", "Edit"} and not _search_box(view, control) and _part_of_the_document(control, view):
            return control
    return None


def _part_kept_from_the_text(view: dict, goal: str | None, objective: str | None) -> dict | None:
    """The part of a document that has the keyboard (``_unasked_part_in_focus``) when a text at the caret must not go
    there: it is no placeholder line («Haga clic para agregar título», no one's text) nor a vacancy of this sub-goal
    (``_placeholder_field`` with the view: empty and new since the first look). One rule for the step of the rule and
    the model's step (review 3 of r20 P1, B2: the rule clicked the body of a form just opened, beside its empty title)."""

    part = _unasked_part_in_focus(view, goal, objective)
    if part is None or _PLACEHOLDER_LINE.search(fold(part.get("name"))):
        return None
    # window.focused carries no value: the view's own entry of that control says whether it holds text.
    listed = next((
        control for control in (view.get("controls") or []) if isinstance(control, dict) and _same_control(control, part)
    ), part)
    return None if _placeholder_field(listed, view) else part


def _unasked_part_in_focus(view: dict, goal: str | None, objective: str | None) -> dict | None:
    """The part of a document that has the keyboard (``_unnamed_part_in_focus``) when the request names no part: neither
    the sub-goal nor the objective names its slot (review 2 of r20 P1, finding 2: «escribe «Compras» como título» is
    the sub-goal «escribir compras», the title only the objective's), and neither gives an item a name (finding 3:
    the box a tab, a window or a list is renamed in is called «Título»; that title is the item's)."""

    if text_slot(goal) is not None or text_slot(objective) is not None or names_an_item(goal) or names_an_item(objective):
        return None
    return _unnamed_part_in_focus(view)


def _into_the_focused_part(arguments: dict[str, object], view: dict) -> dict[str, object]:
    """A text at the caret on a part of a document the request lets it go to (one it names, a vacancy of this sub-goal,
    a placeholder line, an item's name box) names that part as its field (review 2 of r20 P1, finding 1): the App takes
    an index read from the focus as no choice of the step, so only «field» tells the part was chosen. Without
    «replace»: the text goes in at the part's caret, the same delivery as by the focus's index. Only when the App
    resolves that label to the same control (the first control of the view that takes text by that label); else the
    step stays at the caret."""

    part = _unnamed_part_in_focus(view)
    controls = view.get("controls") if isinstance(view, dict) else None
    if part is None or arguments.get("field") or not isinstance(controls, list):
        return arguments
    label = str(part.get("name") or "").rstrip(":： ").strip()
    same = [
        control for control in controls
        if isinstance(control, dict) and control.get("kind") in {"Edit", "Document", "ComboBox"}
        and isinstance(control.get("i"), int) and not {"readonly", "password"} & set(str(control.get("state") or "").split())
        and fold(str(control.get("name") or "").rstrip(":： ")) == fold(label)
    ]
    if not label or not same or not _same_control(same[0], part):
        return arguments
    return {**arguments, "field": label}


def _body_click(view: dict, history: list[dict]) -> dict[str, object] | None:
    """The click that puts the caret in the document's body when the keyboard is on a part the goal does not name: the
    one empty Document of the view (or the one field named as a body) that names no part, is no search box nor a
    message box; None (the model's step) when there is none or more than one, or it was just clicked."""

    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)] if isinstance(view, dict) else []
    bodies = [
        control for control in controls
        if control.get("kind") in {"Document", "Edit"} and _writable(control) and not _search_box(view, control)
        and not _part_of_the_document(control, view) and not str(control.get("value") or "").strip()
        and (control.get("kind") == "Document" or re.search(r"\b(?:cuerpo|body)\b", fold(control.get("name"))))
        and str(control.get("name") or "").strip()
    ]
    if len(bodies) != 1:
        return None
    body = bodies[0]
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is not None and last.get("operation") == "input.visible.click" and label_names(
        str(body.get("name") or ""), str(last.get("label") or "")
    ):
        return None
    return _click(body, "pongo el cursor en el cuerpo: el objetivo no nombra la parte que tiene el teclado")


def _slot_destination(
    view: dict, slot: str, text: str, history: list[dict], semantic: SemanticMatcher | None, why: str,
    press: Callable[[str], dict[str, object]],
) -> dict[str, object] | None:
    """Where a text that names its part goes (v3 campo-texto): the one empty writable field of the view named as that
    part (by its name, the other language's, or by meaning past the click threshold with the E5 matcher), never a
    search box nor a message box, and never a field that already holds text (review r10 campo-texto, finding 1: the
    person's «María Pérez» is never written over by a redirected text); else a placeholder line of the window's text
    that names it («Haga clic para agregar título»), pressed first so the part takes the keyboard, through ``press``
    (every check of a click). None when nothing empty names the part."""

    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)] if isinstance(view, dict) else []
    fields = [
        control for control in controls
        if _writable(control) and not _search_box(view, control) and str(control.get("name") or "").strip()
    ]
    named = [control for control in fields if _names_slot(control.get("name"), slot)]
    if not named and semantic is not None and fields:
        scored = semantic.scored(slot, {"controls": fields}, (_SLOT_OTHER.get(slot, slot),))
        top = scored[0] if scored else None
        if top is not None and top[1] >= CLICK_SIMILARITY and top[1] - runner_up(scored, top[0]) >= CLICK_MARGIN:
            named = [control for control in fields if str(control.get("name") or "").strip() == top[0]]
    # Only a part still to fill, in the view's reading order: a redirected text never replaces what a field holds.
    field = next((control for control in named if not str(control.get("value") or "").strip()), None)
    if field is not None:
        arguments = _form_field_arguments(field, str(field.get("name") or ""), text)
        if field.get("kind") == "Document":
            # A document is never replaced whole: the text goes into it (the provider refuses replacing a document).
            arguments.pop("replace", None)
        return {"operation": "input.text.type", "arguments": arguments, "reason": why or "escribo en el campo que el objetivo nombra"}
    text_lines = view.get("text") if isinstance(view, dict) else None
    clicked = {fold(step.get("label")) for step in history if step.get("operation") == "input.visible.click"}
    for zone in (text_lines.values() if isinstance(text_lines, dict) else ()):
        for line in zone if isinstance(zone, list) else ():
            folded = fold(str(line))
            if _PLACEHOLDER_LINE.search(folded) and _names_slot(folded, slot) and folded not in clicked:
                return press(str(line).strip())
    return None


def _focused_slot_step(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Pasada r15b (v3-08): «ponele de título Lista del super» with the keyboard already in the page's empty «Título de
    página»: the text goes there, no model asked (it pressed «Nuevo cuaderno»). Only a Document or an Edit that has
    the keyboard, takes text (``_writable``: never a password, a read-only field or a message box), is no search box,
    holds nothing yet (never the person's work written over) and names the part the goal names (``_names_slot``: the
    word shared with the goal, in either language). Once: a text already sent there is the check's or the model's."""

    slot = text_slot(goal)
    text = slot_text(goal) if slot is not None else None
    if not text:
        return None
    focused = next((
        control for control in _focused_controls(view)
        if control.get("kind") in {"Document", "Edit"} and str(control.get("name") or "").strip()
    ), None)
    if (
        focused is None or not _writable(focused) or _search_box(view, focused)
        or str(focused.get("value") or "").strip() or not _names_slot(focused.get("name"), slot)
        or any(step.get("operation") == "input.text.type" for step in history if isinstance(step, dict))
    ):
        return None
    arguments = _form_field_arguments(focused, str(focused.get("name") or ""), typed_text(text))
    if focused.get("kind") == "Document":
        # A document is never replaced whole: the text goes into it (the provider refuses replacing a document).
        arguments.pop("replace", None)
    return {"operation": "input.text.type", "arguments": arguments, "reason": "escribo en la parte que el objetivo nombra"}


def _named_field(named: str) -> tuple[str, str | None]:
    """The field's name the model gave, without the «kind «name»» wrapping the view's lines use."""

    wrapped = _KIND_AND_NAME.match(named)
    return (wrapped.group("name").strip(), wrapped.group("kind")) if wrapped else (named.strip(), None)


def _typing_without_arrival(
    decision: dict[str, object], history: list[dict], view: dict,
) -> dict[str, object]:
    """A text sent to the same field (or to the focus) that did not take the goal anywhere is not sent again: once
    the field already shows it, or after ``_SAME_TEXT_TRIES`` sends, the step is another place or an honest limit
    (measured on v3-04: the title went six times into the window's search box). The place of a past send is the one
    the App's history gives the mind: its «field» when it named one, else its «into» (the control that had the
    keyboard), so two «sí» typed into two different cells are two places."""

    if decision.get("operation") != "input.text.type":
        return decision
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    text, field = fold(arguments.get("text")), fold(arguments.get("field"))
    focused = None if field else _focused(view)
    into = fold(focused.get("name")) if focused is not None else ""
    same = [
        step for step in history
        if step.get("operation") == "input.text.type" and fold(step.get("text")) == text
        and fold(step.get("field")) == field and (bool(field) or fold(step.get("into")) == into)
    ]
    if not same:
        return decision
    target = _field_named(view, (str(arguments.get("field")),)) if field else focused
    shows = target is not None and fold(target.get("value")).strip() == text.strip()
    if shows or len(same) >= _SAME_TEXT_TRIES:
        where = f"«{str(arguments.get('field'))[:40]}»" if field else "el campo enfocado"
        return _none(
            f"ya escribí «{str(arguments.get('text'))[:40]}» en {where} y no llevó al objetivo; otro campo o none",
            code="text_not_arriving",
        )
    return decision


def _slot_or_refusal(
    view: dict, slot: str, text: str, history: list[dict], semantic: SemanticMatcher | None, why: str,
    last_failed: dict | None, press: Callable[[str], dict[str, object]],
) -> dict[str, object]:
    destination = _slot_destination(view, slot, text, history, semantic, why, press)
    if destination is None:
        return _none(
            "el cuadro de búsqueda sólo recibe búsquedas; el texto va al campo que el objetivo nombra",
            code="search_box_not_target",
        )
    return _typing_without_arrival(_guard_repeat(destination, last_failed), history, view)


def _pressed_instead(named: str, control: dict, goal: str | None) -> dict[str, object] | None:
    """A text aimed at a control that is pressed (a gallery's item, a button): the press the sub-goal names, as a click
    act, or None (then the step is refused). As ``_evidence_names_a_press``: only what the current sub-goal names
    (never the rest of the request), and never a press that removes, discards or changes the account."""

    name = str(control.get("name") or "").strip()
    if not name or str(control.get("kind") or "") not in _PRESSED_KINDS or not goal:
        return None
    if _REMOVAL_NAME.search(fold(name)) or _DISCARD_NAME.search(fold(name)) or account_act(name) is not None:
        return None
    if not label_names(name, goal):
        return None
    act: dict[str, object] = {"act": "click", "text": name}
    if isinstance(control.get("i"), int):
        act["i"] = control["i"]
    return act


def _names_place(name: object, place: str) -> bool:
    """A field's own name says every word of the place, or its other language's word («subject» for «asunto»)."""

    folded = fold(name)
    return all(
        any(re.search(rf"\b{re.escape(word)}\b", folded) for word in {said, _SLOT_OTHER.get(said, said)})
        for said in place.split()
    )


def _typing_place_step(text: str, view: dict, history: list[dict], reason: str) -> dict[str, dict | None] | None:
    """«escribir hola en el campo nombre», «hi in the Name field» (cu-v3 texto-webview): the field the place after the
    text names, when one writable field of the view carries that name (or its other language's), never a search box
    nor a password. The phrase alone cannot tell a field from a place of the world («nos vemos en el campo de
    fútbol», «see you on the soccer field»): with no such field in the view this is None and the whole phrase is the
    text. Found, ``{"step": …}``: typed at the caret when the field has the keyboard; by its label into an empty form
    field; otherwise the field is clicked first (what it holds, a person's draft, is never replaced), and after that
    click a field that still does not show the keyboard is the model's step (``{"step": None}``)."""

    placed = named_typing_place(fold(text))
    if placed is None:
        return None
    typed_folded, place = placed
    typed = " ".join(text.split()[: len(typed_folded.split())])
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)] if isinstance(view, dict) else []
    fields = [
        control for control in controls
        if control.get("kind") in _EDITABLE_KINDS and str(control.get("name") or "").strip()
        and not {"password", "readonly", "disabled"} & set(str(control.get("state") or "").split())
        and not _search_box(view, control) and _names_place(control.get("name"), place)
    ]
    focused = {(fold(control.get("name")), control.get("kind")) for control in _focused_controls(view)}
    keyboard = [field for field in fields if (fold(field.get("name")), field.get("kind")) in focused]
    if len(fields) != 1 and len(keyboard) != 1:
        return None
    field = keyboard[0] if keyboard else fields[0]
    if keyboard:
        return {"step": {"operation": "input.text.type", "arguments": {"text": typed}, "reason": reason}}
    if (
        not str(field.get("value") or "").strip() and field.get("kind") in _FORM_FIELD_KINDS
        and not _COMPOSER_NAME.search(fold(field.get("name")))
    ):
        return {"step": {"operation": "input.text.type", "arguments": _form_field_arguments(field, place, typed), "reason": reason}}
    last = history[-1] if history else None
    if last is not None and last.get("operation") == "input.visible.click" and label_names(
        str(field.get("name") or ""), str(last.get("label") or "")
    ):
        return {"step": None}
    arguments: dict[str, object] = {"label": str(field.get("name") or "")}
    if isinstance(field.get("i"), int):
        arguments["index"] = field["i"]
    return {"step": {"operation": "input.visible.click", "arguments": arguments, "reason": "pongo el cursor en el campo que dice el pedido"}}


def _place_to_type(view: dict, history: list[dict]) -> dict | None:
    """The text field to click before typing when the keyboard is not on one: a message box first, else the only
    editable field; None when a text field already has the keyboard, when it was just clicked, or when there is no
    single field to choose."""

    focused = _focused(view)
    if focused is not None and str(focused.get("kind")) in {"Edit", "Document", "ComboBox"}:
        return None
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    if any("focused" in str(control.get("state") or "").split() and str(control.get("kind")) in {"Edit", "Document"}
           for control in controls):
        return None
    fields = [
        control for control in controls
        if str(control.get("kind")) in {"Edit", "Document"} and "password" not in str(control.get("state") or "")
        and not _is_search_field(control) and not re.search(r"\b(?:direcc|address|url)", fold(control.get("name")))
    ]
    composers = [control for control in fields if _COMPOSER_NAME.search(fold(control.get("name")))]
    chosen = composers[0] if len(composers) == 1 else fields[0] if len(fields) == 1 else None
    if chosen is None:
        return None
    last = history[-1] if history else None
    if last is not None and last.get("operation") == "input.visible.click" and label_names(
        str(chosen.get("name") or ""), str(last.get("label") or "")
    ):
        return None
    return chosen


# What deterministic_step returns for «the model decides» where a rule had something to say (no step of its own).
_MODEL_DECIDES = "model"


def _off_the_search(view: dict, history: list[dict]) -> tuple[str, dict | None] | None:
    """Ronda 24b (banco r23 c6): a free text («escribir X», never «buscar», a field said or the search said) with the
    keyboard on the window's search box goes where text is written, not into the search. ``("click", field)``: the one
    message box of the view (named so, ``_COMPOSER_NAME``), else its one editable field that is no search, address,
    password or read-only part, is clicked first. ``("stuck", field)``: that field was just clicked and the keyboard
    stayed in the search, so nothing is typed. ``("model", None)``: several such fields and no single message box, or
    none readable in a window that writes to people (``_message_window``: a chat whose box the view cannot read); the
    model decides, never the rule typing into the search. None: the keyboard is not on a search, or the search is the
    window's only field (a launcher or the Start menu, «escribí notepad»): the text goes where the keyboard is.

    Revisión 3 de r24b. B1: a search that holds a text this very mission typed into it («buscar Ron» left «ron» in the
    message search while the chat stayed @Ana's) does not prove the place: its message box may be someone else's, and
    the model decides (a search left dirty by another mission, the c6 base, still has its box clicked). B2: a chosen
    field that already holds text (a draft of the person's; not the view's empty mark U+FEFF nor its own name) is
    never clicked by rule: the text would join the person's and leave with it, so the model decides."""

    search = _keyboard_on_a_search(view)
    if search is None:
        return None
    if _search_holds_the_missions_text(view, search):
        return (_MODEL_DECIDES, None)
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    fields = [
        control for control in controls
        if str(control.get("kind")) in {"Edit", "Document"}
        and not {"password", "readonly", "disabled"} & set(str(control.get("state") or "").split())
        and not _search_field_box(view, control) and not _ADDRESS_NAME.search(fold(control.get("name")))
        and not _same_control(control, search)
    ]
    composers = [control for control in fields if _COMPOSER_NAME.search(fold(control.get("name")))]
    chosen = composers[0] if len(composers) == 1 else fields[0] if not composers and len(fields) == 1 else None
    if chosen is None:
        return (_MODEL_DECIDES, None) if fields or _names_a_message_box(view) else None
    if _holds_text(chosen):
        return (_MODEL_DECIDES, None)
    last = history[-1] if history else None
    if last is not None and last.get("operation") == "input.visible.click" and label_names(
        str(chosen.get("name") or ""), str(last.get("label") or "")
    ):
        return ("stuck", chosen)
    return ("click", chosen)


def _content_of(value: object) -> str:
    """A field's value without what only marks it empty: blanks and format characters (a U+FEFF)."""

    return "".join(ch for ch in str(value or "") if unicodedata.category(ch) != "Cf").strip()


def _holds_text(control: dict) -> bool:
    """Revisión 3 de r24b (B2): the field already holds someone's text: its value is neither empty (blanks, format
    marks) nor only the field's example text (its own name, ``_example_text``)."""

    held = _content_of(control.get("value"))
    return bool(held) and not _example_text(control, held)


def _search_holds_the_missions_text(view: dict, search: dict) -> bool:
    """Revisión 3 de r24b (B1): the search with the keyboard holds the text this mission typed into a search
    (``view.lastTyped`` with ``intoSearch``, a receipt of the App), as a whole word of its value."""

    typed = view.get("lastTyped") if isinstance(view, dict) else None
    if not isinstance(typed, dict) or typed.get("intoSearch") is not True:
        return False
    text = fold(_content_of(typed.get("text")))
    if not text:
        return False
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    values = [search.get("value"), *(control.get("value") for control in controls if _same_control(control, search))]
    word = re.compile(rf"(?<!\w){re.escape(text)}(?!\w)")
    return any(word.search(fold(_content_of(value))) for value in values)


def _names_a_message_box(view: dict) -> bool:
    """The view names a message box that is no search (``_message_window`` without the search's own placeholder: a
    launcher's «Escribe aquí para buscar» is its search, «Enviar mensaje a @Ron92» a chat's box)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if any(
        isinstance(control, dict) and str(control.get("kind")) in _EDITABLE_KINDS
        and _COMPOSER_NAME.search(fold(control.get("name"))) and not _search_field_box(view, control)
        for control in (controls if isinstance(controls, list) else [])
    ):
        return True
    text = view.get("text") if isinstance(view, dict) else None
    return isinstance(text, dict) and any(
        isinstance(line, str) and len(line.split()) <= 6 and _COMPOSER_NAME.search(fold(line))
        and not _SEARCH_NAME.search(_search_words(fold(line)))
        for lines in text.values() if isinstance(lines, list) for line in lines
    )
