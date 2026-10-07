"""Motor de computer use, lado mente (documentacion/computer-use/CONTRATO_VISTA_ACCION.md).

Tres responsabilidades, ninguna sabe de una aplicación concreta:

1. **Leer el pedido** (`mission_request`): «en <app> <hacé X>», «abre <app> y
   <hacé X>», «<hacé X> en <app>», «andá a la pestaña
   de X» → una misión ``mission.computer.use`` con
   aplicación, objetivo y la comprobación de éxito determinista (§4.3). La
   aplicación tiene que estar en el catálogo de Inicio, o ser la categoría
   «navegador» (el navegador predeterminado de la persona) cuando sólo se nombra
   una pestaña; el resto de la frase es el objetivo, con el verbo en cualquier
   persona (tú, vos, usted, infinitivo, inglés).
2. **Elegir un paso** (`decide_step`): primero lo que el objetivo dicta sin
   modelo, incluida la búsqueda de un destino que no está en pantalla (campo de
   búsqueda, botón de navegación o menú, ctrl_k / ctrl_f, desplazar la lista:
   `_find_step`); si no queda
   nada, la vista compacta se serializa en pocas
   líneas, el modelo contesta UN acto con esquema JSON estricto a temperatura
   0, y unas comprobaciones sin modelo deciden si ese acto es legítimo: la
   etiqueta existe en la vista, la evidencia de «done» está en pantalla, no se
   escribe en una contraseña, no se repite el paso que acaba de fallar, no se
   pulsa un control que cubre la ventana ni se repite por tercera vez un paso
   que no hizo aparecer nada. En una misión encadenada cada paso es del
   sub-objetivo en curso.
3. **Proyectar lo observado** para el compositor (`project_seen`,
   `mission_defect`): qué se hizo, con qué evidencia, y los vetos —«entré al
   canal» sin ``seen.joined``, pasado falso, misión no lograda narrada como
   logro—.
"""

from __future__ import annotations

import json
import re
import unicodedata
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from . import effect_intent, operation_floor
from .semantic.account_acts import account_act, goal_asks_for
from .semantic.colours import changes_the_tool, colour_shades, is_basic_colour, screen_language, shade_of
from .semantic.missions import (
    BROWSER_CATEGORY,
    KEYS,
    QUESTION_MARK,
    _key_from_words,
    fold,
    gender_twin,
    label_alternatives,
    mode_named as _mode_named,
    names_a_blank_item,
    names_a_file,
    names_a_file_column,
    names_a_templates_list,
    names_own_files_list,
)

OPERATION = "mission.computer.use"
STEP_REQUEST = "computer.use.step"
STEP_RESULT = "computer.use.step.result"

# El repertorio cerrado del bucle (contrato §2).
ACTS = ("click", "type", "key", "scroll", "open", "done", "none")

# ------------------------------------------------------------- elegir un paso

STEP_PROMPT = (
    "Sos el motor de computer use de BAXY. Ves la ventana de delante como texto: una "
    "lista de controles (índice · tipo · nombre · estado · zona · color) y el texto leído "
    "por zonas. Devolvés EXACTAMENTE UN acto en JSON compacto: "
    '{"act":"click","i":N} (N = índice del control), {"act":"click","text":"…"} (un texto escrito en '
    'pantalla que no es control), {"act":"type","text":"…"}, {"act":"key","key":"…"}, '
    '{"act":"scroll","direction":"down|up"}, {"act":"open","application":"…"}, '
    '{"act":"done","evidence":"…"} (texto de la vista que prueba el objetivo) o {"act":"none"}. '
    "Reglas: sólo controles o textos que están en la vista; si el objetivo ya se ve cumplido, done con "
    "la evidencia literal; si el último paso falló, otro control u otro acto; para escribir hace falta "
    "un campo enfocado; nunca en una contraseña; números, expresiones o textos con type completo y "
    "después key enter si hace falta. Si el destino no está en la vista: un campo de búsqueda (click), "
    "o key ctrl_k / ctrl_f, escribí el nombre y elegí el resultado; si no, scroll. Si un clic abrió un "
    "menú, elegí la opción que lleva al destino. done sólo cuando ves la página o sección pedida: citá "
    "algo de ella, no sólo su nombre. El objetivo puede estar dicho en otro idioma que el de la ventana: "
    "elegí el control por su significado, no por sus letras. Un clic en un elemento de una lista de "
    "contenido sólo lo elige: para entrar en él, key enter; nunca en un instalador, un programa de una lista de "
    "programas ni un archivo que se ejecuta."
)


def _gbnf_quoted(value: str) -> str:
    """A GBNF literal that matches the JSON text ``"value"``."""

    return '"\\"' + value + '\\""'


def _gbnf_string(name: str, limit: int) -> str:
    """A JSON string of at most ``limit`` plain characters (no control characters, simple escapes)."""

    return (
        f'{name} ::= "\\"" {name}-char{{0,{limit}}} "\\""\n'
        f'{name}-char ::= [^"\\\\\\x00-\\x1F] | "\\\\" ["\\\\/bfnrt]'
    )


# The act first and only the fields it needs (measured: the nine-field reply cost ≈148 tokens, ≈3.2 s of the
# ≈4 s model step). Compact JSON, no whitespace: every character is a model pass.
STEP_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("act") + ' ":" (click | type | key | scroll | open | done | none) "}"',
    "click ::= " + _gbnf_quoted("click") + ' "," (' + _gbnf_quoted("i") + ' ":" index | '
    + _gbnf_quoted("text") + ' ":" short)',
    "type ::= " + _gbnf_quoted("type") + ' "," ' + _gbnf_quoted("text") + ' ":" long',
    "key ::= " + _gbnf_quoted("key") + ' "," ' + _gbnf_quoted("key") + ' ":" ('
    + " | ".join(_gbnf_quoted(key) for key in KEYS) + ")",
    "scroll ::= " + _gbnf_quoted("scroll") + ' "," ' + _gbnf_quoted("direction") + ' ":" ('
    + _gbnf_quoted("down") + " | " + _gbnf_quoted("up") + ")",
    "open ::= " + _gbnf_quoted("open") + ' "," ' + _gbnf_quoted("application") + ' ":" short',
    "done ::= " + _gbnf_quoted("done") + ' "," ' + _gbnf_quoted("evidence") + ' ":" short',
    "none ::= " + _gbnf_quoted("none"),
    "index ::= [0-9] | [1-5] [0-9]",
    _gbnf_string("short", 80),
    _gbnf_string("long", 400),
])


_SHOWN_CONTROLS = 30


def _ranked_controls(controls: list, goal: str | None, limit: int) -> list:
    """The controls the model is shown when there are more than ``limit``: the ones whose names share words with the
    goal, then the focused, selected and search-like ones, then the rest in screen order (measured: a Discord view of
    250 controls cut at the first 60 hid the server that held the target). The view's own order is kept."""

    if len(controls) <= limit:
        return controls
    wanted = {word for word in fold(goal or "").split() if len(word) >= 3}

    def weight(position: int, control: object) -> tuple[int, int]:
        if not isinstance(control, dict):
            return (9, position)
        name = fold(control.get("name"))
        state = str(control.get("state") or "")
        if wanted and any(word in name for word in wanted):
            return (0, position)
        if "focused" in state or "selected" in state or _SEARCH_NAME.search(name):
            return (1, position)
        return (2, position)

    chosen = sorted(range(len(controls)), key=lambda position: weight(position, controls[position]))[:limit]
    return [controls[position] for position in sorted(chosen)]


def compact_view_text(view: dict, limit_controls: int = _SHOWN_CONTROLS, limit_lines: int = 40, goal: str | None = None) -> str:
    """The view as the model reads it: one short line per control (the ones that matter for the goal when there are
    many, with how many were left out), then the text by zone."""

    lines: list[str] = []
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict):
        title = str(window.get("title") or "")[:80]
        process = str(window.get("process") or "")[:40]
        lines.append(f"ventana: «{title}» ({process})")
        focused = window.get("focused")
        if isinstance(focused, dict) and focused.get("name"):
            value = focused.get("value")
            lines.append(
                f"foco: {focused.get('kind')} «{str(focused.get('name'))[:60]}»"
                + (f" valor=«{str(value)[:40]}»" if value else "")
            )
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        shown = _ranked_controls(controls, goal, limit_controls)
        lines.append("controles:" if len(shown) == len(controls) else f"controles ({len(shown)} de {len(controls)}):")
        for control in shown:
            if not isinstance(control, dict):
                continue
            bits = [str(control.get("i")), str(control.get("kind") or ""), "«" + str(control.get("name") or "")[:60] + "»"]
            state = str(control.get("state") or "")
            if state:
                bits.append(state)
            value = control.get("value")
            if value:
                bits.append("valor=«" + str(value)[:40] + "»")
            zone = control.get("zone")
            if zone:
                bits.append(str(zone))
            color = control.get("color")
            if color and color not in {"gray", "white", "black"}:
                bits.append(str(color))
            repeated = control.get("repeated")
            if isinstance(repeated, int) and repeated > 0:
                bits.append(f"x{repeated + 1}")
            lines.append(" · ".join(bits))
    appeared = view.get("newText") if isinstance(view, dict) else None
    if isinstance(appeared, list) and appeared:
        lines.append("apareció tras el último paso: " + " · ".join("«" + str(line)[:60] + "»" for line in appeared[:12]))
    text = view.get("text") if isinstance(view, dict) else None
    if isinstance(text, dict):
        count = 0
        for zone in ("TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"):
            zone_lines = text.get(zone)
            if not isinstance(zone_lines, list) or not zone_lines:
                continue
            kept = []
            for line in zone_lines:
                if count >= limit_lines:
                    break
                kept.append(str(line)[:80])
                count += 1
            if kept:
                lines.append(f"texto {zone}: " + " | ".join(kept))
    return "\n".join(lines)


def _view_strings(view: dict) -> list[str]:
    found: list[str] = []
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict):
        found.append(str(window.get("title") or ""))
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict):
                found.append(str(control.get("name") or ""))
                if control.get("value"):
                    found.append(str(control.get("value")))
    text = view.get("text") if isinstance(view, dict) else None
    if isinstance(text, dict):
        for zone_lines in text.values():
            if isinstance(zone_lines, list):
                found.extend(str(line) for line in zone_lines)
    return found


def view_contains(view: dict, needle: str) -> bool:
    folded = fold(needle)
    if not folded:
        return False
    joined = " ".join(fold(item) for item in _view_strings(view))
    return folded in joined


def _edit_distance(left: str, right: str, cap: int) -> int:
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + (left_char != right_char)))
        if min(current) > cap:
            return cap + 1
        previous = current
    return previous[-1]


def label_names(label: str, name: str) -> bool:
    """Requested label against a seen name: folded equality, containment, or a typo per five letters."""

    needle, haystack = fold(label), fold(name)
    if not needle or not haystack:
        return False
    if needle == haystack or needle in haystack:
        return True
    allowed = len(needle) // 5
    return allowed > 0 and _edit_distance(needle, haystack, allowed) <= allowed


_DESCRIPTIVE_KINDS = frozenset({"Text", "Group", "Pane", "Custom", "Document"})


def _short_name(name: str, label: str) -> bool:
    """A control's name short enough to be what it names: at most six words beyond the label's own."""

    return len(fold(name).split()) <= len(fold(label).split()) + 6


def find_control(view: dict, label: str, index: int | None = None, kind: str | None = None) -> dict | None:
    """The one control the label (and index, when given; of that kind, when given) names; None when absent or
    ambiguous."""

    listed = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(listed, list):
        return None
    if isinstance(index, int) and 0 <= index < len(listed):
        candidate = listed[index]
        if (
            isinstance(candidate, dict)
            and (kind is None or candidate.get("kind") == kind)
            and label_names(label, str(candidate.get("name") or ""))
        ):
            return candidate
    controls = [control for control in listed if isinstance(control, dict) and (kind is None or control.get("kind") == kind)]
    exact = [control for control in controls if fold(control.get("name")) == fold(label)]
    if len(exact) == 1:
        return exact[0]
    # A sentence that merely mentions the name is no place (measured on Settings: «Usa un servidor proxy para conexiones
    # Ethernet o Wi-Fi…» was clicked for «Wi-Fi» on a PC without one): containment counts in short names only.
    loose = [
        control for control in controls
        if label_names(label, str(control.get("name") or ""))
        and (str(control.get("kind")) not in _DESCRIPTIVE_KINDS or _short_name(str(control.get("name") or ""), label))
    ]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        # «Biblioteca» as a navigation item and as a heading: the actionable one wins when unique.
        actionable = [control for control in loose if str(control.get("kind")) in effect_intent_actionable_kinds()]
        if len(actionable) == 1:
            return actionable[0]
    return None


_KIND_WORDS: dict[str, str] = {
    "pestana": "TabItem", "tab": "TabItem", "solapa": "TabItem", "boton": "Button", "button": "Button",
    "enlace": "Hyperlink", "link": "Hyperlink", "casilla": "CheckBox", "checkbox": "CheckBox",
}


def effect_intent_actionable_kinds() -> frozenset[str]:
    return frozenset({
        "Button", "MenuItem", "ListItem", "TabItem", "Hyperlink", "CheckBox", "RadioButton",
        "Edit", "ComboBox", "TreeItem", "SplitButton", "Slider", "Document",
    })


def _text_line_with(view: dict, label: str) -> str | None:
    text = view.get("text") if isinstance(view, dict) else None
    if not isinstance(text, dict):
        return None
    hits = []
    for zone_lines in text.values():
        if isinstance(zone_lines, list):
            for line in zone_lines:
                if label_names(label, str(line)):
                    hits.append(str(line))
    # The OCR reads the window twice (plain and darkened), so a word on screen once is often in two lines; where it
    # is, and whether it is one place, is the click cascade's business (it refuses an ambiguous word).
    return hits[0] if hits else None


def _focused(view: dict) -> dict | None:
    window = view.get("window") if isinstance(view, dict) else None
    focused = window.get("focused") if isinstance(window, dict) else None
    return focused if isinstance(focused, dict) else None


def _focused_is_password(view: dict) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict) and "focused" in str(control.get("state") or "") and "password" in str(control.get("state") or ""):
                return True
    return False


_COMPOSER_NAME = re.compile(r"\b(?:mensaj|message|chat|escrib|say\s+something|type\s+a\s+message|conversa)")
# What Enter or space may send from: a message box, and a reply, comment, post or send box or button.
_SENDING_NAME = re.compile(
    r"\b(?:mensaj|message|chat|escrib|say\s+something|type\s+a\s+message|conversa|respon|reply|coment|comment|"
    r"publica|post\b|tweet|envia|send\b)"
)
# The name the view gives a text field that has none of its own: «(edit)», «(document)».
_UNNAMED_FIELD = re.compile(r"^(?:\((?:edit|document)\))?$")
_EDITABLE_KINDS = frozenset({"Edit", "Document", "ComboBox"})


def _composer_with_text(view: dict, history: list[dict] | None = None) -> bool:
    """Whether Enter (or space) on the focused control may hand something to a person (contract §2.1), so the step
    is marked ``message_composer`` and RiskPolicy asks first. Conservative by design (safety review 2026-10-07):

    * a focused control named like a message, chat, reply, comment or send box asks, unless it exposes a value and
      that value is empty (nothing to send);
    * a focused text field with no name of its own that does not expose its value asks too: what it is and what it
      holds cannot be read, and in a chat that is the message box (measured: Discord's editor exposes no value);
    * a window whose focus cannot be read (none reported, or a bare pane or custom control: measured on WhatsApp,
      drawn without a tree) right after this sub-goal typed a text asks: the text may sit in a chat's message box;
    * free: a search or address field (named so), a document editor that exposes its value (Notepad), and a window
      with no focused editable where nothing was just typed (a calculator's buttons).
    """

    focused = _focused(view)
    if _last_verified_typed(history) and (focused is None or str(focused.get("kind")) in _OPAQUE_FOCUS_KINDS):
        return True
    if focused is None:
        return False
    name = fold(focused.get("name"))
    value = focused.get("value")
    if _SENDING_NAME.search(name) is not None and not _SEARCH_NAME.search(name) and not _ADDRESS_NAME.search(name):
        # A message box whose content the screen does not expose may hold the text just typed: Enter there sends.
        return value is None or bool(str(value).strip())
    return str(focused.get("kind")) in _EDITABLE_KINDS and _UNNAMED_FIELD.match(name) is not None and value is None


# A focused control that says nothing of what has the keyboard: a window's bare pane or a custom drawn control.
_OPAQUE_FOCUS_KINDS = frozenset({"Pane", "Custom"})


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
        and _ADDRESS_NAME.search(fold(control.get("name"))) is not None
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


# Line breaks, tabs and other control characters in a typed text are keys of their own: a line break in a chat box
# sends what was written without anyone asking. A typed step carries one line.
_TYPED_BREAKS = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]+")


def typed_text(text: str) -> str:
    return _TYPED_BREAKS.sub(" ", text)


# The windows where the person's own work and BAXY live: never taken for another application. Each is adopted only
# when the request names that very application (the words on the right).
_PROTECTED_PROCESSES: dict[str, frozenset[str]] = {
    "code": frozenset({"code", "vs code", "vscode", "visual studio code"}),
    "code - insiders": frozenset({"code insiders", "visual studio code insiders"}),
    "devenv": frozenset({"visual studio", "devenv"}),
    "windowsterminal": frozenset({"terminal", "windows terminal"}),
    "openconsole": frozenset({"terminal", "windows terminal"}),
    "powershell": frozenset({"powershell", "windows powershell"}),
    "pwsh": frozenset({"powershell", "pwsh"}),
    "cmd": frozenset({"cmd", "simbolo del sistema", "command prompt"}),
    "conhost": frozenset({"cmd", "simbolo del sistema", "command prompt", "consola"}),
    "baxy": frozenset({"baxy"}),
    "baxy-core": frozenset({"baxy"}),
}
_GENERIC_APPLICATION_WORDS = frozenset({
    "the", "los", "las", "navegador", "browser", "google", "microsoft", "mozilla", "app", "aplicacion",
})


def _window_fold(value: object) -> str:
    """fold without format characters (Edge writes «Microsoft\u200b Edge» in its titles)."""

    return fold("".join(character for character in str(value or "") if unicodedata.category(character) != "Cf"))


def _process_key(process: object) -> str:
    folded = _window_fold(process)
    return folded[:-4] if folded.endswith(".exe") else folded


def protected_process(process: object, application: str | None) -> bool:
    """A developer's or BAXY's own window (an editor, a terminal, a console, BAXY) that the request did not name."""

    names = _PROTECTED_PROCESSES.get(_process_key(process))
    return names is not None and _window_fold(application) not in names


def _title_names(title: object, application: str) -> bool:
    """The application named as whole words in the title's last « - » segment, where windows put their own name
    («SteamLocalAdapter.cs - BAXY - Visual Studio Code» names Visual Studio Code, never Steam). A title with no
    separator is the application's name itself («Steam», «Calculadora»)."""

    segment = re.split(r"\s+[-\u2013\u2014|]\s+", _window_fold(title))[-1].strip()
    wanted = _window_fold(application)
    return bool(segment) and bool(wanted) and re.search(rf"(?<!\w){re.escape(wanted)}(?!\w)", segment) is not None


def application_is_in_front(view: dict, application: str | None) -> bool:
    """Whether the window of the view is the application's: the provider resolved it for the application
    (``requested``), its process is the application's executable, or its title names it in its last segment. Never a
    developer's or BAXY's own window unless that is what was named (safety review 2026-10-07)."""

    if not application:
        return True
    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict):
        return False
    process = _process_key(window.get("process"))
    if protected_process(process, application):
        return False
    if window.get("requested") is True:
        return True
    tokens = [token for token in _window_fold(application).split() if len(token) >= 3 and token not in _GENERIC_APPLICATION_WORDS]
    joined = "".join(_window_fold(application).split())
    if process and (process == joined or process in tokens):
        return True
    return _title_names(window.get("title"), application) or any(_title_names(window.get("title"), token) for token in tokens)


_CALC_TRANSLATE = str.maketrans({"×": "*", "x": "*", "X": "*", "÷": "/", "−": "-", ",": "."})


def _expression_for_typing(expression: str) -> str:
    return "".join(expression.translate(_CALC_TRANSLATE).split())


def _steps_ok(history: list[dict], operation: str, **match: str) -> list[dict]:
    found = []
    for step in history:
        if step.get("operation") != operation or step.get("ok") is not True:
            continue
        if all(fold(step.get(key)) == fold(value) for key, value in match.items()):
            found.append(step)
    return found


# «activar modo X»: the reader's goal for «poné el modo X», which is a switch only where the window has one so named.
_MODE_SWITCH_GOAL = re.compile(r"^activar\s+modo\s+(?P<what>\S.*)$")


def _switch_named(view: dict, what: str) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _is_switch(control)
        and (label_names(what, str(control.get("name") or "")) or label_names(f"modo {what}", str(control.get("name") or "")))
        for control in controls or ()
    )


def deterministic_step(
    *,
    goal: str,
    view: dict,
    history: list[dict],
    application: str | None = None,
    objective: str | None = None,
    _tried: tuple[str, ...] = (),
) -> dict[str, object] | None:
    """The step the goal itself dictates when the view shows it (contract §4.2):
    a key to press, a text or an expression to type, a named control to click
    or to switch, a tab to close while more than one is open. No model, no
    application knowledge; anything else, or a step that just failed, goes to
    the model."""

    folded_goal = fold(goal)
    mode = _MODE_SWITCH_GOAL.match(folded_goal)
    if mode is not None and not _switch_named(view, mode.group("what")):
        # «poné el modo programador» on a window with no switch of that name: the mode is one of the window's places,
        # chosen the way «cambiá a programador» chooses it (live y1: the model wandered and flipped «Alternar grados»).
        return deterministic_step(
            goal=f"ir a {mode.group('what')}", view=view, history=history, application=application,
            objective=objective, _tried=_tried,
        )
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is not None and last.get("ok") is not True:
        # An opening that could not be verified but left the application in
        # front (measured: the Calculator's hosted window is invisible to the
        # opener's inventory) does not stop what the goal dictates.
        if not (last.get("operation") == "app.open" and application_is_in_front(view, application)):
            # A failed click while the menu the place's own click opened is still on screen: its entry is the step.
            place = folded_goal[len("ir a "):].strip() if folded_goal.startswith("ir a ") else ""
            entry = _menu_opened_by(view, history, place, goal) if place and last.get("operation") == "input.visible.click" else None
            if entry is not None:
                return {"operation": "input.visible.click", "arguments": {"label": entry}, "reason": "el clic abrió un menú"}
            if last.get("operation") != "input.visible.click":
                return None
            # A click that failed (a learned label now ambiguous or gone, measured on Settings after a replay) leaves
            # the goal's own step to be found again on this view, by identity, never the same act once more.
            # Without the failed step its look is not the last one: what the last verified click made appear is the
            # App's newTextAfterClick, never the failed look's newText (stale or empty).
            after_click = view.get("newTextAfterClick")
            retry_view = {**view, "newText": after_click if isinstance(after_click, list) else []}
            # A click on the goal's own name by label alone that found nothing stays tried: the next name (the other
            # language's) is the step, never the same name once more.
            tried = (*_tried, str(last.get("label") or "")) if not isinstance(last.get("index"), int) else _tried
            retried = deterministic_step(
                goal=goal, view=retry_view, history=history[:-1], application=application, objective=objective, _tried=tried,
            )
            if retried is None or retried.get("operation") != "input.visible.click":
                return retried
            arguments = retried.get("arguments") or {}
            same_index = isinstance(arguments, dict) and arguments.get("index") is not None and arguments.get("index") == last.get("index")
            same_label = isinstance(arguments, dict) and arguments.get("index") is None and fold(arguments.get("label")) == fold(last.get("label"))
            if same_index or same_label:
                # The goal's own control is the one that failed (measured on Discord: «Cotele» clicked, nothing
                # changed): the place is looked up the way the window offers, as a person would; only a name said
                # without a kind is looked up («la pestaña de Gmail» is never searched as «pestaña de Gmail»).
                parsed = _goal_target(goal)
                if parsed is None or parsed[1] is not None or parsed[3] is not None:
                    return None
                return _find_step(parsed[2], view, history, navigate=parsed[0] == "ir a ")
            return retried
    reason = "el objetivo lo dice"
    if folded_goal == "enviar":
        # «… y mandalo»: sending what was written is Enter in the message box, always marked so RiskPolicy asks first
        # (measured: an unmarked Enter sent «prueba BAXY C6» without asking).
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": {"key": "enter", "target": "message_composer"},
                    "reason": reason}
        return None
    if folded_goal.startswith("apretar "):
        key = _key_from_words(folded_goal[len("apretar "):])
        if key is not None and not _steps_ok(history, "input.key.press", key=key):
            return {"operation": "input.key.press", "arguments": key_arguments(key, view, history, blind_asks=True), "reason": reason}
        return None
    if folded_goal.startswith("calcular "):
        expression = _expression_for_typing(goal[len("calcular "):])
        if not expression:
            return None
        if not _steps_ok(history, "input.text.type"):
            return {"operation": "input.text.type", "arguments": {"text": expression}, "reason": reason}
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": key_arguments("enter", view), "reason": reason}
        return None
    if folded_goal.startswith("escribir "):
        text = typed_text(goal[len("escribir "):]).strip()
        if not text or _steps_ok(history, "input.text.type") or _focused_is_password(view):
            return None
        field = _place_to_type(view, history)
        if field is not None:
            # The keyboard is not on a text field: the field is clicked first, the way a person puts the cursor there
            # (measured: in Discord the text went to the message search instead of the message box).
            arguments = {"label": str(field.get("name") or "")}
            if isinstance(field.get("i"), int):
                arguments["index"] = field["i"]
            return {"operation": "input.visible.click", "arguments": arguments, "reason": "pongo el cursor donde se escribe"}
        return {"operation": "input.text.type", "arguments": {"text": text}, "reason": reason}
    if folded_goal.startswith("ir a la direccion "):
        # «andá a es.wikipedia.org»: the browser's address bar, the address, Delete, Enter. The bar completes what is
        # typed with a page of the history, selected after the caret (measured on Opera: «es.wikipedia.org» became
        # «…/wiki/Curicó» and Enter went there); Delete drops that completion and nothing else.
        address = typed_text(goal[len("ir a la direccion "):]).strip()
        if not _steps_ok(history, "input.key.press", key="ctrl_l"):
            return {"operation": "input.key.press", "arguments": {"key": "ctrl_l"}, "reason": reason}
        if not _steps_ok(history, "input.text.type"):
            return {"operation": "input.text.type", "arguments": {"text": address}, "reason": reason}
        if not _steps_ok(history, "input.key.press", key="delete"):
            # Delete erases characters only where the view shows the keyboard on the address field; anywhere else
            # (ctrl_l did not reach the bar, a page took the focus) it would delete what is selected: stop.
            if not _keyboard_on_address_field(view):
                return None
            return {"operation": "input.key.press", "arguments": key_arguments("delete", view), "reason": reason}
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": key_arguments("enter", view), "reason": reason}
        return None
    if folded_goal.startswith("buscar "):
        # «buscá Hades»: the window's own search (field, button or shortcut), the name, then Enter to submit it.
        target = goal[len("buscar "):].strip()
        if not _typed_target(history, target):
            # A search is the window's search, never its navigation menu.
            step = _find_step(target, view, history, navigate=False)
            return None if step is None or step.get("operation") == "input.scroll" else step
        if not _steps_ok(history, "input.key.press", key="enter") and not _focused_is_password(view):
            # Enter submits the search only in a field the view shows is a search; anywhere else (a focus that cannot
            # be read, measured on WhatsApp with a chat open) the name may be in a message box and Enter would send
            # it, so RiskPolicy asks first.
            field = _focused_field(view)
            searching = (field is not None and _is_search_field(field)) or _typed_into_written_search(view, history)
            arguments = {"key": "enter"} if searching else {"key": "enter", "target": "message_composer"}
            return {"operation": "input.key.press", "arguments": arguments, "reason": reason}
        return None
    parsed = _goal_target(goal)
    if parsed is None:
        return None
    head, wanted, target, kind = parsed
    searching = wanted is None and kind is None
    # Going to a place (any «ir a», and a click on a name said without a kind) never changes a setting on the way.
    placing = wanted is None and (head == "ir a " or kind is None)
    navigate = head == "ir a "
    typed = searching and _typed_target(history, target)
    opened = None if typed else _menu_opened_by(view, history, target, goal)
    if opened is not None:
        # The click on the destination opened a short menu instead of going there (measured on Steam: «BIBLIOTECA»
        # → «Página principal · Colecciones · Descargas»): the entry the goal names, else the destination's own
        # page, else the first entry of a menu in the tree (``_menu_opened_by``).
        return {"operation": "input.visible.click", "arguments": {"label": opened}, "reason": "el clic abrió un menú"}
    if typed:
        # The name was typed into a search: what to click is the result that names it, never the field's echo.
        return _find_step(target, view, history, navigate=navigate)
    # Only a mode's name has two genders on screen; a place keeps the gender said («partido» is no «partida»),
    # neither as a second name nor as the one typo the loose match allows.
    is_mode = _mode_named(target) is not None
    twin = gender_twin(target) if searching and is_mode else None
    names = (target, *label_alternatives(target), *((twin,) if twin else ()))
    other_gender = None if is_mode else gender_twin(target)
    seen = _without_name(view, other_gender) if other_gender else view
    if placing:
        seen = _without_fixed_fields(seen)
    chosen = _content_item_chosen(view, history, names) if head == "ir a " and kind is None else None
    if chosen is not None:
        # One click on an item of a content list chose it and opened nothing (measured on Explorer: «Descargas»
        # in the Home view); a person then presses Enter. Enter on a list item sends nothing to anyone, but on an
        # application, a shortcut or a file it may start something: pressed only where the view shows the item is
        # a folder or a drive (``_is_container``), never on a file that runs nor in a view that offers to remove
        # what is chosen (a list of programs); anything else is the model's step.
        if (
            _runs_when_opened(chosen) or _offers_uninstall(view) or _REMOVAL_NAME.search(fold(chosen.get("name")))
            or not _is_container(chosen, view)
        ):
            return None
        return {"operation": "input.key.press", "arguments": key_arguments("enter", view),
                "reason": "el clic sólo eligió el elemento: Enter lo abre"}
    # Going to a place looks among the controls that are not switches first («Bluetooth» as a switch and as the
    # navigation item: the item is the place).
    among = _without_switches(seen) if placing else seen
    colour = wanted == "selected" and kind is None and is_basic_colour(target)
    if colour:
        # A colour is its swatch's whole name: «azul» is never «Gris azulado», «rojo» never «Rojo oscuro» nor
        # «Color 1: Rojo» (live e2), and never a tool that picks colours from the canvas.
        control = _swatch(among, names)
        if control is None:
            return _colour_step(view, history, names, target, _tried)
    else:
        control = next((found for name in names if (found := find_control(among, name, kind=kind)) is not None), None)
    if control is None and placing:
        control = next((found for name in names if (found := find_control(seen, name, kind=kind)) is not None), None)
    if control is not None and placing and _is_switch(control):
        # Going somewhere never changes a setting on the way: a switch named like the place is not the place, and
        # neither is its written name; the place is looked up the way the window offers.
        return _find_step(target, view, history, navigate=navigate) if searching else None
    if control is None and wanted == "on":
        # «poné el modo científico» where no switch is called so: the mode is chosen like a place (the
        # Calculator's modes are items of its navigation).
        mode = _mode_named(target)
        if mode is not None:
            return deterministic_step(goal=f"ir a {mode}", view=view, history=history, application=application)
    if control is None and kind == "TabItem" and wanted is None and _window_fold(application) != _window_fold(BROWSER_CATEGORY):
        # A tab of an editor's workspace exists only with a document open; on the start page a person first creates
        # the blank one it offers (live v5/v6: Excel and Word opened on «Libro/Documento en blanco» and recent files).
        started = _start_page_step(view, history, objective, application)
        if started is not None:
            return started
    carrying = _controls_carrying(seen, names, kind, placing) if control is None and wanted is None else []
    if len(carrying) >= 2:
        # Two controls carry the name (measured on Discord: «Cotele» was a server and an activity card; on Explorer
        # «Descargas» is the side list's item and a tile of the Home view). The one navigation item among them (an
        # item of a list in the window's left column, not content) is the place; otherwise neither is surely it,
        # the written word is the same doubt, and the place is looked up instead.
        navigation = [found for found in carrying if _navigation_item(found, view)]
        if len(navigation) == 1 and not _steps_ok(history, "input.visible.click", label=str(navigation[0].get("name") or "")):
            return _click(navigation[0], reason)
        return _find_step(target, view, history, navigate=navigate) if searching else None
    if control is None:
        # A window drawn without an accessible tree (CEF, Electron, canvas: measured on Steam, one control and
        # the navigation only in the OCR lines): the word written on screen is clicked by its label, and the
        # click's cascade (UIA → OCR → vision) finds where it is. Never the written name of a switch.
        written = next(
            (name for name in names
             if (line := _text_line_with(seen, name)) is not None and not (placing and _names_a_switch(view, line))),
            None,
        ) if kind is None else None
        if wanted in (None, "selected") and written is not None and not _steps_ok(history, "input.visible.click", label=written):
            return {"operation": "input.visible.click", "arguments": {"label": written}, "reason": reason}
        # A navigation button not opened yet goes first: right after a cold start a name clicked by label alone is
        # waited for as the application draws (live y1: «programador» took 39 s to be not found; it was behind
        # «Abrir navegación»).
        opener_first = navigate and _navigation_opener(view, history) is not None
        if written is None and kind is None and wanted in (None, "selected") and not opener_first:
            unlisted = _unlisted_name_click(view, history, names, _tried)
            if unlisted is not None:
                return unlisted
        # Not on screen: looked up the way any window offers (search field, quick switcher, find, the list).
        return _find_step(target, view, history, navigate=navigate) if searching and written is None else None
    states = str(control.get("state") or "").split()
    if wanted is not None and (wanted in states or (wanted == "selected" and "on" in states)):
        # Already so; a tool or a colour chosen shows as selected or pressed.
        return None
    if _steps_ok(history, "input.visible.click", label=str(control.get("name") or "")) or _click_failed(
        history, str(control.get("name") or "")
    ):
        # Clicked and not there yet (measured on Discord: the name was written in an activity card, not the
        # channel), or clicked and refused (measured 2026-10-07: a field that cannot be pressed was clicked four times
        # in one sub-goal): looked up the way the window offers, never clicked again.
        return _find_step(target, view, history, navigate=navigate) if searching else None
    arguments = {"label": str(control.get("name") or target)}
    if isinstance(control.get("i"), int):
        arguments["index"] = control["i"]
    return {"operation": "input.visible.click", "arguments": arguments, "reason": reason}


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


def _start_page_step(
    view: dict, history: list[dict], objective: str | None, application: str | None = None,
) -> dict[str, object] | None:
    """A tab of the editor was asked and the window is a start page: no document named in its title, one offer to
    create a blank item. A person creates the blank item first, then goes to the tab: Enter when the focused element is
    the offer itself, else one click on it. Creating an unsaved blank document is reversible and touches no file;
    never when the person named a file of their own (opening a recent one is theirs to say), and never twice: once the
    offer was pressed or clicked, a start page still there is said as such, without another step that could create a
    second one."""

    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict) or _title_names_a_document(window.get("title")):
        return None
    offer = _blank_item(view)
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


# The goals that name a control, with the state each one wants (None: a place to go or a control to press).
_GOAL_HEADS: tuple[tuple[str, str | None], ...] = (
    ("ir a ", None), ("hacer clic en ", None), ("activar ", "on"), ("desactivar ", "off"), ("seleccionar ", "selected"),
)


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


def _placing_goal(goal: str | None) -> bool:
    """A goal that places the person somewhere or presses a named thing, never one that sets something: «ir a …»,
    «buscar …», and «hacer clic en …» unless it names a switch's kind («la casilla …»)."""

    folded = fold(goal or "")
    if folded.startswith(("ir a ", "buscar ")):
        return True
    parsed = _goal_target(goal or "") if folded.startswith("hacer clic en ") else None
    return parsed is not None and parsed[3] not in _SWITCH_KINDS


# How many controls the App lists in a view (its ``limit``); a view without ``controlCount`` that lists this many may
# leave out the rest of the window's tree.
_LISTED_CONTROLS = 60
REASON_BY_NAME = "el objetivo lo nombra y la vista no lo lista: lo busco por su nombre en toda la ventana"
REASON_SHADE = "la ventana no tiene ese color por su nombre: elijo su tono más cercano"


def colour_goal(goal: str | None) -> str | None:
    """The basic colour a goal «seleccionar X» chooses («azul», «blue»), or None for any other goal."""

    parsed = _goal_target(goal or "")
    if parsed is None or parsed[1] != "selected" or parsed[3] is not None:
        return None
    return parsed[2] if is_basic_colour(parsed[2]) else None


def _swatch(view: dict, names: Iterable[str]) -> dict | None:
    """The one listed control whose whole name is one of ``names`` (a colour's swatch), never a tool that picks
    colours; None when there is none or more than one."""

    wanted = {fold(name) for name in names if fold(name)}
    controls = view.get("controls") if isinstance(view, dict) else None
    found = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and fold(control.get("name")) in wanted and not changes_the_tool(control.get("name"))
    ]
    return found[0] if len(found) == 1 else None


def _colour_step(view: dict, history: list[dict], names: tuple[str, ...], target: str, tried: Iterable[str]) -> dict[str, object] | None:
    """A colour the listing does not carry by its name: the name by label alone first (beyond the listed controls),
    then the closest of its shades the view lists, then each of its shades by label alone, closest first, in the
    window's language when its names tell it (measured on Paint: no «Azul», «Añil» is the blue of the palette). Each
    label once per sub-goal; the label keeps the written spelling, which the click matches whole."""

    lines = {fold(line) for line in _view_lines(view)}
    written = next((name for name in names if fold(name) in lines), None)
    if written is not None and not _steps_ok(history, "input.visible.click", label=written):
        # Written on screen whole, outside the accessible tree: its label, which the click's cascade finds.
        return {"operation": "input.visible.click", "arguments": {"label": written}, "reason": "el objetivo lo dice"}
    by_name = _unlisted_name_click(view, history, names, tried)
    if by_name is not None:
        return by_name
    clicked = {
        str(step.get("label") or "").casefold() for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    } | {str(label).casefold() for label in tried}
    controls = view.get("controls") if isinstance(view, dict) else None
    listed = [str(control.get("name") or "") for control in controls if isinstance(control, dict)] if isinstance(controls, list) else []
    language = screen_language([*listed, *_view_lines(view)])
    shades = [shade for shade in colour_shades(target, language) if shade.casefold() not in clicked]
    for shade in shades:
        swatch = _swatch(view, (shade,))
        if swatch is not None and str(swatch.get("name") or "").casefold() not in clicked:
            if "selected" in str(swatch.get("state") or "").split():
                return None
            return _click(swatch, REASON_SHADE)
    if not _lists_part_of_the_tree(view) or not shades:
        return None
    return {"operation": "input.visible.click", "arguments": {"label": shades[0]}, "reason": REASON_SHADE}


def _lists_part_of_the_tree(view: dict) -> bool:
    """The view lists only part of the window's controls: ``controlCount`` (all the tree holds) above the listed ones,
    or, without it, the listing full at the App's limit."""

    controls = view.get("controls") if isinstance(view, dict) else None
    listed = len(controls) if isinstance(controls, list) else 0
    count = view.get("controlCount") if isinstance(view, dict) else None
    if isinstance(count, int) and not isinstance(count, bool):
        return count > listed
    return listed >= _LISTED_CONTROLS


def _unlisted_name_click(view: dict, history: list[dict], names: Iterable[str], tried: Iterable[str] = ()) -> dict[str, object] | None:
    """A click by label alone (no index) on the goal's own name, the person's word first and then its other names,
    when the view lists only part of the window and neither a listed control nor a written line carries it: the
    click resolves the label against the whole tree (measured on Paint: the palette's colours lie beyond the 60
    listed controls, and the model clicked the colour picker tool and a shape instead). Each name once per sub-goal,
    failed or not; never a name that removes something."""

    if not _lists_part_of_the_tree(view):
        return None
    clicked = {
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    } | {fold(label) for label in tried}
    names = tuple(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if any(_REMOVAL_NAME.search(fold(name)) or _OPENS_ELSEWHERE.search(fold(name)) for name in names):
        return None
    # The name the window itself writes somewhere (a word of a listed control or a line on screen) goes first: it is
    # the window's language, and a click on the other language's name costs one of the sub-goal's steps.
    shown = _view_words(view)
    names = tuple(sorted(names, key=lambda name: not _shown_as_words(fold(name), shown)))
    for name in names:
        if fold(name) in clicked:
            continue
        return {"operation": "input.visible.click", "arguments": {"label": name}, "reason": REASON_BY_NAME}
    return None


def _view_words(view: dict) -> str:
    """The listed controls' names and the view's lines, folded, one per line."""

    controls = view.get("controls")
    named = [str(control.get("name") or "") for control in controls if isinstance(control, dict)] if isinstance(controls, list) else []
    appeared = view.get("newText")
    lines = [str(line) for line in appeared] if isinstance(appeared, list) else []
    return "\n".join(fold(text) for text in (*named, *lines, *_view_lines(view)))


def _shown_as_words(name: str, shown: str) -> bool:
    return bool(name) and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", shown) is not None


def _without_fixed_fields(view: dict) -> dict:
    """The view without the fields that only show a value (read-only, or a browser's address): going to a place never
    clicks one (measured 2026-10-07: «search» matched a web app's read-only «Address and search bar», whose clicks
    all failed)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [
        control for control in controls
        if not (
            isinstance(control, dict) and control.get("kind") in {"Edit", "ComboBox", "Document"}
            and ("readonly" in str(control.get("state") or "").split() or _ADDRESS_NAME.search(fold(control.get("name"))))
        )
    ]}


def _click_failed(history: list[dict], label: str) -> bool:
    """A click on this label already failed in this sub-goal."""

    return bool(label) and any(
        step.get("operation") == "input.visible.click" and step.get("ok") is False and fold(step.get("label")) == fold(label)
        for step in history if isinstance(step, dict)
    )


def _without_switches(view: dict) -> dict:
    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [control for control in controls if not (isinstance(control, dict) and _is_switch(control))]}


# What may follow a name at the start of a control's name that is still that name («Cotele (servidor)», «general ·
# Mi servidor», «Descargas - Anclado»); a name inside a sentence is not one.
_NAME_SEPARATORS = (" (", ",", " ·", " -", ":")


def _carries_name(control_name: str, name: str) -> bool:
    """A control's name is ``name``: equal folded, or ``name`` followed by a separator at its start."""

    folded, wanted = fold(control_name), fold(name)
    return bool(wanted) and (folded == wanted or any(folded.startswith(wanted + mark) for mark in _NAME_SEPARATORS))


def _controls_carrying(view: dict, names: Iterable[str], kind: str | None, placing: bool) -> list[dict]:
    """The controls (of ``kind`` when given; never a switch while going to a place) that carry one of the names as
    their own (``_carries_name``): a message that says «… en general …» does not make «general» two places."""

    names = tuple(names)
    controls = view.get("controls") if isinstance(view, dict) else None
    return [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and (kind is None or control.get("kind") == kind)
        and not (placing and _is_switch(control))
        and any(_carries_name(str(control.get("name") or ""), name) for name in names)
    ]


def _controls_naming(view: dict, names: Iterable[str], kind: str | None, placing: bool) -> int:
    """How many controls carry one of the names as their own (``_controls_carrying``)."""

    return len(_controls_carrying(view, names, kind, placing))


_NAVIGATION_ITEM_KINDS = frozenset({"TreeItem", "ListItem", "TabItem"})


def _navigation_item(control: dict, view: dict) -> bool:
    """An item of the window's navigation: a tree, list or tab item in the left column (zones L, TL, BL) that is not
    an item of a content view (``is_content_item``)."""

    return (
        str(control.get("kind")) in _NAVIGATION_ITEM_KINDS and str(control.get("zone") or "").endswith("L")
        and not is_content_item(control, view)
    )


def _without_name(view: dict, name: str) -> dict:
    """The view without the controls and written lines whose whole folded name is ``name``."""

    if not isinstance(view, dict):
        return view
    wanted = fold(name)
    controls = view.get("controls")
    text = view.get("text")
    return {
        **view,
        "controls": [
            control for control in controls if not (isinstance(control, dict) and fold(control.get("name")) == wanted)
        ] if isinstance(controls, list) else controls,
        "text": {
            zone: [line for line in lines if fold(line) != wanted] if isinstance(lines, list) else lines
            for zone, lines in text.items()
        } if isinstance(text, dict) else text,
    }


def _names_a_switch(view: dict, line: str) -> bool:
    """A written line that is a switch's own name (the same words, a typo apart): clicking it presses the switch."""

    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _is_switch(control)
        and label_names(str(control.get("name") or ""), line) and label_names(line, str(control.get("name") or ""))
        for control in (controls if isinstance(controls, list) else [])
    )


_CONTENT_KINDS = {"ListItem", "DataItem"}


def is_content_item(control: dict, view: dict | None = None) -> bool:
    """A ListItem or DataItem of a content view (files, pictures, results), where one click selects and does not
    open: out of the window's left column (zones L, TL, BL), where navigation lists sit; or in it, when another item
    of the view sits in the same row out of that column (a grid of tiles that starts at the left edge). Same row:
    vertical centres within half the item's height (the App's ``IsContentItem`` reads it the same way)."""

    zone = str(control.get("zone") or "")
    if str(control.get("kind")) not in _CONTENT_KINDS or not zone:
        return False
    if not zone.endswith("L"):
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    centre, height = _vertical_centre(control.get("rect"))
    if centre is None or not isinstance(controls, list):
        return False
    for other in controls:
        if other is control or not isinstance(other, dict) or str(other.get("kind")) not in _CONTENT_KINDS:
            continue
        other_zone = str(other.get("zone") or "")
        other_centre, _ = _vertical_centre(other.get("rect"))
        if (
            other_zone and not other_zone.endswith("L") and other_centre is not None
            and abs(other_centre - centre) <= height / 2 and _same_size(control.get("rect"), other.get("rect"))
        ):
            return True
    return False


def _same_size(rect: object, other: object) -> bool:
    """A tile of the same grid has the item's size; a card of the page beside a navigation list does not."""

    try:
        width, height = float(rect["w"]), float(rect["h"])  # type: ignore[index]
        other_width, other_height = float(other["w"]), float(other["h"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return False
    return width > 0 and height > 0 and abs(other_width - width) <= width * 0.25 and abs(other_height - height) <= height * 0.25


def _vertical_centre(rect: object) -> tuple[float | None, float]:
    try:
        top, height = float(rect["y"]), float(rect["h"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return None, 0.0
    return (top + height / 2, height) if height > 0 else (None, 0.0)


# A control that removes what is chosen (a list of programs, a file manager's delete): with it on offer, Enter on the
# chosen item is no safe default. Whole words, so «Borradores» or «Quitarse» names nothing here.
_REMOVAL_NAME = re.compile(
    r"(?<!\w)(?:desinstal\w*|uninstall\w*|elimin(?:ar|a)|delete|borr(?:ar|a)|quit(?:ar|a)|remove)(?!\w)"
)
# A file that runs, installs or launches something when opened.
_RUNS_WHEN_OPENED = re.compile(r"\.(?:exe|msi|bat|cmd|ps1|vbs|js|lnk|appx|msix|reg|hta|scr|cpl|jar|com|pif)(?!\w)")
# What a file view calls a folder or a drive: the item's own type (the App's ``itemType``), or the type cell of its
# row in a details view.
_CONTAINER_TYPE = re.compile(r"(?<!\w)(?:carpeta|folder|directorio|directory|unidad|drive)")
_CONTAINER_CELL = frozenset({"carpeta de archivos", "file folder"})


# Only an uninstall offered by the window vetoes Enter on a chosen item (a list of programs); delete-like commands are
# on every file view (Explorer's «Eliminar (Supr)») and only count when they are the chosen item's own name.
_UNINSTALL_NAME = re.compile(r"(?<!\w)(?:desinstal\w*|uninstall\w*)(?!\w)")


def _offers_uninstall(view: dict) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _UNINSTALL_NAME.search(fold(control.get("name"))) is not None
        for control in (controls if isinstance(controls, list) else ())
    )


def _runs_when_opened(control: dict) -> bool:
    return _RUNS_WHEN_OPENED.search(fold(control.get("name"))) is not None


def _is_container(control: dict, view: dict) -> bool:
    """Positive evidence that the item is a folder or a drive (opening it shows what it holds and starts nothing):
    its ``itemType`` says so, or a control on its row (vertical centres within half the item's height) is the
    type cell «Carpeta de archivos» / «File folder». Without it, nothing tells a folder from an application."""

    item_type = fold(control.get("itemType"))
    if item_type:
        # The item says what it is: only a folder or a drive opens without running anything.
        return _CONTAINER_TYPE.search(item_type) is not None
    centre, height = _vertical_centre(control.get("rect"))
    controls = view.get("controls") if isinstance(view, dict) else None
    if centre is None or not isinstance(controls, list):
        return False
    for other in controls:
        if other is control or not isinstance(other, dict):
            continue
        other_centre, _ = _vertical_centre(other.get("rect"))
        if other_centre is None or abs(other_centre - centre) > height / 2 or not _inside(other.get("rect"), control.get("rect")):
            continue
        if fold(other.get("name")).strip() in _CONTAINER_CELL or fold(other.get("value")).strip() in _CONTAINER_CELL:
            return True
    return False


def _content_item_chosen(view: dict, history: list[dict], names: tuple[str, ...]) -> dict | None:
    """The content item named as the place that the last step, a verified click on it, left selected while the
    window's title does not name the place yet; None otherwise."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True:
        return None
    if not any(label_names(name, str(last.get("label") or "")) for name in names):
        return None
    window = view.get("window") if isinstance(view, dict) else None
    title = _window_fold(window.get("title")) if isinstance(window, dict) else ""
    if any(re.search(rf"(?<!\w){re.escape(fold(name))}(?!\w)", title) for name in names if fold(name)):
        return None
    controls = view.get("controls") if isinstance(view, dict) else None
    for control in controls if isinstance(controls, list) else ():
        if (
            isinstance(control, dict)
            and is_content_item(control, view)
            and "selected" in str(control.get("state") or "").split()
            and any(fold(control.get("name")) == fold(name) for name in names)
        ):
            return control
    return None


# ------------------------------------------------------------- buscar el destino

# A place to look a name up in, by what it is called in either language: a search or filter field, a quick switcher
# («¿A dónde quieres ir?»), a «go to» box. The address bar is not one: what it finds is the web, not the window.
_SEARCH_NAME = re.compile(
    r"\b(?:busc\w*|busqueda|search\w*|find|filtr\w*|filter\w*|a donde quieres ir|ir a|go to|jump to|quick switcher)\b"
)
_ADDRESS_NAME = re.compile(r"\b(?:direccion\w*|address|url)\b")
# What a browser's address field holds on a site: «https://es.wikipedia.org/…», «es.wikipedia.org/wiki/…» (a folder
# path or «Este equipo > Descargas» is a file explorer's).
_WEB_ADDRESS = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[^\W\d_]{2,}(?::\d+)?(?:[/?#]|$)")
_SEARCH_KINDS = ("Edit", "ComboBox", "Button", "ListItem")
_SENTENCE_END = re.compile(r"[.!?]\s")
_FIELD_KINDS = frozenset({"Edit", "ComboBox"})
# What a search shows its results as, best first; the field itself is never a result.
_RESULT_KINDS = ("ListItem", "TreeItem", "Button", "Hyperlink", "DataItem", "MenuItem", "TabItem")
_LIST_KINDS = frozenset({"List", "Tree", "DataGrid", "Table"})
_ITEM_KINDS = frozenset({"ListItem", "TreeItem", "DataItem"})
_SEARCH_KEYS = ("ctrl_k", "ctrl_f")
_SCROLLS = 3
_REASON_FIND = "el destino no está en pantalla: lo busco"


def _typed_target(history: list[dict], target: str) -> bool:
    return any(
        step.get("operation") == "input.text.type" and step.get("ok") is True and fold(step.get("text")) == fold(target)
        for step in history
    )


def _is_search_field(control: dict) -> bool:
    name = fold(control.get("name"))
    if _ADDRESS_NAME.search(name) or "password" in str(control.get("state") or ""):
        return False
    return _SEARCH_NAME.search(name) is not None


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


def _focused_field(view: dict) -> dict | None:
    """The field that has the keyboard (window.focused, or a control whose state says so), when typing a name into it
    is a search: never a password, a message composer or the address bar."""

    focused = _focused(view)
    candidates = [focused] if focused is not None else []
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        candidates += [
            control for control in controls
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        ]
    for control in candidates:
        if control.get("kind") not in _FIELD_KINDS or "password" in str(control.get("state") or ""):
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


def _web_browser(view: dict) -> bool:
    """The window is a web browser showing a site: a field named as the address holds a web address."""

    controls = view.get("controls") if isinstance(view, dict) else None
    focused = _focused(view)
    candidates = [*(controls if isinstance(controls, list) else []), *([focused] if focused is not None else [])]
    return any(
        isinstance(control, dict) and control.get("kind") in _FIELD_KINDS
        and _ADDRESS_NAME.search(fold(control.get("name"))) is not None
        and _WEB_ADDRESS.match(str(control.get("value") or "").strip()) is not None
        for control in candidates
    )


def _area(rect: object) -> float:
    try:
        return max(float(rect["w"]), 0.0) * max(float(rect["h"]), 0.0)  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return 0.0


def _page(view: dict) -> dict | None:
    """The web page in a browser's view: its largest document, when it is the size of a page (a quarter of the
    window; 200×150 without the window's rectangle). None while the page is not exposed (measured on Opera loading:
    only a 22×22 «Cargando…» document beside the frame)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    documents = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "Document" and _area(control.get("rect")) > 0
    ]
    if not documents:
        return None
    page = max(documents, key=lambda control: _area(control.get("rect")))
    rect = page["rect"]
    window = view.get("window") if isinstance(view, dict) else None
    window_area = _area(window.get("rect")) if isinstance(window, dict) else 0.0
    if window_area > 0:
        return page if _area(rect) >= window_area / 4 else None
    return page if float(rect["w"]) >= 200 and float(rect["h"]) >= 150 else None


def _of_the_page(view: dict, control: dict) -> bool:
    """A control is the window's own unless the window is a web browser: there only what lies inside the page and
    comes after it in the tree is the page's. The tab strip's «Buscar pestañas», the bookmarks and the side bar lie
    outside it; the browser's own pop-ups (its tab search) are drawn over it but listed before it (measured on Opera)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not _web_browser(view) or not any(isinstance(item, dict) and item.get("rect") for item in controls or []):
        # Not a browser, or a view without rectangles: nothing tells the frame from the page.
        return True
    return _inside_the_page(view, control)


def _search_affordance(view: dict, history: list[dict]) -> dict | None:
    """The search field or button of the window not used yet in this sub-goal, fields first; in a web browser, the
    page's own (measured on Opera: the tab search was clicked and «Ñuñoa» typed into it)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return None
    # A control is a search when its name says so before any sentence of help it carries: an entry of a search's
    # history («speedtest. Presione la tecla Suprimir para borrar el historial de búsqueda.», measured on a packaged
    # store) is one of its suggestions, not the search.
    found = [
        control for control in controls
        if isinstance(control, dict) and control.get("kind") in _SEARCH_KINDS
        and _is_search_field({**control, "name": _SENTENCE_END.split(str(control.get("name") or ""), 1)[0]})
        and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
        and _of_the_page(view, control)
    ]
    found.sort(key=lambda control: _SEARCH_KINDS.index(str(control.get("kind"))))
    if found:
        return found[0]
    if _web_browser(view):
        # The written lines of a browser mix the frame with the page (OCR has no tree to tell them apart).
        return None
    # A window that exposes no tree still writes its search box (measured on WhatsApp: «Buscar un chat o iniciar uno
    # nuevo» read by OCR, nothing in UIA): the written line is clicked like the field.
    written = [
        line.strip() for line in _view_lines(view)
        if 0 < len(line.split()) <= 8 and _is_search_field({"name": line})
        and not _steps_ok(history, "input.visible.click", label=line.strip())
    ]
    written.sort(key=lambda line: (len(line.split()[0]) <= 2, len(line)))
    return {"name": written[0]} if written else None


# The button that opens a window's navigation or menu, by its whole name in either language: «Abrir navegación»,
# «Open Navigation», «Menú», «Más opciones», «More options», «Main menu», a hamburger. Its opposite («Cerrar
# navegación»), a group of buttons, a resize handle or a «Más» that is an operator are not.
_NAVIGATION_OPENER = re.compile(
    r"^(?:(?:abrir|abre|open|mostrar|muestra|show|expandir|expand|alternar|toggle)\s+(?:(?:el|la|the)\s+)?)?"
    r"(?:(?:panel|barra|pane|menu)\s+(?:de\s+)?)?"
    r"(?:navegacion|navigation|nav|menu|menu\s+principal|main\s+menu|hamburguesa|hamburger|"
    r"mas\s+opciones|more\s+options|mas\s+acciones|more\s+actions|more)"
    r"(?:\s+(?:menu|button|boton|pane|panel|principal|de\s+navegacion))?$"
)
# A bare «Menú» or «More» (a list's «more», a card's menu) says nothing of navigation: it opens the window's
# navigation only with a verb («Abrir menú») or the navigation's own words («Menú de navegación», «Hamburger menu»).
_BARE_OPENER = re.compile(
    r"^(?:(?:panel|barra|pane|menu)\s+(?:de\s+)?)?(?:menu|more)(?:\s+(?:menu|button|boton|pane|panel))?$"
)
_OPENER_KINDS = frozenset({"Button", "MenuItem", "SplitButton"})


def _opener_name(name: object) -> bool:
    folded = fold(name).strip()
    return _NAVIGATION_OPENER.match(folded) is not None and _BARE_OPENER.match(folded) is None


def _has_address_field(view: dict) -> bool:
    """A text field named as an address, whatever it holds (a browser on a new tab holds nothing)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    focused = _focused(view)
    candidates = [*(controls if isinstance(controls, list) else []), *([focused] if focused is not None else [])]
    return any(
        isinstance(control, dict) and control.get("kind") in _FIELD_KINDS
        and _ADDRESS_NAME.search(fold(control.get("name"))) is not None
        for control in candidates
    )


def _inside_the_page(view: dict, control: dict) -> bool:
    """The control lies inside the page document and after it in the tree; False when no page is exposed."""

    page = _page(view)
    if page is None or not _inside(control.get("rect"), page.get("rect")):
        return False
    position, page_position = control.get("i"), page.get("i")
    return not (isinstance(position, int) and isinstance(page_position, int)) or position > page_position


def _navigation_opener(view: dict, history: list[dict]) -> dict | None:
    """The window's navigation or menu button not clicked yet in this sub-goal and not open already. Where the window
    has an address field (a browser, even on an empty tab), only one inside the page: the frame's menu is not where
    the page keeps its places. Never a switch."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return None
    framed = _has_address_field(view)
    for control in controls:
        if (
            isinstance(control, dict) and control.get("kind") in _OPENER_KINDS
            and _opener_name(control.get("name"))
            and "expanded" not in str(control.get("state") or "").split() and not _is_switch(control)
            and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
            and (_inside_the_page(view, control) if framed else _of_the_page(view, control))
        ):
            return control
    return None


def _click(control: dict, reason: str) -> dict[str, object]:
    arguments: dict[str, object] = {"label": str(control.get("name") or "")}
    if isinstance(control.get("i"), int):
        arguments["index"] = control["i"]
    return {"operation": "input.visible.click", "arguments": arguments, "reason": reason}


def _type_into(view: dict, history: list[dict], target: str) -> dict[str, object] | None:
    """Typing the name into the search field in focus; a search field that still holds an earlier text is selected
    whole first, so the name replaces it (measured on Settings: «colores» appended to a leftover «colorespantalla»).
    One that already holds the name is not typed into again: its results are picked, else the name is selected and
    typed once more so the search runs. Select-all only in a field named as a search (in a document editor exposed as
    a text field it would select the person's work); a field without a search name that holds text is left to the
    model."""

    focused = _focused_field(view)
    held = str((focused or {}).get("value") or "").strip()
    if not held:
        return _type(target)
    if not _is_search_field(focused or {}):
        return None
    last = history[-1] if history and isinstance(history[-1], dict) else {}
    if last.get("operation") == "input.key.press" and last.get("key") == "ctrl_a":
        return _type(target)
    if fold(held) == fold(target):
        picked = _result_naming(view, target, history)
        if picked is not None:
            return picked
    return _key("ctrl_a")


REASON_SEARCH_FOCUS_UNPROVEN = "el clic en el cuadro de búsqueda escrito no probó que tomara el teclado: no se escribe nada"
SEARCH_FOCUS_UNPROVEN = "search_focus_unproven"


def _search_line_appeared(view: dict, clicked: str = "") -> str | None:
    """A written search prompt the last act made appear (a box that opened or took the caret: «Q Buscar por nombre»),
    other than the line just clicked."""

    for line in view.get("newText") or []:
        line = str(line).strip()
        if 0 < len(line.split()) <= 8 and _is_search_field({"name": line}) and fold(line) != fold(clicked):
            return line
    return None


def _written_box_took_keyboard(view: dict, label: str) -> bool:
    """The next look after a click on a search box's written line proves it took the keyboard: a written search prompt
    appeared with the click, or the clicked line is gone (its placeholder cleared for the caret) while the rest of the
    window stayed (a few new lines at most: a window that went elsewhere is no box with the caret)."""

    if _search_line_appeared(view, label) is not None:
        return True
    appeared = view.get("newText")
    if not isinstance(appeared, list) or not label.strip() or len(appeared) > 3:
        return False
    return _text_line_with(view, label) is None and bool(_view_lines(view))


def _keyboard_on_another_field(view: dict) -> bool:
    """The view reports the keyboard on a field that is not a search: a message box (whatever its kind), a password,
    or a text field named otherwise. Typing a name there would write into it, or send it with the next Enter."""

    focused = _focused(view)
    candidates = [focused] if focused is not None else []
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        candidates += [
            control for control in controls
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        ]
    for control in candidates:
        if "password" in str(control.get("state") or ""):
            return True
        name = fold(control.get("name"))
        if _COMPOSER_NAME.search(name) and not _is_search_field(control):
            return True
        if control.get("kind") in _FIELD_KINDS and not _is_search_field(control):
            return True
    return False


def _typed_into_written_search(view: dict, history: list[dict]) -> bool:
    """The last step typed into a written search box whose keyboard was proven (the step before it was a search key or
    a click on a search's written line) and the text now shows as that box's new line, with no other field reporting
    the keyboard: the Enter that follows submits the search."""

    if len(history) < 2 or _keyboard_on_another_field(view):
        return False
    typed, before = history[-1], history[-2]
    if typed.get("operation") != "input.text.type" or typed.get("ok") is not True or before.get("ok") is not True:
        return False
    searched = (
        (before.get("operation") == "input.key.press" and before.get("key") in _SEARCH_KEYS)
        or (before.get("operation") == "input.visible.click" and _is_search_field({"name": before.get("label")})
            and not isinstance(before.get("index"), int))
    )
    text = fold(typed.get("text")).strip(" «»\"'")
    if not searched or not text:
        return False
    # The box's own line: the typed text alone, after at most a drawn magnifier («Q Cuphead»).
    return any(
        re.fullmatch(rf"(?:\S{{1,2}}\s+)?{re.escape(text)}", fold(line).strip()) is not None
        for line in view.get("newText") or []
    )


def _type(target: str) -> dict[str, object]:
    return {"operation": "input.text.type", "arguments": {"text": typed_text(target)}, "reason": _REASON_FIND}


def _key(key: str) -> dict[str, object]:
    return {"operation": "input.key.press", "arguments": {"key": key}, "reason": _REASON_FIND}


def _result_naming(view: dict, target: str, history: list[dict]) -> dict[str, object] | None:
    """The result of a search that names the target: a control (list item, tree item, button, link first), else a
    line of text, preferring one that is more than the typed name (the field's own echo). Never Enter: a voice
    channel stays a click RiskPolicy confirms. Never a switch (going to a place changes no setting on the way)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    named = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") not in _FIELD_KINDS and control.get("kind") != "Document"
        and not _is_switch(control)
        and label_names(target, str(control.get("name") or ""))
        and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
        and _of_the_page(view, control)
    ]
    if named:
        # A result first (a list item, a link…), and among the results the one that is exactly the name: «Ñuñoa del
        # Mar» before «Festival de Ñuñoa», never the place whose name only contains it.
        named.sort(key=lambda control: (
            control.get("kind") not in _RESULT_KINDS,
            fold(control.get("name")) != fold(target),
            _RESULT_KINDS.index(str(control.get("kind"))) if control.get("kind") in _RESULT_KINDS else len(_RESULT_KINDS),
        ))
        return _click(named[0], "el resultado de la búsqueda")
    # A line equal to the typed name is the field's own echo as often as a result; the new lines first.
    for lines in ([str(line) for line in (view.get("newText") or [])], _view_lines(view)):
        for line in lines:
            if (
                label_names(target, line) and fold(line) != fold(target)
                and not _steps_ok(history, "input.visible.click", label=line.strip())
                and not _names_a_switch(view, line.strip())
            ):
                return {"operation": "input.visible.click", "arguments": {"label": line.strip()}, "reason": "el resultado de la búsqueda"}
    return None


def _view_lines(view: dict) -> list[str]:
    text = view.get("text") if isinstance(view, dict) else None
    if not isinstance(text, dict):
        return []
    return [str(line) for zone_lines in text.values() if isinstance(zone_lines, list) for line in zone_lines]


def _find_step(target: str, view: dict, history: list[dict], *, navigate: bool = True) -> dict[str, object] | None:
    """The next step of looking the target up when it is not on screen, from the view and this sub-goal's history
    alone, the same in any application: a search field or button (click, type the name, click the result naming it),
    else the window's navigation or menu button (the target is then looked for among what appeared), else ctrl_k and
    ctrl_f (kept only when a field takes the keyboard, otherwise escape), else scrolling the list that
    may hold it (up to three times while the view changes). The navigation button only when ``navigate`` (going to a
    place; a search is the window's search). None leaves the step to the model."""

    last = history[-1] if history else None
    last_operation = last.get("operation") if last is not None else None
    if last is not None and last_operation == "input.text.type" and fold(last.get("text")) == fold(target):
        # The name was just typed: its result, or the search closed to try the next way.
        return _result_naming(view, target, history) or _key("escape")
    if _typed_target(history, target):
        picked = _result_naming(view, target, history)
        if picked is not None:
            return picked
    if last is not None and last_operation == "input.key.press" and last.get("key") in _SEARCH_KEYS:
        if _focused_field(view) is not None:
            return _type_into(view, history, target)
        if _search_line_appeared(view) is not None and not _keyboard_on_another_field(view):
            # The key brought up a written search prompt (measured on Steam's library: ctrl_f wrote «Q Buscar por
            # nombre» where only a magnifier was drawn, with no tree to report the focus): that box has the keyboard.
            return _type_into(view, history, target)
        if view.get("newText") != [] or _focused(view) is not None:
            return _key("escape")
        # The key changed nothing on screen (no line appeared): there is nothing to close, and an Escape would only
        # spend a look that changes nothing (measured on Steam: ctrl_k and Escape left the screen still twice and the
        # mission stopped before ctrl_f); the next way is tried.
    if last is not None and last_operation == "input.visible.click":
        clicked = find_control(view, str(last.get("label") or ""))
        # A search box clicked by its written line (no tree to tell focus) takes the keyboard as a person expects.
        written_box = clicked is None and last.get("ok") is True and not isinstance(last.get("index"), int)
        # A field the receipt says was clicked keeps the caret when the next look no longer lists it (a pop-up of
        # its suggestions or history came up over it): a person types now, never picks a suggestion as the search.
        hidden_field = clicked is None and last.get("ok") is True and last.get("kind") in _FIELD_KINDS
        # A search button that changed the window opened its box (measured on Discord: «Buscar o iniciar una
        # conversación» opens the quick switcher, whose field the tree does not report focused): a person types now.
        opened_box = (
            clicked is not None and last.get("ok") is True and clicked.get("kind") in {"Button", "SplitButton", "MenuItem"}
            and (last.get("surfaceChanged") is True or bool(view.get("newText")))
        )
        if _is_search_field({"name": last.get("label")}) and (
            _focused_field(view) is not None or (clicked is not None and clicked.get("kind") in _FIELD_KINDS)
            or opened_box or hidden_field
        ):
            return _type_into(view, history, target)
        if _is_search_field({"name": last.get("label")}) and written_box:
            # A box clicked by its written line (no tree to tell focus) takes the name only when the next look proves
            # it has the keyboard (its line changed); otherwise the name could land in a message box or another field.
            if _keyboard_on_another_field(view) or not _written_box_took_keyboard(view, str(last.get("label") or "")):
                return _none(REASON_SEARCH_FOCUS_UNPROVEN, code=SEARCH_FOCUS_UNPROVEN)
            return _type_into(view, history, target)
    searched = _typed_target(history, target)
    if not searched:
        focused = _focused_field(view)
        if focused is not None and _is_search_field(focused):
            return _type_into(view, history, target)
        affordance = _search_affordance(view, history)
        if affordance is not None:
            return _click(affordance, _REASON_FIND)
    opener = _navigation_opener(view, history) if navigate else None
    if opener is not None:
        # Modes, sections and pages often live behind the window's navigation or menu button (the Calculator's
        # modes, a WinUI app's pages, a web app's «Menú»): opened before any blind shortcut, and the target is then
        # looked for among what appeared.
        return _click(opener, "el destino no está en pantalla: abro la navegación")
    # In a web browser ctrl_k searches the web from the address bar, not the page: only the page's find (ctrl_f).
    keys = ("ctrl_f",) if _web_browser(view) else _SEARCH_KEYS
    for key in keys:
        if not any(step.get("operation") == "input.key.press" and step.get("key") == key for step in history):
            return _key(key)
    return _scroll_step(view, history)


def _scroll_step(view: dict, history: list[dict]) -> dict[str, object] | None:
    scrolls = [step for step in history if step.get("operation") == "input.scroll"]
    if len(scrolls) >= _SCROLLS or any(
        step.get("ok") is not True or step.get("changed") is False or step.get("surfaceChanged") is False
        for step in scrolls
    ):
        return None
    arguments: dict[str, object] = {"direction": "down", "amount": 5}
    holder = _list_holding_items(view)
    if holder is not None:
        arguments["index"] = holder
    return {"operation": "input.scroll", "arguments": arguments, "reason": _REASON_FIND}


def _inside(inner: object, outer: object) -> bool:
    if not isinstance(inner, dict) or not isinstance(outer, dict):
        return False
    try:
        x, y = float(inner["x"]) + float(inner["w"]) / 2, float(inner["y"]) + float(inner["h"]) / 2
        return float(outer["x"]) <= x <= float(outer["x"]) + float(outer["w"]) and float(outer["y"]) <= y <= float(outer["y"]) + float(outer["h"])
    except (KeyError, TypeError, ValueError):
        return False


def _list_holding_items(view: dict) -> int | None:
    """The index of the list (or pane) holding the most items of the view, by their rectangles; the first list when
    the view carries no rectangles; None when there is no list."""

    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    items = [control for control in controls if control.get("kind") in _ITEM_KINDS]
    best: tuple[int, int] | None = None
    first_list: int | None = None
    for control in controls:
        if not isinstance(control.get("i"), int):
            continue
        kind = control.get("kind")
        if kind in _LIST_KINDS and first_list is None:
            first_list = control["i"]
        if kind not in _LIST_KINDS and kind != "Pane":
            continue
        held = sum(1 for item in items if _inside(item.get("rect"), control.get("rect")))
        if (kind in _LIST_KINDS or held >= 3) and held and (best is None or held > best[0]):
            best = (held, control["i"])
    return best[1] if best is not None else first_list


def _menu_opened_by(view: dict, history: list[dict], target: str, goal: str = "") -> str | None:
    """The entry of the short menu the last click, made on ``target``, opened that the goal's words name best, else
    the place's own page, else its first entry when the menu is in the tree; never an entry that does something
    (play, install, send…). None when no menu opened or none of those holds."""

    # The last verified click: a failed step after it (a learned entry no longer on the menu, measured on Steam: the
    # replayed click was ambiguous and the model answered none) leaves the menu it opened on screen.
    verified = [step for step in history if isinstance(step, dict) and step.get("ok") is True]
    last = verified[-1] if verified else None
    if last is None or last.get("operation") != "input.visible.click":
        return None
    trailing = history[history.index(last) + 1:]
    if any(isinstance(step, dict) and step.get("operation") != "input.visible.click" for step in trailing):
        return None
    clicked = str(last.get("label") or "")
    if not (label_names(target, clicked) or label_names(clicked, target)):
        return None
    # What the verified click made appear: after failed clicks the view's newText is what the last look changed
    # (nothing, for a click that changed nothing), so the App's newTextAfterClick (the look right after the last
    # verified click) is read instead; without it the menu cannot be told.
    if trailing:
        after_click = view.get("newTextAfterClick")
        if not isinstance(after_click, list):
            return None
        new_lines = after_click
    else:
        new_lines = view.get("newText") or []
    # A menu's entries are short new lines; the OCR also rereads, garbled, the long lines the menu now covers.
    # OCR noise (a cut word, an address, a mark) is not an entry: an entry is a short run of real words.
    appeared = [
        str(line).strip() for line in new_lines
        if str(line).strip() and len(str(line).split()) <= 3 and len(str(line)) <= 30
        and re.fullmatch(r"[^\W\d_][\w'’.-]*(?:\s+[\w'’.-]+){0,2}", str(line).strip()) is not None
        and "://" not in str(line) and len(fold(line).replace(" ", "")) >= 3
    ]
    if not 1 < len(appeared) <= 8:
        return None
    entries = [
        entry for entry in appeared
        if not label_names(clicked, entry) and not _steps_ok(history, "input.visible.click", label=entry)
        and _ACT_ENTRY.search(fold(entry)) is None
    ]
    # «colecciones de la biblioteca» after a click on «Biblioteca»: the goal's other words name the entry.
    words = [word for word in fold(goal).split() if len(word) >= 4 and not label_names(word, clicked)]
    scored = sorted(
        ((sum(1 for word in words if label_names(word, entry)), position) for position, entry in enumerate(entries)),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if scored and scored[0][0] > 0:
        return entries[scored[0][1]]
    # No word of the goal names an entry: the destination's own page when the menu offers one by that name
    # (measured on Steam: «BIBLIOTECA» → «Página principal»), else the first entry only when the menu is in the tree
    # (its entries are menu or list items that appeared together); never a blind click on a written line.
    home = next((entry for entry in entries if _HOME_ENTRY.fullmatch(fold(entry).strip()) is not None), None)
    if home is not None:
        return home
    first = appeared[0]
    return first if first in entries and _menu_in_tree(view, appeared) else None


# The entry of a place's menu that is the place's own page.
_HOME_ENTRY = re.compile(
    r"(?:pagina\s+principal|principal|inicio|home|home\s+page|main|main\s+page|overview|vista\s+general|resumen)"
)
# An entry that does something instead of going somewhere: never chosen by default.
_ACT_ENTRY = re.compile(
    r"(?<!\w)(?:jugar|play|instalar|install|iniciar|launch|ejecutar|run|comprar|buy|enviar|send|unirse|join|"
    r"desinstalar|uninstall|eliminar|delete)(?!\w)"
)
_MENU_ENTRY_KINDS = frozenset({"MenuItem", "ListItem"})


def _menu_in_tree(view: dict, appeared: list[str]) -> bool:
    """Every appeared entry is a menu or list item of the view's controls: the menu is in the tree."""

    controls = view.get("controls") if isinstance(view, dict) else None
    named = {
        fold(control.get("name")).strip() for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and str(control.get("kind")) in _MENU_ENTRY_KINDS
    }
    return bool(appeared) and all(fold(entry).strip() in named for entry in appeared)


def decide_step(
    llm: Any,
    *,
    objective: str,
    goal: str,
    application: str | None,
    success_check: str | None,
    view: dict,
    history: list[dict],
    budget_left: int,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    subgoal: int = 0,
    subgoal_count: int = 1,
) -> dict[str, object]:
    """One step for the shell: {operation, arguments, reason}; operation is a
    catalog primitive, «done» or «none». In a chained mission ``goal``,
    ``application`` and ``success_check`` are the current sub-goal's
    (``subgoal`` of ``subgoal_count``, 0-based) and ``history`` its steps."""

    # «… y decime si está activado» rides on a single mission's goal for the final to answer; the steps are the
    # goal's, never the question's («escribir hola; y responder: …» types «hola»).
    goal = goal.split(QUESTION_MARK, 1)[0]
    # Deterministic first: the application named by the request is not in
    # front and nothing was done yet → bring it to the front (app.open reuses a
    # running window). No model needed for what the request already says.
    if application and not history and not application_is_in_front(view, application):
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
        if app_id is not None:
            return {"operation": "app.open", "arguments": {"appId": app_id}, "reason": "la aplicación pedida no está delante"}
    dictated = deterministic_step(goal=goal, view=view, history=history, application=application, objective=objective)
    if dictated is not None:
        return dictated
    last_failed = history[-1] if history and isinstance(history[-1], dict) and history[-1].get("ok") is False else None
    user = (
        f"Pedido: {objective}\n"
        + (f"Sub-objetivo {subgoal + 1} de {subgoal_count}\n" if subgoal_count > 1 else "")
        + f"Objetivo: {goal}"
        + (f"\nAplicación: {application}" if application else "")
        + (f"\nSe cumple cuando: {success_check}" if success_check else "")
        + f"\nPasos que quedan: {budget_left}\n"
        + ("Historial:\n" + "\n".join(_history_line(step) for step in history[-6:]) + "\n" if history else "")
        + "Vista:\n" + compact_view_text(view, goal=goal)
    )
    payload = {
        "messages": [
            {"role": "system", "content": STEP_PROMPT},
            {"role": "user", "content": user},
        ],
        "grammar": STEP_GRAMMAR,
        "temperature": 0.0,
        "max_tokens": 160,
        "cache_prompt": True,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    raw = _model_step(llm, payload)
    if raw is None:
        return _none("el modelo no dio un paso legible", code="decision_unreadable")
    decision = validate_decision(raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal)
    if decision["operation"] == "none" and decision.get("code") in _RETRIED:
        # One more try with the rejection in front of the model (contract §4.4).
        payload["messages"].append({"role": "assistant", "content": as_json(raw)})
        payload["messages"].append({"role": "user", "content": f"Ese paso no vale: {decision['reason']}. Elegí otro acto de la vista, o none si no hay ninguno."})
        raw = _model_step(llm, payload)
        if raw is None:
            return _none("el modelo no dio un paso legible", code="decision_unreadable")
        decision = validate_decision(raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal)
    return decision


def _model_step(llm: Any, payload: dict) -> Any:
    """One strict-JSON step from the model; one more try when the reply cannot be read (measured live: a reply cut
    short left the shell without any step)."""

    for _ in range(2):
        try:
            return llm._post_schema_object(payload, "el paso de computer use")
        except (ValueError, RuntimeError, KeyError, TypeError, OSError):
            continue
    return None


def _history_line(step: dict) -> str:
    parts = [f"{step.get('step')}. {step.get('operation')}"]
    for key in _ACT_KEYS:
        if step.get(key):
            parts.append(f"{key}={str(step.get(key))[:40]}")
    parts.append("ok" if step.get("ok") else f"FALLÓ ({step.get('error') or 'sin efecto'})")
    return " ".join(parts)


def _destination(goal: str | None) -> str:
    """«ir a la biblioteca» → «biblioteca»: the place a go-to goal names, folded; empty for other goals."""

    folded = fold(goal or "")
    if not folded.startswith("ir a "):
        return ""
    return re.sub(r"^(?:el|la|los|las|the|al)\s+", "", folded[len("ir a "):]).strip()


# The refusals the model gets one more try at, with the refusal in front of it (contract §4.4).
_RETRIED = frozenset({
    "label_not_visible", "evidence_not_visible", "already_open", "application_unknown", "control_covers_window",
    "no_progress", "opens_elsewhere", "changes_a_setting", "changes_the_tool",
})
# A control that opens another tab or window: the mission's window would stop being the one in front (measured on
# Opera: the model clicked «Nueva pestaña» while searching a page and the mission went on in an empty tab).
_OPENS_ELSEWHERE = re.compile(
    r"\b(?:(?:nueva|nuevo|new)\s+(?:pestana|ventana|tab|window)|(?:pestana|ventana)\s+nueva|open\s+in\s+new)\b"
)
_ELSEWHERE_WORDS = re.compile(r"\b(?:pestana|ventana|tab|window)s?\b")
# A control this much of its window is the window's body (a document, a web view, a canvas), not a place to go.
_COVERS_WINDOW = 0.8


_SWITCH_KINDS = frozenset({"CheckBox", "RadioButton", "ToggleButton", "Slider"})


def _is_switch(control: dict) -> bool:
    """A control that sets something when pressed: a check box, a radio button, a toggle or a slider, or any control
    shown on/off/checked."""

    state = str(control.get("state") or "").split()
    # A button named as the act of switching («Alternar grados», «Toggle units») switches even without a state
    # (measured on the Calculator: going to «Científica» the model pressed «Alternar grados» and DEG became RAD).
    name = fold(control.get("name"))
    # «Alternar navegación» / «Toggle navigation» opens a menu: it shows places, it sets nothing.
    toggles = re.match(r"(?:alternar|cambiar entre|toggle|switch between)\b", name) is not None and re.search(
        r"\b(?:navegacion|navigation|menu|panel|pane|barra lateral|sidebar)\b", name
    ) is None
    return control.get("kind") in _SWITCH_KINDS or toggles or any(word in {"on", "off", "checked", "unchecked"} for word in state)


def validate_decision(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    history: list[dict] | None = None,
    goal: str | None = None,
) -> dict[str, object]:
    """The model's act, checked against the view without any model (contract §4.4): a click on a control that
    covers the window, or an act that repeats the last two that changed nothing, is refused too."""

    decision = _checked_act(
        raw, view=view, last_failed=last_failed, application_names=application_names, history=history, goal=goal,
    )
    if decision["operation"] == "input.visible.click" and _covers_window(view, decision["arguments"]):
        return _none("ese control ocupa casi toda la ventana; elegí uno concreto", code="control_covers_window")
    if _repeats_without_progress(decision, history or [], view):
        return _none("repetiría por tercera vez un paso que no hizo aparecer nada", code="no_progress")
    return decision


def _covers_window(view: dict, arguments: object) -> bool:
    window = view.get("window") if isinstance(view, dict) else None
    controls = view.get("controls") if isinstance(view, dict) else None
    index = arguments.get("index") if isinstance(arguments, dict) else None
    label = str(arguments.get("label") or "") if isinstance(arguments, dict) else ""
    if not isinstance(window, dict) or not isinstance(controls, list):
        return False
    if isinstance(index, int):
        control = next((item for item in controls if isinstance(item, dict) and item.get("i") == index), None)
    else:
        # A click by label alone on the name of the window's body (measured on a web view: «Chrome Legacy Window»,
        # the only control of the tree) is the same click.
        control = next((item for item in controls if isinstance(item, dict) and label and fold(item.get("name")) == fold(label)), None)
        if control is not None and control.get("kind") not in {"Pane", "Document", "Window", "Custom", "Group"}:
            return False
    outer, inner = window.get("rect"), control.get("rect") if control is not None else None
    if not isinstance(outer, dict) or not isinstance(inner, dict):
        return False
    try:
        window_area = float(outer["w"]) * float(outer["h"])
        width = min(float(inner["x"]) + float(inner["w"]), float(outer["x"]) + float(outer["w"])) - max(float(inner["x"]), float(outer["x"]))
        height = min(float(inner["y"]) + float(inner["h"]), float(outer["y"]) + float(outer["h"])) - max(float(inner["y"]), float(outer["y"]))
    except (KeyError, TypeError, ValueError):
        return False
    return window_area > 0 and width > 0 and height > 0 and width * height >= _COVERS_WINDOW * window_area


_ACT_KEYS = ("label", "key", "text", "direction", "appId")


def _repeats_without_progress(decision: dict[str, object], history: list[dict], view: dict) -> bool:
    """The act equals the last two steps, both done, and nothing new appeared on screen after them."""

    if decision["operation"] in {"none", "done"} or len(history) < 2 or view.get("newText"):
        return False
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    return all(
        isinstance(step, dict) and step.get("ok") is True and step.get("operation") == decision["operation"]
        and all(fold(step.get(key)) == fold(arguments.get(key)) for key in _ACT_KEYS)
        for step in history[-2:]
    )


def _checked_act(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    history: list[dict] | None,
    goal: str | None,
) -> dict[str, object]:
    if not isinstance(raw, dict):
        return _none("respuesta inválida del modelo")
    act = str(raw.get("act") or "")
    why = str(raw.get("why") or "")[:160]
    if act == "done":
        evidence = str(raw.get("evidence") or "").strip()
        destination = _destination(goal)
        if destination and fold(evidence).strip(" «»\"'") in {destination, f"la {destination}", f"el {destination}"}:
            # Measured on Steam: «BIBLIOTECA» is on screen before and after the click (it opened a menu); the
            # destination's own name proves nothing. Something of the page reached must be cited.
            return _none("el nombre del destino ya estaba en pantalla antes; citá algo de lo que se ve al llegar",
                         code="evidence_not_visible")
        if evidence and _echoes_typing(evidence, history or [], contained=not fold(goal or "").startswith("escribir ")):
            # What was typed is on screen because it was typed (the search box's echo, a title that repeats the
            # search: «imagenes - Resultados de la búsqueda en ETC»), never proof of arriving.
            return _none("lo que escribí se ve porque lo escribí; citá algo del resultado", code="evidence_not_visible")
        if evidence and view_contains(view, evidence):
            return {"operation": "done", "arguments": {"evidence": evidence}, "reason": why}
        return _none("la evidencia citada no está en la vista", code="evidence_not_visible")
    if act == "click":
        label = str(raw.get("label") or raw.get("text") or "").strip()
        index = raw.get("i") if isinstance(raw.get("i"), int) and not isinstance(raw.get("i"), bool) else None
        if not label and index is not None:
            controls = view.get("controls") if isinstance(view, dict) else None
            if isinstance(controls, list) and 0 <= index < len(controls) and isinstance(controls[index], dict):
                label = str(controls[index].get("name") or "")
        if not label:
            return _none("el clic no nombra ningún control")
        control = find_control(view, label, index)
        clicked = str(control.get("name") or label) if control is not None else label
        if _OPENS_ELSEWHERE.search(fold(clicked)) and not _ELSEWHERE_WORDS.search(fold(goal)):
            return _none(f"«{clicked[:40]}» abre otra pestaña o ventana y el objetivo no lo pide", code="opens_elsewhere")
        named_explicitly = fold(goal or "").startswith("hacer clic en ") and (
            label_names(_goal_target(goal or "")[2] if _goal_target(goal or "") else "", clicked)
        )
        changes_the_account = account_act(clicked)
        place = _PLACE_NAMED.match(fold(goal or ""))
        # The control IS the place (its whole name), never a control that only mentions it («Seguir a Tu biblioteca»).
        goes_there = place is not None and _POSSESSIVE.sub("", fold(clicked)).strip() == place.group("place").strip()
        if changes_the_account is not None and not goes_there and not goal_asks_for(goal or "", changes_the_account):
            # Live z7 (going to «Tu biblioteca» on a music app): the model followed a profile and saved a playlist in
            # the person's account. Following, saving, liking, subscribing or installing is theirs to ask for.
            return _none(f"«{clicked[:40]}» cambia tu cuenta y el objetivo no lo pide", code="changes_the_account")
        if colour_goal(goal) is not None and changes_the_tool(clicked):
            # Choosing a colour never picks a tool (live e2: the model clicked «Selector de colores», the eyedropper,
            # and the canvas's next click would have picked a colour from the drawing instead).
            return _none(f"«{clicked[:40]}» cambia de herramienta y el objetivo es elegir un color", code="changes_the_tool")
        if control is not None and _placing_goal(goal) and _is_switch(control) and not named_explicitly:
            # Going somewhere never changes a setting on the way (measured on Settings: looking for «Colores» the
            # model clicked «Invertir colores» of the Magnifier).
            return _none(f"«{clicked[:40]}» cambia un ajuste y el objetivo no pide cambiar ninguno", code="changes_a_setting")
        setting = _SETTING_GOAL.match(fold(goal or ""))
        if control is not None and setting is not None and _is_switch(control) and not named_explicitly and not (
            label_names(setting.group("what"), clicked) or label_names(clicked, setting.group("what"))
        ):
            # Setting or choosing one thing never flips another switch on the way (live y1: for «activar modo
            # programador» the model clicked the Calculator's «Alternar grados» and left it in radians).
            return _none(f"«{clicked[:40]}» cambia otro ajuste que el objetivo no nombra", code="changes_a_setting")
        if control is not None:
            arguments: dict[str, object] = {"label": str(control.get("name") or label)}
            if isinstance(control.get("i"), int):
                arguments["index"] = control["i"]
            return _guard_repeat({"operation": "input.visible.click", "arguments": arguments, "reason": why}, last_failed)
        line = _text_line_with(view, label)
        if line is not None:
            return _guard_repeat({"operation": "input.visible.click", "arguments": {"label": label}, "reason": why}, last_failed)
        return _none(f"«{label[:40]}» no está en la vista", code="label_not_visible")
    if act == "type":
        text = typed_text(str(raw.get("text") or ""))
        if not text.strip():
            return _none("no hay texto que escribir")
        if _focused_is_password(view):
            return _none("el campo enfocado es una contraseña", code="password_field")
        if fold(goal or "").startswith("buscar ") and _keyboard_on_another_field(view):
            # A search's name never goes into a message box or another field that has the keyboard.
            return _none("el teclado está en un campo que no es la búsqueda", code="search_focus_unproven")
        return _guard_repeat({"operation": "input.text.type", "arguments": {"text": text[:4096]}, "reason": why}, last_failed)
    if act == "key":
        key = str(raw.get("key") or "")
        if key not in KEYS:
            return _none("tecla fuera del catálogo")
        # A calculation's Enter after typing the expression is the calculator's (no message box there).
        typed = None if fold(goal or "").startswith("calcular ") else history
        return _guard_repeat({"operation": "input.key.press", "arguments": key_arguments(key, view, typed), "reason": why}, last_failed)
    if act == "scroll":
        direction = str(raw.get("direction") or "down")
        if direction not in {"down", "up"}:
            direction = "down"
        return _guard_repeat({"operation": "input.scroll", "arguments": {"direction": direction, "amount": 3}, "reason": why}, last_failed)
    if act == "open":
        application = str(raw.get("application") or "").strip()
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names) if application else None
        if app_id is None:
            return _none("la aplicación no está en el catálogo", code="application_unknown")
        if history and _steps_ok(history, "app.open", appId=app_id):
            return _none("esa aplicación ya está abierta", code="already_open")
        return _guard_repeat({"operation": "app.open", "arguments": {"appId": app_id}, "reason": why}, last_failed)
    return _none(why or "el modelo no ve por dónde seguir")


def _echoes_typing(evidence: str, history: list[dict], *, contained: bool = True) -> bool:
    """The evidence is a text typed in this sub-goal, or (``contained``) holds one as whole words while no verified
    click after that typing moved the window elsewhere: what is on screen then may be there only because it was
    typed. A goal of writing a text is proved by the text, so it only refuses the bare echo."""

    cited = fold(evidence).strip(" «»\"'")
    for position, step in enumerate(history):
        if not isinstance(step, dict) or step.get("operation") != "input.text.type":
            continue
        typed = fold(step.get("text")).strip()
        if not typed:
            continue
        if cited == typed:
            return True
        moved = any(
            isinstance(later, dict) and later.get("ok") is True and later.get("changed") is not False
            and later.get("operation") in {"input.visible.click", "app.open"}
            for later in history[position + 1:]
        )
        if contained and len(typed) >= 3 and not moved and re.search(rf"(?<!\w){re.escape(typed)}(?!\w)", cited):
            return True
    return False


def _guard_repeat(decision: dict[str, object], last_failed: dict | None) -> dict[str, object]:
    if last_failed is None or last_failed.get("operation") != decision["operation"]:
        return decision
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    same = all(
        fold(last_failed.get(key)) == fold(arguments.get(key))
        for key in _ACT_KEYS
        if key in arguments or key in last_failed
    )
    return _none("repetiría el paso que acaba de fallar", code="repeated_step") if same else decision


def _none(reason: str, *, code: str = "no_step_visible") -> dict[str, object]:
    return {"operation": "none", "arguments": {}, "reason": reason, "code": code}


# --------------------------------------------------------------- compositor


def describe_step(step: dict, language: str) -> str:
    operation = str(step.get("operation") or "")
    if operation == "input.visible.click":
        return (f"clicked «{step.get('label')}»" if language == "en" else f"clic en «{step.get('label')}»")
    if operation == "input.key.press":
        return (f"pressed {step.get('key')}" if language == "en" else f"tecla {step.get('key')}")
    if operation == "input.text.type":
        return "typed the text" if language == "en" else "escribió el texto"
    if operation == "input.scroll":
        return "scrolled" if language == "en" else "desplazó la vista"
    if operation == "app.open":
        return "brought the application to the front" if language == "en" else "trajo la aplicación al frente"
    return operation


# The typed stop reasons as facts the final can state (the model words them; «operación» is a forbidden term in finals,
# so no cause says it). Data shared with the App's floor (operation_floor.v1.json «computerUse.causes»).
_STOP_CAUSES: dict[str, dict[str, str]] = operation_floor.floor_data()["computerUse"]["causes"]


def project_seen(observed: dict, language: str) -> dict[str, object]:
    """What the composer may say about a mission: only what the loop observed."""

    raw_steps = observed.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    done = [step for step in steps if isinstance(step, dict) and step.get("ok") is True]
    failed = [step for step in steps if isinstance(step, dict) and step.get("ok") is not True]
    raw_window = observed.get("window")
    window: dict[str, Any] = raw_window if isinstance(raw_window, dict) else {}
    goal = observed.get("goal")
    question = None
    if isinstance(goal, str) and QUESTION_MARK in goal:
        # «… y decime si el modo es claro u oscuro»: the person's question about the window at the end.
        goal, question = goal.split(QUESTION_MARK, 1)
    seen: dict[str, object] = {
        "goal": goal,
        "reached": observed.get("reached") is True,
        "stepsDone": [describe_step(step, language) for step in done][:8],
        "windowTitle": window.get("title"),
        "joined": observed.get("joined") is True,
    }
    if question:
        seen["question"] = question
    if observed.get("application"):
        seen["application"] = observed.get("application")
    if failed:
        seen["stepsFailed"] = [describe_step(step, language) for step in failed][:4]
    if observed.get("evidence"):
        seen["evidence"] = observed.get("evidence")
    if observed.get("satisfiedBy"):
        seen["satisfiedBy"] = observed.get("satisfiedBy")
    shade = _chosen_shade(goal, done) if seen["reached"] else None
    if shade is not None:
        seen["chosenShade"] = shade
    if isinstance(observed.get("screen"), dict):
        seen["screen"] = observed.get("screen")
    cover = window.get("coveredBy")
    if isinstance(cover, dict) and (cover.get("title") or cover.get("process")):
        seen["coveredBy"] = str(cover.get("title") or cover.get("process"))
    if observed.get("stoppedBy"):
        seen["stoppedBy"] = observed.get("stoppedBy")
        seen["stoppedBecause"] = _STOP_CAUSES.get(str(observed.get("stoppedBy")), {}).get(
            "en" if language == "en" else "es", str(observed.get("stoppedBy")).replace("_", " ")
        )
        if observed.get("stoppedBy") == "computer_use_window_covered" and seen.get("coveredBy"):
            seen["stoppedBecause"] = operation_floor.floor_data()["computerUse"]["coveredBy"][
                "en" if language == "en" else "es"
            ].format(window=seen["coveredBy"])
        missing = _floor_name(observed.get("missingPlace"))
        if observed.get("stoppedBy") == "computer_use_place_not_found" and missing:
            # Searched by name in the window and not found (live n5: «Wi-Fi» on a PC without Wi-Fi).
            floor = operation_floor.floor_data()
            lang = "en" if language == "en" else "es"
            seen["stoppedBecause"] = floor["computerUse"]["placeNotFound"][lang].format(
                place=floor["templates"][lang]["quote"].format(value=missing)
            )
    if observed.get("procedure") in {"replayed", "learned", "relearned"}:
        seen["procedure"] = observed.get("procedure")
    raw_subgoals = observed.get("subgoals")
    if isinstance(raw_subgoals, list) and raw_subgoals:
        subgoals = [
            {"goal": item.get("goal"), "application": item.get("application"), "reached": item.get("reached") is True}
            for item in raw_subgoals[:8] if isinstance(item, dict)
        ]
        seen["subgoals"] = subgoals
        unreached = next((item for item in subgoals if not item["reached"]), None)
        if unreached is not None:
            seen["firstUnreached"] = unreached["goal"]
    return seen


def _chosen_shade(goal: object, done: list[dict]) -> dict[str, str] | None:
    """{asked, chosen}: the colour the goal chose and the swatch clicked for it when that swatch is one of its shades
    («Añil» for «azul»), from the last verified click; None otherwise."""

    asked = colour_goal(goal) if isinstance(goal, str) else None
    if asked is None:
        return None
    for step in reversed(done):
        if step.get("operation") != "input.visible.click":
            continue
        for value in (step.get("name"), step.get("label")):
            if isinstance(value, str) and shade_of(asked, value):
                return {"asked": asked, "chosen": " ".join(value.split())}
        return None
    return None


def compose_instruction(seen: dict, language: str) -> str:
    del language
    return _question_instruction(seen) + _result_instruction(seen)


def _question_instruction(seen: dict) -> str:
    if not seen.get("question"):
        return ""
    return (
        "seen.question is what the person asked about the window once the mission was done: answer it FIRST, "
        "only from seen.screen and seen.evidence, saying the value written there; when they do not show the answer, "
        "or the mission did not reach its goal, say you could not see it, never guess. Then: "
    )


# The voice of a mission final is BAXY's own (documentacion/00_IDENTIDAD.md): a companion who confirms the observable
# state, warm and brief, speaking informally to the person; a failure is said plainly with its cause, without apology.
_SPEAKER = (
    "Speak as the one who acted, in the FIRST PERSON (never the third person, never your own name, never «you» for "
    "your own acts), informally and warmly, in the person's language, in {length}. "
)
# What the final confirms depends on what the goal's check read: a place reached or a value read is confirmed as the
# window shows it; a key pressed or a text typed is only said done (its effect was never read).
_CONFIRM_STATE = (
    "Confirm the state the window shows now (where it is, the value asked), not the clicks, keys or steps you took; "
)
_DONE_ONLY = "Say only that it is done in that app, never what it caused, nor the keys or steps you took; "
_MIXED = (
    "For a part that went somewhere or read a value, confirm the state the window shows now; for a part that pressed "
    "a key or typed, say only that it is done in that app, never what it caused; never the clicks, keys or steps; "
)
_NO_META = (
    "never mention the mission, the evidence, the check, the screen or the view as such. A goal «ir a X» only went to "
    "X: never say you set, created, started, turned on or changed anything there. "
)
_ACT_ONLY_GOAL = re.compile(r"^(?:apretar|escribir|enviar)\b")


def _acts_only(goal: object) -> bool:
    """A goal whose check reads nothing of the window: a key to press, a text to type, what was written to send."""

    return isinstance(goal, str) and QUESTION_MARK not in goal and _ACT_ONLY_GOAL.match(fold(goal).strip()) is not None


def _voice(goals: list[object], question: bool, length: str = "ONE short sentence") -> str:
    acting = [_acts_only(goal) for goal in goals] or [False]
    if question or not any(acting):
        body = _CONFIRM_STATE
    elif all(acting):
        body = _DONE_ONLY
    else:
        body = _MIXED
    return _SPEAKER.format(length=length) + body + _NO_META


def _result_instruction(seen: dict) -> str:
    if seen.get("subgoals"):
        goals = [item.get("goal") for item in seen["subgoals"] if isinstance(item, dict)]
        length = "ONE short sentence" if seen.get("reached") else "at most TWO short sentences"
        chained = (
            "This result is a computer-use mission of several parts done in order: seen.subgoals lists each part "
            "(goal, application, reached true or false). " + _voice(goals, bool(seen.get("question")), length)
            + "Name the parts briefly in their order only when there are several applications or places. "
        )
        if seen.get("reached"):
            return chained + (
                "Every part was reached. When seen.evidence names the result, say its text as it is written. "
                "seen.joined says whether a voice channel or call was joined: say you joined only if it is true. "
                "Never add parts, steps, times or results that are not in seen."
            )
        return chained + (
            "Not every part was reached: lead with what you could not do (seen.firstUnreached), said in the first "
            "person singular (Spanish «pude», never «pudiste»: you acted, not the person), and its cause "
            "(seen.stoppedBecause, reworded lightly, never «operación» or «operation»), plainly and without apology; "
            "then, briefly, the parts that were done. Never say that a part with reached false was done, never say "
            "the whole request succeeded, and never invent a cause that is not in seen."
        )
    if seen.get("reached"):
        return (
            "This result is a computer-use mission that REACHED its goal: seen.goal is what was asked, "
            "seen.stepsDone the acts done in order on the window seen.windowTitle, seen.evidence the text on screen "
            "that proves it when present, seen.screen what the window showed at the end (seen.screen.numbers: the "
            "controls and lines carrying a number, such as a display or a counter; seen.screen.values: its fields "
            "and chosen items; seen.screen.lines: a few lines). " + _voice([seen.get("goal")], bool(seen.get("question")))
            + (
                "" if _acts_only(seen.get("goal")) and not seen.get("question") else
                "When the goal asked for a calculation, a number or a value, lead with it, said exactly as the matching "
                "entry of seen.screen.numbers or seen.screen.values writes it; do not list the other lines of the window. "
            )
            + (
                "The window had no colour named seen.chosenShade.asked: you chose its closest shade, the swatch "
                "seen.chosenShade.chosen. Say that swatch's name exactly as written and that it is the asked colour of "
                "the palette (as in «Elegí Añil, el azul de la paleta»); never say you chose a swatch named "
                "seen.chosenShade.asked. " if seen.get("chosenShade") else ""
            )
            + "seen.joined says whether a voice channel or call was joined: say you joined only if it is true. Never "
            "add steps, times or results that are not in seen: a time or a date only as seen.screen writes it, never "
            "the part of the day (morning, afternoon, a.m., p.m.) unless it is written there."
        )
    return (
        "This result is a computer-use mission that did NOT reach its goal: seen.goal is what was asked, "
        "seen.stepsDone what was done before stopping, seen.stepsFailed what could not be done, "
        "seen.stoppedBecause the cause in the person's words. In ONE short sentence, in the person's language and "
        "in the FIRST PERSON, say plainly that you could not do it and why (seen.stoppedBecause, reworded lightly, "
        "never «operación» or «operation»), without apology and without listing steps: say first, in the first "
        "person singular, that you could not (Spanish «pude», never «pudiste»: you acted, not the person). Never say "
        "it succeeded and never invent a cause that is not in seen."
    )

_JOIN_CLAIM = re.compile(
    r"\b(?:me\s+uni|me\s+he\s+unido|nos\s+unimos|joined|entre\s+(?:a|al)\s+(?:el\s+)?canal\s+de\s+voz|estoy\s+en\s+el\s+canal\s+de\s+voz|te\s+uni|ya\s+estoy\s+en\s+la\s+llamada|in\s+the\s+call)\b"
)
_JOIN_NEGATED = re.compile(
    r"\b(?:no|not|sin|didn't|did\s+not|without|todavia\s+no|aun\s+no|never|nunca)\s+(?:\w+\s+){0,2}(?:uni\w*|unir\w*|join\w*|entr\w*)\b"
)
_FALSE_PAST = re.compile(
    r"\b(?:ayer|anoche|antier|anteayer|antes\s+de\s+ayer|la\s+semana\s+pasada|el\s+otro\s+dia|hace\s+(?:un|unos|varios|dos|tres)\s+(?:dia|dias|semana|semanas|hora|horas)|"
    r"yesterday|last\s+night|last\s+week|the\s+other\s+day|days?\s+ago|hours?\s+ago|weeks?\s+ago)\b"
)
_SUCCESS_CLAIM = re.compile(
    r"\b(?:listo|hecho|logrado|conseguido|cumplido|done|achieved|completed|entre\s+a|llegue\s+a|ya\s+estas\s+en|ya\s+esta\s+en|quedo\s+activado|quedo\s+activo|active|activado)\b"
)


# Live 2026-10-07 (cu-r19): «Llegué al modo Oscuro.», «Llegué a la zona horaria y es …»: an arrival is told only at a
# place of the mission (a place goal, its application or its window), never at a value or an option the window shows.
_ARRIVAL = re.compile(
    r"\b(?:llegue|llegamos|i\s+reached|we\s+reached|i\s+got\s+to|i\s+made\s+it\s+to)\s+"
    r"(?:a\s+(?:la|las|los|el)\s+|al\s+|a\s+|the\s+)?([^.;:!?,]+)"
)
_ARRIVAL_FUNCTION = {"del", "los", "las", "the", "and", "seccion", "pagina", "pestana", "section", "page", "tab", "parte"}
_ARRIVAL_END = re.compile(r"\s+(?:y|e|and|donde|where|que|that|con|with|para|to)\s+.*$")


def _arrived_off_mission(folded_reply: str, seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)]
    goals = goals or str(seen.get("goal") or "").split(_PARTS["chain"])
    places = {fold(found.group(1)) for goal in goals if isinstance(goal, str) and (found := _PLACE_GOAL.match(goal.strip()))}
    places |= {fold(seen.get(key)) for key in ("application", "windowTitle") if isinstance(seen.get(key), str)}
    # A place told short («la sección de Bluetooth» for «Bluetooth y dispositivos») shares a word with it.
    words = {word for place in places for word in re.findall(r"[a-z0-9]+", place) if len(word) >= 3} - _ARRIVAL_FUNCTION
    for found in _ARRIVAL.finditer(folded_reply):
        head = set(re.findall(r"[a-z0-9]+", _ARRIVAL_END.sub("", found.group(1)))) - _ARRIVAL_FUNCTION
        if head and not head & words:
            return True
    return False


def mission_defect(folded_reply: str, seen: dict) -> str | None:
    """Vetos of a mission final: a join never observed, a false past time, a
    failed mission told as a success (contract §4.5)."""

    if _FALSE_PAST.search(folded_reply):
        return "extra_claim"
    claims_join = _JOIN_CLAIM.search(folded_reply) is not None and _JOIN_NEGATED.search(folded_reply) is None
    if claims_join and seen.get("joined") is not True:
        return "joined_claimed"
    if seen.get("joined") is True and _JOIN_NEGATED.search(folded_reply) is not None:
        return "joined_claimed"
    if seen.get("reached") is not True and _SUCCESS_CLAIM.search(folded_reply) and not re.search(r"\b(?:no|not)\b", folded_reply):
        return "reversed_polarity"
    for subgoal in seen.get("subgoals") or ():
        if isinstance(subgoal, dict) and subgoal.get("reached") is not True and _claims_part(folded_reply, str(subgoal.get("goal") or "")):
            return "subgoal_claimed"
    if _invented_meridiem(folded_reply, seen):
        return "extra_claim"
    if _arrived_off_mission(folded_reply, seen):
        return "extra_claim"
    shade = seen.get("chosenShade")
    if isinstance(shade, dict) and fold(shade.get("chosen")) not in folded_reply:
        # «Listo, elegí el azul» when the palette had no «Azul» and «Añil» was clicked: the swatch is named.
        return "shade_unnamed"
    if _only_went_somewhere(seen) and _claims_a_change(folded_reply, seen):
        return "extra_claim"
    if _claims_a_containment(folded_reply, seen):
        return "extra_claim"
    if _NEW_STATE_CLAIM.search(folded_reply) and not _toggles_something(seen):
        return "extra_claim"
    return None


# cu-r16 (voice audit 2026-10-07: «Abrazé a la sección de Bluetooth», «donde busco la opción de Wi-Fi», «Ya estamos
# en…», «mis playlists»): every word of a mission final comes from the turn's facts or from BAXY's own small vocabulary
# of arrival, act and function words (data/computer_use_words.v1.json). A word from neither was never observed.
_WORDS_DATA = Path(__file__).resolve().parent / "data" / "computer_use_words.v1.json"
_WORD = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _own_words() -> tuple[frozenset[str], int]:
    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    words: set[str] = set()
    for family in ("function", "own"):
        for listed in data[family].values():
            words.update(fold(word) for word in listed)
    return frozenset(words), int(data["stemLength"])


@lru_cache(maxsize=1)
def _language_words() -> tuple[frozenset[str], frozenset[str], dict[str, tuple[str, ...]]]:
    """The Spanish and English function words (to tell an English reply) and the es→en screen-state map."""

    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    spanish = frozenset(fold(word) for word in data["function"]["es"])
    english = frozenset(fold(word) for word in data["function"]["en"])
    listed = data.get("screenStates") or {}
    states = {fold(word): tuple(fold(item) for item in said) for word, said in listed.items()}
    return spanish - english, english - spanish, states


@lru_cache(maxsize=1)
def _application_kinds() -> dict[str, frozenset[str]]:
    data = json.loads(_WORDS_DATA.read_text(encoding="utf-8"))
    listed = data.get("applicationKinds") or {}
    return {fold(name): frozenset(fold(word) for word in words) for name, words in listed.items()}


def _kinds_of(seen: dict) -> set[str]:
    """The words that name what the mission's applications hold («juegos» in Steam, «disco» in the File Explorer)."""

    kinds = _application_kinds()
    subgoals = [item for item in seen.get("subgoals") or () if isinstance(item, dict)]
    names = [seen.get("application"), *(item.get("application") for item in subgoals)]
    return {word for name in names if isinstance(name, str) for word in kinds.get(fold(name).strip(), ())}


# cu-r17 (voice audit 2026-10-07: «Pegué el texto» from «pegalo», «Cerré la ventana» from «cerrala»): the stem match
# cannot reach a short preterite from the request's imperative, so each imperative or infinitive of the request also
# grounds its own first-person preterite: «copiá» → «copié», «pegalo» → «pegué», «buscá» → «busqué», «abrí» → «abrí»,
# «mové» → «moví», «guardar» → «guardé».
_ENCLITIC = re.compile(r"(?:selos|selas|selo|sela|los|las|les|lo|la|le|me|nos)$")


def _preterites(word: str) -> set[str]:
    forms: set[str] = set()
    bare = word[:-1] if word.endswith("r") and len(word) > 3 else word
    stripped = _ENCLITIC.sub("", bare)
    for base in {bare, stripped}:
        if len(base) < 3:
            continue
        if base.endswith("a"):
            stem = base[:-1]
            if stem.endswith("c"):
                stem = stem[:-1] + "qu"
            elif stem.endswith("g"):
                stem = stem[:-1] + "gu"
            elif stem.endswith("z"):
                stem = stem[:-1] + "c"
            forms.add(stem + "e")
        elif base.endswith(("e", "i")):
            forms.add(base[:-1] + "i")
    return forms


def _reply_is_english(words: list[str]) -> bool:
    spanish, english, _ = _language_words()
    return sum(word in english for word in words) > sum(word in spanish for word in words)


def _fact_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _fact_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _fact_strings(item)


def _folded_words(value: object) -> list[str]:
    return _WORD.findall(fold(value))


def ungrounded_word(folded_reply: str, seen: dict, said: str = "") -> str | None:
    """The first word of a mission final that neither the facts (seen, the person's words) nor BAXY's own vocabulary
    hold; a word sharing its first ``stemLength`` letters with a fact word is the same word in another form
    («calculé» from «calculá»), the preterite of a request verb is BAXY's own act («pegué» from «pegalo»), and an
    English reply may name a Spanish screen state in English («paired» for «Emparejado»). None when every word is
    grounded."""

    own, stem_length = _own_words()
    facts: set[str] = set()
    for text in (*_fact_strings(seen), said):
        facts.update(_folded_words(text))
    stems = {word[:stem_length] for word in facts if len(word) >= stem_length}
    # cu-r18 (live v2-c6: a confirmed send answered «sí», so «Envié «prueba BAXY C6» a Ron92.» had no «mandalo» to come
    # from): the mission's own goal and each subgoal's goal («…; luego enviar») ground their preterites as well.
    goals = [seen.get("goal"), *(item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict))]
    verbs = [word for text in (said, *(goal for goal in goals if isinstance(goal, str))) for word in _folded_words(text)]
    derived = {form for word in verbs for form in _preterites(word)} | _kinds_of(seen)
    reply = _folded_words(folded_reply)
    if _reply_is_english(reply):
        # cu-r17 (x4 «Windows (light)» from «Windows (claro)»): an English reply names a Spanish screen state in English.
        states = _language_words()[2]
        derived.update(said_en for word in facts for said_en in states.get(word, ()))
    for word in reply:
        if word in own or word in facts or word in derived:
            continue
        if len(word) >= stem_length and word[:stem_length] in stems:
            continue
        return word
    return None


# Live 2026-10-07 (v2-a2 «en el Reloj andá a Temporizador y después en Configuración andá a Aplicaciones» → «Estoy en
# Configuración de Aplicaciones dentro de la app Reloj.»; v2-a4 «… andá a Documentos y después a Descargas» → «Estoy en
# la carpeta de Descargas dentro de Documentos»): «X dentro de Y» puts a place of the mission inside another place or
# another application. The facts only say which application each place was reached in: X inside its own application
# passes, X inside anything else of the mission was never observed.
_CONTAINER = re.compile(r"\s+(?:dentro\s+del?|adentro\s+del?|inside(?:\s+of)?|within|in|en)\s+")
_CONTAINER_FILLER = re.compile(
    r"^(?:(?:el|la|los|las|the)\s+)?(?:(?:app|aplicacion|carpeta|ventana|seccion|pestana|pagina|folder|application|"
    r"window|section|tab|page)\s+(?:(?:de|del|of)\s+)?(?:(?:el|la|los|las|the)\s+)?)?"
)


def _mission_places(seen: dict) -> dict[str, str]:
    """Each place a goal «ir a X» reached, folded, with the folded application it was reached in."""

    app = fold(seen.get("application")) if isinstance(seen.get("application"), str) else ""
    parts = [
        (item.get("goal"), item.get("application")) for item in seen.get("subgoals") or () if isinstance(item, dict)
    ] or [(part, None) for part in str(seen.get("goal") or "").split(";")]
    places: dict[str, str] = {}
    for goal, where in parts:
        found = _PLACE_GOAL.match(re.sub(r"^\s*luego\s+", "", goal.strip())) if isinstance(goal, str) else None
        name = fold(_BIDI_MARKS.sub("", found.group(1))).strip(" .") if found is not None else ""
        if name:
            places[name] = fold(where) if isinstance(where, str) and where.strip() else app
    return places


def _claims_a_containment(folded_reply: str, seen: dict) -> bool:
    places = _mission_places(seen)
    apps = {
        fold(name) for name in (seen.get("application"), *(
            item.get("application") for item in seen.get("subgoals") or () if isinstance(item, dict)
        )) if isinstance(name, str) and name.strip()
    }
    names = sorted({*places, *apps} - {""}, key=len, reverse=True)
    if len(names) < 2:
        return False
    for found in _CONTAINER.finditer(folded_reply):
        before, after = folded_reply[:found.start()], _CONTAINER_FILLER.sub("", folded_reply[found.end():])
        outer = next((name for name in names if re.match(rf"{re.escape(name)}\b", after)), None)
        inner = next((name for name in names if re.search(rf"\b{re.escape(name)}$", before)), None)
        if outer is None or inner is None or inner == outer:
            continue
        if outer in apps and places.get(inner) == outer:
            continue
        return True
    return False


# Live 2026-10-07 (v2-a12 «en Configuración buscá Bluetooth» → «Ya busqué Bluetooth en Configuración y ahora está
# activado.»): a state said as the result of «ahora» tells a switch the mission never flipped. «Bluetooth está activado»
# describing the window stays allowed; only a mission whose goals switch something may say what it is «ahora».
_STATE_WORD = r"(?:activad[oa]s?|desactivad[oa]s?|encendid[oa]s?|apagad[oa]s?|prendid[oa]s?|activ[oa]s?|inactiv[oa]s?)"
_NEW_STATE_CLAIM = re.compile(
    rf"\bahora\s+(?:\w+\s+){{0,3}}?(?:ya\s+)?(?:esta|estan|queda|quedan|quedo|quedaron|sigue)\s+(?:ahora\s+)?{_STATE_WORD}\b|"
    rf"\b(?:esta|estan|queda|quedan|quedo|quedaron)\s+ahora\s+{_STATE_WORD}\b|"
    r"\bnow\s+(?:\w+\s+){0,3}?(?:is|it's|are|they're)\s+(?:now\s+)?(?:on|off|enabled|disabled|active|inactive)\b|"
    r"\b(?:is|it's|are|they're)\s+now\s+(?:on|off|enabled|disabled|active|inactive)\b"
)
_TOGGLE_GOAL = re.compile(
    r"^(?:activar|desactivar|encender|apagar|prender|alternar|cambiar|poner|hacer\s+clic|turn|enable|disable|toggle|"
    r"switch|click)\b"
)


def _toggles_something(seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] + [seen.get("goal")]
    return any(
        _TOGGLE_GOAL.match(re.sub(r"^\s*luego\s+", "", fold(part).strip()))
        for goal in goals if isinstance(goal, str) for part in goal.split(";")
    )


# Live 2026-10-07 (v2-v9 «en el Reloj andá a Reloj mundial», v2-u7/v2-w1 «… andá a Alarma»): a clock the window shows is
# what was observed, but Windows writes it with bidi marks inside («7‎:‎58»), and the part of the day is not written.
_BIDI_MARKS = re.compile("[‎‏‪-‮⁦-⁩]")
_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_MERIDIEM = re.compile(
    r"(?<!\d)\d{1,2}:\d{2}(?!\d)\s*(?:hs?\s+)?(?:de\s+la\s+|del\s+|en\s+la\s+|por\s+la\s+|in\s+the\s+)?"
    r"(manana|tarde|noche|madrugada|mediodia|morning|afternoon|evening|night|a\.?\s?m\b\.?|p\.?\s?m\b\.?)"
)


def screen_texts(seen: dict) -> list[str]:
    """Every text the window showed at the end (title, fields, numbers, lines) and the evidence, without bidi marks."""

    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    texts: list[object] = [screen.get("title"), seen.get("evidence"), seen.get("windowTitle")]
    for key in ("numbers", "lines"):
        texts.extend(screen.get(key) if isinstance(screen.get(key), list) else ())
    for item in screen.get("values") if isinstance(screen.get("values"), list) else ():
        if isinstance(item, dict):
            texts.extend((item.get("name"), item.get("value")))
    return [_BIDI_MARKS.sub("", text) for text in texts if isinstance(text, str) and text.strip()]


def screen_clocks(seen: dict) -> frozenset[str]:
    """The «HH:MM» clocks the window wrote: a clock app's time, an alarm's, a call's length."""

    return frozenset(
        f"{int(hour):02d}:{minute}" for text in screen_texts(seen) for hour, minute in _CLOCK.findall(text)
    )


def _invented_meridiem(folded_reply: str, seen: dict) -> bool:
    """«las 7:58 de la tarde» over a window that writes only «7:58»: the part of the day is a guess."""

    shown = fold(" ".join(screen_texts(seen)))
    for found in _MERIDIEM.finditer(folded_reply):
        word = re.sub(r"[\s.]", "", found.group(1))
        if not re.search(rf"\b{word[0]}\.?\s?{word[1:]}\b" if word in {"am", "pm"} else rf"\b{word}\b", shown):
            return True
    return False


# A goal «ir a X» only went to X (_NO_META): a first-person change said beside it was never done nor observed.
_GO_GOAL = re.compile(r"^ir\s+a\b")
_CHANGE_CLAIM = re.compile(
    r"\b(?:puse|configure|cree|programe|cambie|ajuste|encendi|apague|inicie|borre|elimine|agregue|anadi|guarde|"
    r"(?:des)?active\s+(?:el|la|los|las|lo|un|una)|"
    r"pondre|configurare|creare|programare|cambiare|ajustare|encendere|apagare|borrare|eliminare|agregare|anadire|"
    r"guardare|(?:des)?activare|"
    r"voy\s+a\s+(?:poner|configurar|crear|programar|cambiar|ajustar|encender|apagar|borrar|eliminar|agregar|anadir|"
    r"guardar|(?:des)?activar)|"
    r"ahora\s+(?:pongo|configuro|programo|cambio|ajusto|enciendo|apago|borro|elimino|agrego|anado|guardo|(?:des)?activo)|"
    r"i(?:\s+will|'ll|\s+am|'m)\s+(?:set|create|start|turn|change|schedule|enable|disable|delete|add|save|setting|"
    r"creating|starting|turning|changing|scheduling|enabling|disabling|deleting|adding|saving)|"
    r"i(?:\s+have|'ve)?\s+(?:set|created|started|turned|changed|scheduled|enabled|disabled|deleted|added|saved))\b"
)
_CHANGE_DENIED = re.compile(r"\b(?:no|nunca|ni|not|never|didn'?t)\s+(?:\w+\s+)?$")


def _only_went_somewhere(seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] or [seen.get("goal")]
    return all(isinstance(goal, str) and _GO_GOAL.match(fold(goal)) for goal in goals)


def _claims_a_change(folded_reply: str, seen: dict) -> bool:
    return any(
        _CHANGE_DENIED.search(folded_reply[max(0, found.start() - 20):found.start()]) is None
        and _PICK_OFFERED.search(folded_reply[max(0, found.start() - 40):found.start()]) is None
        for found in _CHANGE_CLAIM.finditer(folded_reply)
    ) or _claims_a_pick(folded_reply, seen)


# Live 2026-10-07 (cu-r8, «en el Reloj andá a Alarma» → «Ya elegí la alarma de las 7:00»): a navigation selects the
# place it goes to (the tab «Alarma»), nothing inside it. A first-person pick is what the mission went to or nothing:
# its object must be a place the goals named, a name the steps clicked or a value the window marked, optionally «en»
# the application; «elegí el lápiz» on a mission that picked it is not a navigation and is not judged here.
# Live v6 («en Word andá a la pestaña Diseño» → «Ya estoy en la pestaña Diseño y ahora selecciono Títulos.»): an act
# said in the present or the future beside the arrival is as invented as one in the past.
_PICK_CLAIM = re.compile(
    r"\b(?:elegi|escogi|seleccione|marque|opte\s+por|elijo|escojo|selecciono|elegire|escogere|seleccionare|marcare|"
    r"voy\s+a\s+(?:elegir|escoger|seleccionar|marcar)|"
    r"i(?:\s+have|'ve|\s+will|'ll|\s+am|'m)?\s+(?:chose|chosen|selected|picked|ticked|choose|select|pick|"
    r"choosing|selecting|picking))\s+"
    r"(?P<object>[^.,;:!?\n]+?)(?=\s+(?:y|e|pero|and|but|que|that|which)\b|[.,;:!?\n]|$)"
)
# «Si quieres, selecciono Títulos» offers the act; it does not claim it.
_PICK_OFFERED = re.compile(r"\b(?:si\s+quieres|si\s+deseas|puedo|if\s+you\s+(?:want|like)|i\s+can|want\s+me\s+to)\b[^.;]{0,20}$")
_PICK_HEAD = re.compile(
    r"^(?:(?:el|la|los|las|lo|the|a|an)\s+)?(?:(?:pestana|seccion|opcion|pagina|vista|apartado|tab|section|option|"
    r"page|view)\s+(?:(?:de|del|of)\s+)?(?:(?:el|la|los|las|the)\s+)?)?"
)
_PICK_WHERE = re.compile(
    r"^(?:en|in|on|de|del|of)\s+(?:(?:el|la|the)\s+)?(?:(?:aplicacion|app|ventana|window)\s+(?:(?:de|del|of)\s+)?)?(?P<app>.+)$"
)
_QUOTED = re.compile(r"«([^«»]+)»")


def _picked_places(seen: dict) -> set[str]:
    # What the goals named and what the steps clicked; a value the window marks without this mission clicking it is
    # not its pick (live v6: Word's «Títulos» style, selected by default, said as «ahora selecciono Títulos»).
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] + [seen.get("goal")]
    names = [
        *(found.group(1) for goal in goals if isinstance(goal, str) for part in goal.split(";")
          if (found := _PLACE_GOAL.match(re.sub(r"^\s*luego\s+", "", part.strip()))) is not None),
        *(quoted for step in seen.get("stepsDone") or () if isinstance(step, str) for quoted in _QUOTED.findall(step)),
    ]
    return {fold(_BIDI_MARKS.sub("", name)).strip(" .") for name in names if isinstance(name, str) and name.strip()}


def _claims_a_pick(folded_reply: str, seen: dict) -> bool:
    places = _picked_places(seen)
    apps = {fold(name) for name in (seen.get("application"), seen.get("windowTitle")) if isinstance(name, str)}
    for found in _PICK_CLAIM.finditer(folded_reply):
        before = folded_reply[max(0, found.start() - 40):found.start()]
        if _CHANGE_DENIED.search(before[-20:]) is not None or _PICK_OFFERED.search(before) is not None:
            continue
        picked = _PICK_HEAD.sub("", fold(found.group("object").replace("«", " ").replace("»", " "))).strip()
        if picked in places:
            continue
        place = next((name for name in places if name and picked.startswith(name + " ")), None)
        where = _PICK_WHERE.match(picked[len(place) + 1:]) if place is not None else None
        if where is None or fold(where.group("app")) not in apps:
            return True
    return False


# The floor of a mission (live 2026-10-07): when every draft was refused, «Lo hice en la aplicación «Reloj»; hay 2:
# «Reloj mundial».» counted the steps as a list read. The floor says what the person asked about, from the facts only:
# the place reached, or what could not be done and its cause.
_PLACE_GOAL = re.compile(operation_floor.floor_data()["computerUse"]["placeGoal"], re.IGNORECASE)
_LONGEST_FLOOR_NAME: int = operation_floor.floor_data()["computerUse"]["longestName"]


def _floor_name(value: object) -> str:
    text = " ".join(_BIDI_MARKS.sub("", value).split()).strip(" .;:") if isinstance(value, str) else ""
    return text if text and len(text) <= _LONGEST_FLOOR_NAME and "«" not in text and "»" not in text else ""


def _place_of(goal: object, names: list[str]) -> str:
    """The place a goal «ir a X» went to, spelled as the window wrote it when one of its names is X."""

    found = _PLACE_GOAL.match(str(goal or "").strip()) if isinstance(goal, str) and QUESTION_MARK not in goal else None
    if found is None:
        return ""
    asked = _floor_name(found.group(1))
    return _spelled(asked, names) or asked


# Voice audit 2026-10-07 (cu-r16): a third of the published mission finals the model wrote had a defect («Ya te llevé a
# la sección de sonido», «Abrazé a la sección de Bluetooth», «ahora selecciono Títulos», «mis playlists»), and the
# simple missions are most of them. A mission without a question is told part by part from its facts (data
# «computerUse.parts»): the places reached, the controls picked, the text typed or searched, a calculation whose value
# the window shows. Its twin is the App's OperationFloor.Parts.
_PARTS: dict = operation_floor.floor_data()["computerUse"]["parts"]
_PART_GOALS: dict[str, re.Pattern[str]] = {
    kind: re.compile(_PARTS[kind], re.IGNORECASE) for kind in ("select", "type", "search", "calculate", "key", "mode")
}
_ONE_GENDERED_WORD = re.compile(r"^[a-z]+[oa]$")
_PART_QUOTES = "«»\"“”'"
# Live 2026-10-07: «calcular 1.500 + 500» read as 1,5 + 500. A «.» followed by exactly three digits groups thousands
# (the Chilean writing); a comma after them is the decimal one.
_CALC_TOKEN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\d.])|\d+(?:[.,]\d+)?|\S")
_GROUPED_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
# What a window writes of the expression itself («La expresión es 144 ÷ 12=») never proves its value.
_WRITTEN_EXPRESSION = re.compile(r"\d[\d.,]*(?:\s*[-+×÷*/xX]\s*\(?\s*\d[\d.,]*\)?)+\s*=?")
_LONGEST_DECIMALS = 10


def _part_object(value: object) -> str:
    return " ".join(str(value or "").split()).strip(_PART_QUOTES + " .;:") if isinstance(value, str) else ""


def _mode_chosen(asked: str, done: list[dict], app: str) -> str:
    """Live 2026-10-07 (cu-r20): the mode a goal «activar modo X» reached by choosing it, as the window writes it
    without the application's name («Científica Calculadora» → «Científica» for «activar modo cientifico», either
    gender); "" when no click chose it or a switch set it (data «computerUse.parts.mode»). Twin of the App's
    OperationFloor.ModeChosen."""

    wanted = fold(asked)
    if not wanted:
        return ""
    names = {wanted}
    if _ONE_GENDERED_WORD.match(wanted):
        names.add(wanted[:-1] + ("a" if wanted[-1] == "o" else "o"))
    app_words = set(fold(app).split())
    chosen = ""
    for step in done:
        name = _floor_name(step.get("name"))
        if step.get("operation") != "input.visible.click" or not name:
            continue
        mode = " ".join(word for word in name.split() if fold(word) not in app_words)
        if not mode or fold(mode) not in names:
            continue
        if step.get("kind") in _PARTS["switchKinds"]:
            return ""
        chosen = _calm_caps(mode)
    return chosen


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


def _calculated(tokens: list[str]) -> Fraction | None:
    """The value of an arithmetic expression (numbers, + - × ÷ and parentheses), or None when it is no such thing."""

    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def factor() -> Fraction | None:
        nonlocal position
        token = peek()
        if token == "-":
            position += 1
            inner = factor()
            return None if inner is None else -inner
        if token == "(":
            position += 1
            inner = expression()
            if inner is None or peek() != ")":
                return None
            position += 1
            return inner
        if token is not None and token[0].isdigit():
            position += 1
            plain = token.replace(".", "") if _GROUPED_NUMBER.fullmatch(token) else token
            return Fraction(plain.replace(",", "."))
        return None

    def term() -> Fraction | None:
        nonlocal position
        value = factor()
        while value is not None and peek() in {"×", "÷"}:
            operator = peek()
            position += 1
            right = factor()
            if right is None or (operator == "÷" and right == 0):
                return None
            value = value * right if operator == "×" else value / right
        return value

    def expression() -> Fraction | None:
        nonlocal position
        value = term()
        while value is not None and peek() in {"+", "-"}:
            operator = peek()
            position += 1
            right = term()
            if right is None:
                return None
            value = value + right if operator == "+" else value - right
        return value

    value = expression()
    return value if position == len(tokens) else None


def _value_spellings(value: Fraction) -> list[str]:
    """How a window may write ``value``: plain, with its thousands grouped, with a decimal point or comma; [] when it
    has no finite decimal writing."""

    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator, twos = denominator // 2, twos + 1
    while denominator % 5 == 0:
        denominator, fives = denominator // 5, fives + 1
    decimals = max(twos, fives)
    if denominator != 1 or decimals > _LONGEST_DECIMALS:
        return []
    sign = "-" if value < 0 else ""
    scaled = abs(value.numerator) * (10 ** decimals) // value.denominator
    whole, fraction = divmod(scaled, 10 ** decimals) if decimals else (scaled, 0)
    digits = str(whole)
    groups = [digits[max(0, end - 3):end] for end in range(len(digits), 0, -3)][::-1]
    spellings: list[str] = []
    for separator in ("", ".", ",", " ", "\u00a0"):
        if separator and len(groups) < 2:
            continue
        integer = separator.join(groups)
        if not decimals:
            spellings.append(sign + integer)
            continue
        tail = str(fraction).rjust(decimals, "0")
        spellings.extend(
            sign + integer + point + tail for point in (".", ",") if point != separator
        )
    return spellings


def _calculation_shown(expression: str, texts: list[str]) -> tuple[str, str] | None:
    """(expression as said, value as the window writes it) for «calcular E» when the window shows E's value."""

    operators: dict[str, str] = _PARTS["operators"]
    tokens = [operators.get(token, token) for token in _CALC_TOKEN.findall(expression)]
    if not tokens or any(not (token[0].isdigit() or token in {"+", "-", "×", "÷", "(", ")"}) for token in tokens):
        return None
    value = _calculated(tokens)
    if value is None:
        return None
    shown = [_WRITTEN_EXPRESSION.sub(" ", " ".join(_BIDI_MARKS.sub("", text).split())) for text in texts]
    for spelling in _value_spellings(value):
        pattern = re.compile(r"(?<![\d.,])" + re.escape(spelling) + r"(?![\d]|[.,]\d)")
        if any(pattern.search(text) for text in shown):
            said = " ".join(tokens).replace("( ", "(").replace(" )", ")")
            return said, spelling
    return None


def _screen_texts(observed: dict) -> list[str]:
    screen = observed.get("screen") if isinstance(observed.get("screen"), dict) else {}
    texts: list[str] = []
    for key in ("numbers", "lines"):
        texts.extend(item for item in screen.get(key) or () if isinstance(item, str))
    for item in screen.get("values") or ():
        if isinstance(item, dict):
            texts.extend(value for value in (item.get("name"), item.get("value")) if isinstance(value, str))
    texts.extend(value for value in (screen.get("title"),) if isinstance(value, str))
    return texts


def _join(items: list[str], english: bool) -> str:
    said = operation_floor.floor_data()["templates"]["en" if english else "es"]
    return items[0] if len(items) == 1 else said["list"].join(items[:-1]) + said["and"] + items[-1]


def _parts_final(observed: dict, seen: dict, english: bool, names: list[str], app: str) -> tuple[str, bool]:
    """(the sentence of a reached mission told part by part, whether every name in it is the window's own spelling or
    the text typed); ("", False) when one of its parts cannot be told from the facts."""

    goal = seen.get("goal")
    subgoals = [item for item in seen.get("subgoals") or () if isinstance(item, dict)]
    parts = [(item.get("goal"), item.get("application")) for item in subgoals] or [
        (part, seen.get("application")) for part in str(goal or "").split(_PARTS["chain"])
    ]
    language = "en" if english else "es"
    said, quote = _PARTS[language], operation_floor.floor_data()["templates"][language]["quote"]
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    done = [step for step in raw_steps if isinstance(step, dict) and step.get("ok") is True]
    typed = [
        fold(_part_object(step.get("text"))) for step in done
        if step.get("operation") == "input.text.type" and isinstance(step.get("text"), str)
    ]
    texts = _screen_texts(observed)
    clauses: list[tuple[str, str, str, bool]] = []  # (kind, said, application, the window's own spelling)
    keyed: set[str] = set()
    for part, part_app in parts:
        part = part.strip() if isinstance(part, str) else ""
        where = _floor_name(part_app) or app
        if not part or QUESTION_MARK in part:
            return "", False
        if _PART_GOALS["key"].match(part):
            # A key is never told (the instruction's «never the keys»); its application is told by another part.
            keyed.add(where)
            continue
        found = _PART_GOALS["mode"].match(part)
        if found is not None:
            mode = _mode_chosen(_floor_name(_part_object(found.group(1))), done, where)
            if not mode:
                return "", False
            clauses.append(("place", quote.format(value=mode), where, True))
            continue
        place = _PLACE_GOAL.match(part)
        if place is not None:
            asked = _floor_name(_part_object(place.group(1)))
            if not asked:
                return "", False
            spelled = _spelled(asked, names)
            clauses.append(("place", quote.format(value=spelled or asked), where, spelled is not None))
            continue
        found = _PART_GOALS["select"].match(part)
        if found is not None:
            asked = _floor_name(_part_object(found.group(1)))
            if not asked:
                return "", False
            shade = _chosen_shade(part, done)
            if shade is not None and fold(shade["chosen"]) != fold(asked):
                colour = next(iter(colour_shades(shade["asked"], language)), str(shade["asked"]))
                item = said["shadeItem"].format(chosen=shade["chosen"], asked=colour.casefold())
                clauses.append(("select", item, where, True))
                continue
            spelled = _spelled(asked, names)
            clauses.append(("select", quote.format(value=spelled or asked), where, spelled is not None))
            continue
        found = _PART_GOALS["type"].match(part)
        if found is not None:
            text = _part_object(found.group(1))
            if not text or fold(text) not in typed or not where:
                return "", False
            clauses.append(("type", quote.format(value=text), where, True))
            continue
        found = _PART_GOALS["search"].match(part)
        if found is not None:
            query = _part_object(found.group(1))
            if not query or not any(fold(query) in text for text in typed) or not where:
                return "", False
            search = said["search"].format(query=quote.format(value=query), app=quote.format(value=where))
            clauses.append(("search", search, where, True))
            continue
        found = _PART_GOALS["calculate"].match(part)
        # Only the calculating window's own display proves the value: a chain that ends in another application shows
        # that one's numbers («Línea 1, Columna 13» of the Bloc de notas).
        window = observed.get("window") if isinstance(observed.get("window"), dict) else {}
        title = window.get("title") if isinstance(window.get("title"), str) else ""
        ends_here = bool(where) and (fold(where) == fold(app) or fold(where) in fold(title))
        shown = _calculation_shown(found.group(1), texts) if found is not None and ends_here else None
        if shown is None:
            return "", False
        if len(parts) == 1:
            return said["calculateAlone"].format(expression=shown[0], value=shown[1]) + ".", True
        clauses.append(("calculate", said["calculate"].format(expression=shown[0], value=shown[1]), where, True))
    if not clauses:
        return "", False
    if len(clauses) == 1 and clauses[0][0] == "place":
        return _floor_said(english)["place"].format(place=clauses[0][1]) + ".", clauses[0][3]
    told: list[str] = []
    # Keys pressed in an application no other part is told in (a paste in another window) are the model's to word.
    spelled_all = keyed <= {clause[2] for clause in clauses}
    index = 0
    while index < len(clauses):
        kind, text, where, spelled = clauses[index]
        run = [(text, spelled)]
        while (
            index + 1 < len(clauses) and kind in {"place", "select", "type"}
            and clauses[index + 1][0] == kind and clauses[index + 1][2] == where
        ):
            index += 1
            run.append((clauses[index][1], clauses[index][3]))
        if kind == "place":
            # Live 2026-10-07: «ir a cotele» in Discord then «ir a tienda» in Steam came out «estoy en «TIENDA»»; a
            # mission across applications tells each place with its application.
            crossed = len({fold(clause[2]) for clause in clauses}) > 1
            if index == len(clauses) - 1:
                # Only the places the window spelled are told as passed through; the last is where the mission is.
                passed = [name for name, ok in run[:-1] if ok]
                if passed:
                    told.append(said["places"].format(places=_join(passed, english)))
                last = said["lastPlaceIn"] if crossed and where else said["lastPlace"]
                told.append(last.format(place=run[-1][0], app=quote.format(value=where)))
                spelled_all = spelled_all and run[-1][1]
            elif where and fold(where) != fold(clauses[index + 1][2]):
                # A place in an application the mission then left is told with it.
                told.append(said["placesIn"].format(
                    places=_join([name for name, _ in run], english), app=quote.format(value=where)))
                spelled_all = spelled_all and all(ok for _, ok in run)
            # A place passed on the way to another part of the same application is not told.
            index += 1
            continue
        spelled_all = spelled_all and all(ok for _, ok in run)
        if kind == "select":
            told.append(said["select"].format(items=_join([name for name, _ in run], english)))
        elif kind == "type":
            told.append(said["type"].format(texts=_join([name for name, _ in run], english), app=quote.format(value=where)))
        else:
            told.append(text)
        index += 1
    if len(told) == 1 and clauses[-1][0] == "place" and told[0] == said["lastPlace"].format(place=clauses[-1][1]):
        # The places passed were not the window's spelling: only where the mission is is told.
        return _floor_said(english)["place"].format(place=clauses[-1][1]) + ".", spelled_all
    return said["clauses"].format(clauses=_join(told, english)) + ".", spelled_all


def _floor_said(english: bool) -> dict:
    return operation_floor.floor_data()["computerUse"]["en" if english else "es"]


# Live 2026-10-07 (cu-r19): «Llegué al modo Oscuro.», «Llegué a la zona horaria y es (UTC-04:00) Santiago.» A reached
# mission whose question one fact of the window answers alone is answered from that fact (data «computerUse.answer»):
# the option the question names that the window shows selected, or the one value its noun names. Mind only: the App
# leaves every mission with a question to the mind.
_ANSWER: dict = operation_floor.floor_data()["computerUse"]["answer"]
_ANSWER_OPTIONS = re.compile(_ANSWER["options"], re.IGNORECASE)
_ANSWER_NOUN = re.compile(_ANSWER["noun"], re.IGNORECASE)
_ANSWER_NUMBER = re.compile(_ANSWER["number"])
_ANSWER_SHAPES = [
    (re.compile(shape["noun"], re.IGNORECASE), re.compile(shape["value"], re.IGNORECASE)) for shape in _ANSWER["shapes"]
]


def _answer_words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", fold(text)) if word not in _ANSWER["articles"]]


def question_answer(seen: dict, english: bool) -> str:
    """The answer to a reached mission's question when exactly one fact of the window gives it; "" otherwise."""

    question = " ".join(str(seen.get("question") or "").split()).strip(" .?¿!¡")
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    if seen.get("reached") is not True or not question:
        return ""
    values = [item for item in screen.get("values") or () if isinstance(item, dict)]
    said = _ANSWER["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    asked = _ANSWER_OPTIONS.match(question)
    if asked is not None:
        options = {fold(asked.group("first")), fold(asked.group("second"))}
        chosen = {
            _floor_name(item.get("name")) for item in values
            if str(item.get("state") or "").casefold() in _ANSWER["selectedStates"] and fold(item.get("name")) in options
        } - {""}
        if len(chosen) != 1:
            return ""
        return said["option"].format(noun=asked.group("noun"), value=quote.format(value=next(iter(chosen)))) + "."
    asked = _ANSWER_NOUN.match(question)
    if asked is None:
        return ""
    noun = asked.group("noun")
    words = _answer_words(noun)
    if not words:
        return ""
    named = {
        _floor_name(item.get("value")) for item in values
        if isinstance(item.get("value"), str) and set(words) <= set(_answer_words(str(item.get("name") or "")))
    }
    if not named:
        bare = " ".join(words)
        shapes = [value for noun_shape, value in _ANSWER_SHAPES if noun_shape.match(bare)]
        texts = [
            " ".join(_BIDI_MARKS.sub("", text).split()) for key in ("numbers", "lines")
            for text in screen.get(key) or () if isinstance(text, str)
        ]
        named = {_floor_name(text) for text in texts if any(shape.match(text) for shape in shapes)}
    if len(named) != 1 or "" in named:
        return ""
    value = next(iter(named))
    if _ANSWER_NUMBER.match(value):
        return said["number"].format(noun=noun, value=value) + "."
    return said["text"].format(noun=noun, value=quote.format(value=value)) + "."


def floor_first(observed: dict, english: bool, succeeded: bool) -> str:
    """The final a mission without a question is told with before any draft (voice audit 2026-10-07): its parts
    from the facts when every name in them is the window's or the person's own, or a failure with its typed cause;
    "" when the model has to word it (a question about the window, a part the facts cannot tell)."""

    seen = project_seen(observed, "en" if english else "es")
    if seen.get("question"):
        return question_answer(seen, english) if succeeded else ""
    if succeeded:
        if seen.get("reached") is not True:
            return ""
        sentence, preferred = _parts_final(observed, seen, english, _window_names(observed, seen), _mission_app(seen))
        return sentence if preferred else ""
    if seen.get("subgoals") or str(observed.get("stoppedBy") or "") not in _STOP_CAUSES:
        return ""
    sentence = floor_sentence(observed, english, succeeded)
    return sentence if not sentence.startswith(_floor_said(english)["not"] + ":") else ""


def _window_names(observed: dict, seen: dict) -> list[str]:
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    return [
        name for value in (
            *(step.get("name") for step in raw_steps if isinstance(step, dict) and step.get("ok") is True),
            *(item.get("name") for item in screen.get("values") or () if isinstance(item, dict)),
            *(line for line in screen.get("lines") or () if isinstance(line, str)),
            seen.get("windowTitle"),
        ) if (name := _floor_name(value))
    ]


def _mission_app(seen: dict) -> str:
    return _floor_name(seen.get("application")) or _floor_name(seen.get("windowTitle"))


def floor_sentence(observed: dict, english: bool, succeeded: bool) -> str:
    """The plain final of a mission said from its facts alone (data/operation_floor.v1.json «computerUse»), or ""
    when they hold nothing to say."""

    seen = project_seen(observed, "en" if english else "es")
    if seen.get("question"):
        return question_answer(seen, english) if succeeded else ""
    if succeeded and seen.get("reached") is True:
        told, _ = _parts_final(observed, seen, english, _window_names(observed, seen), _mission_app(seen))
        if told:
            return told
    data = operation_floor.floor_data()
    said = data["computerUse"]["en" if english else "es"]
    quote = data["templates"]["en" if english else "es"]["quote"]
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    names = [
        name for value in (
            *(step.get("name") for step in raw_steps if isinstance(step, dict) and step.get("ok") is True),
            *(item.get("name") for item in screen.get("values") or () if isinstance(item, dict)),
        ) if (name := _floor_name(value))
    ]
    app = _floor_name(seen.get("application")) or _floor_name(seen.get("windowTitle"))
    if succeeded and seen.get("reached") is True:
        shade = seen.get("chosenShade")
        if isinstance(shade, dict) and "shade" in said and _floor_name(shade.get("chosen")):
            # The colour in the final's language («blue» said to a Spanish final is «azul»).
            asked = next(iter(colour_shades(shade.get("asked"), "en" if english else "es")), str(shade.get("asked")))
            return said["shade"].format(chosen=_floor_name(shade.get("chosen")), asked=asked.casefold()) + "."
        goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] or [seen.get("goal")]
        place = _place_of(goals[-1], names)
        if place:
            return said["place"].format(place=quote.format(value=place)) + "."
        return said["app"].format(app=quote.format(value=app)) + "." if app else ""
    if succeeded:
        # A verified result that does not say it reached anything is never told as a failure.
        return ""
    place = _place_of(seen.get("firstUnreached") or seen.get("goal"), names)
    if place and str(observed.get("stoppedBy") or "") == "computer_use_already_there_unconfirmed":
        # The click on the place's own name left the window as it was (live v2-s12: Steam already on its library):
        # probably there already, never told as arrived.
        return data["computerUse"]["alreadyThere"]["en" if english else "es"].format(
            place=quote.format(value=place)) + "."
    if place:
        head = said["notPlace"].format(place=quote.format(value=place))
    elif app:
        head = said["notApp"].format(app=quote.format(value=app))
    else:
        head = said["not"]
    cause = seen.get("stoppedBecause") if str(observed.get("stoppedBy") or "") in _STOP_CAUSES else None
    return (said["cause"].format(head=head, cause=cause) if isinstance(cause, str) and cause.strip() else head) + "."


# The goal heads the mission reader writes (semantic.missions), so a part's object is what is left after them.
_GOAL_HEAD = re.compile(
    r"^(?:ir\s+a\s+la\s+pestana|ir\s+a\s+la\s+direccion|ir\s+a|hacer\s+clic\s+en|activar|desactivar|apretar|calcular|"
    r"escribir|abrir|buscar|seleccionar|reproducir|crear\s+\S+|renombrar(?:\s+.+?)?\s+a)\s+"
)
_PART_NEGATION = re.compile(
    r"\b(?:no|not|ni|sin|nunca|never|cannot|couldn'?t|didn'?t|can'?t|wasn'?t|todavia|aun|pendiente|falta\w*|fallo|failed)\b"
)


def _claims_part(folded_reply: str, goal: str) -> bool:
    """The reply tells the part ``goal`` as done: a clause of it names the part's object and denies nothing."""

    obj = _GOAL_HEAD.sub("", fold(goal), count=1)
    words = [word for word in re.findall(r"[a-z0-9]+", obj) if (len(word) >= 3 or word.isdigit()) and word not in {"the", "los", "las", "del"}]
    if not words:
        return False
    for clause in re.split(r"[.;:!?,]|\b(?:pero|but|aunque|although|sin\s+embargo|however)\b", folded_reply):
        if all(word in clause for word in words) and _PART_NEGATION.search(clause) is None:
            return True
    return False


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
