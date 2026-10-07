"""Lectura del pedido de computer use (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §6).

«en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>», «andá a la pestaña de X» → una misión
``mission.computer.use`` con aplicación, objetivo y la comprobación de éxito determinista (§4.3). La aplicación
tiene que estar en el catálogo de Inicio, o ser la categoría «navegador» (el navegador predeterminado de la persona)
cuando sólo se nombra una pestaña; el resto de la frase es el objetivo, con el verbo en cualquier persona (tú, vos,
usted, infinitivo, inglés). Varias cláusulas de hacer unidas por «y», «,», «luego», «después», «then», «and» son una
misión encadenada: ``steps`` lleva cada sub-objetivo con su aplicación (la última nombrada, o la que nombra la
cláusula) y su comprobación. Vive en ``semantic/`` como toda lectura de la persona (plan de cierre 2026-09-24);
``computer_use`` elige y verifica los pasos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Iterable

from .. import effect_intent
from .catalog import _CATALOG_NAME_ALIASES
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
# «el chat con Ron92», «la conversación con Ana», «el canal de voz de X»: a generic place noun before the name is not the
# name (measured: «abrí el chat con Ron92» searched Discord for «chat con ron92»).
_PLACE_NOUN = (
    r"(?:(?:canal|channel|chat|conversacion|conversation|sala|room|seccion|section|pestana|tab|apartado|menu|carpeta|"
    r"folder|servidor|server|perfil|profile)\s+(?:de\s+(?:voz|texto)\s+)?(?:de\s+|del\s+|con\s+|with\s+|of\s+)?)?"
)
_OPEN_INSIDE_CLAUSE = re.compile(
    r"^(?:abri|abre|abrime|abra|abrir|open)\s+(?:(?:el|la|los|las|the|mi|my|un|una)\s+)?"
    + _PLACE_NOUN + r"(?P<target>\S.{0,60}?)[\s.!?]*$"
)
_NAVIGATE_CLAUSE = re.compile(
    rf"^{_NAVIGATE_HEAD}\s+(?:a(?:l)?|to|hacia|hasta|into|en|por\s+la\s+gui\s+hasta|por\s+la\s+interfaz\s+hasta|through\s+the\s+gui\s+to)\s+"
    r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
    + _PLACE_NOUN + r"(?P<target>\S.{0,60}?)[\s.!?]*$"
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
    r"^(?:calcula|calculame|calcular|computa|resuelve|resolve|multiplica|multiplicar|suma|sumar|resta|restar|divide|dividi|"
    r"dividir|haz|hace|hacer|hazme|haceme|calculate|compute|solve|work\s+out|multiply|add|subtract|do)(?:me)?\s+(?:cuanto\s+(?:es|da|vale)\s+|how\s+much\s+is\s+|what\s+is\s+)?"
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
    r"crear|crea|renombrar|guardar|copiar|pegar|mover|mueve|enviar|envia|mandar|descargar|"
    r"go|navigate|switch|press|hit|tap|turn|enable|disable|calculate|compute|solve|work|type|write|click|"
    r"open|search|find|select|choose|pick|check|uncheck|close|scroll|toggle|create|rename|save|copy|paste|move|send|"
    r"download)"
)


# The same place of a window said in the other language («go to the library» on a Spanish Steam, «andá a
# configuración» on an English app): a check also accepts the names the window may carry instead. Names only, no
# application; the application tables below and in the catalog add theirs.
_LABEL_ALIASES: tuple[frozenset[str], ...] = (
    frozenset({"biblioteca", "library"}), frozenset({"tienda", "store", "shop"}),
    frozenset({"configuracion", "ajustes", "settings", "preferencias", "preferences"}),
    frozenset({"inicio", "home", "pagina principal"}), frozenset({"descargas", "downloads"}),
    frozenset({"amigos", "friends"}), frozenset({"comunidad", "community"}), frozenset({"perfil", "profile"}),
    frozenset({"mensajes", "messages"}), frozenset({"historial", "history"}),
    frozenset({"favoritos", "favorites", "favourites"}), frozenset({"ayuda", "help"}),
    frozenset({"cuenta", "account"}), frozenset({"notificaciones", "notifications"}),
    frozenset({"privacidad", "privacy"}), frozenset({"sonido", "sound"}), frozenset({"pantalla", "display"}),
    frozenset({"red", "network"}), frozenset({"juegos", "games"}), frozenset({"colecciones", "collections"}),
    frozenset({"musica", "music"}), frozenset({"archivos", "files"}), frozenset({"documentos", "documents"}),
    frozenset({"escritorio", "desktop"}), frozenset({"contactos", "contacts"}),
    frozenset({"recibidos", "bandeja de entrada", "inbox"}), frozenset({"enviados", "sent"}),
    frozenset({"borradores", "drafts"}), frozenset({"papelera", "trash"}), frozenset({"herramientas", "tools"}),
    frozenset({"opciones", "options"}), frozenset({"modo avion", "modo de avion", "airplane mode"}),
    frozenset({"actualizaciones", "updates"}), frozenset({"aplicaciones", "apps"}),
    frozenset({"sistema", "system"}), frozenset({"personalizacion", "personalization"}),
    frozenset({"dispositivos", "devices"}), frozenset({"servidores", "servers"}),
    frozenset({"buscar", "search"}), frozenset({"canciones", "songs"}), frozenset({"imagenes", "pictures"}),
    frozenset({"calendario", "calendar"}), frozenset({"insertar", "insert"}), frozenset({"tabla", "table"}),
    frozenset({"elementos enviados", "sent items"}), frozenset({"escala", "scale"}),
    # Colours and drawing tools, said in either language («elegí el rojo» on an English Paint).
    frozenset({"rojo", "red"}), frozenset({"azul", "blue"}), frozenset({"verde", "green"}),
    frozenset({"amarillo", "yellow"}), frozenset({"negro", "black"}), frozenset({"blanco", "white"}),
    frozenset({"naranja", "orange"}), frozenset({"violeta", "morado", "purple", "violet"}),
    frozenset({"rosa", "rosado", "pink"}), frozenset({"gris", "gray", "grey"}), frozenset({"marron", "brown"}),
    frozenset({"lapiz", "pencil"}), frozenset({"pincel", "pinceles", "brush", "brushes"}),
    frozenset({"goma", "goma de borrar", "borrador", "eraser"}),
    frozenset({"balde de pintura", "bote de pintura", "relleno", "rellenar", "fill"}),
    frozenset({"rectangulo", "rectangle"}), frozenset({"texto", "text"}), frozenset({"linea", "line"}),
    frozenset({"circulo", "elipse", "ovalo", "circle", "ellipse", "oval"}),
    frozenset({"selector de color", "cuentagotas", "color picker"}),
)


def label_alternatives(name: str) -> tuple[str, ...]:
    """The other names (other language, catalog aliases) the place ``name`` may carry on screen, sorted; empty
    when none is known."""

    key = fold(name)
    groups = (*_LABEL_ALIASES, *(aliases for aliases, _ in (*_EXTRA_ALIASES, *_CATALOG_NAME_ALIASES)))
    found = {alias for group in groups if key in group for alias in group}
    found.discard(key)
    return tuple(sorted(found))


def _with_alternatives(target: str, atoms: Iterable[str]) -> str:
    """The check ``atoms`` (templates over ``{}``) for the target and each of its other names, OR-ed."""

    names = (target, *label_alternatives(target))
    return "|".join(atom.replace("{}", name) for name in names for atom in atoms)


@dataclass(frozen=True, slots=True)
class MissionStep:
    """One sub-goal of a chained mission: its own goal, application and check (contract §4.1, steps[])."""

    application: str | None
    goal: str
    success_check: str | None
    clause: str = ""

    def arguments(self) -> dict[str, object]:
        return {"goal": self.goal, "application": self.application, "successCheck": self.success_check}


# A chained mission carries at most this many sub-goals (contract §4.1).
MAX_STEPS = 8


@dataclass(frozen=True, slots=True)
class MissionRequest:
    application: str | None
    goal: str
    success_check: str | None
    # The person's clause of doing inside the application («baja el volumen»), empty for a tab named alone.
    clause: str = ""
    # «… y después en Discord andá a general»: the sub-goals in order, empty for a single clause.
    steps: tuple[MissionStep, ...] = ()

    @property
    def names_a_tab(self) -> bool:
        return not self.steps and self.goal.startswith("ir a la pestaña ")

    def arguments(self) -> dict[str, object]:
        arguments: dict[str, object] = {"goal": self.goal}
        if self.application:
            arguments["application"] = self.application
        if self.success_check:
            arguments["successCheck"] = self.success_check
        if self.steps:
            arguments["steps"] = [step.arguments() for step in self.steps]
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
    if len(starts) == 1:
        return starts[0]
    # «Teams» for «Microsoft Teams»: the one catalog name that ends with it.
    ends = [entry_key for entry_key in catalog.keys if entry_key.endswith(" " + key)] if not starts else []
    return ends[0] if len(ends) == 1 else None


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


# «… y mandalo», «envialo», «send it»: sending what was just written is Enter in the message box; RiskPolicy asks
# before it reaches the person (measured: «escribí "prueba" y mandalo» typed «… y mandalo» as text).
_SEND_CLAUSE = re.compile(
    r"^(?:manda|mandale|mandalo|mandala|mandar|mandarlo|envia|envialo|enviala|enviar|enviarlo|send|submit)"
    r"(?:\s+(?:it|el\s+mensaje|the\s+message|eso|that))?[\s.!?]*$"
)


# What a copy or a paste acts on when it is said: the result, the text, the number shown («copiá el resultado»).
_WHAT_IS_SHOWN = (
    r"(?:it|that|this|eso|esto|todo|all|(?:el|la|the)\s+(?:resultado|result|texto|text|numero|number|valor|value|"
    r"respuesta|answer|link|enlace|url|direccion|address))"
)
# The edits every window takes from the keyboard: «seleccioná todo», «copialo», «pegá», «deshacé», «select all».
_SHORTCUT_CLAUSES: tuple[tuple[re.Pattern[str], str, tuple[str, ...]], ...] = (
    (re.compile(r"^(?:selecciona|seleccionar|seleccione|marca|select|highlight)\s+(?:todo(?:\s+el\s+texto)?|all(?:\s+the\s+text)?|everything)$"), "ctrl a", ()),
    (re.compile(rf"^(?:copia|copialo|copiala|copiar|copiarlo|copy)(?:\s+{_WHAT_IS_SHOWN})?$"), "ctrl c", ("copiar", "copy")),
    (re.compile(rf"^(?:pega|pegalo|pegala|pegar|pegarlo|paste)(?:\s+{_WHAT_IS_SHOWN})?(?:\s+(?:aca|aqui|here))?$"), "ctrl v", ("pegar", "paste")),
    (re.compile(r"^(?:deshace|deshaz|deshacer|deshacelo|undo)(?:\s+(?:it|that|eso|lo\s+ultimo|the\s+last\s+(?:thing|change)))?$"), "ctrl z", ("deshacer", "undo")),
)
# «12 por 7», «345 más 12», «100 entre 4», «12 times 7», «6 by 7»: the operation said with words, as its sign.
_SPOKEN_OPERATORS: tuple[tuple[str, str], ...] = (
    (r"multiplicad[oa]\s+por|multiplied\s+by|por|times|x", "×"),
    (r"dividid[oa]\s+(?:por|entre)|divided\s+by|entre|over", "÷"),
    (r"mas|plus", "+"),
    (r"menos|minus", "-"),
)
_CALCULATE_HEAD = re.compile(
    r"^(?:(?P<times>multiplica|multiplicar|multiplicame|multiply)|(?P<split>divide|dividi|dividir|dividime)|"
    r"(?P<sum>suma|sumar|sumame|add)|(?P<less>resta|restar|subtract))\b"
)


def _spoken_expression(folded: str) -> str:
    """The clause with the operations said in words between two numbers written as their signs; «y», «and», «by»
    follow the verb that said which operation («sumá 45 y 30», «multiply 6 by 7»)."""

    head = _CALCULATE_HEAD.match(folded)
    pairs = list(_SPOKEN_OPERATORS)
    if head is not None:
        sign = {"times": "×", "split": "÷", "sum": "+", "less": "-"}[head.lastgroup or "sum"]
        pairs.append((r"y|and|by|con|with|to" if sign in "×÷+" else r"de|from", sign))
    for words, sign in pairs:
        folded = re.sub(rf"(?<=\d)\s+(?:{words})\s+(?=\d)", f" {sign} ", folded)
    return folded


# «poné la primera», «reproducí el primer resultado», «play the first one»: what a search just listed, by its place.
_ORDINAL = r"(?:primer[oa]?|segund[oa]|tercer[oa]?|ultim[oa]|first|second|third|last|1st|2nd|3rd)"
_PLAY_HEAD = r"(?:pone|pon|poneme|ponele|reproduci|reproduce|reproducir|reproducime|toca|tocame|play|start\s+playing|dale\s+play\s+a)"
_PLAY_ORDINAL_CLAUSE = re.compile(
    rf"^{_PLAY_HEAD}\s+(?P<what>(?:(?:la|el|lo|the)\s+)?{_ORDINAL}"
    r"(?:\s+(?:cancion|tema|resultado|video|episodio|capitulo|opcion|playlist|lista|album|disco|podcast|radio|"
    r"one|song|track|result|video|episode|option|list|album|record))?)"
    r"(?:\s+(?:que\s+(?:aparezca|aparece|salga|sale)|de\s+(?:la\s+lista|los\s+resultados)|on\s+the\s+list|"
    r"in\s+the\s+results|that\s+(?:shows\s+up|appears)))?$"
)
# Playing shows as the player's pause control, after a click or a key of this sub-goal (something already playing
# before it does not count).
_PLAYING_CHECK = "|".join(
    f"control:{pause}&stepDone:{operation}"
    for pause in ("pausa", "pause")
    for operation in ("input.visible.click", "input.key.press")
)
# The kinds of things a person creates or renames by name inside an application.
_ITEM_KIND = (
    r"(?:subcarpeta|carpeta|archivo|documento|fichero|nota|lista\s+de\s+reproduccion|lista|playlist|hoja\s+de\s+calculo|"
    r"hoja|canal|grupo|servidor|evento|tarea|presentacion|proyecto|album|directorio|"
    r"subfolder|folder|file|document|note|list|spreadsheet|sheet|channel|group|server|event|task|presentation|"
    r"project|album|directory)"
)
_NAMING = (
    r"(?:que\s+se\s+llame|llamad[oa]|con\s+(?:el\s+)?nombre(?:\s+de)?|de\s+nombre|titulad[oa]|"
    r"named|called|titled|with\s+the\s+name)"
)
# «creá una carpeta llamada X», «create a new folder named X», «hacé la carpeta X».
_CREATE_CLAUSE = re.compile(
    r"^(?:crea|crear|creame|crea\s+me|haz|hace|hacer|hazme|haceme|genera|generar|agrega|agregar|anadi|anade|anadir|"
    r"create|make|add|new)\s+"
    r"(?:(?P<article>un|una|otro|otra|a|an|another|la|el|the)\s+)?(?:(?:nuev[oa]|new)\s+)?(?P<kind>" + _ITEM_KIND + r")"
    r"(?:\s+(?:nuev[oa]|new))?\s+(?:(?P<naming>" + _NAMING + r")\s+)?[\"'«“]?(?P<name>[^\s\"'«».,;!?]\S{0,79}?(?:\s+\S+){0,5}?)[\"'»”]?[\s.!?]*$"
)
# «renombrá la carpeta X a Y», «cambiale el nombre a X por Y», «rename X to Y», «renombralo a Y».
_RENAME_CLAUSE = re.compile(
    r"^(?:renombra|renombrar|renombrale|renombre|rename|cambia(?:le)?\s+el\s+nombre|change\s+the\s+name)"
    r"(?P<pronoun>lo|la|\s+it)?"
    r"(?:\s+(?:de|del|a|al|of))?\s+"
    r"(?:(?:(?:el|la|los|las|the|this|esta|este|mi|my)\s+)?(?:" + _ITEM_KIND + r"\s+)?(?:(?:el|la|the)\s+)?"
    r"[\"'«“]?(?P<old>\S.{0,80}?)[\"'»”]?\s+)??"
    r"(?:a|al|como|por|to|as|into)\s+[\"'«“]?(?P<new>\S.{0,80}?)[\"'»”]?[\s.!?]*$"
)
# «buscá a Duki», «buscá Hades», «search for Queen», «look up X»: typing a name in the window's own search.
_SEARCH_CLAUSE = re.compile(
    r"^(?:busca|buscar|buscame|buscale|busque|search(?:\s+for)?|search\s+up|find(?:\s+me)?|look\s+(?:up|for)|"
    r"encontra|encuentra|encontrar)\s+(?:(?:a|al)\s+)?(?P<what>\S.{0,80}?)[\s.!?]*$"
)
_SEARCH_NOUN = (
    r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
    r"(?:(?:cancion|tema|juego|pelicula|serie|video|archivo|documento|contacto|usuario|artista|album|"
    r"canal|chat|conversacion|servidor|carpeta|playlist|lista|"
    r"song|track|game|movie|show|video|file|document|contact|user|artist|album|channel|server|folder)\s+"
    r"(?:de\s+|del\s+|con\s+|called\s+|named\s+)?)?"
)
# «elegí el lápiz», «seleccioná el color rojo», «pick the red color», «choose the fill tool»: a tool, a colour or an
# option of the window, chosen by clicking it.
_SELECT_CLAUSE = re.compile(
    r"^(?:selecciona|seleccionar|seleccione|elegi|elige|elegir|escogi|escoge|escoger|agarra|usa|usar|"
    r"select|choose|pick|use)\s+(?P<what>\S.{0,60}?)[\s.!?]*$"
)
_SELECT_NOUN_BEFORE = re.compile(
    r"^(?:(?:el|la|los|las|the|un|una|a|an)\s+)?(?:(?:color|colour|herramienta|tool|opcion|option)\s+(?:de\s+(?:la\s+|el\s+)?)?)?"
)
_SELECT_NOUN_AFTER = re.compile(r"\s+(?:color|colour|tool|option|button|boton)$")


def _select_target(what: str) -> str:
    target = _SELECT_NOUN_BEFORE.sub("", what.strip(" \"'«»“”"), count=1)
    return _SELECT_NOUN_AFTER.sub("", target).strip()


def _select_check(target: str) -> str:
    # Chosen is the control selected or pressed; where the window says neither, the verified click on it.
    return _with_alternatives(target, ("control:{}:selected", "control:{}:on", "stepDone:input.visible.click:{}"))


def _read_act(folded: str) -> tuple[str, str | None] | None:
    if _SEND_CLAUSE.match(folded) is not None:
        return "enviar", "stepDone:input.key.press:enter"
    key = _KEY_CLAUSE.match(folded)
    if key is not None:
        catalog_key = _key_from_words(key.group("key"))
        if catalog_key is not None:
            return f"apretar {key.group('key').strip()}", f"stepDone:input.key.press:{catalog_key}"
    for shortcut, keys, labels in _SHORTCUT_CLAUSES:
        if shortcut.match(folded) is not None:
            # The key, or the window's own control for the same edit.
            check = "|".join((f"stepDone:input.key.press:{keys.replace(' ', '_')}",
                              *(f"stepDone:input.visible.click:{label}" for label in labels)))
            return f"apretar {keys}", check
    played = _PLAY_ORDINAL_CLAUSE.match(folded)
    if played is not None:
        return f"reproducir {played.group('what')}", _PLAYING_CHECK
    created = _CREATE_CLAUSE.match(folded)
    if created is not None and (created.group("naming") or created.group("article") in {"la", "el", "the"}):
        name = created.group("name").strip(" \"'«»“”")
        if name and fold(name) not in {"nueva", "nuevo", "new", "vacia", "vacio", "empty"}:
            # The item named appears among the window's controls (never the field the name was typed in).
            return f"crear {created.group('kind')} {name}", f"control:{name}"
    renamed = _RENAME_CLAUSE.match(folded)
    if renamed is not None:
        old = (renamed.group("old") or "").strip(" \"'«»“”")
        new = renamed.group("new").strip(" \"'«»“”")
        if new and not _has_deictic_only(new):
            return (f"renombrar {old} a {new}" if old else f"renombrar a {new}"), f"control:{new}"
    searched = _SEARCH_CLAUSE.match(folded)
    if searched is not None:
        what = re.sub(rf"^{_SEARCH_NOUN}", "", searched.group("what"), count=1).strip(" \"'«»“”")
        if what and not _has_deictic_only(what):
            # Searched is the page titled with the name (a site's search goes to it), or the name typed in this
            # sub-goal and submitted while it is on screen (the window's results).
            return f"buscar {what}", f"title:{what}|stepDone:input.text.type&stepDone:input.key.press:enter&text:{what}"
    selected = _SELECT_CLAUSE.match(folded)
    if selected is not None:
        target = _select_target(selected.group("what"))
        if target and not _has_deictic_only(target):
            return f"seleccionar {target}", _select_check(target)
    calculate = _CALCULATE_CLAUSE.match(_spoken_expression(folded))
    if calculate is not None:
        expression = " ".join(calculate.group("expr").split())
        return (
            f"calcular {expression}",
            "stepDone:input.key.press:enter|stepDone:input.visible.click:igual|stepDone:input.visible.click:=|stepDone:input.text.type:=",
        )
    on = _TOGGLE_ON_CLAUSE.match(folded)
    if on is not None and not _has_deictic_only(on.group("target")) and not re.match(_ORDINAL, on.group("target")):
        target = on.group("target").strip()
        return f"activar {target}", _with_alternatives(target, ("control:{}:on",))
    off = _TOGGLE_OFF_CLAUSE.match(folded)
    if off is not None and not _has_deictic_only(off.group("target")):
        target = off.group("target").strip()
        return f"desactivar {target}", _with_alternatives(target, ("control:{}:off",))
    if _NEW_TAB_CLAUSE.match(folded) is not None:
        return "apretar ctrl t", "stepDone:input.key.press:ctrl_t"
    tab = _tab_named(folded)
    if tab is not None:
        # The selected tab whose title holds the name (the shell matches a control's name by containment), or
        # the browser's window title, which is the title of the tab in front.
        return f"ir a la pestaña {tab}", f"control:{tab}:selected|title:{tab}"
    for place in (_NAVIGATE_CLAUSE.match(folded), _OPEN_INSIDE_CLAUSE.match(folded)):
        if place is None:
            continue
        # «ve a la biblioteca y escribí hola»: the place ends where the next clause of doing begins.
        target = _segments(place.group("target"))[0].strip(" \"'«»")
        address = _ADDRESS.fullmatch(target)
        if address is not None:
            if place.re is _NAVIGATE_CLAUSE:
                # «andá a es.wikipedia.org»: the address typed in the browser's bar; arrived is the site in the title.
                return f"ir a la direccion {target}", f"title:{_site_name(address.group('host'))}"
            continue
        target = _ENGLISH_PLACE_AFTER.sub("", target)
        if target:
            atoms = ["control:{}:selected", "title:{}", "page:{}"]
            if _SECTION_WORD.search(place.group(0)[: place.start("target")]):
                # A section of a page is reached by its link: the verified click on it is arriving.
                atoms.append("stepDone:input.visible.click:{}")
            return f"ir a {target}", _with_alternatives(target, atoms)
    typed = _TYPE_CLAUSE.match(folded)
    if typed is not None:
        return f"escribir {typed.group('text').strip()}", "stepDone:input.text.type"
    return None


# «abrí una pestaña nueva», «open a new tab»: the browser's own key for it.
_NEW_TAB_CLAUSE = re.compile(
    r"^(?:abri|abre|abrir|abrime|open|crea|create)\s+(?:(?:una|otra|a|another)\s+)?(?:(?:nueva|new)\s+)?"
    r"(?:pestana|tab|solapa)(?:\s+(?:nueva|new))?$"
)
_ADDRESS = re.compile(r"(?:https?://)?(?P<host>(?:[a-z0-9-]+\.)+[a-z]{2,63})(?:/\S*)?")
_SECTION_WORD = re.compile(r"\b(?:seccion|section|apartado)\b")
# «the music channel», «the Pictures folder»: the English place noun after the name is not the name.
_ENGLISH_PLACE_AFTER = re.compile(r"(?<=\S)\s+(?:channel|folder|server|section|menu|chat|room|page)$")


def _site_name(host: str) -> str:
    """«es.wikipedia.org» → «wikipedia»: the label a site's pages carry in their titles."""

    labels = [label for label in host.split(".") if label != "www"]
    if len(labels) > 2 and labels[-2] in {"co", "com", "org", "net", "gov", "gob", "edu", "ac"}:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else labels[0]


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
    label = effect_intent._visible_click_label(doing, allow_navigate=True) or effect_intent._visible_click_label(
        _TOUCH_HEAD.sub("haz clic en ", doing, count=1)
    )
    if label is not None:
        return f"hacer clic en {label}", _with_alternatives(label, ("stepDone:input.visible.click:{}",))
    return doing, None


# «tocá Comunidad», «tap Join»: touching a control is clicking it.
_TOUCH_HEAD = re.compile(r"^(?:toca|tocale|toque|tap(?:\s+on)?|clickea|clica|clicka|pincha)\s+(?:(?:en|on)\s+)?")


def _has_deictic_only(target: str) -> bool:
    return fold(target) in {"lo", "la", "eso", "esto", "it", "that", "this"}


def _names_nothing(reading: str) -> bool:
    """«buscalo», «seleccioná eso»: the order's object is only a pronoun, nothing the window can show."""

    head, _, rest = reading.partition(" ")
    if rest:
        return _has_deictic_only(rest)
    clitic = re.search(r"(?:lo|la|los|las)$", head)
    return clitic is not None and _head_is(head[: clitic.start()], _CLAUSE_VERB)


# The goals whose tail is the person's own literal: typed, searched, a name given to what is created or renamed.
_LITERAL_GOAL = re.compile(
    r"^(?P<head>escribir |buscar |crear " + _ITEM_KIND + r" |renombrar (?:(?P<old>.+?) )?a )(?P<literal>.+)$"
)


def _restore(wanted: str, said: str) -> str:
    """The folded piece ``wanted`` as the person wrote it in ``said`` (case, accents), without delimiting quotes."""

    folded_chars: list[str] = []
    origin: list[int] = []
    for position, character in enumerate(said):
        for piece in fold(character) or (" " if character.isspace() else ""):
            folded_chars.append(piece)
            origin.append(position)
    start = "".join(folded_chars).find(wanted)
    if start < 0:
        return wanted.strip("\"'«»“”")
    end = start + len(wanted) - 1
    return said[origin[start]:origin[end] + 1].strip().strip("\"'«»“”").strip()


def _as_said(goal: str, said: str) -> str:
    """«escribir X», «buscar X», «crear carpeta X», «renombrar X a Y»: X and Y as the person wrote them (case,
    accents) and without the quotes that delimit them (measured: «escribí "leche"» typed the quotes, and the folded
    reading would type «hola mundo» for «Hola Mundo»)."""

    found = _LITERAL_GOAL.match(goal)
    if found is None:
        return goal
    head = found.group("head")
    if found.group("old"):
        head = f"renombrar {_restore(found.group('old'), said)} a "
    return head + _restore(found.group("literal").strip(), said)


# An undoing or paying act said anywhere in the request: never read as a mission (owner's rule; RiskPolicy asks for
# such a step, and a whole goal of that kind is not handed to the screen loop).
_UNDOING_OR_PAYING_ACT = re.compile(
    r"\b(?:borra|borrala|borralo|borralas|borralos|borrar|borre|borrame|elimina|eliminala|eliminalo|eliminar|elimine|"
    r"vaciar|vacia\s+(?:la|el|los|las)|formatea|formatear|formatealo|desinstala|desinstalar|desinstalalo|desinstale|"
    r"compra|compralo|comprala|comprar|comprame|compre|paga|pagalo|pagala|pagar|pague|transferi|transferir|transfiere|"
    r"delete|remove|uninstall|format|buy|purchase|pay|wipe|erase)\b"
)
def _orders_undoing_or_paying(folded: str) -> bool:
    """An undoing or paying act in a clause of the request; what a clause types is the person's text, not an act
    («type buy milk»)."""

    for segment in _segments(folded):
        said = next((clause for _, clause in _app_frames(segment, longer_names=False)), segment)
        if any(_TYPE_CLAUSE.match(reading) for reading in _clause_readings(said.strip(" ,;:.!?"))):
            continue
        if _UNDOING_OR_PAYING_ACT.search(segment):
            return True
    return False


# «… y decime si el modo es claro u oscuro», «and tell me what it says»: a question about what the window shows at
# the end. It is no sub-goal: the mission's final answers it from the last view (computer_use.project_seen).
_QUESTION_TAIL = re.compile(
    r"(?:\s*[,;.]\s*(?:(?:y|and)\s+)?|\s+(?:y|and)\s+|\s+(?=(?:despues|luego|then|entonces)\s))"
    r"(?:(?:despues|luego|then|entonces|al\s+final|finally)\s+)?"
    r"(?P<question>(?:decime|dime|digame|deci|contame|cuentame|avisame|fijate|mira|mirame|tell\s+me|let\s+me\s+know|"
    r"show\s+me|check)\s+(?:si|que|cual|cuales|cuanto|cuanta|cuantos|cuantas|como|donde|cuando|quien|whether|if|what|"
    r"which|how|where|when|who)\b.*)$"
)
# The mark between the sub-goals and the question in a mission's goal (computer_use.project_seen reads it).
QUESTION_MARK = "; y responder: "


def mission_request(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """«en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>»,
    «andá a la pestaña de X» → the mission, or None. Closing every tab is not a
    mission: it is browser.control close_all, confirmed (RiskPolicy). A closing
    question about what the window shows («… y decime si está activado») goes
    with the goal, for the final to answer from the last view."""

    if not text or len(text) > 2048:
        return None
    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    folded = effect_intent._strip_request_envelope(fold(re.sub(r"[\r\n]+", " . ", text))).strip()
    if not folded or effect_intent._is_negative_effect_clause(folded) or _orders_undoing_or_paying(folded):
        return None
    asked = _QUESTION_TAIL.search(folded)
    question = None
    if asked is not None and asked.start() > 0:
        question = _restore(asked.group("question").strip(" .!?"), text)
        folded = folded[: asked.start()].strip(" ,;.")
    mission = _read_mission(folded, text, catalog)
    if mission is None or question is None:
        return mission
    steps = mission.steps or (MissionStep(mission.application, mission.goal, mission.success_check, mission.clause),)
    goal = "; luego ".join(step.goal for step in steps).encode("utf-8")[:400].decode("utf-8", "ignore")
    tail = (QUESTION_MARK + question).encode("utf-8")[:100].decode("utf-8", "ignore")
    return replace(mission, goal=goal + tail, steps=steps)


# «en el explorador de archivos, entrá a Descargas …», «en Paint, agarrá el lápiz»: the comma after the application
# that frames the whole request is no joiner of clauses.
_FRAME_COMMA = re.compile(r"^(?P<frame>(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?))\s*[,;:]\s+")


def _read_mission(folded: str, text: str, catalog: effect_intent.ApplicationCatalogIndex) -> MissionRequest | None:
    framed = _FRAME_COMMA.match(folded)
    if framed is not None and _catalog_key(framed.group("app"), catalog) is not None:
        folded = framed.group("frame") + " " + folded[framed.end():]
    chained = _chained_request(folded, catalog)
    if chained is not None:
        steps = tuple(replace(step, goal=_as_said(step.goal, text)) for step in chained.steps)
        joined = "; luego ".join(step.goal for step in steps).encode("utf-8")[:500].decode("utf-8", "ignore")
        return replace(chained, steps=steps, goal=joined if steps else chained.goal)
    for application, clause in _app_frames(folded):
        key = _catalog_key(application, catalog)
        if key is None:
            continue
        clause = clause.strip(" ,;:")
        if len(_segments(clause)) > 1:
            # Several clauses the chain could not read: one of them is no doing it knows, so none is read alone.
            continue
        # «abre Steam y decime la hora»: the second clause must be doing inside
        # the app; a catalog read elsewhere is not a mission.
        read = read_clause(clause)
        if read is None:
            continue
        goal, check = read
        return MissionRequest(_display_name(key, catalog), _as_said(goal, text), check, clause)
    # A tab named with no browser, or with the category alone («en el navegador»): the person's default browser
    # (a named browser above wins).
    tab = _bare_tab(folded)
    if tab is not None:
        goal, check = tab
        return MissionRequest(BROWSER_CATEGORY, goal, check)
    return None


_NAMED_PLACE = re.compile(
    r"(?<![a-z0-9])(?:en|in|on|dentro\s+de|abri|abre|abrime|abra|abrir|open|launch)\s+(?:(?:la|el|the)\s+)?"
    r"(?P<words>[a-z0-9][a-z0-9 .+-]{0,60})"
)


def free_form_arguments(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> dict[str, object] | None:
    """The decider chose the engine for a request the reader does not read: the goal is the person's own words, as
    said, and the application the installed one the request names, if any (else the window in front). No check:
    the loop's model says done with evidence on screen."""

    goal = " ".join(str(text or "").split()).strip(" .!?¡¿")
    if not goal or len(goal.encode("utf-8")) > 512:
        return None
    arguments: dict[str, object] = {"goal": goal}
    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is not None:
        folded = fold(goal)
        exact = catalog.occurrence_pattern.search(folded)
        key = exact.group("target").casefold() if exact is not None else None
        if key not in catalog.keys:
            key = None
            for found in _NAMED_PLACE.finditer(folded):
                words = found.group("words").split()
                key = next(
                    (
                        resolved
                        for count in range(min(len(words), 4), 0, -1)
                        if (resolved := _catalog_key(" ".join(words[:count]), catalog)) is not None
                    ),
                    None,
                )
                if key is not None:
                    break
        if key is not None:
            arguments["application"] = _display_name(key, catalog)
    return arguments


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
    if any(read_clause(clause) is not None for _, clause in _app_frames(folded, longer_names=False)):
        return True
    # «andá a la biblioteca en Steam y después a general en Discord»: clauses of doing, none forbidden, one of them
    # doing something inside an app (opening one alone is app.open's own reading).
    segments = _segments(folded)
    return (
        len(segments) > 1
        and all(_starts_clause(segment) and not effect_intent._is_negative_effect_clause(segment) for segment in segments)
        and any(
            read_clause(clause) is not None
            for segment in segments
            for _, clause in _app_frames(segment, longer_names=False)
        )
    )


# ------------------------------------------------------------ misiones encadenadas

# Where one clause of doing ends and the next begins: a comma, a semicolon, a sentence stop, or a coordinator
# («y», «luego», «después», «y después», «then», «and then», «and»). A split is kept only when what follows is
# itself a clause of doing (``_starts_clause``): «escribí hola y chau» stays one text.
_JOINER = re.compile(
    r"\s*[,;]\s*(?:(?:y|and)\s+)?(?:(?:luego|despues|entonces|then|after\s+that)\s+(?:de\s+eso\s+)?)?"
    r"|\s+\.\s+"
    r"|\s+(?:y|and)\s+(?:(?:luego|despues|entonces|then|after\s+that)\s+(?:de\s+eso\s+)?)?"
    r"|\s+(?:luego|despues|entonces|then|after\s+that)\s+(?:de\s+eso\s+)?"
)
# «abrí Steam» alone, as one clause of a chain: the application the next clauses happen in.
_BARE_OPEN = re.compile(
    r"^(?:abri|abre|abrime|abra|abrir|open|launch|lanza|ejecuta|inicia|start)\s+"
    r"(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s.!?]*$"
)


def _starts_clause(segment: str) -> bool:
    segment = segment.strip(" ,;:.!?")
    if not segment:
        return False
    if _BARE_OPEN.match(segment) is not None or _pronoun_family(segment) is not None or read_clause(segment) is not None:
        return True
    return any(read_clause(clause) is not None for _, clause in _app_frames(segment, longer_names=False))


def _segments(folded: str) -> list[str]:
    """The clauses of doing a request chains, in order; the whole text when it says one."""

    pieces: list[str] = []
    joiners: list[str] = []
    start = 0
    for found in _JOINER.finditer(folded):
        if found.start() == 0 or found.end() >= len(folded):
            continue
        pieces.append(folded[start:found.start()])
        joiners.append(found.group())
        start = found.end()
    pieces.append(folded[start:])
    if len(pieces) == 1:
        return pieces
    merged = [pieces[0]]
    for joiner, piece in zip(joiners, pieces[1:]):
        if _starts_clause(piece):
            merged.append(piece)
            continue
        elliptic = _elliptic(piece, joiner, merged[-1])
        if elliptic is not None:
            merged.append(elliptic)
        elif (_VERB_AND_OBJECT.match(piece) or _CLITIC_ORDER.match(piece)) and _family(merged[-1]) is not None:
            # «andá a la biblioteca y dibujá a Batman»: an order the readers do not know is no part of a place's
            # name; kept apart, it leaves the chain unread (the decider's) instead of glued into the place.
            merged.append(piece)
        else:
            merged[-1] += joiner + piece
    return [segment.strip(" ,;") for segment in merged]


_ELLIPTIC_PLACE = re.compile(r"(?:a|al|hacia|to)\s+\S")
# A word followed by its object («dibujá a Batman», «descargá el juego», «draw a circle»): said like an order.
_VERB_AND_OBJECT = re.compile(
    r"^[a-z]{3,}\s+(?:a|al|el|la|los|las|un|una|unos|unas|mi|mis|tu|que|con|lo|le|me|the|an|my|your|it|me|to)\s+\S"
)
# A verb with its pronoun and nothing else («llamalo», «descargala»): an order, never the end of a name.
_CLITIC_ORDER = re.compile(r"^[a-z]{2,}[aei]r?(?:me|te|se)?(?:lo|la|los|las|le|les)$")
_SEQUENCER = re.compile(r"\b(?:luego|despues|entonces|then|after\s+that)\b")
# «… y después el color rojo», «then the red color»: an object said with its article, the verb said once before.
_ARTICLE_OBJECT = re.compile(r"^(?:el|la|los|las|the)\s+\S")
# «go to System, then Display», «then downloads»: a bare name of at most three words.
_BARE_NAME = re.compile(r"^[a-z0-9][a-z0-9.+-]*(?:\s+[a-z0-9][a-z0-9.+-]*){0,2}$")


def _elliptic(piece: str, joiner: str, previous: str) -> str | None:
    """The clause a piece says with the previous clause's verb left out: «andá a la biblioteca y después a general»,
    «elegí el lápiz y después el color rojo», «hacé clic en Insertar y después en Tabla», «go to System, then
    Display». None when the piece is not such an object, or the previous clause is no go-to, choice or click."""

    family = _family(previous)
    piece = piece.strip(" ,;:.!?")
    sequenced = _SEQUENCER.search(joiner) is not None
    candidates: list[str] = []
    if family == "ir a ":
        if _ELLIPTIC_PLACE.match(piece):
            candidates.append(f"ve {piece}")
        elif sequenced and (_ARTICLE_OBJECT.match(piece) or _BARE_NAME.match(piece)):
            candidates.append(f"ve a {piece}")
    elif family == "seleccionar " and sequenced and (_ARTICLE_OBJECT.match(piece) or _BARE_NAME.match(piece)):
        candidates.append(f"selecciona {piece}")
    elif family == "hacer clic en " and sequenced:
        candidates.append("haz clic en " + re.sub(r"^(?:en|on)\s+", "", piece))
    return next((candidate for candidate in candidates if _starts_clause(candidate)), None)


def _family(segment: str) -> str | None:
    """The goal head of the act a clause says (``ir a ``, ``seleccionar ``, ``hacer clic en ``, ``buscar ``), or
    None."""

    segment = segment.strip(" ,;:.!?")
    reads = (read_clause(segment), *(read_clause(clause) for _, clause in _app_frames(segment, longer_names=False)))
    for read in reads:
        if read is None:
            continue
        for head in ("ir a la pestaña ", "ir a la direccion ", "ir a ", "seleccionar ", "hacer clic en ", "buscar "):
            if read[0].startswith(head):
                return None if head in {"ir a la pestaña ", "ir a la direccion "} else head
    return None


# «abrilo», «activala», «ponelo», «open it», «turn it on»: the object is what the previous clause named.
_PRONOUN_CLAUSE = re.compile(
    r"^(?P<verb>[a-z]+?)(?:me|le|se)?(?:lo|la|los|las)$"
    r"|^(?P<english>open|play|select|choose|pick|enable|disable|activate|start|turn\s+on|turn\s+off)\s+(?:it|that|this|them)$"
    r"|^turn\s+(?:it|that|this|them)\s+(?P<turn>on|off)$"
    # «creá la carpeta Proyectos y entrá»: going in says no object at all.
    r"|^(?P<bare>entra|entrar|entrale|metete|go\s+in|get\s+in|step\s+in)$"
)
_PRONOUN_FAMILIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("open", frozenset({"abri", "abre", "abrir", "open", "entra", "entrar", "entrale", "metete", "go in", "get in",
                        "step in"})),
    ("on", frozenset({"activa", "activar", "prende", "prender", "enciende", "encende", "encender", "habilita",
                      "habilitar", "enable", "activate", "turn on", "on"})),
    ("off", frozenset({"desactiva", "desactivar", "apaga", "apagar", "deshabilita", "deshabilitar", "disable",
                       "turn off", "off"})),
    ("play", frozenset({"pone", "pon", "poner", "reproduci", "reproduce", "reproducir", "play", "start"})),
    ("select", frozenset({"selecciona", "seleccionar", "elegi", "elige", "elegir", "escogi", "escoge", "escoger",
                          "select", "choose", "pick"})),
)


def _pronoun_family(segment: str) -> str | None:
    found = _PRONOUN_CLAUSE.match(segment.strip(" ,;:.!?"))
    if found is None:
        return None
    verb = " ".join(
        (found.group("verb") or found.group("english") or found.group("turn") or found.group("bare") or "").split()
    )
    return next((family for family, verbs in _PRONOUN_FAMILIES if verb in verbs), None)


def _pronoun_read(family: str, referent: str) -> tuple[str, str | None] | None:
    if family == "play":
        return f"reproducir {referent}", _PLAYING_CHECK
    said = {"open": "abri", "on": "activa", "off": "desactiva", "select": "selecciona"}[family]
    return read_clause(f"{said} {referent}")


# A place said by its kind alone after a clause that named one («… y abrí el chat», «and open the folder»).
_GENERIC_PLACE = frozenset({
    "chat", "conversacion", "canal", "carpeta", "perfil", "pagina", "resultado", "primer resultado", "juego",
    "cancion", "archivo", "documento", "ficha", "conversation", "channel", "folder", "profile", "page", "result",
    "first result", "game", "song", "file", "document",
})
# The goal heads whose tail names the thing a pronoun of the next clause stands for.
_REFERENT_GOAL = re.compile(
    r"^(?:ir a la pestaña |ir a la direccion |ir a |buscar |crear " + _ITEM_KIND + r" |renombrar (?:.+? )?a |"
    r"seleccionar |activar |desactivar |hacer clic en |reproducir )(?P<object>.+)$"
)


def _chained_request(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> MissionRequest | None:
    """«abre Steam y andá a la biblioteca, y después en Discord andá a general» → one mission whose ``steps`` are
    the sub-goals in order (contract §4.1). The application is carried forward and switches where a clause names
    another one; each sub-goal has its own goal and check (``read_clause``); a clause whose object is a pronoun
    («buscá Hades y abrilo») acts on what the previous clause named. None for a single clause (today's reading
    stays), for a clause that is not doing, or with no application named at all."""

    segments = _segments(folded)
    if len(segments) < 2 or any(effect_intent._is_negative_effect_clause(segment) for segment in segments):
        return None
    steps: list[MissionStep] = []
    current: str | None = None
    opened: str | None = None
    referent: str | None = None
    for segment in segments:
        segment = segment.strip(" ,;:.!?")
        bare = _BARE_OPEN.match(segment)
        bare_key = _catalog_key(bare.group("app"), catalog) if bare is not None else None
        if bare_key is not None:
            if opened is not None:
                steps.append(_open_step(opened))
            current = opened = _display_name(bare_key, catalog)
            continue
        family = _pronoun_family(segment)
        framed = None if family is not None else next(
            (
                (_display_name(key, catalog), clause.strip(" ,;:"), read)
                for application, clause in _app_frames(segment)
                if (key := _catalog_key(application, catalog)) is not None
                and (read := read_clause(clause.strip(" ,;:"))) is not None
            ),
            None,
        )
        if framed is not None:
            application, clause, read = framed
        else:
            if family is not None:
                read = _pronoun_read(family, referent) if referent is not None else None
            else:
                read = read_clause(segment)
            if read is None:
                return None
            application, clause = current, segment
        goal, check = read
        if referent is not None and goal.startswith("ir a ") and goal[len("ir a "):] in _GENERIC_PLACE:
            # «buscá a Mamá y abrí el chat»: the chat, the folder, the result of what was just named.
            goal, check = _pronoun_read("open", referent) or read
        if application is None and goal.startswith("ir a la pestaña "):
            application = BROWSER_CATEGORY
        if opened is not None and application != opened:
            steps.append(_open_step(opened))
        opened = None
        current = application
        steps.append(MissionStep(application, goal, check, clause))
        named = _REFERENT_GOAL.match(goal)
        if named is not None:
            referent = named.group("object")
    if opened is not None:
        steps.append(_open_step(opened))
    doing = [step for step in steps if not step.goal.startswith("abrir ")]
    if len(steps) < 2 or not doing or len(steps) > MAX_STEPS or all(step.application is None for step in steps):
        return None
    return MissionRequest(
        steps[0].application,
        "; luego ".join(step.goal for step in steps).encode("utf-8")[:500].decode("utf-8", "ignore"),
        None,
        doing[0].clause,
        tuple(steps),
    )


def _open_step(application: str) -> MissionStep:
    """«… y abrí Discord» with nothing to do in it: the sub-goal is having it in front."""

    return MissionStep(application, f"abrir {application}", f"title:{application}|process:{application}")


# «abrí Paint y después elegí el lápiz»: the sequencer after the coordinator is no part of the clause.
_LEADING_SEQUENCER = re.compile(r"^(?:(?:y|and)\s+)?(?:luego|despues|entonces|then|after\s+that)\s+(?:de\s+eso\s+)?")


def _app_frames(folded: str, *, longer_names: bool = True) -> Iterable[tuple[str, str]]:
    """The (application, clause) splits the request frames say; ``longer_names`` also tries names of several words
    after «en», which only the catalog can tell from a statement («en la mañana tengo que ir al banco»)."""

    for pattern in (_APP_FRAME_OPEN, _APP_FRAME_FRONT, _APP_FRAME_BACK):
        found = pattern.match(folded)
        if found is None:
            continue
        clause = _LEADING_SEQUENCER.sub("", found.group("clause"), count=1)
        yield found.group("app"), clause
        if longer_names and pattern is _APP_FRAME_FRONT:
            # «en el bloc de notas escribí hola»: a name of several words ends where the clause begins.
            words = clause.split()
            for count in range(1, min(len(words), 4)):
                yield f"{found.group('app')} {' '.join(words[:count])}", " ".join(words[count:])


# What the engine never tries on its own when no operation serves the request: undoing or paying (owner's rule:
# destructive or paying steps are asked for; a whole goal of that kind is not handed to the screen loop).
_DESTRUCTIVE_OR_PAYING = re.compile(
    r"(?:^|\s)(?:borr|elimin|formate|desinstal|compr|pag|transfer|vaci|delete|remove|uninstall|format|buy|"
    r"purchase|pay|wipe|erase)\w*"
)


def engine_can_try(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Owner 2026-10-07 («que use el PC como yo»): a direct order about the PC that no operation serves is tried by
    the computer-use engine with the person's own words as its goal, instead of being told as a limit. Not for a
    question, a place outside this PC's world, a prohibition, or a destructive or paying goal."""

    from .web import asks_for_information

    folded = fold(text)
    if not folded or len(folded) > 300 or "?" in text or "¿" in text:
        return False
    # The turn already read it as a request (it was closed as a limit, not as talk); here only what the engine
    # must not try is kept out.
    stripped = effect_intent._strip_request_envelope(folded)
    if (
        effect_intent.out_of_world_request(text)
        or effect_intent._is_negative_effect_clause(stripped)
        # «en Discord no escribas nada»: the prohibition said after the application.
        or any(effect_intent._is_negative_effect_clause(clause) for _, clause in _app_frames(stripped, longer_names=False))
        or asks_for_information(text)
        or _DESTRUCTIVE_OR_PAYING.search(folded)
    ):
        return False
    return free_form_arguments(text, application_names) is not None
