"""The text fields of a view: a message box that may hand a text to a person, a search or an address box, the
field the last text went into, the field with the keyboard, and the key arguments RiskPolicy reads.
"""

from __future__ import annotations

import re

from . import operation_floor
from .semantic.account_acts import form_send_button
from .semantic.missions import fold
from .semantic.cu_semejanza import is_search_label
from .cu_view import _FIELD_KINDS, _ONE_LINE_HEIGHT, _area, _focused, _same_control


# Revisión 2 de r24b (B1): the pattern is data (operation_floor.v1.json «computerUse.searchField.composer»), read by the
# App too (OperationFloor.SearchFieldName), so a message box named for a #channel or @person with a search word is no
# search on either side.
_COMPOSER_NAME = re.compile(operation_floor.floor_data()["computerUse"]["searchField"]["composer"])
# What Enter or space may send from: a message box, and a reply, comment, post or send box or button.
_SENDING_NAME = re.compile(
    r"\b(?:mensaj|message|chat|escrib|say\s+something|type\s+a\s+message|conversa|respon|reply|coment|comment|"
    r"publica|post\b|tweet|envia|send\b)"
)
# The name the view gives a text field that has none of its own: «(edit)», «(document)».
_UNNAMED_FIELD = re.compile(r"^(?:\((?:edit|document)\))?$")
_EDITABLE_KINDS = frozenset({"Edit", "Document", "ComboBox"})


def _own_name(control: dict) -> str:
    """The control's own Name, folded; empty when the view gave it a fallback name (``nameSource``: its help text,
    its label or its readable AutomationId). A fallback name may say more than the control is, so it never frees a
    step that a field without a name would ask for: it is not a search, an address or a harmless field."""

    return "" if control.get("nameSource") else fold(control.get("name"))


def _composer_with_text(view: dict, history: list[dict] | None = None) -> bool:
    """Whether Enter (or space) on the focused control may hand something to a person (contract §2.1), so the step
    is marked ``message_composer`` and RiskPolicy asks first. Conservative by design (safety review 2026-10-07):

    * a focused control named like a message, chat, reply, comment or send box asks, unless it exposes a value and
      that value is empty (nothing to send);
    * a focused text field with no name of its own that does not expose its value asks too: what it is and what it
      holds cannot be read, and in a chat that is the message box (measured: Discord's editor exposes no value);
      a fallback name (``nameSource``: help text, label, AutomationId) is not a name of its own;
    * a window whose focus cannot be read (none reported, or a bare pane or custom control: measured on WhatsApp,
      drawn without a tree) right after this sub-goal typed a text asks: the text may sit in a chat's message box;
    * a view read behind the person's window (no keyboard focus to read) asks when any message box in it may hold
      text, whatever the last step was;
    * free: a search or address field (named so by its own Name), a document editor that exposes its value (Notepad), and a window
      with no focused editable where nothing was just typed (a calculator's buttons);
    * free where the focus cannot be read: the text just typed went into a field of a form or a search
      (``_typed_into_plain_field``: a search, filter, name or value field named so by its own Name, never a message
      box, in a view with no send button and no other box that may hand a text to a person), measured on the r9 pass
      where the Character Map's «Buscar:» read behind asked before its Enter. A view where a message box (or a box
      with no name of its own hiding its content) may hold text never frees: where the text went is proven by a click
      or a value, and neither says the keyboard did not stay in that box (adversarial review of r9), read behind or
      in front.
    """

    focused = _focused(view)
    unreadable = _focus_unreadable(view)
    if _last_verified_typed(history) and unreadable and _typed_into_plain_field(view, history) is None:
        return True
    if unreadable and _looked_behind(view) and _sending_box_may_hold_text(view):
        # A view read behind the person's window (v3 point 0) has no keyboard focus to tell (adversarial review
        # r10a): the focused message box with text cannot be seen, so a message box anywhere in the view that may
        # hold text (its value is not shown empty: a draft of the person's, or a text typed before a click on a
        # mention) makes Enter ask.
        return True
    if focused is None:
        return False
    name = fold(focused.get("name"))
    own = _own_name(focused)
    value = focused.get("value")
    # A fallback name may make a field ask (it reads as a message box) but never frees it from asking.
    if _SENDING_NAME.search(name) is not None and not _SEARCH_NAME.search(_search_words(own)) \
            and not _ADDRESS_NAME.search(own):
        # A message box whose content the screen does not expose may hold the text just typed: Enter there sends.
        return value is None or bool(str(value).strip())
    unnamed = _UNNAMED_FIELD.match(name) is not None or bool(focused.get("nameSource"))
    return str(focused.get("kind")) in _EDITABLE_KINDS and unnamed and value is None


# A focused control that says nothing of what has the keyboard: a window's bare pane or a custom drawn control.
_OPAQUE_FOCUS_KINDS = frozenset({"Pane", "Custom"})


def _focus_unreadable(view: dict) -> bool:
    """The view does not say what has the keyboard: no focus reported, or a bare pane or custom control."""

    focused = _focused(view)
    return focused is None or str(focused.get("kind")) in _OPAQUE_FOCUS_KINDS


def _looked_behind(view: dict) -> bool:
    """The view was read behind the person's window (``window.foreground`` is false): it has no keyboard focus."""

    window = view.get("window") if isinstance(view, dict) else None
    return isinstance(window, dict) and window.get("foreground") is False


def _sending_box_may_hold_text(view: dict) -> bool:
    """A text box of the view named like a message, reply, comment or send box (by its own Name or a fallback one,
    never a search or an address by its own Name) whose value is not shown, or shown with text. The view lists a
    value only when it holds one, so a box without one may be empty or may not expose it: both ask."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return False
    for control in controls:
        if not isinstance(control, dict) or str(control.get("kind")) not in _EDITABLE_KINDS:
            continue
        own = _own_name(control)
        if _SENDING_NAME.search(fold(control.get("name"))) is None or _SEARCH_NAME.search(_search_words(own)) \
                or _ADDRESS_NAME.search(own):
            continue
        value = control.get("value")
        if value is None or str(value).strip():
            return True
    return False


# A button that hands what was written to someone: a form with one of these may submit to a person on Enter
# (adversarial review of r9: «Submit», «Mandar», «Compartir», «Share», «Postear» were missing). Ronda 29: the pattern
# is data, beside the words RiskPolicy asks for (data/world_acts.v1.json «formSendButton»).
_SEND_BUTTON_NAME = form_send_button()
# A drawn send button read by the OCR: a short line (a button's caption) that says send.
_SEND_CAPTION_WORDS = 3


def _typed_field(view: dict, history: list[dict] | None) -> tuple[dict, str] | None:
    """The field of the view the last step's text went into, and how that is known: ``value`` (one field of the view
    shows exactly the typed text as its value, no other field shows it, and, when the view says what text appeared
    since the last look, the text is among it) or ``click`` (the step right before the text was a verified click on
    a field the view lists once under that same name, no other control but a static text carries that name, and the
    click's own receipt, when it says what it pressed, says a text field). None when the last step was not a verified
    text, or nothing proves where it went: the keyboard of a window read behind is its own focus, which the view
    cannot report."""

    steps = [step for step in (history or []) if isinstance(step, dict)]
    if not steps:
        return None
    typed = steps[-1]
    if typed.get("operation") != "input.text.type" or typed.get("ok") is not True:
        return None
    listed = view.get("controls") if isinstance(view, dict) else None
    controls = [control for control in (listed if isinstance(listed, list) else []) if isinstance(control, dict)]
    fields = [control for control in controls if str(control.get("kind")) in _EDITABLE_KINDS]
    text = fold(typed.get("text")).strip()
    # A value that only contains the text (an address «…/messages/t/ok» for «ok») says nothing of where it went.
    showing = [field for field in fields if text and field.get("value") is not None and text in fold(field.get("value"))]
    exact = [field for field in showing if fold(field.get("value")).strip() == text]
    appeared = view.get("newText") if isinstance(view, dict) else None
    new_on_screen = not isinstance(appeared, list) or any(text in fold(line) for line in appeared)
    if exact and new_on_screen:
        # Two fields showing it say nothing of which one has the keyboard.
        return (exact[0], "value") if len(showing) == 1 else None
    if len(steps) < 2:
        return None
    clicked = steps[-2]
    label = fold(clicked.get("label")).strip()
    if clicked.get("operation") != "input.visible.click" or clicked.get("ok") is not True or not label:
        return None
    pressed = clicked.get("kind")
    if isinstance(pressed, str) and pressed and pressed not in _EDITABLE_KINDS:
        return None
    # By name, not by index: the view renumbers its controls after a text (measured on the Character Map, where a
    # Button took the clicked field's index). A button or any other control named the same may be what was clicked.
    if any(
        fold(control.get("name")).strip() == label and str(control.get("kind")) not in _EDITABLE_KINDS | {"Text"}
        for control in controls
    ):
        return None
    named = [field for field in fields if fold(field.get("name")).strip() == label]
    return (named[0], "click") if len(named) == 1 else None


def _other_box_may_send(view: dict, field: dict) -> bool:
    """Another text box of the view may hold a text Enter hands to a person: one named like a message, reply,
    comment or send box (by its own Name or a fallback one, never a search or an address by its own Name) whose value
    is not shown or is shown with text; one with no name of its own that hides its content (measured: Discord's
    editor exposes no value); or, drawn without a tree, a short line of the screen naming a message box that no
    listed control carries (a placeholder such as «Escribe un mensaje»)."""

    listed = view.get("controls") if isinstance(view, dict) else None
    controls = [control for control in (listed if isinstance(listed, list) else []) if isinstance(control, dict)]
    for control in controls:
        if control is field or str(control.get("kind")) not in _EDITABLE_KINDS:
            continue
        if "password" in str(control.get("state") or ""):
            continue
        own = _own_name(control)
        if _SEARCH_NAME.search(_search_words(own)) or _ADDRESS_NAME.search(own):
            continue
        value = control.get("value")
        if value is not None and not str(value).strip():
            continue
        if _SENDING_NAME.search(fold(control.get("name"))) is not None:
            return True
        if value is None and (not own or _UNNAMED_FIELD.match(own) is not None):
            return True
    names = {fold(control.get("name")).strip() for control in controls} - {""}
    text = view.get("text") if isinstance(view, dict) else None
    for lines in (text.values() if isinstance(text, dict) else []):
        for line in (lines if isinstance(lines, list) else []):
            folded = fold(line).strip()
            if len(folded.split()) <= 5 and _COMPOSER_NAME.search(folded) is not None \
                    and not any(name in folded or folded in name for name in names):
                return True
    return False


def _view_may_send(view: dict) -> bool:
    """The view has something that sends what was written: a control other than a text field named send, submit,
    share, post or reply (a button, a link, a menu item, a drawn group or label), or a short OCR line saying so (a
    drawn button)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if any(
        isinstance(control, dict) and str(control.get("kind")) not in _EDITABLE_KINDS
        and _SEND_BUTTON_NAME.search(fold(control.get("name"))) is not None
        for control in (controls if isinstance(controls, list) else [])
    ):
        return True
    text = view.get("text") if isinstance(view, dict) else None
    return any(
        len(fold(line).split()) <= _SEND_CAPTION_WORDS and _SEND_BUTTON_NAME.search(fold(line)) is not None
        for lines in (text.values() if isinstance(text, dict) else [])
        for line in (lines if isinstance(lines, list) else [])
    )


def _typed_into_plain_field(view: dict, history: list[dict] | None) -> str | None:
    """How it is known (``value`` or ``click``, see ``_typed_field``) that the text just typed went into a field
    where Enter submits a search or moves on in a form and never hands anything to a person: a field named by its
    own Name (never a fallback name, never unnamed), not named like a message, reply, comment or send box unless that
    own Name says search or address, not a password, a rich text box only when it is a search box
    (``_search_document``: any other Document is the person's work or a mail body), in a view with nothing that
    sends (``_view_may_send``: a form that sends on Enter) and no other box that may hold a text for a person
    (``_other_box_may_send``: the keyboard may have stayed there). None otherwise."""

    found = _typed_field(view, history)
    if found is None:
        return None
    field, known = found
    if "password" in str(field.get("state") or ""):
        return None
    own = _own_name(field)
    if not own or _UNNAMED_FIELD.match(own) is not None:
        return None
    if _SENDING_NAME.search(own) is not None and not _SEARCH_NAME.search(_search_words(own)) \
            and not _ADDRESS_NAME.search(own):
        return None
    if str(field.get("kind")) == "Document" and not _search_document(view, field):
        return None
    if _view_may_send(view) or _other_box_may_send(view, field):
        return None
    return known


def _last_verified_typed(history: list[dict] | None) -> bool:
    """The last verified step of this sub-goal typed a text."""

    verified = [step for step in (history or []) if isinstance(step, dict) and step.get("ok") is True]
    return bool(verified) and verified[-1].get("operation") == "input.text.type"


def _focused_controls(view: dict) -> list[dict]:
    """What has the keyboard: window.focused, and the controls whose state says focused."""

    focused = _focused(view)
    found = [focused] if focused is not None else []
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        found += [
            control for control in controls
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        ]
    return found


def _keyboard_on_address_field(view: dict) -> bool:
    """The keyboard is on a text field named as an address (an Edit or a ComboBox called «dirección», «address»,
    «url»): Delete there erases characters of what was typed."""

    return any(
        str(control.get("kind")) in {"Edit", "ComboBox"} and "password" not in str(control.get("state") or "")
        and _ADDRESS_NAME.search(_own_name(control)) is not None
        for control in _focused_controls(view)
    )


def _focused_is_text_field(view: dict) -> bool:
    focused = _focused(view)
    if focused is not None and str(focused.get("kind")) in _EDITABLE_KINDS:
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    return isinstance(controls, list) and any(
        isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        and str(control.get("kind")) in _EDITABLE_KINDS
        for control in controls
    )


def key_arguments(key: str, view: dict, history: list[dict] | None = None, *, blind_asks: bool = False) -> dict[str, object]:
    """The arguments of a key press with the target RiskPolicy reads: Enter or space on a possible message composer
    is ``message_composer`` (it asks); Delete on a text field is ``text_field`` (it erases characters; anywhere else it
    deletes what is selected, and RiskPolicy asks). ``history`` is the sub-goal's steps (a text just typed where the
    focus cannot be read asks too)."""

    arguments: dict[str, object] = {"key": key}
    focused = _focused(view)
    unreadable = focused is None or str(focused.get("kind")) in {"Pane", "Custom"}
    if key in {"enter", "space"} and (_composer_with_text(view, history) or (blind_asks and unreadable)):
        # «apretá enter» said alone in a chain (its typing was another sub-goal) where the focus cannot be read: it
        # may send what was written, so it is asked first.
        arguments["target"] = "message_composer"
    elif key == "delete" and _focused_is_text_field(view):
        arguments["target"] = "text_field"
    return arguments


def _search_box(view: dict, control: dict | None) -> bool:
    """The window's own search box (by its own name, or a small search document)."""

    return control is not None and (_is_search_field(control) or _search_document(view, control))


def _writable(control: dict) -> bool:
    states = str(control.get("state") or "").split()
    return (
        control.get("kind") in _EDITABLE_KINDS and not {"password", "readonly", "disabled"} & set(states)
        and not (_COMPOSER_NAME.search(fold(control.get("name"))) and not _is_search_field(control))
    )


def _search_box_to_type(view: dict) -> dict | None:
    """The writable search box of the view that takes a typed search: the one with the keyboard, else the first in
    the view's reading order; None when the view shows none (the model's step: the box may be behind a button)."""

    boxes = [
        control for control in (view.get("controls") or []) if isinstance(control, dict)
        and control.get("kind") in _EDITABLE_KINDS and _search_box(view, control)
        and not {"password", "readonly", "disabled"} & set(str(control.get("state") or "").split())
        and str(control.get("name") or "").strip()
    ] if isinstance(view, dict) else []
    focused = {(fold(control.get("name")), control.get("kind")) for control in _focused_controls(view)}
    return next((box for box in boxes if (fold(box.get("name")), box.get("kind")) in focused), boxes[0] if boxes else None)


def _message_window(view: dict) -> bool:
    """A window that writes to people: a field or a written line named like a message, chat or conversation box
    («Escribe un mensaje», «Buscar o empezar un chat nuevo», «Type a message»)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if any(
        isinstance(control, dict) and str(control.get("kind")) in _EDITABLE_KINDS
        and _COMPOSER_NAME.search(fold(control.get("name")))
        for control in (controls if isinstance(controls, list) else [])
    ):
        return True
    text = view.get("text") if isinstance(view, dict) else None
    return isinstance(text, dict) and any(
        isinstance(line, str) and len(line.split()) <= 6 and _COMPOSER_NAME.search(fold(line))
        for lines in text.values() if isinstance(lines, list) for line in lines
    )


# A place to look a name up in, by what it is called in either language: a search or filter field, a quick switcher
# («¿A dónde quieres ir?»), a «go to» box. The address bar is not one: what it finds is the web, not the window.
# Ronda 24b: the pattern is data (operation_floor.v1.json «computerUse.searchField»), read by the App's typing receipt
# too (OperationFloor.SearchFieldName: «intoSearch»), so both tell a search box the same way.
_SEARCH_FIELD: dict = operation_floor.floor_data()["computerUse"]["searchField"]
_SEARCH_NAME = re.compile(_SEARCH_FIELD["name"])
# The filters as a thing («filtros», «filters»): a button so named opens them. The verb («Filtrar», «Filter») filters,
# like a search (review of fable/cu-v3-menus-teclas, finding 5).
_FILTER_WORD = re.compile(r"filtros?|filters")
# The kinds that are pressed, never typed into: a name of filters on one opens them, and a text aimed at one is the
# press it meant or nothing (``_pressed_instead``). Estabilización R22: the one binding; a wider list bound earlier in
# this module (2026-10-08, 50d4aed91) was overridden by this one an hour later (44d9a38c8) and never read by anyone.
_PRESSED_KINDS = frozenset({"Button", "SplitButton", "MenuItem", "ListItem"})
_ADDRESS_NAME = re.compile(_SEARCH_FIELD["address"])
_RECIPIENT = re.compile(_SEARCH_FIELD["recipient"])


def _search_words(name: str) -> str:
    """Revisión 2 de r24b (B1): the part of a folded field name whose search words make it a search. A name that is a
    message box once its recipients (#channel, @person) are read off («enviar mensaje a #busqueda-de-equipo», «message
    #job-search», «mensaje @buscador99») has its search words only in who it writes to: those do not count. Any other
    name is read whole: «buscar o empezar un chat nuevo» is a search though it says «chat»."""

    without = _RECIPIENT.sub(" ", name)
    return without if _COMPOSER_NAME.search(without) else name


_SMALL_FIELD_SHARE = 1 / 20

_SEARCH_KEYS = ("ctrl_k", "ctrl_f")


def _is_search_field(control: dict) -> bool:
    # Only a field's own Name makes it a search: a fallback name (help text in prose, an AutomationId) would let
    # Enter submit without asking in a box that may be a message box.
    name = _own_name(control)
    if _ADDRESS_NAME.search(name) or "password" in str(control.get("state") or ""):
        return False
    name = _search_words(name)
    found = _SEARCH_NAME.search(name)
    if found is not None and _FILTER_WORD.fullmatch(found.group(0)) and control.get("kind") in _PRESSED_KINDS:
        # A box that filters a list is a search; a button or a menu entry named for filters opens them (v3-52: OBS's
        # «Abrir filtros de la escena» was clicked as the window's search and opened «Filtros para 'Pruebas'»).
        return any(not _FILTER_WORD.fullmatch(other.group(0)) for other in _SEARCH_NAME.finditer(name))
    return found is not None


def _search_document(view: dict, control: dict) -> bool:
    """A rich text box (Document) that is a search field (P4, measured on v3-30: the Character Map's «Buscar:» is a
    Document): its whole own name is a search label (``is_search_label``: never a document titled «Búsqueda de
    empleo» or a web window's root «Spotify – Buscar»), and, when the view gives rectangles, it is a small one-line
    field and not the largest document of the view. Any other Document is the person's work."""

    if control.get("kind") != "Document" or "password" in str(control.get("state") or ""):
        return False
    if not is_search_label(_own_name(control)):
        return False
    rect = control.get("rect")
    if not isinstance(rect, dict) or _area(rect) <= 0:
        return True
    window = view.get("window") if isinstance(view, dict) else None
    window_area = _area(window.get("rect")) if isinstance(window, dict) else 0.0
    if float(rect.get("h") or 0) > _ONE_LINE_HEIGHT or (window_area > 0 and _area(rect) > window_area * _SMALL_FIELD_SHARE):
        return False
    controls = view.get("controls") if isinstance(view, dict) else None
    others = [
        _area(item.get("rect")) for item in (controls if isinstance(controls, list) else [])
        if isinstance(item, dict) and item.get("kind") == "Document" and item is not control
        and not (isinstance(control.get("i"), int) and item.get("i") == control.get("i"))
    ]
    larger = [area for area in others if area > 0]
    return not larger or max(larger) > _area(rect)


def _keyboard_on_a_search(view: dict) -> dict | None:
    """The search box that has the keyboard (window.focused, or a text field whose state says so): never a password."""

    focused = _focused(view)
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)] if isinstance(view, dict) else []
    candidates = [focused] if focused is not None else [
        control for control in controls if "focused" in str(control.get("state") or "").split()
    ]
    for control in candidates:
        if str(control.get("kind")) in _EDITABLE_KINDS and "password" not in str(control.get("state") or "") \
                and _search_field_box(view, control):
            return control
    return None


def _search_field_box(view: dict, control: dict) -> bool:
    """Revisión 1 de r24b (B3): the window's search box as the free-text rules read it. An Edit or a ComboBox by a
    search word in its own name (``_is_search_field``); a Document only by ``_search_document`` (its whole name a
    search label, one line, not the largest document): the person's document «Búsqueda de empleo» or «Ir a la playa»
    with the keyboard is where the text goes, never a search to step off."""

    kind = str(control.get("kind"))
    if kind == "Document":
        return _search_document(view, control)
    return kind in _FIELD_KINDS and _is_search_field(control)


def _example_text(control: dict | None, held: str) -> bool:
    """Ronda 20 P1 (v3-03: «Búsqueda de Microsoft» valor=«Buscar»): a value that is only the field's example text
    (its own name, or a bare search label in a search field) is no content of anyone's."""

    folded = fold(held).strip(" :.…")
    if not folded or not isinstance(control, dict):
        return False
    return folded == fold(control.get("name")).strip(" :.…") or (_is_search_field(control) and is_search_label(held))


def _focused_field(view: dict) -> dict | None:
    """The field that has the keyboard (window.focused, or a control whose state says so), when typing a name into it
    is a search: never a password, a message composer or the address bar."""

    focused = _focused(view)
    candidates = [focused] if focused is not None else []
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        # Ronda 20 P1 (v3-03): when window.focused names the control that has the keyboard, a control whose state
        # still says «focused» and is another one is a stale state (the front went back and the keyboard returned to
        # the canvas); it never counts as the field in focus.
        candidates += [
            control for control in controls
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
            and (focused is None or _same_control(control, focused))
        ]
    for control in candidates:
        # A rich text box named as a search is a search field too (P4, ``_search_document``); any other Document is
        # the person's work.
        searching_document = _search_document(view, control)
        if (control.get("kind") not in _FIELD_KINDS and not searching_document) or "password" in str(control.get("state") or ""):
            continue
        name = fold(control.get("name"))
        if _is_search_field(control):
            return control
        if _ADDRESS_NAME.search(name) or _COMPOSER_NAME.search(name):
            continue
        # A field without a search name has the keyboard only because the last key opened a search over the window
        # (new text appeared with it); otherwise it is the document or the form being worked on.
        if view.get("newText"):
            return control
    return None
