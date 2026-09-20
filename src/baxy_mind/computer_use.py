"""Motor de computer use, lado mente (documentacion/computer-use/CONTRATO_VISTA_ACCION.md).

Tres responsabilidades, ninguna sabe de una aplicación concreta:

1. **Leer el pedido** (`mission_request`): «en <app> <hacé X>», «abre <app> y
   <hacé X>», «<hacé X> en <app>», «cerrá todas las pestañas de <navegador>»
   → una misión ``mission.computer.use`` con aplicación, objetivo y la
   comprobación de éxito determinista (§4.3). La aplicación tiene que estar en
   el catálogo de Inicio; el resto de la frase es el objetivo.
2. **Elegir un paso** (`decide_step`): la vista compacta se serializa en pocas
   líneas, el modelo contesta UN acto con esquema JSON estricto a temperatura
   0, y unas comprobaciones sin modelo deciden si ese acto es legítimo: la
   etiqueta existe en la vista, la evidencia de «done» está en pantalla, no se
   escribe en una contraseña, no se repite el paso que acaba de fallar.
3. **Proyectar lo observado** para el compositor (`project_seen`,
   `mission_defect`): qué se hizo, con qué evidencia, y los vetos —«entré al
   canal» sin ``seen.joined``, pasado falso, misión no lograda narrada como
   logro—.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from . import effect_intent

OPERATION = "mission.computer.use"
STEP_REQUEST = "computer.use.step"
STEP_RESULT = "computer.use.step.result"

# El repertorio cerrado del bucle (contrato §2) y las teclas del catálogo.
ACTS = ("click", "type", "key", "scroll", "open", "done", "none")
KEYS = (
    "alt_tab", "arrow_down", "arrow_left", "arrow_right", "arrow_up",
    "backspace", "context_menu", "control", "ctrl_a", "ctrl_c", "ctrl_f", "ctrl_k",
    "ctrl_l", "ctrl_shift_escape", "ctrl_t", "ctrl_v", "ctrl_w", "ctrl_z",
    "delete", "end", "enter", "escape", "f5", "home", "page_down", "page_up",
    "shift", "space", "tab", "win",
)
_KEY_WORDS: dict[str, str] = {
    "enter": "enter", "intro": "enter", "return": "enter",
    "escape": "escape", "esc": "escape",
    "tab": "tab", "tabulador": "tab",
    "espacio": "space", "space": "space", "barra espaciadora": "space",
    "supr": "delete", "suprimir": "delete", "delete": "delete", "del": "delete",
    "backspace": "backspace", "retroceso": "backspace",
    "home": "home", "inicio": "home", "end": "end", "fin": "end",
    "f5": "f5",
    "abajo": "arrow_down", "down": "arrow_down", "arriba": "arrow_up", "up": "arrow_up",
    "izquierda": "arrow_left", "left": "arrow_left", "derecha": "arrow_right", "right": "arrow_right",
    "ctrl a": "ctrl_a", "ctrl c": "ctrl_c", "ctrl f": "ctrl_f", "ctrl k": "ctrl_k",
    "ctrl l": "ctrl_l", "ctrl t": "ctrl_t", "ctrl v": "ctrl_v", "ctrl w": "ctrl_w",
    "ctrl z": "ctrl_z",
}

# Aplicaciones que la gente nombra de otra forma que el catálogo de Inicio
# (bilingüe, sin código por app: sólo nombres). Se suman a las del lector de
# clics (effect_intent._CATALOG_NAME_ALIASES).
_EXTRA_ALIASES: tuple[tuple[frozenset[str], tuple[str, ...]], ...] = (
    (frozenset({"configuracion", "ajustes", "settings", "configuracion de windows",
                "windows settings", "la configuracion", "los ajustes"}),
     ("configuracion", "settings")),
    (frozenset({"chrome", "google chrome", "navegador chrome"}), ("google chrome", "chrome")),
    (frozenset({"edge", "microsoft edge", "navegador edge"}), ("microsoft edge", "edge")),
    (frozenset({"brave", "navegador brave"}), ("brave",)),
    (frozenset({"firefox", "mozilla firefox", "navegador firefox"}), ("firefox", "mozilla firefox")),
    (frozenset({"explorador de archivos", "explorador", "file explorer", "explorer"}),
     ("explorador de archivos", "file explorer")),
    (frozenset({"la calculadora", "calculadora", "calc", "calculator", "the calculator"}),
     ("calculadora", "calculator")),
)

_BROWSER_WORD = r"(?:chrome|google\s+chrome|opera(?:\s*gx)?|edge|microsoft\s+edge|brave|firefox|mozilla\s+firefox)"

_NAVIGATE_HEAD = (
    r"(?:ve|vete|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|"
    r"cambia|cambiate|take\s+me|abri|abre|open)"
)
_NAVIGATE_CLAUSE = re.compile(
    rf"^{_NAVIGATE_HEAD}\s+(?:a(?:l)?|to|hacia|hasta|into|en|por\s+la\s+gui\s+hasta|por\s+la\s+interfaz\s+hasta|through\s+the\s+gui\s+to)\s+"
    r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
    r"(?:(?:canal|channel|chat|sala|room|seccion|section|pestana|tab|apartado|menu)\s+(?:de\s+(?:voz|texto)\s+)?(?:de\s+|del\s+)?)?"
    r"(?P<target>\S.{0,60}?)[\s.!?]*$"
)
_KEY_CLAUSE = re.compile(
    r"^(?:apreta|aprieta|apretale|pulsa|pulsale|presiona|presionale|press|hit|toca|tocale|dale(?:\s+a)?)"
    r"(?:le|lo|la)?\s+(?:(?:la|el|the)\s+)?(?:tecla\s+|key\s+)?(?:(?:la|el|the)\s+)?"
    r"(?P<key>[a-z0-9]+(?:\s*\+\s*[a-z0-9]+|\s+[a-z](?![a-z]))?)[\s.!?]*$"
)
_TOGGLE_ON_CLAUSE = re.compile(
    r"^(?:activa|activame|activar|prende|prendeme|prender|enciende|encende|encender|habilita|habilitar|"
    r"turn\s+on|enable|switch\s+on|pon|pone|poneme)\s+(?:(?:el|la|los|las|the)\s+)?(?P<target>\S.{0,60}?)[\s.!?]*$"
)
_TOGGLE_OFF_CLAUSE = re.compile(
    r"^(?:desactiva|desactivame|desactivar|apaga|apagame|apagar|deshabilita|deshabilitar|quita|"
    r"turn\s+off|disable|switch\s+off|saca)\s+(?:(?:el|la|los|las|the)\s+)?(?P<target>\S.{0,60}?)[\s.!?]*$"
)
_CALCULATE_CLAUSE = re.compile(
    r"^(?:calcula|calculame|calcular|computa|resuelve|resolve|multiplica|suma|resta|divide|"
    r"calculate|compute|solve|work\s+out)(?:me)?\s+(?:cuanto\s+(?:es|da|vale)\s+|how\s+much\s+is\s+|what\s+is\s+)?"
    r"(?P<expr>[0-9][0-9\s.,+\-*/x×÷^%()=]*[0-9)])[\s.!?]*$"
)
_TYPE_CLAUSE = re.compile(
    r"^(?:escribi|escribe|escribime|tipea|tipeame|teclea|type|write)\s+(?P<text>\S.*?)[\s]*$"
)
_APP_FRAME_FRONT = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:en|in|on|dentro\s+de)\s+"
    r"(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)\s*[,;:]?\s+(?P<clause>.+)$"
)
_APP_FRAME_BACK = re.compile(
    r"^(?P<clause>.+?)\s+(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s.!?]*$"
)
_APP_FRAME_OPEN = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:abri|abre|abrime|abra|open|launch|lanza|ejecuta|inicia|start)\s+"
    r"(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)\s*(?:,|\s+y\s+|\s+and\s+|\s+y\s+luego\s+|\s+and\s+then\s+|\s+then\s+|\s+luego\s+|\s+despues\s+)\s*(?P<clause>.+)$"
)
_CLOSE_TABS = re.compile(
    r"^(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:(?:podes|puedes|podrias|can\s+you|could\s+you)\s+)?"
    r"(?:cierra|cierre|cerra|cerrame|cierrame|cerrar|close)\s+(?:todas\s+|all\s+)?(?:las\s+|the\s+|my\s+|mis\s+)?"
    r"(?:pestanas|tabs)(?:\s+abiertas|\s+open)?\s+(?:de|del|of|in|en)\s+(?:el\s+|the\s+|mi\s+|my\s+)?"
    rf"(?:navegador\s+|browser\s+)?(?P<browser>{_BROWSER_WORD})(?:\s*,?\s*(?:por\s+favor|please|porfa))?[\s.!?]*$"
)
_CLAUSE_HEAD = re.compile(
    r"^(?:ve|vete|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|cambia|cambiate|take\s+me|"
    r"apreta|aprieta|apretale|pulsa|pulsale|presiona|presionale|press|hit|toca|tocale|dale|"
    r"activa|activame|activar|prende|prendeme|prender|enciende|encende|encender|habilita|habilitar|turn|enable|pon|pone|poneme|"
    r"desactiva|desactivame|desactivar|apaga|apagame|apagar|deshabilita|deshabilitar|quita|disable|saca|"
    r"calcula|calculame|calcular|computa|resuelve|resolve|multiplica|suma|resta|divide|calculate|compute|solve|work|"
    r"escribi|escribe|escribime|tipea|tipeame|teclea|type|write|"
    r"haz|hace|clic|click|clickea|clica|abri|abre|open|busca|buscar|search|selecciona|select|elige|choose|"
    r"marca|desmarca|check|uncheck|cierra|cerra|close|desplaza|scroll|baja|sube)\b"
)


@dataclass(frozen=True, slots=True)
class MissionRequest:
    application: str | None
    goal: str
    success_check: str | None

    def arguments(self) -> dict[str, object]:
        arguments: dict[str, object] = {"goal": self.goal}
        if self.application:
            arguments["application"] = self.application
        if self.success_check:
            arguments["successCheck"] = self.success_check
        return arguments


# --------------------------------------------------------------------- lectura


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.split())


def _catalog_key(candidate: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    key = effect_intent._application_name_key(candidate.strip(" ,.;:!?"))
    resolved = effect_intent._catalog_alias_key(key, catalog.keys)
    if resolved is not None:
        return resolved
    for aliases, names in _EXTRA_ALIASES:
        if key in aliases:
            for name in names:
                if name in catalog.keys:
                    return name
    # «abre Steam»: the catalog name itself, or one catalog name that starts with it.
    starts = [entry_key for entry_key in catalog.keys if entry_key.startswith(key + " ") or entry_key == key]
    return starts[0] if len(starts) == 1 else None


def _display_name(key: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    for name, entry_key in catalog.entries:
        if entry_key == key:
            return name
    return key


def catalog_application(candidate: str, application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex) -> str | None:
    """The catalog display name a person's word names, or None when not installed."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    key = _catalog_key(candidate, catalog)
    return _display_name(key, catalog) if key is not None else None


def _key_from_words(words: str) -> str | None:
    folded = fold(words).replace("+", " ").replace("control ", "ctrl ")
    folded = " ".join(folded.split())
    if folded in _KEY_WORDS:
        return _KEY_WORDS[folded]
    if folded in KEYS:
        return folded
    return None


def read_clause(clause: str) -> tuple[str, str | None] | None:
    """One clause of doing inside an application → (goal, successCheck).

    Returns None when the clause has no request head at all (a plain noun,
    a question), so the mission reader abstains instead of inventing a goal.
    """

    folded = fold(clause).strip(" ,;:.!?")
    if not folded or len(folded) > 240:
        return None
    if _CLAUSE_HEAD.match(folded) is None and effect_intent._gerund_click_label(folded) is None:
        return None
    key = _KEY_CLAUSE.match(folded)
    if key is not None:
        catalog_key = _key_from_words(key.group("key"))
        if catalog_key is not None:
            return f"apretar {key.group('key').strip()}", f"stepDone:input.key.press:{catalog_key}"
    calculate = _CALCULATE_CLAUSE.match(folded)
    if calculate is not None:
        expression = " ".join(calculate.group("expr").split())
        return (
            f"calcular {expression}",
            "stepDone:input.key.press:enter|stepDone:input.visible.click:igual|stepDone:input.visible.click:=|stepDone:input.text.type:=",
        )
    on = _TOGGLE_ON_CLAUSE.match(folded)
    if on is not None and not _has_deictic_only(on.group("target")):
        target = on.group("target").strip()
        return f"activar {target}", f"control:{target}:on"
    off = _TOGGLE_OFF_CLAUSE.match(folded)
    if off is not None and not _has_deictic_only(off.group("target")):
        target = off.group("target").strip()
        return f"desactivar {target}", f"control:{target}:off"
    navigate = _NAVIGATE_CLAUSE.match(folded)
    if navigate is not None:
        target = navigate.group("target").strip(" \"'«»")
        if target and not re.search(r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b", target):
            return (
                f"ir a {target}",
                f"stepDone:input.visible.click:{target}|control:{target}:selected|title:{target}",
            )
    typed = _TYPE_CLAUSE.match(folded)
    if typed is not None:
        return f"escribir {typed.group('text').strip()}", "stepDone:input.text.type"
    label = effect_intent._visible_click_label(folded, allow_navigate=True)
    if label is not None:
        return f"hacer clic en {label}", f"stepDone:input.visible.click:{label}"
    return folded, None


def _has_deictic_only(target: str) -> bool:
    return fold(target) in {"lo", "la", "eso", "esto", "it", "that", "this"}


def mission_request(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """«en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>»,
    «cerrá todas las pestañas de <navegador>» → the mission, or None."""

    if not text or len(text) > 2048:
        return None
    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    folded = effect_intent._strip_request_envelope(fold(re.sub(r"[\r\n]+", " . ", text))).strip()
    if not folded or effect_intent._is_negative_effect_clause(folded):
        return None
    tabs = _CLOSE_TABS.match(folded)
    if tabs is not None:
        key = _catalog_key(tabs.group("browser"), catalog)
        if key is None:
            return None
        return MissionRequest(_display_name(key, catalog), "cerrar todas las pestañas", "count:TabItem<=1")
    for pattern in (_APP_FRAME_OPEN, _APP_FRAME_FRONT, _APP_FRAME_BACK):
        found = pattern.match(folded)
        if found is None:
            continue
        key = _catalog_key(found.group("app"), catalog)
        if key is None:
            continue
        clause = found.group("clause").strip(" ,;:")
        # «abre Steam y decime la hora»: the second clause must be doing inside
        # the app; a catalog read elsewhere is not a mission.
        read = read_clause(clause)
        if read is None:
            continue
        goal, check = read
        return MissionRequest(_display_name(key, catalog), goal, check)
    return None


def mission_clause_is_direct(text: str) -> bool:
    """Speech-act gate (effect_intent._is_direct_request): an app frame with a
    doing clause, or a close-all-tabs order on a named browser."""

    folded = effect_intent._strip_request_envelope(fold(text)).strip()
    if _CLOSE_TABS.match(folded) is not None:
        return True
    for pattern in (_APP_FRAME_OPEN, _APP_FRAME_FRONT, _APP_FRAME_BACK):
        found = pattern.match(folded)
        if found is not None and read_clause(found.group("clause")) is not None:
            return True
    return False


# ------------------------------------------------------------- elegir un paso

STEP_PROMPT = (
    "Sos el motor de computer use de BAXY. Ves la ventana de delante como texto: una "
    "lista de controles (índice · tipo · nombre · estado · zona · color) y el texto leído "
    "por zonas. Tenés un objetivo y devolvés EXACTAMENTE UN acto en JSON: "
    "click (i = índice del control y label = su nombre tal cual aparece), "
    "type (text), key (una tecla del catálogo), scroll (direction), open (application), "
    "done (evidence = texto que está en la vista y prueba el objetivo) o none (no ves por dónde seguir). "
    "Reglas: elegí sólo controles que están en la lista; no inventes nombres; si el objetivo "
    "ya se ve cumplido devolvé done con la evidencia literal; si el último paso falló, elegí otro "
    "control o otro acto, nunca el mismo; para escribir texto primero hace falta un campo enfocado; "
    "nunca escribas en un campo de contraseña; para enviar un mensaje o entrar a un canal de voz "
    "usá click en el control que lo nombra. why: una frase corta."
)

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "act": {"type": "string", "enum": list(ACTS)},
        "i": {"type": "integer", "minimum": -1, "maximum": 59},
        "label": {"type": "string", "maxLength": 80},
        "text": {"type": "string", "maxLength": 512},
        "key": {"type": "string", "enum": [*KEYS, ""]},
        "direction": {"type": "string", "enum": ["", "down", "up"]},
        "application": {"type": "string", "maxLength": 80},
        "evidence": {"type": "string", "maxLength": 120},
        "why": {"type": "string", "maxLength": 160},
    },
    "required": ["act", "i", "label", "text", "key", "direction", "application", "evidence", "why"],
    "additionalProperties": False,
}


def compact_view_text(view: dict, limit_controls: int = 60, limit_lines: int = 40) -> str:
    """The view as the model reads it: one short line per control, then the text by zone."""

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
        lines.append("controles:")
        for control in controls[:limit_controls]:
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


def find_control(view: dict, label: str, index: int | None = None) -> dict | None:
    """The one control the label (and index, when given) names; None when absent or ambiguous."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return None
    if isinstance(index, int) and 0 <= index < len(controls):
        candidate = controls[index]
        if isinstance(candidate, dict) and label_names(label, str(candidate.get("name") or "")):
            return candidate
    exact = [control for control in controls if isinstance(control, dict) and fold(control.get("name")) == fold(label)]
    if len(exact) == 1:
        return exact[0]
    loose = [control for control in controls if isinstance(control, dict) and label_names(label, str(control.get("name") or ""))]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        # «Biblioteca» as a navigation item and as a heading: the actionable one wins when unique.
        actionable = [control for control in loose if str(control.get("kind")) in effect_intent_actionable_kinds()]
        if len(actionable) == 1:
            return actionable[0]
    return None


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
    return hits[0] if len(hits) == 1 else None


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


def _composer_with_text(view: dict) -> bool:
    """Enter over a message composer that holds text reaches a person (contract §2.1)."""

    focused = _focused(view)
    if focused is None:
        return False
    name = fold(focused.get("name"))
    value = str(focused.get("value") or "").strip()
    return bool(value) and _COMPOSER_NAME.search(name) is not None


def application_is_in_front(view: dict, application: str | None) -> bool:
    if not application:
        return True
    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict):
        return False
    haystack = fold(window.get("title")) + " " + fold(window.get("process"))
    tokens = [token for token in fold(application).split() if len(token) >= 3 and token not in {"the", "los", "las", "navegador", "browser", "google", "microsoft", "mozilla"}]
    return any(token in haystack for token in tokens) if tokens else fold(application) in haystack


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
) -> dict[str, object]:
    """One step for the shell: {operation, arguments, reason}; operation is a
    catalog primitive, «done» or «none»."""

    # Deterministic first: the application named by the request is not in
    # front and nothing was done yet → bring it to the front (app.open reuses a
    # running window). No model needed for what the request already says.
    if application and not history and not application_is_in_front(view, application):
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
        if app_id is not None:
            return {"operation": "app.open", "arguments": {"appId": app_id}, "reason": "la aplicación pedida no está delante"}
    last_failed = history[-1] if history and isinstance(history[-1], dict) and history[-1].get("ok") is False else None
    user = (
        f"Pedido: {objective}\nObjetivo: {goal}"
        + (f"\nAplicación: {application}" if application else "")
        + (f"\nSe cumple cuando: {success_check}" if success_check else "")
        + f"\nPasos que quedan: {budget_left}\n"
        + ("Historial:\n" + "\n".join(_history_line(step) for step in history[-6:]) + "\n" if history else "")
        + "Vista:\n" + compact_view_text(view)
    )
    payload = {
        "messages": [
            {"role": "system", "content": STEP_PROMPT},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "baxy_computer_use_step", "schema": _STEP_SCHEMA}},
        "temperature": 0.0,
        "max_tokens": 160,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    raw = llm._post_schema_object(payload, "el paso de computer use")
    return validate_decision(raw, view=view, last_failed=last_failed, application_names=application_names)


def _history_line(step: dict) -> str:
    parts = [f"{step.get('step')}. {step.get('operation')}"]
    for key in ("label", "key", "text", "direction", "appId"):
        if step.get(key):
            parts.append(f"{key}={str(step.get(key))[:40]}")
    parts.append("ok" if step.get("ok") else f"FALLÓ ({step.get('error') or 'sin efecto'})")
    return " ".join(parts)


def validate_decision(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> dict[str, object]:
    """The model's act, checked against the view without any model (contract §4.4)."""

    if not isinstance(raw, dict):
        return _none("respuesta inválida del modelo")
    act = str(raw.get("act") or "")
    why = str(raw.get("why") or "")[:160]
    if act == "done":
        evidence = str(raw.get("evidence") or "").strip()
        if evidence and view_contains(view, evidence):
            return {"operation": "done", "arguments": {"evidence": evidence}, "reason": why}
        return _none("la evidencia citada no está en la vista", code="evidence_not_visible")
    if act == "click":
        label = str(raw.get("label") or "").strip()
        index = raw.get("i") if isinstance(raw.get("i"), int) and not isinstance(raw.get("i"), bool) else None
        if not label and index is not None:
            controls = view.get("controls") if isinstance(view, dict) else None
            if isinstance(controls, list) and 0 <= index < len(controls) and isinstance(controls[index], dict):
                label = str(controls[index].get("name") or "")
        if not label:
            return _none("el clic no nombra ningún control")
        control = find_control(view, label, index)
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
        text = str(raw.get("text") or "")
        if not text.strip():
            return _none("no hay texto que escribir")
        if _focused_is_password(view):
            return _none("el campo enfocado es una contraseña", code="password_field")
        return _guard_repeat({"operation": "input.text.type", "arguments": {"text": text[:4096]}, "reason": why}, last_failed)
    if act == "key":
        key = str(raw.get("key") or "")
        if key not in KEYS:
            return _none("tecla fuera del catálogo")
        arguments = {"key": key}
        if key == "enter" and _composer_with_text(view):
            arguments["target"] = "message_composer"
        return _guard_repeat({"operation": "input.key.press", "arguments": arguments, "reason": why}, last_failed)
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
        return _guard_repeat({"operation": "app.open", "arguments": {"appId": app_id}, "reason": why}, last_failed)
    return _none(why or "el modelo no ve por dónde seguir")


def _guard_repeat(decision: dict[str, object], last_failed: dict | None) -> dict[str, object]:
    if last_failed is None or last_failed.get("operation") != decision["operation"]:
        return decision
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    same = all(
        fold(last_failed.get(key)) == fold(arguments.get(key))
        for key in ("label", "key", "text", "direction", "appId")
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


def project_seen(observed: dict, language: str) -> dict[str, object]:
    """What the composer may say about a mission: only what the loop observed."""

    raw_steps = observed.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    done = [step for step in steps if isinstance(step, dict) and step.get("ok") is True]
    failed = [step for step in steps if isinstance(step, dict) and step.get("ok") is not True]
    raw_window = observed.get("window")
    window: dict[str, Any] = raw_window if isinstance(raw_window, dict) else {}
    seen: dict[str, object] = {
        "goal": observed.get("goal"),
        "reached": observed.get("reached") is True,
        "stepsDone": [describe_step(step, language) for step in done][:8],
        "windowTitle": window.get("title"),
        "joined": observed.get("joined") is True,
    }
    if observed.get("application"):
        seen["application"] = observed.get("application")
    if failed:
        seen["stepsFailed"] = [describe_step(step, language) for step in failed][:4]
    if observed.get("evidence"):
        seen["evidence"] = observed.get("evidence")
    if observed.get("satisfiedBy"):
        seen["satisfiedBy"] = observed.get("satisfiedBy")
    if observed.get("stoppedBy"):
        seen["stoppedBy"] = observed.get("stoppedBy")
    if observed.get("procedure") in {"replayed", "learned", "relearned"}:
        seen["procedure"] = observed.get("procedure")
    return seen


def compose_instruction(seen: dict, language: str) -> str:
    del language
    if seen.get("reached"):
        return (
            "This result is a computer-use mission that REACHED its goal: seen.goal is what was asked, "
            "seen.stepsDone the acts done in order (clicks, keys, typing) on the window seen.windowTitle, "
            "seen.evidence the text on screen that proves it when present. Say in one or two sentences, in "
            "the person's language and in the past tense, what you did and what you saw; quote seen.evidence "
            "exactly when it exists. seen.joined says whether a voice channel or call was joined: say you "
            "joined only if it is true. Never add steps, times or results that are not in seen."
        )
    return (
        "This result is a computer-use mission that did NOT reach its goal: seen.goal is what was asked, "
        "seen.stepsDone what was done before stopping, seen.stepsFailed what could not be done, "
        "seen.stoppedBy the typed reason. Say in one or two sentences, in the person's language, what was "
        "done and that the goal was not reached, naming what stopped it plainly (the control was not "
        "found, the screen did not change, the budget ran out). Never say it succeeded and never invent "
        "a cause that is not in seen."
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
    return None


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
