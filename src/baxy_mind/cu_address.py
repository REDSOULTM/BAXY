"""Going to a place by its address: a folder's path typed in the address bar with its Enter, and a place of
the application whose data declare its address (semantic.app_places), opened on it.
"""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

from . import effect_intent
from .semantic.missions import fold
from .semantic import app_places
from .semantic.windows import asks_for_the_front
from .cu_view import _focused
from .cu_fields import (
    _ADDRESS_NAME, _EDITABLE_KINDS, _UNNAMED_FIELD, _is_search_field, _other_box_may_send, _own_name, _typed_field,
    _view_may_send, key_arguments,
)
from .cu_acts import _click, _key, typed_text
from .cu_window import _WEB_ADDRESS, _window_fold, reopens_unraised
from .cu_history import _steps_ok


# A file system path («c:\windows\system32», «Documentos\baxy-prueba-v3»): an address to type, never a name to press.
_PATH_NAME = re.compile(r"^[A-Za-z]:[\\/]|\\")


_REASON_ADDRESS = "una ruta de carpeta va a la barra de dirección, no al buscador"
_REASON_ADDRESS_ENTER = "escribí la ruta en la barra de dirección: Enter va a la carpeta"
# The share of the window's width an unnamed text field at its top must span to be its address field (measured on a
# file manager's address box: 1337 of 1424 px; a search box at the top spans a fraction).
_ADDRESS_WIDTH = 0.6
# A local drive's letter: a share on another machine (\\servidor\…) is never looked up nor typed.
_LOCAL_DRIVE = re.compile(r"^[A-Za-z]:$")

# What the keyboard may be on when the address bar's key would edit the person's work instead (a line cut, a paragraph
# aligned, a table made): a text field, a document, a grid or its cell.
_EDITING_KINDS = _EDITABLE_KINDS | {"DataGrid", "DataItem", "Table"}


def _address_path(target: str) -> str | None:
    """The folder path a goal goes to (``_PATH_NAME``), rooted when it starts at a known folder of the person
    («documentos\\baxy-prueba-v3» → where this PC keeps it), as an address field takes it. Only a folder that exists on
    a local drive of this PC: Enter in an address field opens a file and runs a program (adversarial review: «ir a
    …\\setup.exe» would launch it without asking), a share on another machine is a network access nobody asked for,
    and a relative path that no known folder roots is a search in a browser. None for any other target."""

    from .known_folders import rooted

    text = typed_text(target).strip().strip("«»\"'").strip()
    if not text or _PATH_NAME.search(text) is None:
        return None
    path = rooted(text)
    local = PureWindowsPath(path)
    if not local.is_absolute() or _LOCAL_DRIVE.match(local.drive) is None:
        return None
    return path if Path(path).is_dir() else None


def _shows_location(value: object, view: dict) -> bool:
    """The field's value is where the window is: a path, a web address, or the place the window's title starts with
    (a file manager titled «Este equipo - Explorador de archivos» shows «Este equipo»). A form's address field holds
    what the person wrote there, never that."""

    text = str(value or "").strip()
    if not text:
        return False
    if _PATH_NAME.search(text) or _WEB_ADDRESS.match(text.casefold()):
        return True
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    title = _window_fold(window.get("title"))
    place = re.split(r"\s+[-\u2013\u2014|]\s+", title)[0].strip()
    return fold(text) in {title, place} - {""}


def _address_field(view: dict) -> dict | None:
    """The window's address field, at the top of a window with nothing that sends what was written (a form's
    «Dirección de correo» or a checkout's «Dirección» with its «Enviar» would take the path and submit it on Enter,
    adversarial review): a writable text field named as an address by its own Name that shows where the window is
    (``_shows_location``), or an unnamed one spanning most of the window's width (a file manager's address box). Never
    a search field, a password or a read-only field (a browser's displayed address in a web app). The one with the
    keyboard first."""

    window = (view.get("window") or {}) if isinstance(view.get("window"), dict) else {}
    width = float(((window.get("rect") or {}) if isinstance(window.get("rect"), dict) else {}).get("w") or 0)
    if _view_may_send(view):
        return None
    found: list[dict] = []
    for control in view.get("controls") or []:
        if not isinstance(control, dict) or control.get("kind") not in {"Edit", "ComboBox"} or not isinstance(control.get("i"), int):
            continue
        states = str(control.get("state") or "")
        if {"readonly", "disabled"} & set(states.split()) or "password" in states or _is_search_field(control):
            continue
        if not str(control.get("zone") or "").startswith("T"):
            continue
        rect = control.get("rect") if isinstance(control.get("rect"), dict) else {}
        named = _ADDRESS_NAME.search(_own_name(control)) is not None and _shows_location(control.get("value"), view)
        unnamed_wide = (
            not control.get("nameSource") and _UNNAMED_FIELD.match(fold(control.get("name"))) is not None
            and width > 0 and float(rect.get("w") or 0) >= width * _ADDRESS_WIDTH
        )
        if named or unnamed_wide:
            found.append(control)
    found.sort(key=lambda control: "focused" not in str(control.get("state") or "").split())
    return found[0] if found else None


def _address_enter(field: dict | None, view: dict, history: list[dict]) -> dict[str, object]:
    """The Enter after the path, with the target RiskPolicy reads (``key_arguments``). Where the focus cannot be read
    (v3-48: a window read behind reports none) it would ask as if the text sat in a message box; it does not when the
    path is proven in the address field (``_typed_field``: its value shows it, or the step before was the click on it)
    and no other box of the view may hold a text for a person."""

    arguments = key_arguments("enter", view, history)
    if "target" not in arguments or field is None:
        return arguments
    found = _typed_field(view, history)
    if found is not None and found[0] is field and not _other_box_may_send(view, field):
        return {"key": "enter"}
    return arguments


def _keyboard_on_work(view: dict) -> bool:
    """The keyboard is on the person's work, or the window shows a document: an application's own key would edit it."""

    focused = _focused(view)
    if focused is not None and str(focused.get("kind")) in _EDITING_KINDS:
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and (
            str(control.get("kind")) == "Document"
            or ("focused" in str(control.get("state") or "").split() and str(control.get("kind")) in _EDITING_KINDS)
        )
        for control in (controls if isinstance(controls, list) else [])
    )


def _address_step(target: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Going to a folder's path (cu-v3-scroll-pegar-direccion; t-scroll-4 typed «c:\\windows\\system32» into the
    search box, v3-48 pressed three search keys in a window without one): the address field is clicked, the path
    replaces what it holds, and Enter goes there. A window whose view lists no address field, where the keyboard is
    not on the person's work, gets the address bar's own key (ctrl_l) once, and the path is typed where it put the
    keyboard only when that is an address field showing where the window is. None for a target that is no folder, once
    the path was typed and sent, when the click on the field failed, or when nothing takes it: the model decides."""

    path = _address_path(target)
    if path is None:
        return None
    typed = [step for step in history if step.get("operation") == "input.text.type" and fold(step.get("text")) == fold(path)]
    last = history[-1] if history else None
    field = _address_field(view)
    if typed:
        if last is typed[-1] and last.get("ok") is True:
            return {"operation": "input.key.press", "arguments": _address_enter(field, view, history), "reason": _REASON_ADDRESS_ENTER}
        return None
    if field is not None:
        focused = "focused" in str(field.get("state") or "").split()
        label = str(field.get("name") or "")
        if not focused and not _steps_ok(history, "input.visible.click", label=label):
            clicked = [step for step in history if step.get("operation") == "input.visible.click" and fold(step.get("label")) == fold(label)]
            # A click on the field that failed is not tried again on every step.
            return None if clicked else _click(field, _REASON_ADDRESS)
        return {"operation": "input.text.type", "arguments": {"text": path, "index": field["i"], "replace": True}, "reason": _REASON_ADDRESS}
    keyed = [step for step in history if step.get("operation") == "input.key.press" and step.get("key") == "ctrl_l"]
    if not keyed:
        return None if _keyboard_on_work(view) else _key("ctrl_l")
    focused = _focused(view)
    controls = view.get("controls") if isinstance(view.get("controls"), list) else []
    # A listed field with the keyboard that is no address field (``_address_field`` took none) is the person's.
    listed = any(
        isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        and str(control.get("kind")) in _EDITABLE_KINDS
        for control in controls
    )
    if (
        not listed and last is keyed[-1] and last.get("ok") is True and focused is not None
        and focused.get("kind") in {"Edit", "ComboBox"}
        and not _is_search_field(focused) and "password" not in str(focused.get("state") or "")
        and "readonly" not in str(focused.get("state") or "").split()
        and _ADDRESS_NAME.search(_own_name(focused)) is not None and _shows_location(focused.get("value"), view)
        and not _view_may_send(view)
    ):
        # The key put the keyboard on an address field the view does not list among its controls (its own Name says
        # address and it shows where the window is): the path replaces its selected text there. Any other field the
        # keyboard is on is the person's (a note, a form): nothing is typed there.
        return {"operation": "input.text.type", "arguments": {"text": path}, "reason": _REASON_ADDRESS}
    return None


def _view_names(view: dict, target: str) -> bool:
    """Some control of the view, or the window's title, names the target as whole words."""

    pattern = re.compile(rf"(?<!\w){re.escape(fold(target).strip())}(?!\w)")
    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    names = [window.get("title"), *(control.get("name") for control in (view.get("controls") or ()) if isinstance(control, dict))]
    return any(pattern.search(fold(name)) for name in names if isinstance(name, str))


def _place_by_address(
    objective: str,
    goal: str,
    application: str | None,
    view: dict,
    history: list[dict],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    game_catalog: Iterable[tuple[str, str, str]] | Any,
) -> dict[str, object] | None:
    """Estabilización, encargo C (banco r30 x10: the OCR click on Steam's store tab changed nothing; g1: Steam would not
    take text in its search box): a sub-goal that goes to a place of the application, or searches in it, whose data
    declare that place's address (semantic.app_places, data app_places.v1.json) opens the application on it, once per
    sub-goal and before any click: app.open with the place, its address composed by the kernel. The shell's check then
    reads the window for the arrival; when it does not hold, the sub-goal goes on as before (the opening is in the
    history, never repeated). A window that runs as administrator is opened again first (``reopens_unraised``); the
    front is asked for as the plain opening asks it (``asks_for_the_front``)."""

    if not application or reopens_unraised(view):
        return None
    if any(isinstance(step, dict) and step.get("operation") == "app.open" and step.get("place") for step in history):
        return None
    place = app_places.place_of(application, goal, game_catalog, said=objective)
    if place is None:
        # Encargo IMP2 (banco fix1 c6): a chat the window does not show is gone to from where the application lists its
        # chats (data «chats»), opened by its address; the chat itself is then the window's to find.
        chats = app_places.chats_place(application, goal)
        if chats is None or _view_names(view, chats[1]):
            return None
        place = {"place": chats[0]}
    app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
    if app_id is None:
        return None
    arguments: dict[str, object] = {"appId": app_id, **place}
    if asks_for_the_front(objective):
        arguments["foreground"] = True
    return {
        "operation": "app.open",
        "arguments": arguments,
        "reason": "el lugar pedido tiene dirección propia en los datos de la aplicación",
    }
