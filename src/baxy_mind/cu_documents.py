"""A new or blank document: the window's title and content read as a blank document, the opening that makes
the new one asked for, and an editor's start page with its offer of a blank item.
"""

from __future__ import annotations

import re
from typing import Iterable

from . import effect_intent, operation_floor
from .semantic.missions import (
    fold, names_a_blank_item, names_a_file, names_a_file_column, names_a_templates_list, names_own_files_list,
)
from .semantic import lexicon as semantic_lexicon
from .semantic.arguments import with_new_document
from .semantic.windows import asks_for_the_front
from .cu_vocabulary import _evidence_rules
from .cu_view import _focused, _inside, _is_switch
from .cu_fields import key_arguments
from .cu_acts import _click, _none
from .cu_window import _window_fold
from .cu_history import _may_have_acted, _steps_ok
from .cu_creation import _creating_command_step


REASON_BLANK_ALREADY = "el documento en blanco pedido ya está delante, sin nombre y vacío"
REASON_NEW_DOCUMENT_IN_FRONT = "se pidió un documento nuevo y la aplicación delante muestra otro"
REASON_NEW_DOCUMENT_MADE = "la apertura creó el documento nuevo pedido y la ventana lo muestra en blanco"


def _document_part(title: object) -> tuple[str, str]:
    """(the document part of a window's title as written, as folded words): «Libro1 - Excel» → («Libro1», «libro1»)."""

    written = re.split(r"\s+[-–—|•·]\s+", str(title or "").strip())[0].strip()
    return written, " ".join(part for part in re.split(r"[^\w]+", fold(written)) if part)


def _blank_document_shown(view: dict, *, made: bool = False) -> bool:
    """Ronda 24b (banco r23 u5, n6): the window shows a new blank document: its title's document part is a name no
    document is saved under (data «untitledDocument», «defaultDocument»: «Sin título», «Libro1») and what it holds was
    read empty (``_document_content``). Revisión 1 (B2, B3): an unread surface is never blank (an editor that gives no value for
    its document, a grid that lists no cell, a canvas with no text): only a read empty value or a status count of zero proves
    it. ``made``: the mission's own opening just made the document and saw it made (``newDocument`` in its receipt);
    then unread is enough, only content shown denies it. Twin of the App's ComputerUseMissionWindow.BlankDocumentShown
    (that one without ``made``: the App only checks the blank document that already was)."""

    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    _, document = _document_part(window.get("title"))
    rules = _evidence_rules()
    if not document or not (re.match(rules["untitledDocument"], document) or re.match(rules["defaultDocument"], document)):
        return False
    content = _document_content(view)
    return content is not True if made else content is False


def _document_content(view: dict) -> bool | None:
    """Revisión 1 de la ronda 24b (B2, B3): whether the window's document holds content: True when something shows it
    (a status count above zero, a document's or a large field's text that is no placeholder nor an address, a cell's
    value); False only when it was read empty (every count zero, or a content surface whose value was read and is
    empty, none left unread); None when the view does not read it (a Document with no value, a grid whose cells are not
    listed, a canvas). Twin of the App's ComputerUseMissionWindow.DocumentContentShown."""

    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    counted = _status_count_shows_content(view)
    if counted is True:
        return True
    placeholder = re.compile(operation_floor.floor_data()["computerUse"]["contentErasing"]["placeholder"])
    frame = window.get("rect") if isinstance(window.get("rect"), dict) else {}
    whole = float(frame.get("w") or 0) * float(frame.get("h") or 0)
    focused = window.get("focused") if isinstance(window.get("focused"), dict) else None
    unread = read_empty = False
    for control in [*(view.get("controls") or ()), *([focused] if focused else [])]:
        if not isinstance(control, dict):
            continue
        kind = control.get("kind")
        readonly = "readonly" in str(control.get("state") or "").split()
        rect = control.get("rect") if isinstance(control.get("rect"), dict) else {}
        large = whole > 0 and float(rect.get("w") or 0) * float(rect.get("h") or 0) >= whole / 4
        surface = not readonly and (kind == "Document" or (kind == "Edit" and large))
        if surface and control.get("value") is None:
            unread = True
            continue
        value = fold(control.get("value")).strip()
        if kind == "DataItem" and value:
            return True
        if not surface:
            continue
        if value and not placeholder.search(value) and not re.match(r"^(?:[a-z][a-z0-9+.\-]*://|about:)\S*$", value):
            return True
        read_empty = True
    if counted is False:
        return False
    return False if read_empty and not unread else None


def _status_count_shows_content(view: dict) -> bool | None:
    """Revisión 1 de la ronda 24b (B2): what an editor's status text counts of its document (data ``contentCount``:
    «21 caracteres.», «Mensaje de estado Documento1: 13 caracteres», «0 palabras»): True when a count is above zero,
    False when every count is zero, None when the view shows none. Twin of the App's
    ComputerUseMissionWindow.StatusCountShowsContent."""

    count = re.compile(_evidence_rules()["contentCount"])
    shown: bool | None = None
    for control in view.get("controls") or ():
        if not isinstance(control, dict) or control.get("kind") not in ("Text", "StatusBar"):
            continue
        for found in count.finditer(fold(control.get("name"))):
            if re.search(r"[1-9]", found.group(1)):
                return True
            shown = False
    return shown


def _goal_is_the_blank_item(goal: str | None) -> bool:
    """The sub-goal is the blank item itself, chosen or created («seleccionar documento en blanco», «crear libro en
    blanco»): its words after the verb name an offer to create a new empty item (``names_a_blank_item``). «escribir hola»
    is not."""

    words = fold(goal).split()
    return len(words) >= 2 and names_a_blank_item(" ".join(words[1:]))


def _new_document_made(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Ronda 24b (n6): the sub-goal is the blank item and its one act made the new document, and the window shows it
    blank: «done» citing it, an act with its effect. The act is the opening that made it and saw it made
    (``newDocument`` in its receipt) or, encargo EX (tanda n5 t4-c06: «Libro en blanco» clicked on Excel's start page
    made «Libro1 - Excel» and the model then pressed the title's «Libro1 - Excel», which opened «Guardar este
    archivo»), the click whose receipt the App marked with the document it made (``createdDocument``, the App's
    ComputerUseMissionWindow.NoteCreatedDocument), the one the title now shows. Nothing is pressed after it."""

    acts = [step for step in history if _may_have_acted(step)]
    if not _goal_is_the_blank_item(goal) or len(acts) != 1:
        return None
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    written, document = _document_part(window.get("title"))
    made = (acts[0].get("operation") == "app.open" and acts[0].get("newDocument") is True) or (
        acts[0].get("operation") == "input.visible.click" and bool(document)
        and _document_part(acts[0].get("createdDocument"))[1] == document
    )
    if not made or not _blank_document_shown(view, made=True):
        return None
    return {"operation": "done", "arguments": {"evidence": written}, "reason": REASON_NEW_DOCUMENT_MADE}


def _new_document_in_front(
    objective: str, goal: str, view: dict, application: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex, *, subgoal: int,
) -> dict[str, object] | None:
    """Ronda 24b (banco r23 u5 «elegí libro en blanco» over «Libro1 - Excel» blank; n6 «abrí Word y elegí documento en
    blanco» over Word showing the person's thesis): the request asks for a new document (``with_new_document``, the
    person's words only) and the application is in front showing a document (its title names one; a start page is
    ``_start_page_step``'s). Blank and unnamed already, it is the one asked for: «done» as it already was. Named or
    holding content, the opening makes the new one and sees it made, never the window of the person's document.

    Revisión 1 (B1): only for the sub-goal that is the blank item itself, or for the mission's first sub-goal (no
    opening nor creation of the mission made the document yet). A later sub-goal («guardar como prueba» after
    «escribir hola» in the new document) works on the document the mission made, whatever it now holds: a second
    opening would leave the written text in another window.

    Revisión 2 (B1: «en excel agregá una hoja nueva» with «Nueva hoja» on screen opened a new workbook by Ctrl+N and the
    person's book stayed without the sheet; «en el explorador de archivos crea un archivo nuevo» opened another Explorer
    window, verified as a document made): only what the request asks for. The new document is a whole one an editor
    makes on its New command, said by its kind (``semantic_lexicon.WHOLE_DOCUMENT_NOUNS``: a sheet, a note or a file is
    a part of a document or a folder's item) or by the application's own name; never ahead of the one command of the
    view that creates what the goal asks (``_creating_command_step``), and never over a file manager's content view
    (``_shows_files``), whose window is a folder, no document."""

    if subgoal > 0 and not _goal_is_the_blank_item(goal):
        return None
    app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
    if app_id is None:
        return None
    arguments: dict[str, object] = with_new_document(
        {"appId": app_id}, (objective,), application_names, nouns=semantic_lexicon.WHOLE_DOCUMENT_NOUNS,
    )
    if arguments.get("newDocument") is not True:
        return None
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    if not _title_names_a_document(window.get("title")):
        return None
    controls = [control for control in view.get("controls") or () if isinstance(control, dict)]
    if _shows_files(controls) or _creating_command_step(goal, view, []) is not None:
        return None
    if _blank_document_shown(view):
        # The blank document asked for is there: the sub-goal that is that item holds as it already was; any other
        # (typing into it) goes on there.
        if not _goal_is_the_blank_item(goal):
            return None
        written, _ = _document_part(window.get("title"))
        return {"operation": "done", "arguments": {"evidence": written, "already": True}, "reason": REASON_BLANK_ALREADY}
    if asks_for_the_front(objective):
        arguments["foreground"] = True
    return {"operation": "app.open", "arguments": arguments, "reason": REASON_NEW_DOCUMENT_IN_FRONT}


# The kinds that can be a start page's offer to create a blank item (a template tile, a button, a link).
_OFFER_KINDS = frozenset({"ListItem", "DataItem", "Button", "Hyperlink", "MenuItem", "SplitButton", "TreeItem"})
REASON_CREATE_BLANK = "la ventana está en su página de inicio: creo el elemento en blanco que ofrece para llegar al lugar"
REASON_NO_DOCUMENT = "la aplicación está en su página de inicio, sin ningún documento abierto"
# A creation step's mark for the shell: the next look waits, bounded, for the window's title to change (the new
# document's window takes a moment to replace the start page).
EXPECTS_TITLE_CHANGE = "expects_title_change"
NO_DOCUMENT_OPEN = "no_document_open"


def _title_names_a_document(title: object) -> bool:
    """A title with a « - » segment names what the window holds besides the application («Libro1 - Excel»); a start
    page carries only the application's name («Excel»)."""

    return re.search(r"\s+[-–—|]\s+", _window_fold(title)) is not None


# The containers whose items are things the window holds (files, rows, nodes): an offer to create is accepted inside
# one only when the container is named as the offers to create («Plantillas», «Nueva»).
_ITEM_CONTAINER_KINDS = frozenset({"List", "DataGrid", "Table", "Tree"})


def _shows_files(controls: list[dict]) -> bool:
    """A file manager's content view: items that expose their type (Explorer's «Documento de Microsoft Word») or the
    columns of one («Tamaño», «Fecha de modificación»). Nothing in it is an offer to create."""

    return any(
        control.get("itemType") or (str(control.get("kind")) == "HeaderItem" and names_a_file_column(control.get("name")))
        for control in controls
    )


def _blank_item(view: dict) -> dict | None:
    """The one control of the view named as an offer to create a new empty item («Documento en blanco», «Blank
    workbook»): an actionable kind, never a switch, never in a file manager's content view and never inside a list,
    grid or tree other than the offers' own («Plantillas», «Nueva»): a recent file, or a file in a folder, may be called
    «Plantilla en blanco» or «Documento en blanco», and the lists of recent files are not always in the (capped) view.
    None when there is none or more than one (which one would be a guess)."""

    controls = [control for control in view.get("controls") or [] if isinstance(control, dict)]
    if _shows_files(controls):
        return None
    own_lists = [
        control.get("rect") for control in controls
        if str(control.get("kind")) in {"List", "Group", "Pane", "DataGrid", "Table", "Tree"} and names_own_files_list(control.get("name"))
    ]
    containers = [control for control in controls if str(control.get("kind")) in _ITEM_CONTAINER_KINDS]
    offers = [
        control for control in controls
        if str(control.get("kind")) in _OFFER_KINDS and not _is_switch(control) and names_a_blank_item(control.get("name"))
        and not any(_inside(control.get("rect"), rect) for rect in own_lists)
        and all(
            names_a_templates_list(container.get("name")) for container in containers
            if container is not control and _inside(control.get("rect"), container.get("rect"))
        )
    ]
    return offers[0] if len(offers) == 1 else None


def _start_page_offer(view: dict) -> dict | None:
    """The window is a start page: no document named in its title, one offer to create a blank item (``_blank_item``),
    which it returns; None otherwise."""

    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict) or _title_names_a_document(window.get("title")):
        return None
    return _blank_item(view)


def _start_page_step(
    view: dict, history: list[dict], objective: str | None, application: str | None = None,
) -> dict[str, object] | None:
    """A tab of the editor was asked and the window is a start page: no document named in its title, one offer to
    create a blank item. A person creates the blank item first, then goes to the tab: Enter when the focused element is
    the offer itself, else one click on it. Creating an unsaved blank document is reversible and touches no file;
    never when the person named a file of their own (opening a recent one is theirs to say), and never twice: once the
    offer was pressed or clicked, a start page still there is said as such, without another step that could create a
    second one."""

    offer = _start_page_offer(view)
    if offer is None:
        return None
    name = fold(offer.get("name"))
    acted = _steps_ok(history, "input.key.press", key="enter") or any(
        fold(step.get("label")) == name for step in history if step.get("operation") == "input.visible.click"
    )
    if names_a_file(objective, application) or acted:
        return _none(REASON_NO_DOCUMENT, code=NO_DOCUMENT_OPEN)
    focused = _focused(view)
    is_the_offer = (
        focused is not None and fold(focused.get("name")) == name and str(focused.get("kind")) == str(offer.get("kind"))
        and not offer.get("repeated")
        and (not isinstance(focused.get("i"), int) or not isinstance(offer.get("i"), int) or focused["i"] == offer["i"])
    )
    if is_the_offer:
        return {"operation": "input.key.press", "arguments": key_arguments("enter", view, history),
                "reason": REASON_CREATE_BLANK, "code": EXPECTS_TITLE_CHANGE}
    return {**_click(offer, REASON_CREATE_BLANK), "code": EXPECTS_TITLE_CHANGE}
