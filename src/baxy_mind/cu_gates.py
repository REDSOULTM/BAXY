"""Gate screens (semantic.app_gates): a window that asks for what only the person can give instead of its
working view, said with its cause, or passed by its offer to go on without giving anything.
"""

from __future__ import annotations

from .semantic.app_gates import (
    asks_about_the_gate,
    gate_kind,
    is_a_navigation_line,
    is_an_address,
    names_a_gate_skip,
    names_an_account_field,
)
from .semantic.missions import fold
from .cu_view import _view_lines, find_control, label_names
from .cu_goals import _goal_target
from .cu_fields import _message_window
from .cu_acts import _click
from .cu_window import _system_menu
from .cu_history import _may_have_acted


APP_GATE = "app_gate"
REASON_APP_GATE = "la aplicación muestra una pantalla que pide algo que sólo la persona puede dar o esperar"
REASON_GATE_SKIP = "la pantalla de puerta ofrece seguir sin dar nada"
# A gate is the whole screen: a few controls and lines (Outlook's wizard read 0 controls and 5 lines). A working
# window that merely offers to sign in (a document's title bar, a store's link) holds far more.
_GATE_MAX_CONTROLS = 12
_GATE_MAX_LINES = 15
_GATE_CONTENT_KINDS = frozenset({"Document"})
# A window with places to go (tabs, menus, a list or a tree of entries) is a working window, never a gate: Steam's
# downloads list a game «Actualizando», the Clock lists «Iniciar sesión de concentración» among its pages.
_NAVIGATION_KINDS = frozenset({"TabItem", "MenuItem", "MenuBar", "TreeItem", "ListItem", "DataItem"})

# The controls whose name may say the gate (its message or its button).
_GATE_SAYING_KINDS = frozenset({"Text", "Button", "Hyperlink"})
# Besides the gate's phrase, its buttons, its fields and the application's name, a gate writes little: a line or two
# of explanation. More is a working window where the phrase is one line among its content.
_GATE_MAX_OTHER_LINES = 4


def app_gate(view: dict) -> dict[str, str] | None:
    """{kind, text} when the window is a gate screen (semantic.app_gates): few controls and lines, no document or
    conversation of the person's, no navigation (tabs, menus, list or tree entries, a bar of places in capitals), and
    its title says an account, a sign-in, an update or a resource not found, or a line or a message or button control
    says it and dominates the screen (at most a few other lines); or a sign-in form (a field named as an address or a
    password beside an address written). ``text`` is what the screen writes, to be quoted: the title first, never an
    address. None otherwise."""

    if not isinstance(view, dict):
        return None
    controls = [control for control in view.get("controls") or [] if isinstance(control, dict)]
    lines = [line.strip() for line in _view_lines(view) if line.strip()]
    if len(controls) > _GATE_MAX_CONTROLS or len(lines) > _GATE_MAX_LINES:
        return None
    if any(str(control.get("kind")) in _GATE_CONTENT_KINDS for control in controls) or _message_window(view):
        return None
    if any(str(control.get("kind")) in _NAVIGATION_KINDS and not _system_menu(view, control) for control in controls):
        return None
    if sum(1 for line in lines if is_a_navigation_line(line)) >= 2:
        return None
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    title = str(window.get("title") or "").strip()
    if title and not is_an_address(title) and (kind := gate_kind(title)) is not None:
        return {"kind": kind, "text": title[:120]}
    names = [str(control.get("name") or "").strip() for control in controls
             if str(control.get("kind")) in _GATE_SAYING_KINDS]
    buttons = {fold(control.get("name")) for control in controls if str(control.get("kind")) in {"Button", "Hyperlink"}}
    folded_title = fold(title)

    def other(line: str) -> bool:
        folded = fold(line)
        return not (
            (folded and folded in folded_title) or folded in buttons or gate_kind(line) is not None
            or names_an_account_field(line) or is_an_address(line)
        )

    if sum(1 for line in _unwrapped_lines(view) if other(line)) > _GATE_MAX_OTHER_LINES:
        return None
    for text in (*lines, *names):
        kind = gate_kind(text) if text and not is_an_address(text) else None
        if kind is not None:
            return {"kind": kind, "text": text[:120]}
    if any(is_an_address(text) for text in (*lines, *(str(control.get("value") or "") for control in controls))):
        fields = (*lines, *(str(control.get("name") or "").strip() for control in controls))
        field = next((text for text in fields if names_an_account_field(text)), None)
        if field is not None:
            return {"kind": "account", "text": field}
    return None


# A line that ends a sentence, and how full a line is when the reading wrapped it (``_unwrapped_lines``; counted in
# characters, so a proportional font's widest line need not be the longest).
_SENTENCE_ENDS = (".", "!", "?", ":", "…")
_WRAP_FILL = 0.9


def _unwrapped_lines(view: dict) -> list[str]:
    """The view's written lines with a sentence the reading wrapped joined back (live v3-34: «Haz una copia de
    seguridad de tus» / «notas y sincroniza en todos los» / «dispositivos. Solo tienes que iniciar» / «sesión.» is one
    line of a gate, never four lines of content). A run of lines in one zone is one wrapped sentence only when each
    line after the first begins in lower case, the line above it ends no sentence and is as wide as the zone's widest
    (the next line's first word would not have fit on it), and the run's last line ends the sentence. A zone that
    writes entries in lower case («comprar pan» / «pagar la luz»: a line in lower case that continues nothing) has
    no wrapped sentence (review of r9, finding 1)."""

    text = view.get("text") if isinstance(view, dict) else None
    if not isinstance(text, dict):
        return []
    joined: list[str] = []
    for zone_lines in text.values():
        if not isinstance(zone_lines, list):
            continue
        lines = [line for line in (str(raw).strip() for raw in zone_lines) if line]
        width = max((len(line) for line in lines), default=0)

        def wraps(above: str, below: str, width: int = width) -> bool:
            return (
                below[0].islower() and not above.endswith(_SENTENCE_ENDS)
                and len(above) + 1 + len(below.split()[0]) > width * _WRAP_FILL
            )

        if any(line[0].islower() and (n == 0 or not wraps(lines[n - 1], line)) for n, line in enumerate(lines)):
            # A line in lower case that continues nothing: this zone writes its entries in lower case, and one
            # of them right under a full line («… tus notas» / «comprar pan.») is an entry too.
            joined.extend(lines)
            continue
        position = 0
        while position < len(lines):
            end = position
            while end + 1 < len(lines) and wraps(lines[end], lines[end + 1]):
                end += 1
            if end > position and lines[end].endswith(_SENTENCE_ENDS):
                joined.append(" ".join(lines[position:end + 1]))
                position = end + 1
            else:
                joined.append(lines[position])
                position += 1
    return joined


def _goal_on_screen(goal: str, view: dict) -> bool:
    """The goal names a control or a line of this screen (the gate's own «Opciones avanzadas»): its step is the
    goal's, not the gate's. Never the window's title or the application's name written on it, nor the gate's own
    phrase («ir a notas» over «Notas» asking «Inicia sesión para sincronizar tus notas» is not on the gate)."""

    parsed = _goal_target(goal)
    if parsed is None or not parsed[2]:
        return False
    target = parsed[2]
    window = view.get("window") if isinstance(view.get("window"), dict) else {}
    title = fold(window.get("title"))

    def of_the_gate(text: object) -> bool:
        folded = fold(text)
        return bool(folded) and folded not in title and gate_kind(text) is None and label_names(target, str(text))

    control = find_control(view, target)
    return (control is not None and of_the_gate(control.get("name"))) or any(
        of_the_gate(line) for line in _view_lines(view)
    )


def _goal_pressed(goal: str, history: list[dict]) -> bool:
    """This goal already pressed the control it names («hacer clic en Opciones avanzadas» on the account wizard): the
    gate it pressed on is the goal's, also once that control is gone from the view."""

    parsed = _goal_target(goal or "")
    target = parsed[2] if parsed is not None else ""
    return bool(target) and any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("ok") is not False
        and label_names(target, str(step.get("label") or ""))
        for step in history
    )


def _gate_holds(view: dict, history: list[dict], objective: str | None, goal: str | None) -> dict[str, str] | None:
    """The gate that stops this goal, one rule for the step and for a success over it: None when the request or the
    goal is about the gate itself (sign in, the account, an update), when the goal names a control or a line of the
    gate, or when this goal already pressed the control it names there."""

    if asks_about_the_gate(objective or "") or asks_about_the_gate(goal or ""):
        return None
    gate = app_gate(view)
    if gate is None or _goal_on_screen(goal or "", view) or _goal_pressed(goal or "", history):
        return None
    return gate


def _gate_stop(gate: dict[str, str], history: list[dict]) -> dict[str, object]:
    """The «none» a gate ends in: its text as the evidence the shell checks on the view, its kind, and the control
    pressed on it to pass it without giving anything, when one was («Ahora no»), for the final not to say nothing was."""

    arguments: dict[str, object] = {"evidence": gate["text"], "gate": gate["kind"]}
    pressed = next(
        (str(step.get("label") or "").strip() for step in reversed(history)
         if isinstance(step, dict) and step.get("operation") == "input.visible.click" and step.get("ok") is not False
         and names_a_gate_skip(step.get("label"))),
        "",
    )
    if pressed:
        arguments["pressed"] = pressed[:60]
    return {"operation": "none", "arguments": arguments, "reason": REASON_APP_GATE, "code": APP_GATE}


def _gate_step(view: dict, history: list[dict], objective: str, goal: str) -> dict[str, object] | None:
    """On a gate screen that stops this goal (``_gate_holds``): its control to pass without giving anything («Ahora
    no», «Skip»), pressed once; else no step, with the gate's own text as the evidence the shell checks on the view.
    Credentials are never typed."""

    gate = _gate_holds(view, history, objective, goal)
    if gate is None:
        return None
    pressed = {fold(step.get("label")) for step in history if step.get("operation") == "input.visible.click"}
    skip = next(
        (control for control in view.get("controls") or []
         if isinstance(control, dict) and str(control.get("kind")) in {"Button", "Hyperlink"}
         and names_a_gate_skip(control.get("name")) and fold(control.get("name")) not in pressed),
        None,
    )
    if skip is not None and not any(names_a_gate_skip(label) for label in pressed):
        return _click(skip, REASON_GATE_SKIP)
    return _gate_stop(gate, history)


# The controls whose name says a dialog read as the window (its title is often empty): its own element first.
_DIALOG_NAMING_KINDS = ("Window", "Text")


def inherited_dialog(view: dict, history: list[dict], goal: str, subgoal: int) -> dict[str, object] | None:
    """Encargo EX (tanda n6 t4-c06: Excel held «Guardar este archivo» left by an earlier turn, and the mission ended «no
    vi en la pantalla un control con el que seguir»): on the mission's first sub-goal, before any act of it, the
    application's window was read through a modal dialog (the provider's ``window.modal``). The mission did not open
    it, so nothing is pressed on it: the stop says it as a gate of kind «dialog», named by its title or else by its own
    element's or first text's name. Never when the goal names a control or a line of it (its step is the goal's)."""

    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    if subgoal > 0 or window.get("modal") is not True or any(_may_have_acted(step) for step in history):
        return None
    if _goal_on_screen(goal or "", view):
        return None
    controls = [control for control in view.get("controls") or () if isinstance(control, dict)]
    named = [str(window.get("title") or "").strip()] + [
        str(control.get("name") or "").strip()
        for kind in _DIALOG_NAMING_KINDS for control in controls if str(control.get("kind")) == kind
    ]
    text = next((name for name in named if name), "")
    return _gate_stop({"kind": "dialog", "text": text[:120]}, history) if text else None
