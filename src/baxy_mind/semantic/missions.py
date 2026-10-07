"""Lectura del pedido de computer use (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §6).

«en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>», «andá a la pestaña de X» → una misión
``mission.computer.use`` con aplicación, objetivo y la comprobación de éxito determinista (§4.3). La aplicación
tiene que estar en el catálogo de Inicio, o ser la categoría «navegador» (el navegador predeterminado de la persona)
cuando sólo se nombra una pestaña; el resto de la frase es el objetivo, con el verbo en cualquier persona (tú, vos,
usted, infinitivo, inglés). Vive en ``semantic/`` como toda lectura de la persona (plan de cierre 2026-09-24);
``computer_use`` elige y verifica los pasos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from .. import effect_intent
from .grammar import _head_is, imperative_rewrites

# The application a mission names when the person names only a tab: the shell
# resolves it to the front window of the person's default browser.
BROWSER_CATEGORY = "navegador"

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


_NAVIGATE_HEAD = (
    r"(?:ve|vete|ir|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|"
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
# Going to a tab by what it shows: «andá a la pestaña de YouTube», «go to the YouTube tab», «switch to the tab
# with YouTube». The tab is named by a part of its title.
_TAB_WORD = r"(?:pestana|tab|solapa)"
_TAB_CLAUSE = re.compile(
    rf"^{_NAVIGATE_HEAD}\s+(?:a(?:l)?|to|hacia|en)\s+(?:(?:la|el|the|mi|my)\s+)?"
    rf"(?:{_TAB_WORD}\s+(?:(?:de|del|con|que\s+tiene|que\s+dice|donde\s+esta|with|of|for|called|named)\s+)?"
    r"(?:(?:el|la|los|las|the)\s+)?(?P<after>\S.{0,60}?)"
    rf"|(?P<before>\S.{{0,60}}?)\s+{_TAB_WORD})(?:\s+on\s+it)?[\s.!?]*$"
)
# Words that say which tab by its place, not by what it shows («la siguiente pestaña», «the other tab»), and the
# article left alone when no tab is named («andá a la pestaña»).
_TAB_POSITION = frozenset({
    "siguiente", "anterior", "otra", "nueva", "ultima", "primera", "esta", "esa", "next", "previous", "other",
    "new", "last", "first", "this", "that", "la", "el", "the", "mi", "my",
})
# A name said before the tab word never ends on these: «andá a YouTube en otra pestaña», «go to google in a new
# tab» say where to open a page, not which tab to go to.
_TAB_PLACE_END = _TAB_POSITION | {"un", "una", "a", "an", "another", "en", "in", "on"}
# «… en el navegador», «in the browser»: the category said instead of a browser's name.
_BROWSER_CATEGORY_PLACE = r"(?:en|in|on|de|del|of)\s+(?:(?:el|the|mi|my)\s+)?(?:navegador|browser|web\s+browser)"
# The doing verbs of a clause, by their infinitive or by the form no rule derives (grammar._head_is reads
# «elegí», «seleccioná», «apretale» through their infinitive). «poner» is a doing only as the toggle reader reads
# it («poné el modo oscuro»): «ponme una canción» is music, which has its own operation.
_CLAUSE_VERB = (
    r"(?:ir|ve|vete|andar|entrar|meter|navegar|llevar|cambiar|apretar|aprieta|pulsar|presionar|tocar|dale|"
    r"activar|prender|encender|enciende|habilitar|desactivar|apagar|deshabilitar|quitar|sacar|"
    r"calcular|computar|resolver|resuelve|multiplicar|sumar|restar|dividir|divide|"
    r"escribir|escribe|tipear|teclear|hacer|haz|clic|clickear|clicar|abrir|abre|buscar|seleccionar|"
    r"elegir|elige|escoger|escoge|marcar|desmarcar|cerrar|cierra|desplazar|bajar|subir|sube|"
    r"go|navigate|switch|press|hit|tap|turn|enable|disable|calculate|compute|solve|work|type|write|click|"
    r"open|search|find|select|choose|pick|check|uncheck|close|scroll|toggle)"
)


@dataclass(frozen=True, slots=True)
class MissionRequest:
    application: str | None
    goal: str
    success_check: str | None
    # The person's clause of doing inside the application («baja el volumen»), empty for a tab named alone.
    clause: str = ""

    @property
    def names_a_tab(self) -> bool:
        return self.goal.startswith("ir a la pestaña ")

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


def _clause_readings(folded: str) -> tuple[str, ...]:
    """The clause as said and with its order as the tú/voseo imperative the readers read («seleccione»,
    «elegir», «pulse» → grammar.imperative_rewrites over this module's verbs)."""

    return (folded, *imperative_rewrites(folded, _CLAUSE_VERB))


def _is_doing(reading: str) -> bool:
    if re.match(r"take\s+me\b", reading):
        return True
    head = re.match(r"[a-z]+", reading)
    return head is not None and _head_is(head.group(), _CLAUSE_VERB)


def _tab_named(reading: str) -> str | None:
    """The part of a tab's title a «go to the tab» clause names, or None."""

    tab = _TAB_CLAUSE.match(reading)
    if tab is None:
        return None
    named = (tab.group("after") or tab.group("before") or "").strip(" \"'«»")
    if not named or named.split()[0] in _TAB_POSITION:
        return None
    return None if tab.group("before") and named.split()[-1] in _TAB_PLACE_END else named


def _read_act(folded: str) -> tuple[str, str | None] | None:
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
    tab = _tab_named(folded)
    if tab is not None:
        # The selected tab whose title holds the name (the shell matches a control's name by containment), or
        # the browser's window title, which is the title of the tab in front.
        return f"ir a la pestaña {tab}", f"control:{tab}:selected|title:{tab}"
    navigate = _NAVIGATE_CLAUSE.match(folded)
    if navigate is not None:
        target = navigate.group("target").strip(" \"'«»")
        if target and not re.search(r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b", target):
            return (
                f"ir a {target}",
                f"control:{target}:selected|title:{target}|page:{target}",
            )
    typed = _TYPE_CLAUSE.match(folded)
    if typed is not None:
        return f"escribir {typed.group('text').strip()}", "stepDone:input.text.type"
    return None


def read_clause(clause: str) -> tuple[str, str | None] | None:
    """One clause of doing inside an application → (goal, successCheck).

    The order may be said in any person (tú, vos, usted, infinitive, English).
    Returns None when the clause has no request head at all (a plain noun,
    a question, a statement), so the mission reader abstains instead of
    inventing a goal.
    """

    folded = fold(clause).strip(" ,;:.!?")
    if not folded or len(folded) > 240:
        return None
    readings = _clause_readings(folded)
    for reading in readings:
        act = _read_act(reading)
        if act is not None:
            return act
    doing = next((reading for reading in readings if _is_doing(reading)), None)
    if doing is None:
        if effect_intent._gerund_click_label(folded) is None:
            return None
        doing = folded
    elif _names_nothing(doing):
        return None
    label = effect_intent._visible_click_label(doing, allow_navigate=True)
    if label is not None:
        return f"hacer clic en {label}", f"stepDone:input.visible.click:{label}"
    return doing, None


def _has_deictic_only(target: str) -> bool:
    return fold(target) in {"lo", "la", "eso", "esto", "it", "that", "this"}


def _names_nothing(reading: str) -> bool:
    """«buscalo», «seleccioná eso»: the order's object is only a pronoun, nothing the window can show."""

    head, _, rest = reading.partition(" ")
    if rest:
        return _has_deictic_only(rest)
    clitic = re.search(r"(?:lo|la|los|las)$", head)
    return clitic is not None and _head_is(head[: clitic.start()], _CLAUSE_VERB)


def mission_request(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """«en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>»,
    «andá a la pestaña de X» → the mission, or None. Closing every tab is not a
    mission: it is browser.control close_all, confirmed (RiskPolicy)."""

    if not text or len(text) > 2048:
        return None
    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    folded = effect_intent._strip_request_envelope(fold(re.sub(r"[\r\n]+", " . ", text))).strip()
    if not folded or effect_intent._is_negative_effect_clause(folded):
        return None
    for application, clause in _app_frames(folded):
        key = _catalog_key(application, catalog)
        if key is None:
            continue
        clause = clause.strip(" ,;:")
        # «abre Steam y decime la hora»: the second clause must be doing inside
        # the app; a catalog read elsewhere is not a mission.
        read = read_clause(clause)
        if read is None:
            continue
        goal, check = read
        return MissionRequest(_display_name(key, catalog), goal, check, clause)
    # A tab named with no browser, or with the category alone («en el navegador»): the person's default browser
    # (a named browser above wins).
    tab = _bare_tab(folded)
    if tab is not None:
        goal, check = tab
        return MissionRequest(BROWSER_CATEGORY, goal, check)
    return None


def _bare_tab(folded: str) -> tuple[str, str] | None:
    bare = re.sub(rf"^{_BROWSER_CATEGORY_PLACE}\s*[,;:]?\s+|\s+{_BROWSER_CATEGORY_PLACE}(?=[\s.!?]*$)", "", folded, count=1)
    for reading in _clause_readings(bare.strip(" ,;:.!?")):
        named = _tab_named(reading)
        if named is not None:
            return f"ir a la pestaña {named}", f"control:{named}:selected|title:{named}"
    return None


def mission_clause_is_direct(text: str) -> bool:
    """Speech-act gate (effect_intent._is_direct_request): an app frame with a
    doing clause, or going to a tab."""

    folded = effect_intent._strip_request_envelope(fold(text)).strip()
    if _bare_tab(folded) is not None:
        return True
    return any(read_clause(clause) is not None for _, clause in _app_frames(folded, longer_names=False))


def _app_frames(folded: str, *, longer_names: bool = True) -> Iterable[tuple[str, str]]:
    """The (application, clause) splits the request frames say; ``longer_names`` also tries names of several words
    after «en», which only the catalog can tell from a statement («en la mañana tengo que ir al banco»)."""

    for pattern in (_APP_FRAME_OPEN, _APP_FRAME_FRONT, _APP_FRAME_BACK):
        found = pattern.match(folded)
        if found is None:
            continue
        yield found.group("app"), found.group("clause")
        if longer_names and pattern is _APP_FRAME_FRONT:
            # «en el bloc de notas escribí hola»: a name of several words ends where the clause begins.
            words = found.group("clause").split()
            for count in range(1, min(len(words), 4)):
                yield f"{found.group('app')} {' '.join(words[:count])}", " ".join(words[count:])
