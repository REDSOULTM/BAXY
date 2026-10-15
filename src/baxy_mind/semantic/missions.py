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

import functools
import itertools
import json
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Iterator

from .. import effect_intent
from .account_acts import account_act
from .catalog import _CATALOG_NAME_ALIASES, app_alias_rows, app_alias_words, application_name_without_frame
from .colours import colour_check_words, is_basic_colour, names_the_colour_kind
from . import app_places, chats, cu_tipos, lexicon, messaging
from .drag import asks_to_drag
from .grammar import _ASSISTANT_NAME, _COVERAGE_ACTION_HEAD, _head_is, imperative_rewrites
from .normalize import alternation

# The application a mission names when the person names only a tab: the shell
# resolves it to the front window of the person's default browser.
BROWSER_CATEGORY = "navegador"

# The keys of the shell's input.key.press whose effect is not in the window they are sent to: switching to another
# window, the Start menu, the Task Manager. Never a step of a mission (safety review r10a: bound to the mission's
# window they still act on the desktop over the person); the shell refuses them too (computer_use_key_outside_window).
KEYS_OUTSIDE_THE_WINDOW = ("alt_tab", "ctrl_shift_escape", "win")

# The keys a mission step may press: the shell's catalog without those.
KEYS = (
    "arrow_down", "arrow_left", "arrow_right", "arrow_up",
    "backspace", "context_menu", "control", "ctrl_a", "ctrl_c", "ctrl_f", "ctrl_h", "ctrl_k",
    "ctrl_l", "ctrl_o", "ctrl_s", "ctrl_shift_s", "ctrl_t", "ctrl_v", "ctrl_w",
    "ctrl_x", "ctrl_z", "delete", "end", "enter", "escape", "f10", "f5", "home", "page_down", "page_up",
    "shift", "shift_f10", "space", "tab",
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
    "ctrl z": "ctrl_z", "ctrl h": "ctrl_h", "ctrl o": "ctrl_o", "ctrl s": "ctrl_s", "ctrl x": "ctrl_x",
    "ctrl shift s": "ctrl_shift_s", "shift f10": "shift_f10", "f10": "f10",
}

# Aplicaciones que la gente nombra de otra forma que el catálogo de Inicio
# (bilingüe, sin código por app: sólo nombres). Se suman a las del lector de
# clics (effect_intent._CATALOG_NAME_ALIASES). Los dos van en data/app_aliases.v1.json.
_EXTRA_ALIASES: tuple[tuple[frozenset[str], tuple[str, ...]], ...] = app_alias_rows("mission_aliases")


# «cambiá a descargas», «pasá al canal general», «switch over to general»: changing to a place that names no mode
# (``_read_mode`` reads the modes) is going there.
_NAVIGATE_HEAD = (
    r"(?:ve|vete|ir|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch(?:\s+over)?|change|"
    r"cambia|cambiate|pasa|pasate|take\s+me|abri|abre|open)"
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
    r"^(?:apreta|aprieta|apretale|pulsa|pulsale|presiona|presionale|press|hit|(?P<touch>toca|tocale|dale(?:\s+a)?|tap(?:\s+on)?))"
    r"(?:le|lo|la)?\s+(?:(?:la|el|the)\s+)?(?P<named>tecla\s+|key\s+)?(?:(?:la|el|the)\s+)?"
    r"(?P<key>[a-z0-9]+(?:\s*\+\s*[a-z0-9]+|\s+[a-z](?![a-z]))?)[\s.!?]*$"
)
# «tocá Inicio», «tap Home»: touching a word that names a key and also a place of the window (Spotify's and
# YouTube's «Inicio») is clicking that place; only «tocá la tecla Inicio» or «apretá Inicio» is the key. «dale enter»,
# «tocá escape» name no place and stay keys.
_KEYS_THAT_NAME_PLACES = frozenset({"inicio", "home", "fin", "end"})
# Ronda 20 P8 (v3-33): a switch is a thing already there, said definite. A verb that also gets or makes a thing
# («sacá», «quitá», «poné», data ``lexicon.TOGGLE_AMBIGUOUS_*``) turns it off or on only before a definite object
# («sacá el modo oscuro»), and no verb does before an indefinite or counted one («sacá una captura», «desactivá un
# filtro»): those fall to the free reading, with no check of a switch. Review 2: the article, once said, is never given
# back to the name (possessive ``?+``): «apagá el 5G» is the switch «5g», and «apagá la otra pantalla» stays no switch
# instead of one named «la otra pantalla». A count is a number apart («sacá 2 fotos»); a number inside the name
# («el 5G», «el 2FA») is no count.
_TOGGLE_OBJECT = (
    r"(?!" + alternation(lexicon.INDEFINITE_LEADS) + r"\s|\d+(?:[.,]\d+)?\s)(?P<target>\S.{0,60}?)[\s.!?]*$"
)
_TOGGLE_DEFINITE = r"\s+" + alternation(lexicon.TOGGLE_DEFINITE_LEADS) + r"\s+"
_TOGGLE_ON_CLAUSE = re.compile(
    r"^(?:(?:activa|activame|activar|prende|prendeme|prender|enciende|encende|encender|habilita|habilitar|"
    r"turn\s+on|enable|switch\s+on)\s+(?:(?:el|la|los|las|the)\s+)?+|"
    + alternation(lexicon.TOGGLE_AMBIGUOUS_ON_VERBS) + _TOGGLE_DEFINITE + r")" + _TOGGLE_OBJECT
)
_TOGGLE_OFF_CLAUSE = re.compile(
    r"^(?:(?:desactiva|desactivame|desactivar|apaga|apagame|apagar|deshabilita|deshabilitar|"
    r"turn\s+off|disable|switch\s+off|"
    # v3 punto 2: a box unticked («desmarcá X», «uncheck X», «sacale lo de X», «sacale el tilde a X»).
    r"desmarca|desmarcar|desmarcale|destilda|destildar|uncheck|untick|deselect|"
    r"sacale\s+(?:lo\s+de|el\s+(?:tilde|check|visto)\s+(?:a|de))|quitale\s+el\s+(?:tilde|check|visto)\s+(?:a|de))"
    r"\s+(?:(?:el|la|los|las|the|lo\s+de)\s+)?+|"
    + alternation(lexicon.TOGGLE_AMBIGUOUS_OFF_VERBS) + _TOGGLE_DEFINITE + r")" + _TOGGLE_OBJECT
)
_CALCULATE_CLAUSE = re.compile(
    r"^(?:calcula|calculame|calcular|computa|resuelve|resolve|multiplica|multiplicar|suma|sumar|resta|restar|divide|dividi|"
    r"dividir|haz|hace|hacer|hazme|haceme|calculate|compute|solve|work\s+out|multiply|add|subtract|do)(?:me)?\s+(?:cuanto\s+(?:es|da|vale)\s+|how\s+much\s+is\s+|what\s+is\s+)?"
    r"(?P<expr>[0-9][0-9\s.,+\-*/x×÷^%()=]*[0-9)])[\s.!?]*$"
)
# v3-11 r7 «escribe ahi: comprar pan, leche y huevos» typed «ahi: comprar pan…»: the place said before the colon
# («ahí», «aquí», «there», «en ella») points at where to write and is no part of the text.
_TYPE_CLAUSE = re.compile(
    r"^(?:escribi|escribe|escribime|tipea|tipeame|teclea|type|write)"
    r"(?:\s+(?:ahi|aqui|alli|aca|alla|there|here|in\s+it|en\s+ella|en\s+el)(?=\s*:))?"
    r"(?:\s*:\s*|\s+)(?P<text>\S.*?)[\s]*$"
)
# «in the Clock app go to …», «en la app de Configuración andá a …»: the word that says it is an application frames the
# name, before or after it, and is no part of the clause.
_APP_FRAME_FRONT = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:en|in|on|dentro\s+de)\s+"
    r"(?:(?:la|el|the)\s+)?(?:(?:app|aplicacion|application)\s+(?:(?:de|del)\s+)?)?"
    r"(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)(?:\s+(?:app|aplicacion|application))?\s*[,;:]?\s+(?P<clause>.+)$"
)
_APP_FRAME_BACK = re.compile(
    r"^(?P<clause>.+?)\s+(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s.!?]*$"
)
_APP_FRAME_BACK_LAST = re.compile(
    r"^(?P<clause>.+)\s+(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s.!?]*$"
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


# The modes a window offers by their own name, said with no mode word («cambiá a científica», «switch to
# scientific»): choosing one is a mode reading (``_read_mode``) whose check needs the window to name it.
_MODE_NAMES: tuple[frozenset[str], ...] = (
    frozenset({"cientifica", "scientific"}), frozenset({"conversor", "converter"}),
    frozenset({"estandar", "standard"}), frozenset({"grafica", "graphing"}),
    frozenset({"programador", "programmer"}),
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
    frozenset({"buscar", "busqueda", "search"}), frozenset({"canciones", "songs"}), frozenset({"imagenes", "images", "pictures"}),
    frozenset({"calendario", "calendar"}), frozenset({"insertar", "insert"}), frozenset({"tabla", "table"}),
    frozenset({"elementos enviados", "sent items"}), frozenset({"escala", "scale"}),
    # The modes a window offers by name: «cambiá a científica» on an English calculator.
    *_MODE_NAMES,
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
    # 2026-10-07 «in the Clock app go to Stopwatch» on a Spanish Windows («Cronómetro»): the places and items that
    # Windows and its own apps show, by both of their names.
    frozenset({"cronometro", "stopwatch"}), frozenset({"temporizador", "temporizadores", "timer", "timers"}),
    frozenset({"alarma", "alarmas", "alarm", "alarms"}), frozenset({"reloj mundial", "world clock"}),
    frozenset({"enfoque", "sesiones de enfoque", "focus", "focus sessions"}),
    frozenset({"colores", "colors", "colours"}), frozenset({"temas", "themes"}), frozenset({"fondo", "background"}),
    # 2026-10-07 «go to Start» passed on Settings' Home at the first look: «inicio» is that Home, never Start.
    frozenset({"pantalla de bloqueo", "lock screen"}),
    frozenset({"barra de tareas", "taskbar"}), frozenset({"fuentes", "fonts"}),
    frozenset({"hora e idioma", "hora y idioma", "time & language", "time and language"}),
    frozenset({"accesibilidad", "accessibility"}), frozenset({"cuentas", "accounts"}),
    # 2026-10-07 a3 «go to Accessibility and then to Text size» on a Spanish Settings: «Tamaño de texto» is its name.
    frozenset({"tamano de texto", "tamano del texto", "text size"}),
    frozenset({"efectos visuales", "visual effects"}), frozenset({"puntero del mouse", "mouse pointer"}),
    frozenset({"energia", "power"}), frozenset({"energia y bateria", "power & battery", "power and battery"}),
    frozenset({"bateria", "battery"}), frozenset({"almacenamiento", "storage"}),
    frozenset({"portapapeles", "clipboard"}), frozenset({"acerca de", "about"}),
    frozenset({"wi-fi", "wifi", "wlan"}), frozenset({"impresoras", "printers"}),
    frozenset({"impresoras y escaneres", "printers & scanners", "printers and scanners"}),
    # Ronda 20b, palanca 8, objetivo 3 (pasada r18, v3-44): the Control Panel's «Dispositivos e impresoras» is handed by
    # Windows 11 to Settings, whose page with the printers is «Impresoras y escáneres»: the place reached is that page.
    frozenset({
        "dispositivos e impresoras", "devices and printers", "devices & printers", "impresoras y escaneres",
        "printers & scanners", "printers and scanners",
    }),
    frozenset({"raton", "mouse"}), frozenset({"teclado", "keyboard"}),
    frozenset({"bluetooth y dispositivos", "bluetooth & devices", "bluetooth and devices"}),
    frozenset({"privacidad y seguridad", "privacy & security", "privacy and security"}),
    frozenset({"red e internet", "network & internet", "network and internet"}),
    frozenset({"aplicaciones instaladas", "installed apps"}), frozenset({"modo oscuro", "dark mode"}),
    frozenset({"cientifica", "scientific"}), frozenset({"estandar", "standard"}),
    frozenset({"programador", "programmer"}), frozenset({"grafica", "graphing"}),
    frozenset({"conversor", "convertidor", "converter"}), frozenset({"memoria", "memory"}),
    frozenset({"rendimiento", "performance"}), frozenset({"procesos", "processes"}),
    frozenset({"servicios", "services"}), frozenset({"aplicaciones de arranque", "aplicaciones de inicio", "startup apps"}),
    frozenset({"usuarios", "users"}), frozenset({"detalles", "details"}),
    frozenset({"galeria", "gallery"}), frozenset({"albumes", "albums"}), frozenset({"carpetas", "folders"}),
    frozenset({"recientes", "recent"}), frozenset({"compartido", "compartidos", "shared"}),
    frozenset({"este equipo", "this pc"}), frozenset({"papelera de reciclaje", "recycle bin"}),
    # Menu names only; «archivo», «vista», «nuevo» and «abrir» are acts as well, which a window's title or a control
    # holds at the first look («Nuevo» beside any list, «Abrir» in a title), so they carry no other name.
    frozenset({"editar", "edicion", "edit"}),
    frozenset({"formato", "format"}), frozenset({"diseno", "design"}), frozenset({"revisar", "review"}),
)


def label_alternatives(name: str) -> tuple[str, ...]:
    """The other names (other language, catalog aliases) the place ``name`` may carry on screen, sorted; empty
    when none is known."""

    key = fold(name)
    found = {alias for group in _LABEL_ALIASES if key in group for alias in group}
    if not found:
        # An application's names only for a word no place of a window carries: «alarmas» is the Clock's page, never
        # its title «Reloj» (a check that accepted it would hold before any step).
        found = {alias for aliases, _ in (*_EXTRA_ALIASES, *_CATALOG_NAME_ALIASES) if key in aliases for alias in aliases}
    found.discard(key)
    return tuple(sorted(found))


# Names never translated by the model (cu_model_calls.translate_label): the acts a window's title or any control holds
# at the first look («Nuevo» beside any list, «Abrir» in a title; see the menu names above), and the acts that change
# an account or data, which are clicked only by the name the person said.
_UNTRANSLATED_LABELS = frozenset({
    "archivo", "file", "vista", "view", "ver", "nuevo", "nueva", "new", "abrir", "open", "guardar", "save",
    "cerrar", "close", "salir", "exit", "quit", "eliminar", "borrar", "delete", "remove", "quitar", "enviar", "send",
    "comprar", "buy", "pagar", "pay", "instalar", "install", "desinstalar", "uninstall", "seguir", "follow",
    "suscribirse", "subscribe", "me gusta", "like", "aceptar", "ok", "cancelar", "cancel", "si", "yes", "no",
})
# A label is a control's name, never a sentence: the longest names a window shows are a few words.
_TRANSLATED_WORDS = 5
_TRANSLATED_LETTERS = 40


def label_translatable(name: object) -> bool:
    """Whether a place's name may be translated by the model when no name of it is on screen: the table knows none
    of its other names (the table goes first), it is a short name with letters, and it is no act."""

    key = fold(name).strip()
    return (
        bool(key) and len(key) <= _TRANSLATED_LETTERS and len(key.split()) <= _TRANSLATED_WORDS
        and any(character.isalpha() for character in key)
        and key not in _UNTRANSLATED_LABELS and not label_alternatives(key)
        # «following», «saved», «subscriptions»: a name an account act carries is clicked only as said.
        and account_act(key) is None
    )


# A request that writes or sends something to someone («… y escribile hola y mandalo», «… and send it»): the place it
# goes to first is a conversation, a contact or a document of the person, named as they named it, never translated
# (a chat «Family» is not the «familia» the person meant).
_WRITES_OR_SENDS = re.compile(
    r"\b(?:escrib\w*|mand(?:a|ale|alo|ales|alos|ar|arle|arlo|e|en)|envi\w*|respond\w*|contest\w*|deci(?:le|les)|"
    r"dile|write|writes|type|send|sends|reply|answer|message|text\s+(?:him|her|them))\b"
)


# Review of v3 r3a lectura L3: a free sub-goal that sends something to someone («mandale hola», «escribile a Juan»,
# «reply to her», «mandalo») acts on the person's account in words no reader checked; such a chain stays the
# decider's, which reads a message to send as such (message.send and its confirmation).
_SENDS_TO_SOMEONE = re.compile(
    r"\b(?:mand(?:a|ale|ales|alo|ala|alos|alas|ar|arle|arles|arlo)|envi(?:a|ale|ales|alo|ala|ar|arle|arles|arlo)|"
    r"escribi(?:le|les)|escribirle|escribirles|respond\w*|contest\w*|deci(?:le|les)|dile|"
    r"send|sends|reply|answer|message|dm|text\s+(?:him|her|them))\b"
)


def sends_to_someone(goal: object) -> bool:
    """Whether a sub-goal said in the person's words sends something to someone (a message, a reply, «mandalo»)."""

    return _SENDS_TO_SOMEONE.search(fold(goal)) is not None


def writes_or_sends(objective: object) -> bool:
    """Whether the person's request writes or sends something (its later sub-goals type or send): its places are then
    the person's own content, which no translation names."""

    return _WRITES_OR_SENDS.search(fold(objective)) is not None


# Ronda 22: a span of the request between quotes of any kind («…», "…", '…', “…”, ‘…’).
_ANY_QUOTED = re.compile(r"«([^«»]+)»|\"([^\"]+)\"|“([^“”]+)”|'([^']+)'|‘([^‘’]+)’")


def quotes_the_text(text: object, *said: object) -> bool:
    """Ronda 22: the text to type is, whole, a span the request puts between quotes («escribe "Ctrl+B" en el
    documento»): the request gives it as the text itself, never as a key to press."""

    typed = fold(text).strip()
    return bool(typed) and any(
        fold(next(group for group in found.groups() if group is not None)).strip() == typed
        for item in said if isinstance(item, str) for found in _ANY_QUOTED.finditer(item)
    )


# The operation's successCheck holds at most this many bytes (ProductCatalog, mission.computer.use).
_CHECK_BYTES = 512


def _with_alternatives(target: str, atoms: Iterable[str]) -> str:
    """The check ``atoms`` (templates over ``{}``) for the target and each of its other names, OR-ed; the other names
    stop where the check would no longer fit the operation (the target's own atoms always stay)."""

    terms: list[str] = []
    others = label_alternatives(target)
    # The target is a name of the tables when it has other names there; only such a name is known to hold its first
    # piece on screen in either spelling.
    names = dict.fromkeys(
        (_check_name(target, known=bool(others)), *(_check_name(name, known=True) for name in others))
    )
    for name in (name for name in names if name):
        named = [atom.replace("{}", name) for atom in atoms]
        if terms and len("|".join((*terms, *named)).encode("utf-8")) > _CHECK_BYTES:
            break
        terms.extend(named)
    return "|".join(terms)


# A piece of a name said shorter than this is no proof of the whole name («q» of «Q&A», «at» of «AT&T»: inside any
# word on screen).
_SHORTEST_CHECK_PIECE = 4


def _check_name(name: str, *, known: bool = True) -> str:
    """A name as a check can hold it: «&» and «|» join the check's atoms. A name of the tables («Time & language»)
    is checked by the part before them («time»), which the place's name holds in either spelling. A name only the
    person said («Q&A», «Rock & Roll») by its longest piece, and by nothing (empty) when that piece is too short to
    tell the place from any other («at» of «AT&T»)."""

    pieces = [piece.strip() for piece in re.split(r"[&|]", name)]
    if len(pieces) == 1:
        return pieces[0]
    if known:
        return pieces[0] or max(pieces, key=len)
    longest = max(pieces, key=len)
    return longest if len(longest) >= _SHORTEST_CHECK_PIECE else ""


@dataclass(frozen=True, slots=True)
class MissionStep:
    """One sub-goal of a chained mission: its own goal, application and check (contract §4.1, steps[])."""

    application: str | None
    goal: str
    success_check: str | None
    clause: str = ""
    # A clause no reader reads, kept in the chain as a free sub-goal (v3 punto 2, A7): the model does it and says done
    # with evidence on screen.
    free: bool = False
    # Revisión 2 de la ronda 20b (bloqueante 1): the form this sub-goal belongs to, as the check of the whole unit (its
    # fields all holding at once, ``_with_form_checks``): every field of a form whose fields are tied and its default
    # button carry it, so the engine switches the link off before the first field and evaluates the whole form again
    # before accepting it (cu_forms._form_unit_step, _form_confirm_step).
    form_check: str | None = None

    def arguments(self) -> dict[str, object]:
        arguments: dict[str, object] = {
            "goal": self.goal, "application": self.application, "successCheck": self.success_check}
        if self.form_check:
            arguments["formCheck"] = self.form_check
        return arguments


# A chained mission carries at most this many sub-goals (contract §4.1): the shell's own limit, ProductCatalog
# «mission.computer.use» steps maximumItems (tests/test_cu_v3_tipos_lectura.py holds them equal).
MAX_STEPS = 10


@dataclass(frozen=True, slots=True)
class MissionRequest:
    application: str | None
    goal: str
    success_check: str | None
    # The person's clause of doing inside the application («baja el volumen»), empty for a tab named alone.
    clause: str = ""
    # «… y después en Discord andá a general»: the sub-goals in order, empty for a single clause.
    steps: tuple[MissionStep, ...] = ()
    # Corrección ronda 5: only a look at the application and an answer from it («en Seguridad de Windows decime…»,
    # ``_looking_in``). It is read for the engine's goal, never ahead of a typed operation or the decider
    # (semantic.patterns.resolve_explicit_effects).
    looks_only: bool = False

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


def _catalog_key(
    candidate: str, catalog: effect_intent.ApplicationCatalogIndex, *, loose: bool = False
) -> str | None:
    """The catalog key a name said reaches. ``loose`` also tries a near spelling («powerpint»): only for the whole
    slot an open verb delimits («abre powerpint y …»), never for a place frame («en stream escribí hola») or a scan
    of a clause's first words, where an ordinary word one letter away from a name is still that word."""

    key = effect_intent._application_name_key(candidate.strip(" ,.;:!?"))
    resolved = effect_intent._catalog_alias_key(key, catalog.keys)
    if resolved is not None:
        return resolved
    for aliases, names in _EXTRA_ALIASES:
        if key in aliases:
            for name in names:
                if name in catalog.keys:
                    return name
    if key in catalog.keys:
        return key
    content = _content_words(_said_name_words(key))
    if len(content) == 1 and content[0] in _common_words():
        # v3 destino (r5a M4, t-drag-3 «…a la derecha de la pantalla» opened «Teclado en pantalla»): an ordinary word
        # alone is no application because one name starts or ends with it; only the whole name said is. Erratas r9
        # (t-drag-2 «en el panel de miniaturas» read «panel de» as Panel de control): nor with a function word beside it.
        return _catalog_key_by_words(key, catalog, loose=loose)
    # «abre Steam»: the catalog name itself, or one catalog name that starts with it.
    starts = [entry_key for entry_key in catalog.keys if entry_key.startswith(key + " ") or entry_key == key]
    if len(starts) == 1:
        return starts[0]
    # «Teams» for «Microsoft Teams»: the one catalog name that ends with it.
    ends = [entry_key for entry_key in catalog.keys if entry_key.endswith(" " + key)] if not starts else []
    if len(ends) == 1:
        return ends[0]
    # «in the Clock app», «la aplicación Reloj»: the name inside the word that says it is an application.
    bare = application_name_without_frame(key)
    if bare is not None and bare != key:
        # «el registro de aplicación» (the Application log) is no application called «registro de …»: a name that
        # ends in a function word is cut, not framed.
        if not bare.split()[-1:] or bare.split()[-1] in _NAME_FUNCTION_WORDS:
            return None
        return _catalog_key(bare, catalog, loose=loose)
    return _catalog_key_by_words(key, catalog, loose=loose)


# v3 r3a lectura L2: «7zip» for «7-Zip File Manager», «sticky note» for «Sticky Notes (new)», «adminsitrador de
# tareas», «visr de eventos», «powerpint». A name is its words: a digit and a letter part words, a qualifier in
# brackets is no part of it, a plural is its singular. Function words never tell an application apart.
_DIGIT_LETTER = re.compile(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)")
_QUALIFIER = re.compile(r"\([^)]*\)")
_NAME_ARTICLES = frozenset({"el", "la", "los", "las", "the", "un", "una", "a", "an", "mi", "my"})
_NAME_FUNCTION_WORDS = frozenset({
    "de", "del", "la", "el", "los", "las", "the", "of", "for", "y", "and", "en", "in", "on", "para", "con", "with",
    "to", "a", "an",
})


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _name_words(name: str) -> tuple[str, ...]:
    folded = _DIGIT_LETTER.sub(" ", _QUALIFIER.sub(" ", fold(name)))
    return tuple(_singular(word) for word in re.findall(r"[a-z0-9]+", folded))


def _said_name_words(name: str) -> tuple[str, ...]:
    words = list(_name_words(name))
    while words and words[0] in _NAME_ARTICLES:
        words.pop(0)
    return tuple(words)


def _content_words(words: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(word for word in words if word not in _NAME_FUNCTION_WORDS)


_OBJECT_STOP_WORDS = frozenset({"que", "de", "del", "en", "con", "para", "y", "e", "in", "on", "with", "for", "that", "saying", "and"})


def act_object_names_application(clause: object, application: object) -> bool:
    """The thing the act makes or works on is what the application is named for: «crea una nota que diga …» after «abre
    Notas rápidas» (its object «nota» is a word of «Notas rápidas»). Such an act belongs to that application, never to a
    store of BAXY's own that reads the same words (v3-34 r7: app.open + note.create saved the note in BAXY and said it
    was created in the notes app). The object is read from the words right after the verb, before what is dictated and
    before a «que»/«de»/«en» that starts its complement; contracase: «abre Spotify y crea una nota …», «abre Spotify y
    pon música de Spotify» (the object «música» is no word of the name)."""

    folded = fold(clause)
    dictated = _dictated_text_opens(folded)
    if dictated is not None:
        folded = folded[: dictated.start()]
    words = re.findall(r"[a-z0-9]+", folded)[1:]
    name = set(_content_words(_name_words(str(application or ""))))
    for word in words[:4]:
        if word in _OBJECT_STOP_WORDS:
            break
        if word in _NAME_ARTICLES:
            continue
        if _singular(word) in name:
            return True
    return False


_INDEFINITE_ARTICLES = frozenset({"un", "una", "a", "an"})
_NEW_WORDS = frozenset({"nueva", "nuevo", "new", "otra", "otro", "another"})


def application_said_as_object(
    text: object,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """Pasada r15b2 (v3-35 «crea una nota rapida nueva»): the one thing an order of one clause makes is said with an
    indefinite article and an installed application's own name («una nota rápida» is one of «Notas rápidas», «a sticky
    note») after a verb that makes it (``lexicon.MAKE_VERBS``: «compra una cámara», «busca un terminal» or «ponme una
    música» make nothing in Cámara, Terminal or Música): the order is that application's, never a store of BAXY's
    own that reads the same words (note.create saved it in BAXY's notes and said «He creado la nota…» while Notas
    rápidas had none). The name is said precisely (``_named_precisely``): «crea una nota» names no application, «busca
    fotos de gatos» says no article, «abre una terminal» is app.open's own reading (no verb that makes). Returns the
    application's display name, or None."""

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    if catalog.occurrence_pattern is None or not text:
        return None
    folded = effect_intent._strip_request_envelope(fold(" ".join(str(text).split()))).strip(" .!?")
    dictated = _dictated_text_opens(folded)
    if dictated is not None:
        folded = folded[: dictated.start()]
    words = re.findall(r"[a-z0-9]+", folded)
    if len(words) < 3 or words[0] not in lexicon.MAKE_VERBS or words[1] not in _INDEFINITE_ARTICLES:
        return None
    taken: list[str] = []
    for word in words[2:6]:
        if word in _OBJECT_STOP_WORDS:
            break
        taken.append(word)
    while taken and taken[0] in _NEW_WORDS:
        taken.pop(0)
    while taken and taken[-1] in _NEW_WORDS:
        taken.pop()
    if not taken or doing_clauses(str(text), catalog) != 1:
        return None
    key = _named_precisely(" ".join(taken), catalog)
    return _display_name(key, catalog) if key is not None else None


def _in_order(said: tuple[str, ...], name: tuple[str, ...]) -> bool:
    position = 0
    for word in said:
        try:
            position = name.index(word, position) + 1
        except ValueError:
            return False
    return True


def _near_word(said: str, name: str) -> int | None:
    """The edits from a word said to a name's word, or None when it is too far («visr» → «visor» 1, «adminsitrador»
    → «administrador» 1). A function word or a number is said exactly."""

    if said == name:
        return 0
    if said in _NAME_FUNCTION_WORDS or name in _NAME_FUNCTION_WORDS or said.isdigit() or name.isdigit():
        return None
    if min(len(said), len(name)) < 4:
        return None
    distance = effect_intent._edit_distance(said, name)
    return distance if distance <= (1 if len(name) <= 5 else 2) else None


def _catalog_key_by_words(
    key: str, catalog: effect_intent.ApplicationCatalogIndex, *, loose: bool = False
) -> str | None:
    """The one catalog name the words said name: an alias said in another number or spelling, a unique run of two or
    more of a name's own words in order, or (``loose``) one name a near spelling of every word reaches. Two names keep
    asking which (APPS1495); a single loose word («zip», «notas») names nothing here."""

    said = _said_name_words(key)
    content = _content_words(said)
    if not content:
        return None
    for aliases, names in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES):
        if any(_said_name_words(alias) == said for alias in aliases):
            for name in names:
                if name in catalog.keys:
                    return name
    entries = _catalog_words(catalog.keys)
    if len(content) >= 2:
        runs = [entry for entry, words in entries if _in_order(said, words)]
        runs = _without_companions(runs)
        if len(runs) == 1:
            return runs[0]
        if runs:
            return None
    if not loose or sum(len(word) for word in content) < 5:
        return None
    one_word = len(said) == 1
    if one_word and (len(said[0]) < _NEAR_ONE_WORD_LETTERS or said[0] in _common_words()):
        return None
    near: list[tuple[int, str]] = []
    for entry, words in (*entries, *_alias_words(catalog.keys)):
        if len(words) != len(said):
            continue
        edits = [_near_word(a, b) for a, b in zip(said, words)]
        if not all(edit is not None for edit in edits) or sum(edits) == 0:
            continue
        # One word alone is one letter off a name of its length or more («powerpint»), never two: «stream», «cursos»
        # and «route» are ordinary words a letter or two from Steam, Cursor and Router.
        if one_word and (sum(edits) != 1 or len(words[0]) < _NEAR_ONE_WORD_LETTERS):
            continue
        near.append((sum(edits), entry))
    near_names = _without_companions(list(dict.fromkeys(entry for _, entry in sorted(near))))
    return near_names[0] if len(near_names) == 1 else None


@functools.lru_cache(maxsize=8)
def _alias_words(keys: frozenset[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Erratas r9: each other name of an installed application (data/app_aliases.v1.json) as the catalog name it
    stands for and its words, so a typing slip of it («task manger», «control pael») reaches that application the way
    a slip of its own name does."""

    found: list[tuple[str, tuple[str, ...]]] = []
    for aliases, names in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES):
        name = next((name for name in names if name in keys), None)
        if name is not None:
            found.extend((name, _said_name_words(alias)) for alias in sorted(aliases))
    return tuple(found)


# A one-word name reached by a near spelling has at least this many letters, said and named.
_NEAR_ONE_WORD_LETTERS = 6


def _common_words() -> frozenset[str]:
    return frozenset(_singular(word) for word in app_alias_words("common_words"))


def _without_companions(entries: list[str]) -> list[str]:
    """A Start catalog lists beside an application its help, its uninstaller or its readme («7-Zip Help»); when the
    application is among the names, the companions are not what was said."""

    companion = _companion_words()
    kept = [entry for entry in entries if not companion.intersection(_name_words(entry))]
    return kept or entries


def _companion_words() -> frozenset[str]:
    return frozenset(_singular(word) for word in app_alias_words("companion_words"))


_CATALOG_WORDS: dict[frozenset[str], tuple[tuple[str, tuple[str, ...]], ...]] = {}


def _catalog_words(keys: frozenset[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    found = _CATALOG_WORDS.get(keys)
    if found is None:
        if len(_CATALOG_WORDS) > 8:
            _CATALOG_WORDS.clear()
        found = _CATALOG_WORDS[keys] = tuple((entry, _name_words(entry)) for entry in sorted(keys))
    return found


def _display_name(key: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    for name, entry_key in catalog.entries:
        if entry_key == key:
            return name
    return key


_REQUEST_WORD = re.compile(r"[^\s,;:.!?¡¿«»\"'()]+")


def application_named_in(
    app_id: str,
    texts: Iterable[str | None],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    application: str | None = None,
) -> bool:
    """True when the mission's own application is that one, or when some run of up to five words of one of ``texts``
    (the request, the sub-goal) names it the way the mission reader names a destination (``_catalog_key``): its whole
    name, an alias of it («bloc de notas» names Notepad), or the one name that starts or ends with a distinctive word
    («edge», «teams», «store»), never an ordinary word one name contains (a request's «de la pantalla» is no «Teclado
    en pantalla»: «pantalla» is a common word of data/app_aliases.v1.json). A run the opener resolves to the same
    application also names it when it says the whole name or the application is no catalog name («editor de texto»
    is Notepad's opener alias)."""

    catalog = effect_intent.build_application_catalog_index(application_names)

    def opens(name: str) -> str | None:
        return effect_intent.resolve_application_catalog_app_id(f"abre {name}", catalog)

    if application and opens(application) == app_id:
        return True
    names = [set(fold(name).split()) - _NAME_ARTICLES for name, _ in catalog.entries if name == app_id]
    for text in texts:
        words = _REQUEST_WORD.findall(text or "")
        for size in range(1, 6):
            for start in range(len(words) - size + 1):
                span = " ".join(words[start : start + size])
                key = _catalog_key(span, catalog)
                if key is not None and opens(_display_name(key, catalog)) == app_id:
                    return True
                if opens(span) != app_id:
                    continue
                said = set(fold(span).split()) - _NAME_ARTICLES
                if any(said & name and not name <= said for name in names):
                    continue
                return True
    return False


def catalog_application(candidate: str, application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex) -> str | None:
    """The catalog display name a person's word names, or None when not installed."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    # The name an open reading took (its whole slot), so a near spelling of it is the application.
    key = _catalog_key(candidate, catalog, loose=True)
    return _display_name(key, catalog) if key is not None else None


def _key_from_words(words: str) -> str | None:
    folded = fold(words).replace("+", " ").replace("control ", "ctrl ")
    folded = " ".join(folded.split())
    # Only a key the shell's input.key.press accepts (``KEYS`` mirrors its enum; review of v3 punto 2: a key outside
    # it ends the mission at its first step with computer_use_step_arguments_invalid).
    key = _KEY_WORDS.get(folded) or folded.replace(" ", "_")
    return key if key in KEYS else None


def field_names_for(field: str) -> tuple[str, ...]:
    """The names a form's field may carry on screen («ancho» → «ancho», «width», «horizontal»; «nombre de archivo» →
    «nombre de archivo», «nombre», «file name»)."""

    key = fold(field).strip()
    if key == cu_tipos.FILE_NAME_FIELD[0]:
        return cu_tipos.FILE_NAME_FIELD
    return cu_tipos.field_names(key)


EMPTY_SPACE_TARGET = cu_tipos.EMPTY_SPACE_TARGET
_FIELD_GOAL_PARTS = re.compile(r"^poner\s+(?P<field>.+?)\s+en\s+(?P<value>\S.*)$", re.IGNORECASE)


def field_goal_parts(goal: str) -> tuple[str, str] | None:
    """«poner ancho en 800» → («ancho», «800»): the field and the value of a form's sub-goal, or None."""

    found = _FIELD_GOAL_PARTS.match(str(goal or "").strip())
    if found is None:
        return None
    return found.group("field").strip(), found.group("value").strip()


# «volvé a estándar», «regresá al modo científico», «go back to standard», «switch back to Home»: going back to a mode or
# a place is changing to it (the mode reader and the navigate reader read «cambiá a X»). «volvé a abrir X» says the
# order again («volver a» + an infinitive), never a place: it stays as said.
_RETURN_CLAUSE = re.compile(
    r"^(?:volve|volver|vuelve|vuelva|volvete|volvamos|regresa|regresar|regresate|regrese|retorna|retornar|"
    r"go\s+back|get\s+back|switch\s+back|change\s+back|head\s+back)\s+(?P<to>(?:a|al|to|into|en|in)\s+\S.*)$"
)
# «volvé a abrir X», «volvé a intentarlo después»: an infinitive with more said after it is the order again.
_INFINITIVE_ORDER = re.compile(r"[a-z]+(?:ar|er|ir)(?:lo|la|los|las|le|les|me|te|se)?\b(?!\s*$)")


def _clause_readings(folded: str) -> tuple[str, ...]:
    """The clause as said and with its order as the tú/voseo imperative the readers read («seleccione»,
    «elegir», «pulse» → grammar.imperative_rewrites over this module's verbs); a going back as the change it is
    (``_RETURN_CLAUSE``)."""

    returned = _RETURN_CLAUSE.match(folded)
    if returned is not None:
        to = returned.group("to")
        rest = re.sub(r"^(?:a|al|to|into|en|in)\s+", "", to)
        # Only «a» takes the infinitive: «volvé al lugar anterior» is a place.
        if not _is_doing(rest) and not (to.startswith("a ") and _INFINITIVE_ORDER.match(rest) is not None):
            folded = f"cambia {returned.group('to')}"
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
    # v3 punto 2 (t-long-1): «2 elevado a 10», «2 to the power of 10».
    (r"elevado\s+a(?:\s+la)?|to\s+the\s+power\s+of|a\s+la\s+potencia(?:\s+de)?", "^"),
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


def _playing_check(named: str | None = None) -> str:
    """Playing shows as the player's pause control together with an act of this sub-goal that started it: a click
    on a control that says it plays («Reproducir …», «Play …»), a click on the result named by the clause before
    («buscá Duki y poné la primera»: a click on «Duki …»), or Enter on the chosen result. Any click or key is not
    enough (review 2026-10-07: with music already playing, any click of the sub-goal passed).

    Residual: the grammar has no order between atoms, so the pause control is not proven to appear after that act;
    with something already playing, a play click that did not change the track still passes. Without a named
    result, a click on a result by its own title (a video's) is not recognised and the loop asks the model."""

    clicks = ["reproducir", "play", *((named,) if named else ())]
    acts = [*(f"stepDone:input.visible.click:{label}" for label in clicks), "stepDone:input.key.press:enter"]
    return "|".join(f"control:{pause}&{act}" for pause in ("pausa", "pause") for act in acts)


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
_CREATE_VERB = (
    r"(?:crea|crear|creame|crea\s+me|haz|hace|hacer|hazme|haceme|genera|generar|agrega|agregar|anadi|anade|anadir|"
    r"create|make|add|new)"
)
_CREATE_CLAUSE = re.compile(
    r"^" + _CREATE_VERB + r"\s+"
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
# Encargo EX (tanda n5 t4-c06 «crea un blank workbook»): an order to create, read as a choice only when what it names is
# the offer of a whole blank document (``names_a_blank_document``), planned as that offer's creation.
_CREATE_ITEM_CLAUSE = re.compile(r"^" + _CREATE_VERB + r"\s+(?P<what>\S.{0,60}?)[\s.!?]*$")
_SELECT_NOUN_BEFORE = re.compile(
    r"^(?:(?:el|la|los|las|the|un|una|a|an)\s+)?(?:(?:color|colour|herramienta|tool|opcion|option|archivo|file|carpeta|"
    r"folder|elemento|item)\s+(?:de\s+(?:la\s+|el\s+)?)?)?"
)
_SELECT_NOUN_AFTER = re.compile(r"\s+(?:color|colour|tool|option|button|boton)$")


# The marks that delimit a name said or written between quotes («Sistema», "Sistema", “Sistema”, 'Sistema').
_QUOTE_MARKS = " \"'«»“”‘’"
# A literal said between quotes: it ends at its closing quote («escribí «Informe semanal» como título, …»).
_QUOTED_LITERAL = re.compile(r"^(?:\"(?P<d>[^\"]+)\"|«(?P<g>[^»]+)»|“(?P<c>[^”]+)”|'(?P<s>[^']+)')")


def quoted_literal(text: str) -> str | None:
    """The literal a text opens with between quotes, or None."""

    found = _QUOTED_LITERAL.match(text.strip())
    if found is None:
        return None
    return next(group for group in found.groups() if group is not None)


def _unquoted(name: str) -> str:
    """A name without the quotes and spaces around it: the quotes delimit the name, the window never shows them."""

    return name.strip(_QUOTE_MARKS).strip()


def clean_target(what: str) -> str:
    """The name a choice, a search or a reveal names, without what the person adds after it (v3 punto 2): a remark
    («, pero no lo abras», «, nada más»), the way to do it («bajando en la lista», «desde el menú») or a restatement
    («la omega mayúscula, la Ω»). A quoted name is kept whole."""

    stripped = what.strip()
    if stripped[:1] in _QUOTE_MARKS.strip() and _QUOTED_LITERAL.match(stripped):
        return stripped
    cut = cu_tipos.TARGET_TAIL.sub("", stripped, count=1)
    cut = cu_tipos.TARGET_APPOSITION.sub("", cut, count=1)
    return cut.strip(" ,;") or stripped


def search_target(what: str) -> str:
    """The query a search names, whole (review of v3 punto 2: «vuelos desde Santiago a Madrid», «recetas sin gluten,
    solo veganas» are the query); only the way to scroll said at its end, a one-word restatement and a closing «ahí» /
    «there» that points at the place are dropped."""

    stripped = what.strip()
    if stripped[:1] in _QUOTE_MARKS.strip() and _QUOTED_LITERAL.match(stripped):
        return stripped
    cut = cu_tipos.SEARCH_TAIL.sub("", stripped, count=1)
    cut = cu_tipos.SEARCH_APPOSITION.sub("", cut, count=1)
    cut = cut.strip(" ,;")
    here = cu_tipos.SEARCH_HERE.search(cut)
    # Review of L5: after a preposition the adverb is the query's own place («restaurantes cerca de acá», «hotels
    # near here», «qué hay por aquí»), never the place the search happens.
    if here is not None and cu_tipos.SEARCH_HERE_OWN.search(cut[: here.start()]) is None:
        cut = cut[: here.start()]
    return cut.strip(" ,;") or stripped


def _select_target(what: str) -> str:
    target = _SELECT_NOUN_BEFORE.sub("", _unquoted(clean_target(what)), count=1)
    bare = _SELECT_NOUN_AFTER.sub("", target).strip()
    # Ronda 22: a kind word joined to the name by a coordinator is part of it («Brillo y color»), never dropped.
    words = bare.split()
    return target.strip() if words and words[-1] in lexicon.OBJECT_COORDINATORS else bare


def _named_item_check(name: str) -> str:
    """Created or renamed is a control carrying the whole name (``control:=``: «informe2» is not «informe»; never the
    field the name was typed in) once this sub-goal typed that name: an item of that name already there at the
    first look («creá un canal llamado general» beside the old #general) is not the one this sub-goal made.

    Residual: a create that types the name and is abandoned before confirming still passes beside an older item of
    the same name; the grammar cannot tell the two items apart."""

    return f"control:={name}&stepDone:input.text.type:{name}"


def _select_check(target: str) -> str:
    # Chosen is the control selected or pressed; where the window says neither, the verified click on it. The name
    # whole (``=``): measured on Paint, «red» inside «Rectángulo redondeado» passed a click on that shape as the colour
    # chosen, and the mission learned that click as the way to choose red.
    check = _with_alternatives(target, ("control:={}:selected", "control:={}:on", "stepDone:input.visible.click:={}"))
    if not is_basic_colour(target):
        return check
    # A basic colour the window's palette does not carry by that name (measured on Paint: no «Azul», only «Añil»):
    # a click on one of its shades, whole, is the colour chosen, the closest first while the check fits.
    covered = [fold(target), *label_alternatives(target)]
    for word in colour_check_words(target, covered):
        atom = f"stepDone:input.visible.click:={word}"
        if len(f"{check}|{atom}".encode("utf-8")) > _CHECK_BYTES:
            break
        check = f"{check}|{atom}"
    return check


# «cambiá a científica», «pasá a la vista compacta», «poné el modo científico», «switch to scientific mode», «set it
# to dark mode»: choosing one of the modes or views a window offers, often behind its navigation or menu button.
# «poner» and «set»/«put» take the mode word («poné la música» is no mode); «cambiar», «pasar», «switch» and «change»
# choose a mode only with the mode word or a mode's own name (``_MODE_NAMES``): «cambiá a descargas», «pasá al canal
# general» go to a place, which the navigate reader reads.
_MODE_WORD = r"(?:modo|vista|mode|view)"
_MODE_CLAUSE = re.compile(
    r"^(?:(?P<put>pon|pone|poneme|ponele|ponela|ponelo|ponla|ponlo|set|put)(?:\s+(?:it|la|lo))?\s+(?:(?:en|in|to|into|a|al)\s+)?"
    r"|(?:cambia|cambiate|cambiala|cambialo|cambiar|cambie|pasa|pasate|pasala|pasalo|pasar|pase|switch|change)"
    r"(?:\s+(?:it|la|lo|over))?\s+(?:a|al|to|into|en|in)\s+)"
    rf"(?:(?:el|la|the|un|una|a)\s+)?(?:(?P<before>{_MODE_WORD})\s+(?P<of>de\s+)?(?:(?:el|la|los|las)\s+)?)?"
    rf"(?P<name>[a-z0-9][a-z0-9 .+-]{{0,40}}?)(?:\s+(?P<after>{_MODE_WORD}))?[\s.!?]*$"
)
_VIEW_WORDS = frozenset({"vista", "view"})
# «vista de detalles», «vista previa»: a goal's target that names a view by the view word before it.
_VIEW_AROUND = re.compile(r"^(?:vista|view)\s+(?P<of>de\s+)?(?:(?:el|la|los|las)\s+)?(?P<name>\S.*)$")
# «modo científico», «scientific mode», «vista previa»: a goal's target that names a mode by the mode word.
_MODE_AROUND = re.compile(rf"^{_MODE_WORD}\s+(?:de\s+)?(?:(?:el|la)\s+)?(?P<before>\S.*)$|^(?P<after>\S.*?)\s+(?:mode|view)$")
# The endings of a Spanish adjective said in either gender: the person says «el modo científico» and the window
# names it after its own feminine noun («Calculadora Científica»).
_GENDERED_ADJECTIVE = re.compile(r"^[a-z]{2,}(?:ic|iv|ad|id|os)[oa]$")


def gender_twin(name: str) -> str | None:
    """«científico» → «cientifica», «automática» → «automatico»: a one-word adjective in the other gender, folded;
    None for anything else (a noun such as «inicio» keeps its one form).

    Only a mode's name has two genders on screen (``mode_names``): a place keeps the gender said («partido» is no
    «partida»), so callers ask it only for a name ``mode_named`` read as a mode."""

    folded = fold(name)
    if _GENDERED_ADJECTIVE.match(folded) is None:
        return None
    return folded[:-1] + ("a" if folded[-1] == "o" else "o")


def _is_mode_name(name: str) -> bool:
    """«científica», «científico», «standard»: the own name of a mode a window offers, in either gender."""

    key = fold(name).strip()
    twin = gender_twin(key)
    return any(key in group or (twin is not None and twin in group) for group in _MODE_NAMES)


def mode_named(target: str) -> str | None:
    """The mode a goal's target names, or None when it names a place: «modo científico» → «cientifico», «scientific
    mode» → «scientific», «cientifica» (a mode's own name) → «cientifica»; «descargas», «partido» → None.

    The mind asks it before looking a mode up by its other names (``mode_names``, the other gender among them)."""

    key = fold(target).strip(" \"'«».!?")
    view = _VIEW_AROUND.match(key)
    if view is not None:
        # «vista de detalles» → «detalles», what ``_read_mode`` goes to; «vista previa», a compound noun said without
        # «de», keeps the view word as part of its name.
        return view.group("name").strip() if view.group("of") else key
    found = _MODE_AROUND.match(key)
    if found is not None:
        return (found.group("before") or found.group("after") or "").strip() or None
    return key if key and _is_mode_name(key) else None


# Ronda 20b, palanca 6: an order of the window's view said as such («ordenar por nombre», «sort by date», «agrupar por
# tipo»).
_ORDER_AROUND = re.compile(
    r"^(?:(?P<sort>ordenar|ordena|orden|sort|sorted)|(?P<group>agrupar|agrupa|group|grouped))\s+(?:por|by)\s+(?P<name>\S.*)$"
)


def view_option_named(target: str) -> str | None:
    """The option of the window's view or order a goal's target names, or None: «vista de iconos grandes» → «iconos
    grandes», «view of details» → «details», «ordenar por nombre» → «nombre». «vista previa» (said without «de») is a
    mode's own name, not an option of the view; «iconos grandes» alone is a place said bare (``mode_named`` reads it).
    An option is chosen in the control that shows the current one, never looked up in a search of the content."""

    key = fold(target).strip(" \"'«».!?")
    view = _VIEW_AROUND.match(key)
    if view is not None and view.group("of"):
        return view.group("name").strip() or None
    order = _ORDER_AROUND.match(key)
    return order.group("name").strip() or None if order is not None else None


def view_option_family(target: str) -> str | None:
    """Review 3 of palanca 6 (finding 2): the family of the option a goal's target names (``view_option_named``): «view»
    for «vista de X», «sort» for «ordenar por X», «group» for «agrupar por X»; None when it names no option. Only the
    control labelled for that family («Ver por», «Ordenar por», «Agrupar por») shows the option."""

    if view_option_named(target) is None:
        return None
    key = fold(target).strip(" \"'«».!?")
    order = _ORDER_AROUND.match(key)
    if order is None:
        return "view"
    return "sort" if order.group("sort") else "group"


def mode_names(name: str) -> tuple[str, ...]:
    """The names a chosen mode may carry on screen: as said, its other-language names, its other gender and that
    gender's other-language names («científico» → «cientifico», «cientifica», «scientific»)."""

    twin = gender_twin(name)
    found = (fold(name), *label_alternatives(name), *((twin, *label_alternatives(twin)) if twin else ()))
    return tuple(dict.fromkeys(found))


def _fit(*checks: str) -> str:
    """The checks OR-ed, their terms kept in order while they fit the operation (``_CHECK_BYTES``)."""

    terms: list[str] = []
    for term in (term for check in checks for term in check.split("|") if term):
        if term in terms:
            continue
        if terms and len("|".join((*terms, term)).encode("utf-8")) > _CHECK_BYTES:
            break
        terms.append(term)
    return "|".join(terms)


def _mode_check(*names: str) -> str:
    """Chosen is the mode's item selected, the window titled with it, its page, or its header: a text at the top of
    the window that names it and appeared after the verified click on it (``header:X``, measured on the Calculator:
    after «Científica Calculadora» in its navigation the header reads «Modo de calculadora Científica»; title and
    selection do not change). A click alone on something that names it is no proof: a card, a folder or a channel
    that holds the word is clicked as well."""

    atoms = ("control:{}:selected", "title:{}", "page:{}", "header:{}")
    aliases = dict.fromkeys(
        checked for name in names for alias in mode_names(name) if (checked := _check_name(alias, known=False))
    )
    # The marked label of a window without an accessible tree (``mark:X``, v3 punto 5) goes last: where the check
    # would not fit, it is what is left out, never another name of the mode.
    return _fit(
        *(atom.replace("{}", alias) for alias in aliases for atom in atoms), *(f"mark:{alias}" for alias in aliases)
    )


def _read_mode(folded: str) -> tuple[str, str | None] | None:
    mode = _MODE_CLAUSE.match(folded)
    if mode is None or _tab_named(folded) is not None:
        return None
    before, after = mode.group("before"), mode.group("after")
    # «cambiá a científica y calculá 2+2»: the mode ends where the next clause of doing begins.
    name = _segments(mode.group("name"))[0].strip(" \"'«»")
    if not name or _has_deictic_only(name):
        return None
    if not (before or after) and (mode.group("put") or not _is_mode_name(name)):
        # No mode said: «cambiá a descargas», «pasá al canal general» are places (the navigate reader's).
        return None
    put = mode.group("put") is not None
    if not (before or after):
        # «cambiá a científica»: a mode a window offers, said by its own name.
        return f"ir a {name}", _mode_check(name)
    if before in _VIEW_WORDS or after in _VIEW_WORDS:
        # «la vista de detalles», «the details view»: the view chosen is X (the item «Detalles» of the window's view
        # menu). «la vista previa», a compound noun said without «de», keeps its word; it is also checked by X alone,
        # so that «la vista detalles» is never only a name no window carries.
        compound = before in _VIEW_WORDS and not mode.group("of")
        shown = f"{before} {name}" if compound else name
        chosen = _mode_check(shown, name) if compound else _mode_check(name)
        if not put:
            return f"ir a {shown}", chosen
        # «poné la vista previa»: the pane of that name is a switch turned on where there is one (computer_use reads
        # «activar vista de X» as the view X where there is none, ``mode_named``).
        said = f"{before} de {name}" if before and mode.group("of") else (f"{before} {name}" if before else f"{name} {after}")
        return f"activar {said}", _fit(_with_alternatives(said, ("control:{}:on",)), chosen)
    said = f"{before} {name}" if before else f"{name} {after}"
    switched = _with_alternatives(said, ("control:{}:on",))
    if _is_mode_name(name):
        if put:
            # «poné el modo científico»: a switch of that name where there is one, else the mode the window offers.
            return f"activar {said}", _fit(switched, _mode_check(name))
        return f"ir a {name}", _mode_check(name)
    # «poné el modo avión», «cambiá al modo avión», «switch to airplane mode»: a mode no window is known to offer by
    # name is a switch turned on (computer_use reads «activar modo X» so, and chooses the mode X where no switch is
    # called so), or the item X chosen (the theme «Oscuro»). Never a page, a title or a header: the settings page of
    # the switch («Modo avión») is selected, titled and headed with it while the switch stays off.
    return f"activar {said}", _fit(switched, _with_alternatives(name, ("control:{}:selected",)))


# Ronda 24b (banco r23 c6): what a free «escribir X» proves (``stepDone`` with the marker «written», judged by the
# App's TypedTextShows and its typing receipt) and what «enviar» proves: the Enter, and, after the text written by the
# sub-goal before it, the message sent (``sent:``: the box emptied or the text shown once more; ``_with_sent_checks``).
WRITTEN_CHECK = "stepDone:input.text.type:written"
SEND_GOAL = "enviar"
SEND_CHECK = "stepDone:input.key.press:enter"


def going_to(place: str) -> tuple[str, str | None] | None:
    """The sub-goal of going to a place of the application and its check, as this reader writes it for «andá a X»
    (estabilización L3: the place a declared search limit stands in is gone to first, the safe part)."""

    return _read_act(fold(f"anda a {place}"))


def _read_act(folded: str) -> tuple[str, str | None] | None:
    if _SEND_CLAUSE.match(folded) is not None:
        return SEND_GOAL, SEND_CHECK
    if chats.leaves_the_call(folded):
        # Imprescindibles de mensajería: the call is left by its own control (data/conversation_acts.v1.json, the first
        # label the goal's); a verified click on any of the names an application gives it is leaving.
        labels = tuple(fold(label) for label in chats.leave_call_labels())
        return chats.leave_call_goal(), "|".join(f"stepDone:input.visible.click:{label}" for label in labels)
    key = _KEY_CLAUSE.match(folded)
    if key is not None and key.group("touch") and not key.group("named") and key.group("key") in _KEYS_THAT_NAME_PLACES:
        place = key.group("key")
        return f"hacer clic en {place}", _with_alternatives(place, ("stepDone:input.visible.click:{}",))
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
        return f"reproducir {played.group('what')}", _playing_check()
    container = _new_container(folded) if _NEW_TAB_CLAUSE.match(folded) is None else None
    if container is not None:
        # Opened is a container of that kind born in this sub-goal, chosen, with the kind in its name (the shell's
        # born: atom, by difference with the sub-goal's first look): never one of that kind already open.
        noun, kind = container
        return f"abrir una {noun} nueva de {kind}", _with_alternatives(kind, ("born:{}",))
    created = _CREATE_CLAUSE.match(folded)
    if created is not None and (created.group("naming") or created.group("article") in {"la", "el", "the"}):
        name = created.group("name").strip(" \"'«»“”")
        if name and fold(name) not in {"nueva", "nuevo", "new", "vacia", "vacio", "empty"}:
            return f"crear {created.group('kind')} {name}", _named_item_check(name)
    renamed = _RENAME_CLAUSE.match(folded)
    if renamed is not None:
        old = (renamed.group("old") or "").strip(" \"'«»“”")
        new = renamed.group("new").strip(" \"'«»“”")
        if new and not _has_deictic_only(new):
            return (f"renombrar {old} a {new}" if old else f"renombrar a {new}"), _named_item_check(new)
    # Estabilización L4 (t-scroll-2): what is looked for by scrolling a list is shown (_read_type_act), not searched.
    searched = _SEARCH_CLAUSE.match(folded) if cu_tipos.LOOKED_FOR_BY_SCROLLING.match(folded) is None else None
    if searched is not None:
        what = re.sub(rf"^{_SEARCH_NOUN}", "", search_target(searched.group("what")), count=1).strip(" \"'«»“”")
        if what and not _has_deictic_only(what):
            # Searched is the name typed in this sub-goal and submitted while it is on screen (the window's results).
            # Estabilización R17: the page titled with the name after a submit is no proof of its own (bancos r27–r30:
            # 0 achieved, v3-59 a false success over Bing's results).
            return f"buscar {what}", f"stepDone:input.text.type&stepDone:input.key.press:enter&text:{what}"
    selected = _SELECT_CLAUSE.match(folded)
    if selected is None and (made := _CREATE_ITEM_CLAUSE.match(folded)) is not None and names_a_blank_document(
        _unquoted(clean_target(made.group("what")))
    ):
        selected = made
    if selected is not None:
        target = _select_target(selected.group("what"))
        # Revisión 3 (B2: «seleccioná la carpeta vacía» was planned «crear vacia», after the kind word went with the
        # article): only the offer to create a whole document, read on the words as said, before any kind is dropped.
        whole = _unquoted(clean_target(selected.group("what")))
        if target and not _has_deictic_only(target) and names_a_blank_document(whole):
            # Revisión 2 de r24b (B2, banco r23 n6: «abrí Word y elegí documento en blanco»): choosing a blank item is
            # creating it. Planned as its creation, it is told by what was made («creé «Documento1»»), never as a
            # control chosen when the opening made the document by its New command and no control of that name was
            # chosen. The offer's verified click (a start page's «Documento en blanco») still proves it here; the
            # opening that made the document is the mind's to cite (cu_documents._new_document_made).
            return f"crear {target}", _with_alternatives(target, ("stepDone:input.visible.click:={}",))
        if target and not _has_deictic_only(target):
            return f"seleccionar {target}", _select_check(target)
    calculate = _CALCULATE_CLAUSE.match(_spoken_expression(folded))
    if calculate is not None:
        expression = " ".join(calculate.group("expr").split())
        # Live y7 («en la calculadora calculá 9 por 9»): the Enter alone passed while the display read 0. The act that
        # asks for the result counts only with the result on the screen (result:, the expression's value shown, or
        # a new number when it cannot be evaluated).
        acts = ("stepDone:input.key.press:enter", "stepDone:input.visible.click:igual",
                "stepDone:input.visible.click:=", "stepDone:input.text.type:=")
        return f"calcular {expression}", "|".join(f"{act}&result:{expression}" for act in acts)
    mode = _read_mode(folded)
    if mode is not None:
        return mode
    on = _TOGGLE_ON_CLAUSE.match(folded)
    if on is not None and not _has_deictic_only(on.group("target")) and not re.match(_ORDINAL, on.group("target")):
        target = _unquoted(on.group("target"))
        return f"activar {target}", _with_alternatives(target, ("control:{}:on",))
    off = _TOGGLE_OFF_CLAUSE.match(folded)
    if off is not None and not _has_deictic_only(off.group("target")):
        target = _unquoted(off.group("target"))
        return f"desactivar {target}", _fit(
            _with_alternatives(target, ("control:{}:off",)), *(f"control:{bare}:off" for bare in _without_articles(target))
        )
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
        target = _unquoted(_segments(place.group("target"))[0])
        said_before = folded[: place.start("target")].split()
        if re.fullmatch(_OPENING_VERB, said_before[0]) and _names_a_new_thing(said_before[1:], target):
            # «abrí otra pestaña de X», «abrí una nueva carpeta», «open a new window», «abrí una ventana nueva»: a new
            # thing is made, never a place gone to. Review 3 of r20 P8 (blocker 2): only an opening says it; «andá a
            # new york», «go to another page» go to a place.
            continue
        address = _ADDRESS.fullmatch(target)
        if address is not None:
            if place.re is _NAVIGATE_CLAUSE:
                # «andá a es.wikipedia.org»: the address typed in the browser's bar; arrived is the site in the title.
                return f"ir a la direccion {target}", f"title:{_site_name(address.group('host'))}"
            continue
        target = _ENGLISH_PLACE_AFTER.sub("", target)
        if target:
            # «current»: the place chosen in the window's navigation; an item merely selected in a content list (a
            # folder clicked once in Explorer) is not arriving there (the shell's ComputerUseSuccessCheck). «mark»: on a
            # window drawn without an accessible tree, its row of navigation labels writes the place in an ink none of
            # its neighbours share (v3 punto 5, live v2-s12: Steam already on its library, «BIBLIOTECA» blue); it goes
            # last, so where the check would not fit it is what is left out, never another name of the place.
            atoms = ["control:{}:current", "title:{}", "page:{}"]
            if _SECTION_WORD.search(place.group(0)[: place.start("target")]):
                # A section of a page is reached by its link: the verified click on it is arriving.
                atoms.append("stepDone:input.visible.click:{}")
            check = _fit(_with_alternatives(target, atoms), _with_alternatives(target, ("mark:{}",)))
            if target in _SEARCH_PLACE:
                # The search is where a person types what to look for: its field taking the keyboard after this
                # mission's own click or find key is arriving, even where no navigation item is chosen (measured
                # 2026-10-07: «andá a search» focused the search box and stopped out of steps). A box shown on every
                # page, or one that had the keyboard before any step, is not (the shell's focus: atom).
                check = f"{check}|focus:search"
            return f"ir a {target}", check
    typed = _TYPE_CLAUSE.match(folded)
    if typed is not None:
        placed = cu_tipos.split_typing_place(typed.group("text"))
        if placed is not None:
            # «escribí baxyprueba en el buscador de chats» (cu-v3 texto-webview, wa-1): the search box said after the
            # text is where it goes, never part of it. Written is the text typed there and shown by the view after the
            # act (stepDone, judged by TypedTextShows): never a first look that already shows it somewhere (an address
            # bar holding «…/search?q=gatos»).
            text, field = placed
            return f"{_FIELD_GOAL}{field} en {quoted_literal(text) or _unquoted(text)}", "stepDone:input.text.type"
        # A quoted literal ends at its closing quote; what follows («como título») says what it is, never typed.
        literal = quoted_literal(typed.group("text")) or typed.group("text").strip()
        # Ronda 24b (banco r23 c6): a free text is written where text is written; one typed at the caret into the
        # window's search while another field could take it (the App's receipt: atCaret, intoSearch, otherField) is not
        # written. Its own atom, apart from a search's typing and a field said.
        return f"escribir {literal}", WRITTEN_CHECK
    return _read_type_act(folded)


def _read_type_act(folded: str) -> tuple[str, str | None] | None:
    """The one-step acts of the v3 task types (punto 2): a list scrolled until a thing shows («bajá hasta X», «búscame X
    bajando en la lista» → ``mostrar X``, shown is the control named X whole) and the menu of a thing opened by its right click («clic
    derecho en X» → ``abrir el menu contextual de X``)."""

    revealed = cu_tipos.REVEAL.match(folded) or cu_tipos.LOOKED_FOR_BY_SCROLLING.match(folded)
    if revealed is not None:
        target = _unquoted(clean_target(revealed.group("what")))
        if target and not _has_deictic_only(target):
            return f"mostrar {target}", _with_alternatives(target, ("control:={}",))
    right = cu_tipos.RIGHT_CLICK.match(folded)
    if right is not None:
        what = _unquoted(clean_target(right.group("what") or right.group("ewhat") or ""))
        what = re.split(r"\s+(?:y|and)\s+", what, maxsplit=1)[0].strip()
        what = re.sub(r"^(?:el|la|los|las|the)\s+", "", what)
        if cu_tipos.EMPTY_SPACE.match(what):
            what = cu_tipos.EMPTY_SPACE_TARGET
        if what and not _has_deictic_only(what):
            return f"abrir el menu contextual de {what}", context_menu_check(what)
    return None


# Opened is the context menu by its key (context_menu, Shift+F10) in this sub-goal: the one way the shell opens it
# (the catalog has no operation of its own for it).
CONTEXT_MENU_CHECK = "stepDone:input.key.press:context_menu|stepDone:input.key.press:shift_f10"


def context_menu_check(what: str) -> str:
    """The context menu of ``what`` opened: by its key (``CONTEXT_MENU_CHECK``) or (ronda 21, t-menu-1, t-menu-2) by the
    state the click in the manner «menu» left on it, ``menuOpened:<what>`` (the shell's MenuOpenedByAct: a menu act on a
    control its label names, whose receipt opened a menu or after which the view shows one). Revisión 1 (hallazgo 3):
    the atom carries ``what``, so a menu opened on another element proves nothing; an empty space's carries no name
    (the shell takes the menu act on a container that holds items, never on an item); a name the check cannot hold
    (``_check_name`` empty) leaves the key alone."""

    if what == cu_tipos.EMPTY_SPACE_TARGET:
        return f"{CONTEXT_MENU_CHECK}|menuOpened:"
    name = _check_name(what, known=False)
    check = f"{CONTEXT_MENU_CHECK}|menuOpened:{name}"
    return check if name and len(check.encode("utf-8")) <= _CHECK_BYTES else CONTEXT_MENU_CHECK
CONTEXT_MENU_GOAL = "abrir el menu contextual de "


# «abrí una pestaña nueva», «open a new tab»: the browser's own key for it.
_NEW_TAB_CLAUSE = re.compile(
    r"^(?:abri|abre|abrir|abrime|open|crea|create)\s+(?:(?:una|otra|a|another)\s+)?(?:(?:nueva|new)\s+)?"
    r"(?:pestana|tab|solapa)(?:\s+(?:nueva|new))?$"
)
# Ronda 20 P8 (v3-37): «abrí una pestaña nueva de símbolo del sistema», «abrí otra pestaña de powershell», «nueva
# pestaña de X», «open a new tab of X», «open a new X tab»: a new container (data ``lexicon.CONTAINER_NOUNS``) of a
# named kind. The word that says it is new (``lexicon.NOVELTY_WORDS``) is never part of the kind nor of a place.
_OPENING_VERB = r"(?:abri|abre|abrir|abrime|abra|open|crea|crear|creame|create)"
_CONTAINER = alternation(lexicon.CONTAINER_NOUNS)
_NOVELTY = alternation(lexicon.NOVELTY_WORDS)
_NEW_CONTAINER_OF_CLAUSE = re.compile(
    rf"^(?:{_OPENING_VERB}\s+)?(?:(?P<det>una|un|la|el|a|the|{_NOVELTY})\s+)?(?:(?P<before>{_NOVELTY})\s+)?"
    rf"(?P<noun>{_CONTAINER})(?:\s+(?P<after>{_NOVELTY}))?\s+(?:de|del|con|of|with|for)\s+(?P<kind>\S.{{0,60}}?)[\s.!?]*$"
)
_NEW_KIND_CONTAINER_CLAUSE = re.compile(
    rf"^(?:{_OPENING_VERB}\s+)?(?:(?:a|an|another)\s+)?(?P<before>new|another)\s+(?P<kind>\S.{{0,40}}?)\s+"
    rf"(?P<noun>{_CONTAINER})[\s.!?]*$"
)


def _names_a_new_thing(lead: list[str], target: str) -> bool:
    """Whether an opening's object says a new thing (review 1 of r20 P8, finding 3; narrowed in review 3, blocker 2).
    ``lead`` is what the clause read before the target (an article, a place's noun), ``target`` the rest. A new thing
    is a word of novelty beside a container's noun («la pestaña nueva», «a new tab in edge», «ventana nueva»), one that
    is indefinite itself heading the object («otra carpeta», «another window»), or, after an indefinite article, one
    heading the object or right after its noun («una nueva carpeta», «a new window», «una carpeta nueva»). A name that
    only begins with such a word («new york», «nueva carpeta», «new releases», «el menú nuevo») stays a place."""

    words = [*lead, *target.split()]
    if any(
        word in lexicon.NOVELTY_WORDS
        and any(near in lexicon.CONTAINER_NOUNS for near in words[max(index - 1, 0) : index + 2])
        for index, word in enumerate(words)
    ):
        return True
    articles = lexicon.TOGGLE_DEFINITE_LEADS | lexicon.INDEFINITE_ARTICLES
    head = 0
    while head < len(words) and words[head] in articles:
        head += 1
    if head >= len(words):
        return False
    if words[head] in lexicon.INDEFINITE_NOVELTY_WORDS:
        return True
    indefinite = any(word in lexicon.INDEFINITE_ARTICLES for word in words[:head])
    return indefinite and any(word in lexicon.NOVELTY_WORDS for word in words[head : head + 2])


def _new_container(folded: str) -> tuple[str, str] | None:
    """(the container noun, the kind) of «abrí una pestaña nueva de X», «open a new X tab»; None unless a word says
    it is a new one."""

    for clause in (_NEW_CONTAINER_OF_CLAUSE, _NEW_KIND_CONTAINER_CLAUSE):
        said = clause.match(folded)
        if said is None:
            continue
        groups = said.groupdict()
        if groups.get("det") in lexicon.TOGGLE_DEFINITE_LEADS:
            # Review 2 of r20 P8: «la otra pestaña de X», «el otro tab», «la pestaña nueva de X», said definite, name
            # one already open; only an indefinite («una», «otra», «a», «another») or a bare novelty asks a new one.
            continue
        novel = groups.get("before") or groups.get("after") or (
            groups.get("det") if groups.get("det") in lexicon.NOVELTY_WORDS else None)
        kind = _unquoted(re.sub(r"^(?:el|la|los|las|the)\s+", "", said.group("kind").strip()))
        if novel and kind and kind not in lexicon.NOVELTY_WORDS and not _has_deictic_only(kind):
            return lexicon.CONTAINER_GOAL_NOUNS[said.group("noun")], kind
    return None
_ADDRESS = re.compile(r"(?:https?://)?(?P<host>(?:[a-z0-9-]+\.)+[a-z]{2,63})(?:/\S*)?")
_SECTION_WORD = re.compile(r"\b(?:seccion|section|apartado)\b")
# The search as a place, by its names in either language («andá a search», «ve a la búsqueda»): data (ronda 24b,
# ``data/computer_use_words.v1.json`` «searchPlace»), read here and by the computer-use steps (``is_search_place``).
@functools.lru_cache(maxsize=1)
def _search_place_names() -> frozenset[str]:
    path = Path(__file__).resolve().parent.parent / "data" / "computer_use_words.v1.json"
    listed = (json.loads(path.read_text(encoding="utf-8")).get("searchPlace") or {}).get("names") or []
    return frozenset(" ".join(fold(str(name)).split()) for name in listed if str(name).strip())


def is_search_place(target: object) -> bool:
    """The goal's place is the search itself («andá a search», «ve a la búsqueda»), by its whole folded name."""

    return " ".join(fold(str(target or "")).split()) in _search_place_names()


_SEARCH_PLACE = _search_place_names()
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
            # A check left with no atom («ir a Q&A»: no piece of the name proves it) is no check.
            return act[0], act[1] or None
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
        # «haz clic en «Sistema»» (measured 2026-10-07: the context decider's rewrite of «y después a Sistema» quoted
        # the name; the quoted name matched no control, so the loop searched for «sistema» with its quotes and
        # failed): quotes delimit the name, they are no part of it.
        label = _unquoted(label)
    if label and not _label_names_something(label):
        # Falsos éxitos v3 M2 (v3-11): «pulsa «pagina» para crear una nueva pagina» left the label «pagina» para
        # crear…»; the model typed it into the window's search and pressed its own suggestion. A label with a quote
        # inside or a clause of purpose names no control: the goal stays free, with no check that a click proves.
        return doing, None
    if label:
        chosen = _select_target(label)
        if chosen != label and is_basic_colour(chosen):
            # Estabilización G3 (tandas estab1/estab2 t3-c19 «y ponle color rojo» → «hacer clic en color rojo», no
            # control of that name): a click on a colour said with its kind («el color rojo», «the red colour») is the
            # colour chosen, as «seleccioná el color rojo» reads it: its swatch, by the colour's own check.
            return f"seleccionar {chosen}", _select_check(chosen)
        return f"hacer clic en {label}", _with_alternatives(label, ("stepDone:input.visible.click:{}",)) or None
    return doing, None


# A clause of purpose inside a click's label («para crear …», «para que …», «in order to …»): what follows is why,
# never the control's name. «Opciones para desarrolladores» (no verb after «para») is a name.
_LABEL_PURPOSE = re.compile(
    r"\b(?:para\s+que|para\s+[a-z]+(?:ar|er|ir)(?:l[aeo]s?|se|me|te|nos)?|a\s+fin\s+de|con\s+el\s+fin\s+de|"
    r"in\s+order\s+to|so\s+that)\b"
)
_LABEL_QUOTES = frozenset("«»\"“”")


def _label_names_something(label: str) -> bool:
    """A click's label names a control: no quote mark left inside it and no clause of purpose."""

    folded = fold(label).strip()
    return not any(mark in folded for mark in _LABEL_QUOTES) and _LABEL_PURPOSE.search(folded) is None


# «tocá Comunidad», «tap Join»: touching a control is clicking it.
_TOUCH_HEAD = re.compile(r"^(?:toca|tocale|toque|tap(?:\s+on)?|clickea|clica|clicka|pincha)\s+(?:(?:en|on)\s+)?")


_INNER_ARTICLE = re.compile(r"(?<=\S)\s+(?:el|la|los|las|the)\s+(?=\S)")


def _without_articles(target: str) -> tuple[str, ...]:
    """«mantener la relación de aspecto» → «mantener relación de aspecto»: a box is named without the articles a
    person puts inside its name; empty when the name has none."""

    bare = _INNER_ARTICLE.sub(" ", target)
    return (bare,) if bare != target else ()


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


_LINE_BREAKS = frozenset({"\r", "\n"})


def _said_span(wanted: str, said: str) -> str | None:
    """The stretch of ``said`` whose fold is the folded piece ``wanted``, or None. Whitespace is compared by runs
    (a double space or a line break is one space, as in the folded reading, where a line break reads « . »), and
    the stretch comes back with its runs as one space (a line break is never typed as Enter)."""

    folded_chars: list[str] = []
    origin: list[int] = []
    for position, character in enumerate(said):
        if character.isspace():
            # A line break is the « . » the reading puts between lines (mission_request).
            pieces = " . " if character in _LINE_BREAKS and not (position and said[position - 1] in _LINE_BREAKS) else " "
        else:
            pieces = fold(character)
        for piece in pieces:
            if piece == " " and folded_chars and folded_chars[-1] == " ":
                continue
            folded_chars.append(piece)
            origin.append(position)
    needle = " ".join(wanted.split())
    start = "".join(folded_chars).find(needle) if needle else -1
    if start < 0:
        return None
    end = start + len(needle) - 1
    return " ".join(said[origin[start]:origin[end] + 1].split())


def _restore(wanted: str, said: str) -> str:
    """The folded piece ``wanted`` as the person wrote it in ``said`` (case, accents), without delimiting quotes."""

    span = _said_span(wanted, said)
    if span is None:
        return wanted.strip("\"'«»“”")
    return span.strip().strip("\"'«»“”").strip()


def check_fold(value: object) -> str:
    """A name as the shell folds it for a check (ComputerUseSuccessCheck.Fold: FormD, ToLowerInvariant, no
    non-spacing marks, one space): ``fold`` reads the request with casefold and NFKD, which the shell does not
    («Straße» is «strasse» to the reader and «straße» to the shell)."""

    text = unicodedata.normalize("NFD", str(value or "")).lower()
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return " ".join(text.split())


_CONTROL_STATES = frozenset({"selected", "current", "on", "off", "expanded", "focused", "collapsed"})


def _check_as_said(check: str | None, said: str) -> str | None:
    """The check with every name it took from the request folded as the shell folds it (``check_fold`` over the
    words as said); names the request does not hold (another language's, a control's) stay as they are."""

    if not check:
        return check

    def name(folded: str) -> str:
        span = _said_span(folded, said) if folded else None
        return check_fold(span) if span is not None else folded

    def atom(text: str) -> str:
        kind, colon, rest = text.partition(":")
        if not colon:
            return text
        lead = tail = ""
        if kind == "stepDone":
            operation, colon, rest = rest.partition(":")
            if not colon:
                return text
            lead = operation + ":"
            if len(rest) > 1 and rest.startswith("="):
                lead, rest = lead + "=", rest[1:]
        elif kind == "control":
            if rest.startswith("="):
                lead, rest = "=", rest[1:]
            stem, colon, state = rest.rpartition(":")
            if colon and state in _CONTROL_STATES:
                rest, tail = stem, ":" + state
        return f"{kind}:{lead}{name(rest)}{tail}"

    return "|".join("&".join(atom(part) for part in term.split("&")) for term in check.split("|"))


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


# Formatting is destructive for a drive or the computer, for «it»/«lo» (which may be one) and said bare, in both
# languages; a text's format is not (v3 ronda 3 review: «change the format to bold», «formateá el texto en negrita»).
_FORMATTING_A_DRIVE = (
    r"(?:^|\s)format\w*\s+(?:(?:el|la|los|las|un|una|mi|mis|tu|su|este|esta|ese|esa|the|my|this|that|a|your)\s+)?"
    r"(?:(?:disco|unidad|pendrive|usb|drive|disk|particion|partition|computadora|computer|ordenador|equipo|memoria|"
    r"tarjeta|ssd|hdd|laptop|notebook)\w*|(?:pc|sd|it|hard)\b|[a-z]:)"
    r"|(?:^|\s)formate\w*(?:lo|la|los|las)\b|(?:^|\s)formate\w*(?=[\s,;.!]*$)"
)


# An undoing or paying act said anywhere in the request: never read as a mission (owner's rule; RiskPolicy asks for
# such a step, and a whole goal of that kind is not handed to the screen loop).
# Review of v3 r3a lectura L3 (a free sub-goal now reaches the engine): money or a gift sent to someone, and a cart
# taken to its end, are paying too («mandale 20 dólares», «transferile plata», «regalale Hades a Juan», «agregá Hades
# al carrito y finalizá», «send him 20 bucks», «proceed to checkout»).
_SENDING_MONEY_OR_GIFT = (
    r"(?:mand|envi|transferi|transfiere|send|wire|transfer)\w*\s+(?:\S+\s+){0,3}?"
    r"(?:(?:plata|dinero|guita|lucas|money|cash|bucks)\b|\$\s*\d|"
    r"\d+(?:[.,]\d+)?\s*(?:\$|(?:dolares|dolar|pesos|euros|euro|usd|clp|lucas|mil|dollars|bucks)\b))"
    r"|\b(?:regala|regalale|regalales|regalalo|regalala|regalar|regalarle|regalarles|gift|gifts)\b"
    r"|\b(?:carrito|cart|checkout)\b|\bfinaliza(?:r)?\s+(?:la\s+|mi\s+)?compra\b"
)
_UNDOING_OR_PAYING_ACT = re.compile(
    r"\b(?:borra|borrala|borralo|borralas|borralos|borrar|borre|borrame|elimina|eliminala|eliminalo|eliminar|elimine|"
    r"vaciar|vacia\s+(?:la|el|los|las)|desinstala|desinstalar|desinstalalo|desinstale|"
    r"compra|compralo|comprala|comprar|comprame|compre|paga|pagalo|pagala|pagar|pague|transferi\w*|transfiere\w*|"
    r"delete|remove|uninstall|buy|purchase|pay|wipe|erase)\b"
    # Safety review 2026-10-07: removing, discarding, the bin, subscriptions, renting, donating, selling, resetting,
    # clearing, emptying and leaving a server or a group. «sacá» only as «sacá(lo) de» or «sacá a alguien de»: alone it takes a
    # screenshot. «vacía» only imperative before an article (after a noun it is «una carpeta vacía»).
    r"|\b(?:quita|quitar|quitalo|quitala|quitalos|quitalas|quite|quitame|saca(?:lo|la|los|las)?\s+(?:a\s+\S+(?:\s+\S+)?\s+)?(?:de|del)|"
    r"papelera|trash|recycle\s+bin|descarta|descartar|descartalo|descartala|descarte|discard|"
    r"cancela(?:r)?\s+(?:(?:la|mi|el)\s+)?(?:suscripcion|subscripcion|membresia|plan)|unsubscribe|"
    r"cancel\s+(?:(?:my|the)\s+)?(?:subscription|membership|plan)|"
    r"suscribime|suscribirme|suscribite|suscribete|suscribirse|suscribirte|subscribe|"
    r"alquila|alquilar|alquilalo|alquilala|rent|dona|donar|donale|donate|vende|vender|vendelo|vendela|sell|"
    r"restablece|restablecer|restablecelo|resetea|resetear|reset|limpia|limpiar|limpialo|limpiala|clear|"
    r"empty\s+(?:the|my|your|trash|recycle|bin)|"
    r"(?:sali|salir|salite|salirme|abandona|abandonar|leave)\s+(?:(?:del|de|el|la|this|the)\s+)?"
    # Imprescindibles de mensajería: a voice channel is left by hanging up, never by leaving its server («salí del
    # canal de voz»: chats.leaves_the_call).
    r"(?:servidor|server|grupo|group|canal(?!\s+de\s+voz)|channel))\b"
    r"|" + _FORMATTING_A_DRIVE
    + r"|\b(?:" + _SENDING_MONEY_OR_GIFT + r")"
)


def _orders_undoing_or_paying(folded: str) -> bool:
    """An undoing or paying act in a clause of the request; what a clause types is the person's text, not an act
    («type buy milk»), and neither is what a writing or putting verb dictates after its colon or between quotes
    (ronda 21, v3-35 «ponle: pagar la luz»: ``_order_without_its_dictated_text``)."""

    for segment in _segments(_order_without_its_dictated_text(folded)):
        said = next((clause for _, clause in _app_frames(segment, longer_names=False)), segment)
        if any(_TYPE_CLAUSE.match(reading) for reading in _clause_readings(said.strip(" ,;:.!?"))):
            continue
        if _UNDOING_OR_PAYING_ACT.search(segment):
            return True
    return False


# «… y decime si el modo es claro u oscuro», «and tell me what it says»: a question about what the window shows at
# the end. It is no sub-goal: the mission's final answers it from the last view (cu_projection.project_seen).
# A verb of telling also asks with the thing alone (measured 2026-10-07: «… después a Sonido y decime el volumen» was
# left unread, so the whole request went to the engine as one free goal and the model stopped on the first page);
# looking at or checking a thing («mirá el video», «check the box») is a doing, never a question.
_QUESTION_BODY = (
    r"(?P<question>(?:(?:decime|dime|digame|deci|contame|cuentame|avisame|fijate|mira|mirame|tell\s+me|let\s+me\s+know|"
    r"show\s+me|check)\s+(?:si|que|cual|cuales|cuanto|cuanta|cuantos|cuantas|como|donde|cuando|quien|whether|if|what|"
    r"which|how|where|when|who)"
    r"|(?:decime|dime|digame|deci|contame|cuentame|tell\s+me|read\s+me)\s+(?:el|la|los|las|lo\s+que|the|my)(?=\s+\S))\b.*)$"
)
_QUESTION_TAIL = re.compile(
    r"(?:\s*[,;.]\s*(?:(?:y|and)\s+)?|\s+(?:y|and)\s+|\s+(?=(?:despues|luego|then|entonces)\s))"
    r"(?:(?:despues|luego|then|entonces|al\s+final|finally)\s+)?"
    + _QUESTION_BODY
)
# v3 ronda 5 (lectura M3/M5, diseño 4): the question as the whole clause said inside an application («en Seguridad de
# Windows decime cuándo fue el último examen», «en Terminal, decime cuántas pestañas hay»).
_QUESTION_ALONE = re.compile(r"^" + _QUESTION_BODY)
# A question said with no «decime» before it: its interrogative word heads it («cuáles tienen impacto alto»).
_ASKED_HEAD = re.compile(
    r"^(?:que|cual|cuales|cuanto|cuanta|cuantos|cuantas|como|donde|cuando|quien|quienes|hay|what|which|how|where|"
    r"when|who|is|are|does|do|did|was|were|has|have)\b"
)
# The mark between the sub-goals and the question in a mission's goal (cu_projection.project_seen reads it).
QUESTION_MARK = "; y responder: "
# A text to type said after a colon runs to the end of the request: «escribí: pasá por lo de Ana y decime el horario».
_TYPED_LITERAL_TO_END = re.compile(r"(?<!\w)(?:escribi|escribe|escribime|escriba|tipea|tipeame|teclea|type|write)\s*:")
_PAIRED_QUOTES = {"«": "»", "“": "”", "„": "“"}
# The one rule of a dictated text (corrección v3 destino): a verb of writing or putting, with its pronoun too
# («ponle», «escribile»), up to a few words of where («escribe esto en el documento») and a colon; what follows is the
# person's text to the end. A colon before a digit is a time («a las 10:30»), never one.
_DICTATING_VERB = (
    r"(?<![a-z0-9])(?:escrib[a-z]*|tipe[a-z]*|tecle[a-z]*|anot[a-z]*|apunt[a-z]*|agreg[a-z]*|anad[a-z]*|"
    r"pon(?:e|er|ga|gan)?(?:me|te|se|le|les)?(?:lo|la|los|las)?|type|write|put|add|enter)"
)
_DICTATED_TEXT_OPENS = re.compile(_DICTATING_VERB + r"(?:\s+[^\s:;.!?]+){0,5}?\s*:(?!\d)")
# Revisión 2 de la ronda 21 (seguridad): a quoted text is the person's dictated text only as the object of that same
# verb, with a few words of where between them and no other clause («escribí en el chat "hola"», «ponle «pagar la
# luz»»); the quoted label of a click («haz clic en «Restablecer este PC»», «pulsa "Eliminar servidor"») is the order.
_DICTATING_BEFORE_QUOTE = re.compile(
    _DICTATING_VERB
    + r"(?:\s+(?!(?:y|e|o|and|or|luego|despues|then|entonces)(?![a-z0-9]))[^\s:;,.!?\"«»“”„]+){0,5}?\s*:?\s*$"
)


def _dictated_text_opens(folded: str) -> re.Match[str] | None:
    """The writing verb and its colon that open a dictated text (the text begins where the match ends), or None."""

    return _DICTATED_TEXT_OPENS.search(folded)


def _inside_said_text(folded: str, position: int) -> bool:
    """The position falls inside a text the person dictated: between quotes still open there, or after a writing or
    putting verb's colon (``_DICTATED_TEXT_OPENS``: an unquoted literal runs to the end). A question tail or an
    application's name there is part of the text, never a question or a destination."""

    before = folded[:position]
    if before.count('"') % 2 == 1:
        return True
    if any(before.count(opening) > before.count(closing) for opening, closing in _PAIRED_QUOTES.items() if opening != closing):
        return True
    return _TYPED_LITERAL_TO_END.search(before) is not None or _dictated_text_opens(before) is not None


def _question_tail(folded: str) -> re.Match[str] | None:
    """The closing question of the request, skipping a match that starts inside a dictated text."""

    position = 0
    while (asked := _QUESTION_TAIL.search(folded, position)) is not None:
        if not _inside_said_text(folded, asked.start()):
            return asked
        position = asked.start() + 1
    return None


# Uso real v3 ronda 19 (pedido al motor). The shape of an order as the readers read it:
# - «en el excel que tengo abierto seleccioná …»: the relative clause that says the application is open
#   (``lexicon.OPEN_APPLICATION_RELATIVES``) is no question («¿qué tengo abierto?» said alone still is one) and no
#   part of the order that follows it. Only said right after the application's name (a comma between them too:
#   «en el excel, que tengo abierto, seleccioná …», revisión adversarial 2) and followed by an order
#   (``_without_open_relative``): «en chrome qué tengo abierto en las pestañas», «tell me what I have open» and
#   «cerrá todo lo que tengo abierto y …» keep their words;
_OPEN_RELATIVE = re.compile(
    r"(?<=[a-z0-9])(?:\s*,\s*|\s+)" + alternation(lexicon.OPEN_APPLICATION_RELATIVES) + r"(?=\s*[,;:]?\s+[a-z0-9])"
)
# - «abre configuracion que quiero ver lo de la pantalla», «open settings so I can see the display section»: opening
#   an application to see a place of it is opening it and going there. Only a place said as a part of the application
#   (``lexicon.SEEN_PLACE_MARKERS``, or «the <place> section/page/menu/settings»): «abre youtube para ver videos de
#   gatos», «abre word para ver el informe», «abre excel para ver las ventas», «abre youtube pa ver un rato» say content
#   to see, a document to open or a while, never a place; the decider reads them (revisión adversarial 3);
_OPEN_TO_SEE = re.compile(
    r"^(?P<open>(?:abri|abre|abrime|abra|abrir|open|launch)\s+(?:(?:la|el|the)\s+)?"
    r"(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?))\s*,?\s+"
    r"(?P<link>que|para|pa|porque|so\s+(?:that\s+)?i\s+can|to|because)\s+"
    r"(?:(?:yo\s+)?(?:quiero|quisiera|necesito|tengo\s+que|i\s+want\s+to|i\s+need\s+to|want\s+to|need\s+to|wanna)\s+)?"
    r"(?:ver|mirar|revisar|chequear|see|check|look\s+at)\s+"
    r"(?:" + alternation(lexicon.SEEN_PLACE_MARKERS) + r"\s+(?P<place>[a-z0-9][^,;.!?]*?)"
    r"|the\s+(?P<named>[a-z0-9][^,;.!?]*?)\s+(?:section|settings|page|menu))[\s.!?]*$"
)
# - «poné el titulo en negrita», «elige el lapiz con color azul»: an object said with its article and what is applied
#   to it (a format, a colour or a tool: ``lexicon.FORMAT_ATTRIBUTES``, ``colours.is_basic_colour``,
#   ``lexicon.TOOL_ATTRIBUTES``) are two sub-goals, the object selected and the attribute applied; never one control
#   named «titulo en negrita». «la opción con más memoria» or «el modo avión» apply nothing of those. A pronoun
#   («ponelo en negrita» after a text typed) stays one free sub-goal: what it points at may not be selected, and
#   turning bold on alone would format only what comes next.
_ATTRIBUTE_TAIL = (
    r"\s+(?P<prep>en|con|in|with)\s+(?:(?:el|la|un|una|the|a)\s+)?(?:(?P<colour>" + alternation(lexicon.COLOUR_NOUNS)
    + r")\s+)?(?P<attribute>[a-z]+(?:\s+[a-z]+){0,2}?)(?:\s+(?P<colour_after>" + alternation(lexicon.COLOUR_NOUNS) + r"))?$"
)
_OBJECT_WITH_ATTRIBUTE = re.compile(
    r"^(?P<verb>[a-z]+)\s+(?P<object>(?:el|la|los|las|the|this|ese|esa|este|esta)\s+[a-z0-9][a-z0-9 ]*?)" + _ATTRIBUTE_TAIL
)
_SHAPE_LINK = re.compile(r"(\s*[,;]\s*|\s+(?:y|e|and|luego|despues|then)\s+)")


def _attribute_kind(attribute: str, colour_said: bool) -> str | None:
    if attribute in lexicon.FORMAT_ATTRIBUTES and not colour_said:
        return "format"
    if is_basic_colour(attribute):
        return "colour"
    if attribute in lexicon.TOOL_ATTRIBUTES and not colour_said:
        return "tool"
    return None


def _applied_attribute(words: list[str]) -> tuple[int, re.Match[str], str] | None:
    """Where in ``words`` an object said with its article gets a format, a colour or a tool (``_OBJECT_WITH_ATTRIBUTE``):
    (start, match, kind), or None."""

    for start in range(len(words)):
        tail = " ".join(words[start:])
        found = _OBJECT_WITH_ATTRIBUTE.match(tail)
        if found is None:
            continue
        kind = _attribute_kind(found.group("attribute"), bool(found.group("colour") or found.group("colour_after")))
        if kind is None:
            continue
        read = read_clause(tail)
        if read is not None and "input.text.type" in str(read[1]):
            # «escribí el título en negrita», «type the title in bold»: the words are a text to write, never a format.
            return None
        if read is None and found.group("verb") not in lexicon.SETTING_VERBS:
            continue
        return start, found, kind
    return None


def presupposes_an_open_document(text: object) -> bool:
    """Estabilización G3 (tandas f2nb t2-c10 «en word poné el título en negrita y centralo», t3-c02 «en el excel que
    tengo abierto seleccioná la fila 1 y ponela en negrita», t4-c13 «en el word que tengo abierto ponle negrita al
    texto que tengo seleccionado»): the request acts on a document already open — it says its application is the one
    open (``_OPEN_RELATIVE``) or gives a format to a thing of it said with its article («el título en negrita»,
    ``_applied_attribute``). Never a request that asks for a new or blank document (``apps.asks_new_document``, a
    blank word) or writes the text it formats («escribí el título en negrita»)."""

    from .apps import asks_new_document

    folded = " ".join(fold(str(text or "")).split())
    if not folded or _BLANK_ITEM.search(folded) is not None or asks_new_document(folded):
        return False
    if _OPEN_RELATIVE.search(folded) is not None:
        return True
    return any(
        (applied := _applied_attribute(piece.split())) is not None and applied[2] == "format"
        for piece in _SHAPE_LINK.split(folded)
    )


def _split_attribute(piece: str) -> str | None:
    words = piece.split()
    found_at = _applied_attribute(words)
    if found_at is None:
        return None
    start, found, kind = found_at
    english = found.group("prep") in {"in", "with"}
    attribute = found.group("attribute")
    select = "select" if english else "selecciona"
    # The object is selected: by the verb said when it reads as a selection («elige el lápiz»), else by
    # «selecciona» («poné el título …» is no switch called «título»).
    said = f"{found.group('verb')} {found.group('object')}"
    own = read_clause(said)
    chosen = said if own is not None and own[0].startswith("seleccionar ") else f"{select} {found.group('object')}"
    if kind == "format":
        applied = f"{'turn on' if english else 'activa'} {attribute}"
    elif kind == "colour":
        applied = f"{'select the colour' if english else 'selecciona el color'} {attribute}"
    else:
        applied = f"{'select the' if english else 'selecciona el'} {attribute}"
    if kind == "tool":
        done = f"{applied} {'and' if english else 'y'} {chosen}"
    else:
        done = f"{chosen} {'and' if english else 'y'} {applied}"
    return " ".join((*words[:start], done))


def _without_open_relative(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    """The folded request without the relative that says its application is open (``_OPEN_RELATIVE``), only when
    the relative is said right after an application's name and an order follows it; else the same request."""

    if catalog.occurrence_pattern is None:
        return folded
    for relative in _OPEN_RELATIVE.finditer(folded):
        before = folded[:relative.start()]
        if not any(
            found.end() == len(before) and not _inside_a_path(folded, found.start(), found.end())
            for found in catalog.occurrence_pattern.finditer(before)
        ):
            continue
        if not _order_follows(folded[relative.end():]):
            continue
        return before + folded[relative.end():]
    return folded


def _order_follows(rest: str) -> bool:
    """What follows a relative opens with an order (its first piece reads as one), never with more of a question
    («… en las pestañas», «… ahora mismo»)."""

    first = _SHAPE_LINK.split(rest.lstrip(" ,;:"), maxsplit=1)[0]
    return bool(first) and (read_clause(first) is not None or _free_order(first))


def _a_place_to_go(place: str) -> bool:
    """Revisión adversarial 2 r19: what is opened «para ver» is a place of the application to go to only when it is
    said as one — never a clause or a question («si me escribió mi mamá», «cuánto es 5 por 8», «lo que hay»:
    ``lexicon.SEEN_CLAUSE_HEADS``), never a count or a sum, and never something to find out that the readers answer
    elsewhere: what changes with the day or is the person's own («el clima», «my email», «mis mensajes»:
    ``web.memory_may_answer``). Else the turn keeps its words for the decider."""

    from .web import memory_may_answer

    words = re.findall(r"[a-z0-9]+", place.replace("'", "").replace("’", ""))
    if not words or any(word.isdigit() for word in words):
        return False
    if words[0] in lexicon.SEEN_CLAUSE_HEADS or " ".join(words[:2]) in lexicon.SEEN_CLAUSE_HEADS:
        return False
    return memory_may_answer(place)


def request_shape(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    """The folded request as the readers read its shape (``_OPEN_RELATIVE``, ``_OPEN_TO_SEE``,
    ``_OBJECT_WITH_ATTRIBUTE``); the same request when none applies."""

    shaped = _without_open_relative(folded, catalog)
    seen = _OPEN_TO_SEE.match(shaped)
    place = (seen.group("place") or seen.group("named") or "") if seen is not None else ""
    if seen is not None and _catalog_key(seen.group("app"), catalog) is not None and _a_place_to_go(place):
        english = seen.group("link") in {"to", "because"} or seen.group("link").startswith("so")
        shaped = f"{seen.group('open')} {'and go to' if english else 'y ve a'} {place.strip()}"
    pieces = _SHAPE_LINK.split(shaped)
    return "".join(piece if index % 2 else (_split_attribute(piece) or piece) for index, piece in enumerate(pieces))


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
    if asks_to_drag(text):
        # Estabilización L: dragging or drawing is a declared limit (patterns.known_unsupported_effect_request says it);
        # no mission tries it.
        return None
    folded = request_shape(folded, catalog)
    written = _last_written_mission(folded, text, catalog) or send_in_place(text, catalog)
    if written is not None:
        return written
    asked = _question_tail(folded)
    question = None
    if asked is not None and asked.start() > 0:
        question = _restore(asked.group("question").strip(" .!?"), text)
        folded = folded[: asked.start()].strip(" ,;.")
    looked = _question_in_place(folded, text, catalog) if question is None else None
    if looked is not None:
        return looked
    mission = _read_mission(folded, text, catalog)
    if mission is None:
        mission = _in_named_folder(folded, text, catalog)
    mission = _with_place_arrivals(mission, text)
    if mission is None and question is not None:
        # «en Seguridad de Windows, decime cuándo fue el último examen»: nothing to do there but look and answer.
        place = _bare_place(folded, catalog)
        return _looking_in(place, question) if place is not None else None
    if mission is None or question is None:
        return mission
    # The question rides on the goal; a single sub-goal stays a single mission (its budget, not a chain link's).
    goal = "; luego ".join(step.goal for step in mission.steps) if mission.steps else mission.goal
    goal = goal.encode("utf-8")[:400].decode("utf-8", "ignore")
    tail = (QUESTION_MARK + question).encode("utf-8")[:100].decode("utf-8", "ignore")
    if mission.steps:
        # Ronda 23 (live r21 v3-46: «andá a Componentes > Pantalla y decime qué tarjeta de video tengo» closed its last
        # sub-goal on the click's receipt and never read the table): the last sub-goal carries the question too, so it
        # is closed by a look that reads the datum, never by receipts alone.
        last = mission.steps[-1]
        said = last.goal.encode("utf-8")[:400].decode("utf-8", "ignore")
        mission = replace(mission, steps=(*mission.steps[:-1], replace(last, goal=said + tail)))
    return replace(mission, goal=goal + tail)


def _last_written_mission(
    folded: str, text: str, catalog: effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """Imprescindibles de mensajería: «en Discord leé lo último que me escribió Ron92», «qué me escribió Ron92 en
    Discord», «what did Ron92 write me on Discord». The chat is gone to as any place of the application («ir a <chat>»,
    with that check) and the person's question rides on it, answered from the conversation the last view shows
    (``cu_finals.question_answer``). None without an installed application framing it: who wrote is no place."""

    for application, clause in _app_frames(folded, longer_names=False):
        asked = chats.last_written(clause)
        key = _catalog_key(application, catalog) if asked is not None else None
        read = read_clause(f"ir a {asked.chat}") if asked is not None and key is not None else None
        if read is None or read[1] is None:
            continue
        goal = read[0].encode("utf-8")[:400].decode("utf-8", "ignore")
        tail = (QUESTION_MARK + _restore(clause.strip(" .!?"), text)).encode("utf-8")[:100].decode("utf-8", "ignore")
        return MissionRequest(_display_name(key, catalog), goal + tail, read[1], clause=clause)
    return None


def send_in_place(
    text: str, catalog: effect_intent.ApplicationCatalogIndex | Iterable[str],
) -> MissionRequest | None:
    """Encargo IMP2: a message to someone in a client whose sends are a mission (data conversation_acts «sendInPlace»):
    «en WhatsApp mandale a Música "prueba BAXY imp"» is the chain c6 sends with in Discord — go to the chat, write the
    text, send it (``_with_sent_checks``). None for any other request or client."""

    named = messaging.message_request_named_client(text)
    if named is None:
        # The client framed ahead («en WhatsApp mandale a Música "…"»): the clause read with its client after it, in
        # the person's own spelling (the text is typed as said).
        framed = effect_intent._strip_request_envelope(fold(text)).strip(" .!?")
        named = next((
            found for application, clause in _app_frames(framed, longer_names=False)
            if (found := messaging.message_request_named_client(f"{_restore(clause, text)} en {application}")) is not None
        ), None)
    if named is None or named[2] not in chats.data()["sendInPlace"]["clients"]:
        return None
    if not re.search(rf"\b(?:a|al|to)\s+(?:(?:el|la)\s+)?(?:grupo\s+|group\s+)?{re.escape(fold(named[0]).strip())}\b", fold(text)):
        # Someone the message goes to is said as such («a Música»); «escribí X en el buscador de chats» writes in a place.
        return None
    recipient, body, client = named[0], named[1].strip(" \"'«»“”"), named[2]
    catalog = effect_intent.build_application_catalog_index(catalog)
    key = _catalog_key(client, catalog)
    going = read_clause(f"ir a {fold(recipient)}")
    if key is None or going is None or going[1] is None or not body:
        return None
    application = _display_name(key, catalog)
    clause = fold(text).strip(" .!?")
    steps = _with_sent_checks([
        MissionStep(application, going[0], going[1], clause),
        MissionStep(application, f"escribir {body}", WRITTEN_CHECK, clause),
        MissionStep(application, SEND_GOAL, SEND_CHECK, clause),
    ])
    goal = "; luego ".join(step.goal for step in steps).encode("utf-8")[:500].decode("utf-8", "ignore")
    return MissionRequest(application, goal, None, clause, tuple(steps))


def last_written_in_a_place(text: str) -> bool:
    """A last-written question framed by a place («… en Discord», «en WhatsApp …»), whatever the name: the mission reads
    it (``_last_written_mission``) when the application is installed, so the plain limit «no operation reads a chat»
    (``patterns.chat_read_request``) is only for one said with no place («qué me escribió mamá»)."""

    folded = effect_intent._strip_request_envelope(fold(text)).strip(" .!?¿¡")
    return any(chats.last_written(clause) is not None for _, clause in _app_frames(folded, longer_names=False))


def _with_place_arrivals(mission: MissionRequest | None, text: str) -> MissionRequest | None:
    """Estabilización, encargo C: a sub-goal that searches, or goes to a game's page, in an application whose data give
    that place an address is also proved by the value born on the window after that place was opened
    (``app_places.arrival_term``), first, so it always fits; its other terms stay for the way by clicks."""

    def placed(item: MissionRequest | MissionStep) -> MissionRequest | MissionStep:
        term = app_places.arrival_term(item.application, item.goal, text)
        return replace(item, success_check=_fit(term, item.success_check)) if term and item.success_check else item

    if mission is None:
        return None
    if mission.steps:
        return replace(mission, steps=tuple(placed(step) for step in mission.steps))
    return placed(mission)


# r15b t-menu-2 «en baxy-prueba-v3 ordená los archivos por tamaño, con el clic derecho en un espacio vacío, Ordenar
# por»: an order said in a folder of the person's («en baxy-prueba-v3», «en la carpeta X de Documentos», «in my
# Downloads folder») and in no application (the decider took a lone click and acted on no window). A name said bare
# is a folder's only when it is no plain word («en stream escribí hola», «en cursos abrí el primero»: words, whatever
# folders this PC holds): a digit, a hyphen, a dot or an underscore in it, or «carpeta»/«folder» said with it.
_KNOWN_SAID = "|".join(sorted(map(re.escape, cu_tipos.KNOWN_FOLDERS), key=len, reverse=True))
_FOLDER_FRAME = re.compile(
    r"^(?:en|in|inside|dentro\s+de)\s+(?:(?:la|el|mi|the|my)\s+)?(?:(?P<kind>carpeta|folder)\s+)?"
    r"(?P<name>[^\s\\/,;:*?\"<>|]+)(?:\s+(?P<after>folder|carpeta))?"
    rf"(?:\s+(?:de|del|en|in|of|inside)\s+(?:(?:mis|my|la|el|the)\s+)?(?P<known>{_KNOWN_SAID}))?"
    r"\s*[,:]?\s+(?P<rest>\S.*)$"
)
# Ronda 21 (pasada r18, t-drag-1 «arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3»): the same
# folder said as the tail of the order, after a comma; without the comma («descargá el instalador en Descargas») the
# folder is the order's own object, never its place.
_FOLDER_TAIL = re.compile(
    r"^(?P<rest>\S.*?)\s*,\s*(?:en|in|inside|dentro\s+de)\s+(?:(?:la|el|mi|the|my)\s+)?(?:(?P<kind>carpeta|folder)\s+)?"
    r"(?P<name>[^\s\\/,;:*?\"<>|]+)(?:\s+(?P<after>folder|carpeta))?"
    rf"(?:\s+(?:de|del|en|in|of|inside)\s+(?:(?:mis|my|la|el|the)\s+)?(?P<known>{_KNOWN_SAID}))?$"
)
_FOLDER_NAME_SIGN = re.compile(r"[0-9._-]")
_PLACE_SAID_IN_THE_ORDER = re.compile(r"(?:^|\s)(?:en|in|inside|dentro\s+de)\s")


def _in_named_folder(folded: str, text: str, catalog: effect_intent.ApplicationCatalogIndex) -> MissionRequest | None:
    """An order said in a folder of the person's and in no application: read as said in the application that shows
    folders (``folder_application`` in data/app_aliases.v1.json), going first to the folder — its absolute path when
    it is the one folder of that name under the known folders (or the known folder itself), else its name as said
    (two folders of one name are not guessed between: the window may already show the one meant). None when the place
    is an application or no such folder, or the rest is no doing the readers read. The folder may also be said as the
    order's tail after a comma («<orden>, en <carpeta>»: ``_FOLDER_TAIL``), with the same guarantees."""

    found = _FOLDER_FRAME.match(folded.strip(" .!")) or _FOLDER_TAIL.match(folded.strip(" .!"))
    if found is not None and found.re is _FOLDER_TAIL and _PLACE_SAID_IN_THE_ORDER.search(found.group("rest")):
        # «guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3» (t-file-1): an order that says
        # a place of its own is read by its own reader; the tail is the place only of an order that says none.
        return None
    if found is None or _catalog_key(found.group("name"), catalog) is not None:
        return None
    said_as_folder = found.group("kind") or found.group("after") or found.group("known")
    if not said_as_folder and found.group("name") not in cu_tipos.KNOWN_FOLDERS and not _FOLDER_NAME_SIGN.search(
        found.group("name")
    ):
        return None
    if found.re is _FOLDER_TAIL and not said_as_folder and not _FOLDER_NAME_SIGN.search(found.group("name")):
        # Revisión 2 de la ronda 21 (regresión): a known folder said bare as the tail («pon música relajante, en
        # Música», «descargá el instalador, en Descargas», «crea un archivo notas.txt, en Escritorio») is where the typed
        # operation puts or looks for its thing, never a window to work in; the tail is a folder of the person's only
        # said as one («en la carpeta X») or by a name no plain word carries («baxy-prueba-v3»).
        return None
    key = next(
        (key for key in (_catalog_key(name, catalog) for name in app_alias_words("folder_application")) if key), None,
    )
    if key is None:
        return None

    def read(place: str) -> MissionRequest | None:
        said = f"en {_display_name(key, catalog)}, anda a {place} y {_restore(found.group('rest'), text)}"
        mission = _read_mission(fold(said), said, catalog)
        # The folder alone is no mission: the rest must be read as doing there.
        return mission if mission is not None and len(mission.steps) > 1 else None

    named = read(_restore(found.group("name"), text))
    if named is None:
        # No doing read there: the disk is not searched («en serio, …»).
        return None
    from ..known_folders import located_folders

    known = found.group("known")
    folders, told = located_folders(found.group("name"), cu_tipos.KNOWN_FOLDERS[known] if known else None)
    if not folders:
        return None
    pathed = read(folders[0]) if told and len(folders) == 1 else None
    # A path too long for the going reader is gone to by its name.
    return pathed if pathed is not None and not pathed.steps[0].free else named


_BARE_PLACE = re.compile(r"^(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+&-]{1,40})$")


def _bare_place(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    """«en seguridad de windows» and nothing more: the installed application named precisely, as its display name."""

    found = _BARE_PLACE.match(folded.strip(" ,;:.!?¿¡"))
    key = _named_precisely(found.group("app"), catalog) if found is not None else None
    return _display_name(key, catalog) if key is not None else None


def _looking_in(application: str, question: str) -> MissionRequest:
    """v3 ronda 5 (lectura M3/M5, diseño 4): a question about an application is a mission of reading: the application
    in front (opened if it is not) and the question answered from the last view (``QUESTION_MARK``)."""

    goal = f"abrir {application}".encode("utf-8")[:400].decode("utf-8", "ignore")
    tail = (QUESTION_MARK + question).encode("utf-8")[:100].decode("utf-8", "ignore")
    return MissionRequest(application, goal + tail, f"title:{application}|process:{application}", looks_only=True)


def _question_in_place(
    folded: str, text: str, catalog: effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """«en seguridad de windows decime cuándo fue el último examen de virus» (v3-61, no comma before the question):
    the whole clause said inside an installed application named at the head is a question about it."""

    found = _APP_FRAME_FRONT.match(folded)
    head = _head_application(found, catalog) if found is not None else None
    if head is None:
        return None
    key, count = head
    asked = _QUESTION_ALONE.match(" ".join(found.group("clause").split()[count:]).strip(" ,;:"))  # type: ignore[union-attr]
    if asked is None:
        return None
    return _looking_in(_display_name(key, catalog), _restore(asked.group("question").strip(" .!?"), text))


def _head_application(found: re.Match[str], catalog: effect_intent.ApplicationCatalogIndex) -> tuple[str, int] | None:
    """The catalog key an application frame at the head names precisely («en seguridad de windows …»: the frame's
    word and up to three more of its clause) and how many words of the clause belong to the name."""

    words = found.group("clause").split()
    for count in range(min(len(words) - 1, 3), -1, -1):
        key = _named_precisely(" ".join((found.group("app"), *words[:count])), catalog)
        if key is not None:
            return key, count
    return None


def ordered_in_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """v3 ronda 5 (lectura M2/M3, diseño 3): the installed application an order is said to be done in
    (``place_application``) when what is said there is an order the engine may try (``engine_can_try``): a clause a
    reader reads or one headed by a doing verb (``_free_order``: «en Paint draw una línea…», «abre el mapa de
    caracteres y copia el símbolo del euro»). None for an application only opened («abrí Spotify»: app.open's), for
    talk or a remark that names one («en Spotify me encanta esta canción»), and for a question."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None or not text:
        return None
    place = place_application(text, catalog)
    if place is None or not engine_can_try(text, catalog):
        return None
    folded = effect_intent._strip_request_envelope(fold(" ".join(str(text).split()))).strip(" .!?")
    framed = framed_clause(text, catalog)
    pieces = [framed] if framed else []
    for segment in _without_remarks(_segments(folded, catalog)):
        segment = segment.strip(" ,;:")
        if _BARE_OPEN.match(segment) is not None:
            continue
        pieces.append(_LEADING_SEQUENCER.sub("", re.sub(r"^(?:y|e|and)\s+", "", segment), count=1))
    return place if any(
        piece and (_free_order(piece) or read_clause(piece) is not None) for piece in pieces
    ) else None


# Corrección ronda 5: what makes a question that names no application one about what the application in front shows:
# a thing there («hay», «aparece», «sale», «dice», «figura»), a set it lists asked by its members with a plural verb
# («cuáles tienen…», «cuántos usan…»; never «cuáles son», a copula asks about anything), a deictic («esto», «ahí»,
# «acá», «ese botón») or the view itself («la pantalla», «la lista»). «esta»/«estas» fold to «está»/«estás» («¿cómo
# estás?»), so they are none.
_POINTS_AT_THE_VIEW = re.compile(
    r"\b(?:hay|habia|aparece|aparecen|sale|salen|dice|dicen|figura|figuran|muestra|muestran|"
    r"esto|eso|este|estos|ese|esa|esos|esas|ahi|aca|aqui|alli|alla|pantalla|ventana|lista|listado|"
    r"there|here|this|these|those|shown|listed|says|screen|window|list)\b"
    r"|\b(?:cuales|cuantos|cuantas)\s+\w+[ae]n\b|\bwhich\s+(?:ones|of\s+them)\b"
    rf"|{lexicon.ANAPHORIC_QUESTION}"
)
_ANAPHORIC_QUESTION = re.compile(lexicon.ANAPHORIC_QUESTION)
_ANAPHORIC_HEAD = re.compile(lexicon.ANAPHORIC_QUESTION_HEAD)


def anaphoric_question(text: str) -> bool:
    """Ronda 20b (v3-50 t2): a question that points back at what was just shown — its inside («cuántos archivos tiene
    adentro», «what's inside»), what it holds or what it says («qué dice») — with no place of its own («dentro de
    Documentos», «en la carpeta X» or a path name one). «¿qué hora es?» points at nothing."""

    body = str(text or "")
    body = body[_FOLLOW_UP_LINK.match(body).end():]  # type: ignore[union-attr]
    folded = fold(" ".join(body.split())).strip(" ¿?¡!.,;:")
    found = _ANAPHORIC_QUESTION.search(folded) if folded and len(folded) <= 200 else None
    if found is None:
        return False
    # Revisión 3: nothing but a link, a verb of telling or a pointing word before the question («¿el último correo qué
    # dice?», «the clipboard, what is in it?» name their own subject before it).
    head = _ANAPHORIC_HEAD.search(folded, 0, found.end())
    lead = folded[: min(found.start(), head.start()) if head is not None else found.start()]
    if any(word not in lexicon.ANAPHORIC_LEAD_WORDS for word in re.findall(r"\w+", lead)):
        return False
    if re.search(r"[\\/]|\b(?:carpeta|folder|directorio|directory)\b", folded):
        return False
    asks = "?" in body or "¿" in body
    return asks or _ASKED_HEAD.match(folded) is not None or _QUESTION_ALONE.match(folded) is not None


def level_amount_unsaid(
    text: str, application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Corrección ronda 5 (owner rule 2026-09: a relative volume or brightness change without a quantity asks how much,
    never a default step): whether a clause of the order, said inside an application or not, is such a change
    («en Spotify subí el volumen», «en Spotify subí el volumen y pasá a la siguiente»; not «… subí el volumen un 10»)."""

    from . import levels

    catalog = effect_intent.build_application_catalog_index(application_names)
    folded = effect_intent._strip_request_envelope(fold(" ".join(str(text or "").split()))).strip(" .!?")
    if not folded or len(folded) > 512:
        return False
    pieces: list[str] = []
    for segment in _segments(folded, catalog):
        pieces.append(segment)
        pieces.extend(clause for _, clause in _app_frames(segment, longer_names=False))
    for piece in pieces:
        level = levels.read(piece)
        if level is not None and level.direction is not None and level.amount is None and level.target is None:
            return True
    return False


def change_amount_unsaid(text: str) -> bool:
    """Ronda 20 P3 (contracase of v3-11 t3): a change said only by its direction («subele el zoom», «bajá el tamaño de
    la letra»), of any value and not only the volume or brightness ``level_amount_unsaid`` reads, with no amount, no
    number and no extreme said. «subele el zoom a 150» says its amount; the owner rule asks the other one how much."""

    from . import levels

    if levels.direction_of(text) is None:
        return False
    cleaned = levels._clean(text)
    return re.search(rf"\b(?:\d+|{levels._NUMBER}|{levels._EXTREME})\b", cleaned) is None


def application_question(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    conversation: str | None = None,
    *,
    english: bool = False,
) -> str | None:
    """v3 ronda 5 (lectura M3/M5, diseño 4; v3-61 «en seguridad de windows decime cuándo fue el último examen de
    virus», v3-22 t3 «¿cuáles tienen impacto alto?» after the Task Manager was opened): a question about an application
    — the one framing it, else ``conversation`` (``conversation_application``) when the question names none — as the
    one-turn order «en <app>, decime <pregunta>», with the person's words, read by the mission reader as a look and
    an answer. None for no question, for a question that names another application, or when the reader does not read
    it so."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None or not text or len(text) > 300:
        return None
    said = " ".join(str(text).split())
    folded = fold(said)
    framed = framed_clause(said, catalog)
    if framed is not None:
        found = _APP_FRAME_FRONT.match(effect_intent._strip_request_envelope(folded).strip())
        head = _head_application(found, catalog) if found is not None else None
        key = head[0] if head is not None else None
        application = _display_name(key, catalog) if key is not None else None
        body = " ".join(said.split()[-len(framed.split()):])
    elif conversation and not any(
        not _inside_a_path(folded, found.start(), found.end())
        for found in catalog.occurrence_pattern.finditer(folded)
    ):
        application = conversation
        body = said[_FOLLOW_UP_LINK.match(said).end():]  # type: ignore[union-attr]
        if _POINTS_AT_THE_VIEW.search(fold(body)) is None:
            # Corrección ronda 5: after «abrí Spotify», «¿cuál es la capital de Francia?», «¿cómo estás?» or «¿cuál es
            # mi contraseña?» ask nothing about what Spotify shows; only a question that points at it («¿cuáles
            # tienen impacto alto?», «¿cuántos procesos hay?») is a look at the application.
            return None
    else:
        return None
    if not application:
        return None
    body = body.strip(" ¿?¡!.,;:")
    asks = "?" in said or "¿" in said
    if not body:
        return None
    if _QUESTION_ALONE.match(fold(body)) is None:
        if not (asks or _ASKED_HEAD.match(fold(body))):
            return None
        body = ("tell me " if english else "decime ") + body
    request = f"{'in' if english else 'en'} {application}, {body}"
    read = mission_request(request, catalog)
    if read is None or read.application != application or QUESTION_MARK not in read.goal:
        return None
    return request


# «en el explorador de archivos, entrá a Descargas …», «en Paint, agarrá el lápiz»: the comma after the application
# that frames the whole request is no joiner of clauses.
_FRAME_COMMA = re.compile(r"^(?P<frame>(?:en|in|on|dentro\s+de)\s+(?:(?:la|el|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?))\s*[,;:]\s+")


# v3 r3a lectura L2: «windows terminal: open settings», «task scheduler: open library > …», «windows security, go to
# firewall …»: an application named at the head, then a colon or a comma, frames the request as «en X, …» does.
_HEAD_FRAME = re.compile(r"^(?P<app>[a-z0-9][a-z0-9 .+&-]{1,40}?)\s*[:,]\s+(?P<rest>\S.*)$")
# What follows a head that turns it down («no.», «nah,», «mejor …», «instead …») or makes it the object of the order
# («ciérralo», «minimizala», «close it»): that head is no place where the rest happens.
_HEAD_SET_ASIDE = re.compile(
    r"(?:no|nah|nope)\s*[,;:.!]|(?:mejor|better|rather|instead|actually|en\s+vez|en\s+lugar)(?![a-z0-9])"
    r"|[a-z]{3,}[aei](?:lo|la|los|las)(?![a-z0-9])|[a-z]+\s+(?:it|them)(?![a-z0-9])"
)


def _head_frame(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    """The request said as «en <app>, …» when it opens with an installed application named precisely (its catalog
    name, an alias, or two or more of its own words), never a name for the assistant («baxy, …») or a loose word
    («Notas: comprar pan» where no application is called «Notas»)."""

    head = _HEAD_FRAME.match(folded)
    if head is None or re.fullmatch(_ASSISTANT_NAME, head.group("app")):
        return folded
    if _HEAD_SET_ASIDE.match(head.group("rest")) is not None:
        # Erratas r9 (revisión 2): «Edge, no. Abre chrome …», «word, mejor abre excel …», «Steam, ciérralo y abre
        # Discord»: an application the person turns down, or names as what the order acts on, frames nothing.
        return folded
    if _named_precisely(head.group("app"), catalog, loose=True) is None:
        return folded
    return f"en {head.group('app')}, {head.group('rest')}"


def _named_precisely(
    candidate: str, catalog: effect_intent.ApplicationCatalogIndex, *, loose: bool = False
) -> str | None:
    key = effect_intent._application_name_key(candidate.strip(" ,.;:!?"))
    resolved = effect_intent._catalog_alias_key(key, catalog.keys)
    if resolved is not None:
        return resolved
    for aliases, names in _EXTRA_ALIASES:
        if key in aliases:
            return next((name for name in names if name in catalog.keys), None)
    if len(_content_words(_said_name_words(key))) < 2:
        return None
    return _catalog_key_by_words(key, catalog, loose=loose)


def framed_clause(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """The order said inside an installed application named precisely at the head («en el Visor de eventos filtra …»,
    «Terminal: open settings»), folded, or None when no application frames the request."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None or not text or len(text) > 2048:
        return None
    folded = _without_open_relative(effect_intent._strip_request_envelope(fold(text)).strip(), catalog)
    headed = _head_frame(folded, catalog)
    found = _APP_FRAME_FRONT.match(headed)
    if found is None:
        return None
    # A near spelling only for the name the head frame already took whole; «en …» is a place frame.
    loose = headed != folded
    words = found.group("clause").split()
    application = found.group("app")
    # The longest name the catalog knows («en el visor de eventos filtra …»: «visor de eventos», not «visor»).
    for count in range(min(len(words) - 1, 3), -1, -1):
        name = " ".join((application, *words[:count]))
        if _named_precisely(name, catalog, loose=loose) is not None:
            clause = " ".join(words[count:]).strip(" ,;:")
            return clause or None
    return None


def _read_mission(folded: str, text: str, catalog: effect_intent.ApplicationCatalogIndex) -> MissionRequest | None:
    headed = _head_frame(folded, catalog)
    # The head frame took its name whole («powerpint: …»), so a near spelling of it is still that name.
    loose_head, folded = headed != folded, headed
    framed = _FRAME_COMMA.match(folded)
    if framed is not None and _catalog_key(framed.group("app"), catalog, loose=loose_head) is not None:
        folded = framed.group("frame") + " " + folded[framed.end():]
    folded = _going_to_application_opens_it(folded, catalog)
    chained = _chained_request(folded, catalog, text)
    if chained is not None and re.search(_BROWSER_CATEGORY_PLACE, folded) is None and any(
        link.application == BROWSER_CATEGORY and not link.goal.startswith(_TAB_GOAL) for link in chained.steps
    ):
        # r29, review 2 («escribí hola y andá a la pestaña insertar» as a first message typed «hola» in the person's
        # browser): the browser a tab clause takes when nobody says where is lent to no other clause. A chain whose
        # other clauses have no application but that one is a chain with no application: not read (the decider takes
        # it, as every chain with none), and the tab is not read alone out of it either.
        return None
    if chained is not None:
        steps = tuple(
            replace(
                step, goal=_restore(step.goal, text) if step.free else _as_said(_field_as_said(step.goal, text), text),
                success_check=_check_as_said(_field_check_as_said(step, text), text),
            )
            for step in chained.steps
        )
        joined = "; luego ".join(step.goal for step in steps).encode("utf-8")[:500].decode("utf-8", "ignore")
        return replace(chained, steps=steps, goal=joined if steps else chained.goal)
    for application, clause in _app_frames(folded):
        key = _catalog_key(application, catalog, loose=loose_head or _opened_whole(folded, application))
        if key is None:
            continue
        clause = clause.strip(" ,;:")
        doing = _without_remarks(_segments(clause, catalog))
        if len(doing) == 1 and doing[0] != clause and _segments(clause, catalog)[0] == doing[0]:
            # «seleccioná calc.exe, nada más»: the remark after the clause is no clause of its own. A prohibition
            # stays with the one checked reading, which never does anything but what it reads.
            clause = doing[0]
        if len(doing) > 1 or not doing:
            # Several clauses the chain could not read: one of them is no doing it knows, so none is read alone.
            continue
        # «abre Steam y decime la hora»: the second clause must be doing inside
        # the app; a catalog read elsewhere is not a mission.
        read = read_clause(clause)
        if read is None:
            continue
        goal, check = read
        # A field's value as said, the way the chain restores it («escribí BaxyPrueba en el buscador»).
        return MissionRequest(
            _display_name(key, catalog), _as_said(_field_as_said(goal, text), text), _check_as_said(check, text), clause,
        )
    # A tab named with no browser, or with the category alone («en el navegador»): the person's default browser
    # (a named browser above wins).
    tab = _bare_tab(folded)
    if tab is not None:
        goal, check = tab
        return MissionRequest(BROWSER_CATEGORY, goal, _check_as_said(check, text))
    return None


def _going_to_application_opens_it(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> str:
    """«go to Settings, then Bluetooth & devices», «andá a Configuración y después a Sistema»: the first clause goes
    to an application named whole, before any other clause, so it opens it («abrí Configuración, …»; measured
    2026-10-07: the request went unread and the plan's app.open «Settings» was ambiguous). A single clause stays as
    said (going to an application alone is no mission)."""

    segments = _segments(folded)
    if len(segments) < 2:
        return folded
    went = _NAVIGATE_CLAUSE.match(segments[0])
    if went is None or _catalog_key(went.group("target"), catalog) is None:
        return folded
    # The next clauses as the chain read them («then Bluetooth & devices» → «ve a bluetooth & devices»: the verb
    # said once, for both).
    return ", ".join((f"abri {went.group('target')}", *segments[1:]))


_NAMED_PLACE = re.compile(
    r"(?<![a-z0-9])(?:en|in|on|dentro\s+de|abri|abre|abrime|abra|abrir|open|launch)\s+(?:(?:la|el|the)\s+)?"
    r"(?P<words>[a-z0-9][a-z0-9 .+-]{0,60})"
)


def free_form_arguments(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    prior_requests: Iterable[str] = (),
    *,
    similar: Callable[[str], str | None] | None = None,
) -> dict[str, object] | None:
    """The decider chose the engine for a request the reader does not read: the goal is the person's own words, as
    said, and the application where it happens (``mission_destination``: the one the request frames, else the
    conversation's, else one it mentions). With none, no application: the mission then acts on no window it neither
    opened nor had resolved for it — no key, no text, no click, no scroll (``NoApplicationActs`` in the shell:
    the window in front is the person's) — and learns no procedure. Unless the person points at that window
    themselves («en esta ventana …», «in the active window …»; ``names_the_window_in_front``) and frames no
    application: then ``frontWindow`` says the window in front is the destination. No check: the loop's model says
    done with evidence on screen. A save of what the screen shows (``saved_on_screen_check``) in an application carries
    its file's check (the file written at the path said, ``file:``); with no application it never reaches the engine
    (estabilización L: the turn asks which window, ``semantic.limits.asks_which_window``)."""

    goal = " ".join(str(text or "").split()).strip(" .!?¡¿")
    if not goal or len(goal.encode("utf-8")) > 512:
        return None
    # Every way into the engine with the person's own words (the decider's choice, an unserved order) keeps out an
    # undoing or paying goal, the same rule as the mission reader (safety review 2026-10-07), and a declared limit the
    # engine has no act for (estabilización L: dragging or drawing).
    if _orders_undoing_or_paying(fold(goal)) or asks_to_drag(goal):
        return None
    arguments: dict[str, object] = {"goal": goal}
    if names_the_window_in_front(goal):
        framed = said_application(goal, application_names, similar=similar)
        if framed is None or not framed.framed:
            # Integración ronda 5 (seguridad): the person's own window, named by the person, is the destination; not
            # the conversation's application nor one only mentioned.
            arguments["frontWindow"] = True
            return arguments
    application = mission_destination(goal, application_names, prior_requests, similar=similar)
    saved = saved_on_screen_check(goal)
    if application is not None:
        arguments["application"] = application
    if application is None:
        # Ronda 21, destino por contenido (t-menu-4, t-form-4, t-drag-2): with no application, what the request names of
        # the window where it happens (a menu, a dialog, a panel by its name; a selection): the shell binds the one
        # window that shows it, or asks.
        arguments.update(referent_cues(goal))
    if saved is not None:
        # Review of lectura-ruta (finding 5): the dialog's own folder could take the file; only the file written at
        # the path said proves the save (the model's citation of a title names the file, never its folder).
        arguments["successCheck"] = saved
    return arguments


def referent_cues(text: str) -> dict[str, object]:
    """Ronda 21, destino por contenido: what a request that names no application says of the window where it happens,
    as the mission's arguments carry it — ``referentLabels``, the names of a menu, a dialog, a panel or a tab it names
    («desde el menú Imagen > Girar» → imagen, girar; «desde el cuadro de diálogo de Fuente» → fuente; «en el panel de
    miniaturas» → miniaturas), with a quoted name said beside them («la diapositiva «Tres»»); ``referentSelection``,
    a selection of the window's content («el texto seleccionado»). Words inside a dictated text or a path are none of
    them. A quoted name alone («hacé clic en «Aceptar»») is no referent: it names no window. Empty when none."""

    folded = fold(" ".join(str(text or "").split()))
    if not folded:
        return {}
    outside = "".join(
        character if not _inside_said_text(folded, index) and not _inside_a_path(folded, index, index + 1) else " "
        for index, character in enumerate(folded)
    )
    cues: dict[str, object] = {}
    named = cu_tipos.referent_names_by_container(outside, lambda name: _said_as_verb(name, text))
    # Ronda 24 (pasada r23 t-drag-2, t-form-4): a window is the destination by what the request's structure names,
    # never by a word of content. A menu, a panel or a tab (``referentLabels``) makes a window fit; a dialog
    # (``referentDialogs``) only adds when it is already open, since one still closed is seen nowhere; a quoted name said
    # beside them (``referentItems``: the slide «Tres») is content, adding to a window that fits and never making one fit.
    labels = [name for name, dialog in named if not dialog]
    dialogs = [name for name, dialog in named if dialog]
    selection = cu_tipos.REFERENT_SELECTION.search(outside) is not None
    if named:
        items: list[str] = []
        for quoted in cu_tipos.REFERENT_QUOTED.finditer(folded):
            name = " ".join(quoted.group("name").split()).strip(" .,;:")
            if name and name not in labels and name not in dialogs and name not in items:
                items.append(name)
        for key, names in (("referentDialogs", dialogs), ("referentItems", items), ("referentLabels", labels)):
            kept = [name for name in names if len(name.encode("utf-8")) <= 64][:8]
            if kept:
                cues[key] = kept
    if selection:
        cues["referentSelection"] = True
    return cues


def _said_as_verb(name: str, text: str) -> bool:
    """Revisión 3 de r21 (B2): the folded word read after «menú», «panel», «pestaña»… is the order that starts there,
    not the name of what it names («en el diálogo escribí hola», «en el panel seleccioná todo»): a conjugated form of a
    verb the readers know as an order's head, or a voseo imperative as the person wrote it (its last vowel stressed).
    An infinitive is a command's own name in the windows («Insertar», «Revisar», «Girar») and stays a name."""

    if not name or " " in name or name.endswith("r"):
        return False
    if name in cu_tipos.ORDER_HEADS or _head_is(name, _COVERAGE_ACTION_HEAD):
        return True
    return any(
        word[-1] in "áéí" and fold(word) == name
        for word in re.findall(r"[^\W\d_]+", str(text or "").lower())
    )


# Integración ronda 5 (seguridad): the person points at the window in front themselves: «en esta ventana», «en la
# ventana activa / actual / de delante / en primer plano», «in this window», «in the active / current window», «in the
# window in front». «en la ventana» alone is no such point («en la ventana de Spotify»).
_THE_WINDOW_IN_FRONT = re.compile(
    r"(?<![a-z0-9])(?:en|in|on)\s+(?:"
    r"(?:esta|this)\s+(?:ventana|window)"
    r"|(?:la|the)\s+(?:ventana\s+(?:activa|actual|de\s+delante|de\s+adelante|en\s+primer\s+plano)"
    r"|(?:active|current|front|foreground)\s+window|window\s+in\s+front)"
    r")(?![a-z0-9])"
)


# What a save points at on the screen: «esto», «eso», «this», «este dibujo», «this drawing»; never a pronoun («lo», «it»)
# nor an article («la receta», «el texto»), which take their antecedent from the conversation.
_POINTS_AT_THE_SCREEN = re.compile(r"(?<![a-z])(?:esto|eso|this|(?:este|esta|ese|esa)\s+[a-z]+)(?![a-z])")


def saved_on_screen_check(text: str) -> str | None:
    """Lectura-ruta (r9 t-file-1 «guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3»), as the
    review of the branch narrowed it (finding 1): the whole request saves what the screen shows under a file name, at
    a path the dialog reader resolves (``_file_reads``: a known folder, a new file, its extension said), its object a
    word that points at the screen (``_POINTS_AT_THE_SCREEN``), and no text of the person's to write («guardá "hola"
    como x.txt» says one). Then it is the window's own Save As, and the check that proves it is the file written there
    (``file:{path}&title:{stem}``). None for anything else: «guardalo como poema.txt», «guardá la receta como …» (the
    conversation's antecedent), «… y mandalo a Ana» (another clause), a folder no reader knows."""

    folded = fold(" ".join(str(text or "").split())).strip(" .!?¡¿")
    if not folded or len(folded) > 300 or re.search(r"[\"'«»“”:]", folded):
        return None
    found = cu_tipos.SAVE_AS.match(folded)
    if found is None or not _POINTS_AT_THE_SCREEN.search(folded[: found.start("name")]):
        return None
    reads = _file_reads(folded)
    if not reads or reads[0][0] != cu_tipos.SAVE_AS_OPENER:
        return None
    check = reads[-1][1]
    return check if check and check.startswith("file:") else None


def saves_what_is_shown(text: str) -> bool:
    """Whether the request saves what the screen shows through the window's own Save As (``saved_on_screen_check``),
    never a new file written with the request as its text (filesystem.write.text)."""

    return saved_on_screen_check(text) is not None


def names_the_window_in_front(text: str) -> bool:
    """Whether the person says the order happens in the window in front (``_THE_WINDOW_IN_FRONT``), outside a text
    they dictate («escribí "en esta ventana"» names none)."""

    folded = fold(" ".join(str(text or "").split()))
    return any(not _inside_said_text(folded, found.start()) for found in _THE_WINDOW_IN_FRONT.finditer(folded))


# v3 ronda 3 (v3-15, v3-17: «…en Documentos\baxy-prueba-v3…» named the BAXY application): a name glued to a path or
# file name by a separator is part of that path, never the application said.
_PATH_GLUE = frozenset("\\/-_.")


def _inside_a_path(folded: str, start: int, end: int) -> bool:
    before = folded[start - 1] if start > 0 else ""
    after = folded[end] if end < len(folded) else ""
    # A sentence's full stop after the name is no glue: only a separator followed by more of the path is.
    glued_after = after in _PATH_GLUE and end + 1 < len(folded) and not folded[end + 1].isspace()
    return (before != "" and before in _PATH_GLUE) or glued_after


def _named_place_key(
    folded: str, catalog: effect_intent.ApplicationCatalogIndex, *, head_only: bool = False,
) -> str | None:
    """The catalog key of the application a place frame says («en Fotos», «abre PowerPoint con…»): the longest of the
    first four words after the frame that the catalog resolves; a name inside a path is not one. ``head_only``: only
    the frame the text starts with."""

    frames = _NAMED_PLACE.finditer(folded) if not head_only else filter(None, (_NAMED_PLACE.match(folded),))
    for found in frames:
        start = found.start("words")
        words = found.group("words").split()
        key = next(
            (
                resolved
                for count in range(min(len(words), 4), 0, -1)
                if not _inside_a_path(folded, start, start + len(" ".join(words[:count])))
                and (resolved := _catalog_key(" ".join(words[:count]), catalog)) is not None
            ),
            None,
        )
        if key is not None:
            return key
    return None


def place_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """v3 ronda 3 (lectura L1): the installed application an order is said to happen in — the mission reader's, else
    the one a place frame names («en Fotos …», «abrí OneNote, …», «abre PowerPoint con …»). An application only
    mentioned («recordame escribirle por Discord») is not the place; a name inside a path is not one either."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None:
        return None
    mission = mission_request(text, catalog)
    if mission is not None and mission.application:
        return mission.application
    for clause in _place_heads(text, catalog):
        # Only the head of a clause is its place: «recordame mañana abrir Spotify» opens nothing now. The slot is read
        # by the one resolver (v3 destino: exact name, typing slip, distinctive word; never quoted or in a path).
        head = _SAID_APPLICATION_FRAME.match(clause)
        if head is None or _inside_said_text(clause, head.start("words")):
            continue
        resolved = _slot_key(
            clause, head.start("words"), head.group("words").split(), catalog, frame=head.group("frame"),
        )
        if resolved is not None:
            return _display_name(resolved[0], catalog)
    # Pasada r15b2 (v3-35): «crea una nota rápida nueva» is said in Notas rápidas by the thing it makes.
    return application_said_as_object(text, catalog)


# ----------------------------------------------------------------- el destino de la misión (v3 destino, r5a M4/M5)

# Where an order says it happens or what it opens: «en Fotos …», «abrí OneNote …», «… con el Bloc de notas». An open
# verb's slot is the application or nothing (``_OPEN_VERB``).
_SAID_APPLICATION_FRAME = re.compile(
    r"(?<![a-z0-9])(?P<frame>en|in|on|dentro\s+de|con|with|using|usando|abri|abre|abrime|abra|abrir|open|launch)\s+"
    # The slot is a lookahead: a frame inside another's slot («abre la imagen … en fotos») is found too.
    r"(?=(?:(?:el|la|los|las|the|this|that|este|esta|mi|my)\s+)?(?P<words>[a-z0-9][a-z0-9 .+\\/_-]{0,60}))"
)
_OPEN_VERB = frozenset({"abri", "abre", "abrime", "abra", "abrir", "open", "launch"})
_SLOT_WORDS = 4
_SLOT_ENDS = frozenset({"y", "e", "and", "luego", "despues", "then", "que", "that", "para", "to", "porque"})


@dataclass(frozen=True)
class SaidApplication:
    """The installed application a request names, the words it was said with (folded) and whether a frame said it
    as the place or the thing opened (``framed``) or the request only mentions it."""

    name: str
    said: str
    framed: bool
    # Where the frame's slot starts in the folded request (-1 for a mention).
    at: int = -1
    # The frame that said it («abre», «en», «con»…; empty for a mention), how its slot named it («name», «part»,
    # «slip», «word» or «similar»: ``_slot_key``) and whether the name was the whole slot.
    frame: str = ""
    how: str = ""
    whole: bool = False


# The frames whose slot is a place where something happens: there one distinctive word names an application only as
# the complement of a thing («en el correo de outlook»), never alone («en la consola» is no console's manual).
_PLACE_FRAMES = frozenset({"en", "in", "dentro de"})
_OF_WORDS = frozenset({"de", "del", "of"})


def _distinctive_key(
    words: list[str], catalog: effect_intent.ApplicationCatalogIndex, *, complement_only: bool = False,
) -> str | None:
    """The one catalog name a single word of the slot belongs to («correo de outlook» → «Outlook (classic)»): a word
    of four letters or more, no function or ordinary word, no part of a path or a file name, that is a word of exactly
    one name that is no companion (a help, a manual, a readme or docs is never what a word of it names). With
    ``complement_only``, only a word said as the complement «<cosa> de <palabra>»."""

    common, companion = _common_words(), _companion_words()
    for index, token in enumerate(words):
        if complement_only and (index == 0 or words[index - 1] not in _OF_WORDS):
            continue
        if any(glue in token for glue in _PATH_GLUE):
            continue
        word = _singular(token.strip(_SAID_PUNCTUATION))
        if len(word) < 4 or word in _NAME_FUNCTION_WORDS or word in common or word.isdigit():
            continue
        owners = [
            entry for entry, name in _catalog_words(catalog.keys)
            if word in name and not companion.intersection(_name_words(entry))
        ]
        if len(owners) == 1:
            return owners[0]
    return None


def _slot_key(
    folded: str, start: int, words: list[str], catalog: effect_intent.ApplicationCatalogIndex, *, frame: str = "en",
) -> tuple[str, str, str, bool] | None:
    """The (catalog key, words said, how, whole) a frame's slot names: its exact name or alias, then a typing slip of
    it, then one distinctive word. The longest run of its first words wins at each stage; a run glued to a path is
    none. A typing slip of one word only in an open verb's slot: after «en» an ordinary word a letter away from a name
    is still that word («en stream escribí hola»). A distinctive word in an open verb's slot, or as the complement of a
    thing after a place frame («en el correo de outlook»); never after «on», «con», «with» or «using» («turn on
    bluetooth», «con el teclado escribí hola» name no application).

    ``how``: «name» (a catalog name or another name of it, said whole), «part» (a run of a name's words: its start,
    its end, two of its words), «slip» (a typing slip of a name or of another name of it) or «word» (one distinctive
    word). ``whole``: the run is every word of the slot up to the next clause («abre el uninstall de deskflow» names
    «Uninstall» by its first word only)."""

    opened = frame in _OPEN_VERB

    # The slot ends where the next clause begins («abre el zorblax y copiá …»: «copiá» is no word of the name).
    cut = next((index for index, word in enumerate(words) if word in _SLOT_ENDS), len(words))
    words = words[:cut]
    ended = next((index + 1 for index, word in enumerate(words) if word.endswith(".")), len(words))
    slot = " ".join(words[:ended]).strip(_SAID_PUNCTUATION)
    runs = []
    for count in range(min(len(words), _SLOT_WORDS), 0, -1):
        run = " ".join(words[:count]).strip(_SAID_PUNCTUATION)
        if run and not _inside_a_path(folded, start, start + len(" ".join(words[:count]))):
            runs.append(run)
    for loose in (False, True):
        for run in runs:
            if loose and not opened and len(_content_words(_said_name_words(run))) < 2:
                continue
            key = _catalog_key(run, catalog, loose=loose)
            if key is not None:
                how = "slip" if loose else "name" if _named_whole(run, catalog) == key else "part"
                return key, run, how, run == slot
    if not opened and " ".join(frame.split()) not in _PLACE_FRAMES:
        return None
    key = _distinctive_key(words[:_SLOT_WORDS], catalog, complement_only=not opened)
    return (key, " ".join(words[:_SLOT_WORDS]), "word", False) if key is not None else None


def _named_whole(candidate: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    """The catalog key a name said whole reaches: the catalog name itself or another name of it, never a run of its
    words («ayuda» is no «Ayuda WinRAR», «panel de nvidia» no «NVIDIA GeForce NOW»)."""

    key = effect_intent._application_name_key(candidate.strip(_SAID_PUNCTUATION))
    resolved = effect_intent._catalog_alias_key(key, catalog.keys)
    if resolved is not None:
        return resolved
    for aliases, names in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES):
        if key in aliases or any(_said_name_words(alias) == _said_name_words(key) for alias in aliases):
            return next((name for name in names if name in catalog.keys), None)
    return key if key in catalog.keys else None


def said_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    *,
    similar: Callable[[str], str | None] | None = None,
) -> SaidApplication | None:
    """v3 destino (r5a diseño 1): the one resolver of the application a request names, for every reader. Framed names
    first, in the order said («abre el explorador … con el Bloc de notas» → the Explorer): the exact name or an alias,
    a typing slip («adminsitrador de tareas»), one distinctive word of a single catalog name («el correo de outlook»),
    and then another language (``similar``: the mind's encoder or a translation, validated against the catalog). A
    name inside quotes or a dictated text («una nota que dice «baxy prueba»») or inside a path («Documentos\\baxy-…»)
    is none. With no framed name, a name only mentioned (its whole name or a run of two or more of its words, «una
    nota rápida nueva»), unless an open verb's slot named something the catalog does not know («abre system
    information, … de onenote»: what it opens is not OneNote). The assistant's own name is the destination only when
    a frame says it; a mention of it never is."""

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    if catalog.occurrence_pattern is None or not text:
        return None
    # Erratas r9: a request that opens with the application and a colon or a comma («windows terminal: open
    # settings») frames it there, before any place its order goes to («settings» is the Terminal's own page).
    folded = _head_frame(fold(" ".join(str(text).split())), catalog)
    unknown_opened: list[bool] = []
    first = next(_framed_applications(folded, catalog, similar, unknown_opened), None)
    if first is not None:
        return first
    return None if unknown_opened else _mentioned_application(folded, catalog)


def opened_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """Erratas r9 (revisión 1 y 4): the installed application the request's first open verb opens, as ``app.open``
    may launch it: its slot up to the next clause is that application's name or another name of it, said whole or
    with a typing slip («abre el adminsitrador de tareas y ordena …», «open the task manger and …»), or a run of its
    words the conservative opener reads alone as it («abre teams y …»). Never a place said
    before it («copiá lo que dice en word y abrí el bloc de notas» opens the Bloc de notas), never one word of a name
    («open reset this pc», «abre el panel de nvidia», «open windows update»: a function of Windows or an application
    not installed is not the one a word of it reaches) nor a name's first words with more said after them («abre el
    uninstall de deskflow»). None when the first open verb names no such application: BAXY asks which."""

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    if catalog.occurrence_pattern is None or not text:
        return None
    folded = fold(" ".join(str(text).split()))
    for found in _SAID_APPLICATION_FRAME.finditer(folded):
        if found.group("frame") not in _OPEN_VERB:
            continue
        if _inside_said_text(folded, found.start("words")) or _inside_said_text(folded, found.start()):
            continue
        resolved = _slot_key(folded, found.start("words"), found.group("words").split(), catalog, frame="abre")
        if resolved is None or resolved[2] not in {"name", "slip", "part"} or not resolved[3]:
            return None
        name = _display_name(resolved[0], catalog)
        if resolved[2] == "part":
            # A run of a name's words («teams» for Microsoft Teams) only as the conservative opener reads the slot
            # alone: the same application, or none.
            from .patterns import resolve_application_catalog_app_id

            return name if resolve_application_catalog_app_id(f"abre {resolved[1]}", catalog) == name else None
        return name
    return None


def _framed_applications(
    folded: str,
    catalog: effect_intent.ApplicationCatalogIndex,
    similar: Callable[[str], str | None] | None,
    unknown_opened: list[bool],
) -> Iterator[SaidApplication]:
    """Every application a frame of the request says, in the order said (lazily: the encoder is asked only as far as
    the reader goes). An open verb's slot that names nothing the catalog knows is noted in ``unknown_opened``."""

    for found in _SAID_APPLICATION_FRAME.finditer(folded):
        start = found.start("words")
        if _inside_said_text(folded, start) or _inside_said_text(folded, found.start()):
            continue
        words = found.group("words").split()
        resolved = _slot_key(folded, start, words, catalog, frame=found.group("frame"))
        if resolved is not None:
            # The assistant's own window only when the person frames it by name («abrí BAXY.»; contract «Seguridad
            # v2»: never BAXY when the person did not name it).
            yield SaidApplication(
                _display_name(resolved[0], catalog), resolved[1], True, start,
                " ".join(found.group("frame").split()), resolved[2], resolved[3],
            )
            continue
        if similar is not None:
            phrase = " ".join(words[:_SLOT_WORDS]).strip(_SAID_PUNCTUATION)
            other = similar(phrase) if phrase else None
            key = _catalog_key(other, catalog) if other else None
            if key is not None and not re.fullmatch(_ASSISTANT_NAME, key):
                yield SaidApplication(
                    _display_name(key, catalog), phrase, True, start, " ".join(found.group("frame").split()), "similar",
                )
                continue
        if found.group("frame") in _OPEN_VERB:
            unknown_opened.append(True)


def _mentioned_application(folded: str, catalog: effect_intent.ApplicationCatalogIndex) -> SaidApplication | None:
    for found in catalog.occurrence_pattern.finditer(folded):  # type: ignore[union-attr]
        if _inside_a_path(folded, found.start(), found.end()) or _inside_said_text(folded, found.start()):
            continue
        key = found.group("target").casefold()
        if key in catalog.keys and not re.fullmatch(_ASSISTANT_NAME, key):
            return SaidApplication(_display_name(key, catalog), key, False)
    tokens = list(re.finditer(r"\S+", folded))
    for index in range(len(tokens)):
        if _inside_said_text(folded, tokens[index].start()):
            continue
        for count in range(min(_SLOT_WORDS, len(tokens) - index), 1, -1):
            run = folded[tokens[index].start():tokens[index + count - 1].end()]
            if any(glue in run for glue in "\\/_") or _inside_a_path(folded, tokens[index].start(), tokens[index + count - 1].end()):
                continue
            words = run.strip(_SAID_PUNCTUATION)
            if len(_content_words(_said_name_words(words))) < 2 or _said_name_words(words)[0] in _NAME_FUNCTION_WORDS:
                continue
            key = _catalog_key_by_words(words, catalog)
            if key is not None and not re.fullmatch(_ASSISTANT_NAME, key):
                return SaidApplication(_display_name(key, catalog), words, False)
    return None


def resolve_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    *,
    similar: Callable[[str], str | None] | None = None,
) -> str | None:
    """The display name of the application a request names (``said_application``), or None."""

    said = said_application(text, application_names, similar=similar)
    return said.name if said is not None else None


def _inherits_application(said: str) -> bool:
    """A turn that kept the conversation in its application without naming one: a bare yes or no to BAXY's
    question, or an order of doing (no question, no talk) — «ponle: pagar la luz», «split the pane vertical»."""

    from .dialogue import is_assent, is_refusal

    if is_assent(said) or is_refusal(said):
        return True
    folded = fold(said)
    body = folded[_FOLLOW_UP_LINK.match(folded).end():].strip(" ,;:.!")  # type: ignore[union-attr]
    body = _ACKNOWLEDGEMENT.sub("", body, count=1)
    # Uso real v3 t2 (c04 «ahi ponle la escala en 125», «no espera se ve muy grande, regresala como estaba»): a
    # deictic of the place or the start of a correction said before the order is no part of it.
    body = cu_tipos.FOLLOW_UP_PREAMBLE.sub("", body, count=1)
    dictated = _dictated_text_opens(body)
    if dictated is not None:
        # «ponle: pagar la luz», «escribe ahí: ¿vienes?»: a writing verb that dictates a text is an order of doing;
        # the text itself (the resolver's same rule, ``_inside_said_text``) is no question and no talk.
        if dictated.start() == 0:
            return True
        body = body[:dictated.start()].strip(" ,;:")
        said = body
    if not body or "?" in said or "¿" in said:
        return False
    if read_clause(body) is not None or _free_order(body):
        return True
    # «se ve muy grande, regresala como estaba», «te dije la escala no el brillo, regresa la escala a 100»: what the
    # person says of the screen or of the last turn before the order, said with no question, keeps the order's place.
    clauses = [clause.strip() for clause in re.split(r"[,;]", body)]
    return any(clause and (read_clause(clause) is not None or _free_order(clause)) for clause in clauses[1:])


def conversation_application(
    prior_requests: Iterable[str],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    available_operations: Iterable[str] = (),
    *,
    similar: Callable[[str], str | None] | None = None,
) -> tuple[str, str] | None:
    """v3 destino (r5a diseño 2, M5): the application the conversation is in and the request that named it — the one
    the person's last request that acted named, passed back over orders that inherited it and bare yes/no answers
    (``follow_up_in_application``'s cut, without asking the step for a check). Any other message in between ends it
    («cuál es la capital de Francia» does nothing on the screen). ``prior_requests``: the person's earlier messages,
    oldest first, without the current one. The one reader of it (integración ronda 5: the coverage gate, the
    follow-up and the mission's destination share it). With ``available_operations``, an order a typed operation
    serves on its own («poné música de Queen») ends it too, and a request that opened two applications at once
    («abrí la calculadora y el bloc de notas») names none: which one is the decider's to ask."""

    from .patterns import MISSION_SUBSUMES, resolve_explicit_effects

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    operations = tuple(available_operations)
    for said in reversed(tuple(prior_requests)):
        read = resolve_explicit_effects(said, operations, catalog) if operations else None
        typed = set(read.operations) if read is not None else set()
        if read is not None and list(read.operations).count("app.open") > 1:
            return None
        named = _last_said_application(said, catalog, similar)
        if named is not None:
            return named.name, said
        if tab_names_no_application(said, catalog):
            # r29: a tab said with no browser was a step in the conversation's application; it does not end it.
            continue
        if not _inherits_application(said) or typed - MISSION_SUBSUMES:
            return None
    return None


def order_saying_its_value(text: str) -> bool:
    """Ronda 20 P3, revisión 1 (hallazgo 2): whether the message is an order of its own that says the value it sets —
    headed by a doing verb once its spoken link is off («ahora subele el zoom a 150»: ``_free_order``), and with a
    figure, an extreme or a quoted literal said. A question the turn asked about such an order asked for what the
    person already gave. False for talk or noise («ok», «gracias, eso es todo», «asdf qwer») and for an order whose
    value is missing («cambiale el nombre» → «¿Qué nombre le pongo?»: the engine would invent it)."""

    from . import levels

    folded = fold(" ".join(str(text or "").split())).strip(" .!")
    order = _FOLLOW_UP_LINK.sub("", folded, count=1)
    if not order or not _free_order(order):
        return False
    if any(opening in str(text) and closing in str(text) for opening, closing in _PAIRED_QUOTES.items()):
        return True
    cleaned = levels._clean(text)
    return re.search(rf"\b(?:\d+|{levels._NUMBER}|{levels._EXTREME})\b", cleaned) is not None


def _by_referent(arguments: dict[str, object]) -> bool:
    """Ronda 21, destino por contenido: the arguments of a request with no application carry what it names of the
    window where it happens (``referent_cues``): the shell looks for that window.

    Revision 1 of r21 (B2): a selection alone («poné en negrita el texto seleccionado», «copiá el texto seleccionado»)
    names no window: it keeps its typed route, as before the round; it only narrows the search when the request names
    a menu, a dialog or a panel as well. Ronda 24: a dialog said (``referentDialogs``) still names the window where it
    happens, as before the round."""

    return arguments.get("application") is None and bool(
        arguments.get("referentLabels") or arguments.get("referentDialogs")
    )


@functools.cache
def _application_mentions() -> frozenset[tuple[str, ...]]:
    """Every name or kind of an application a person says, installed or not, as folded words: the other names of
    ``aliases`` and ``mission_aliases`` (spoken and catalog) and ``application_mentions`` (data/app_aliases.v1.json)."""

    names: set[str] = set()
    for spoken, catalog_names in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES):
        names.update(spoken)
        names.update(catalog_names)
    names.update(app_alias_words("application_mentions"))
    return frozenset(words for words in (tuple(re.findall(r"[a-z0-9]+", fold(name))) for name in names) if words)


def mentions_an_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Ronda 20 P3, revisión 3 (hallazgos 1 y 2): whether the message mentions any application, framed or not,
    installed or not — what ``said_application`` reads, a run of words the catalog reader reaches (``_catalog_key``:
    «chrome» for Google Chrome, «edge»), or a name or kind of an application a person says (``_application_mentions``:
    «del navegador», «la letra del word», «la ventana de spotify»). Words inside quotes, a dictated text or a path are
    no mention. An order that mentions one is never framed in the conversation's application: it names its own."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if said_application(text, catalog) is not None:
        return True
    folded = fold(" ".join(str(text or "").split()))
    tokens = [
        found for found in re.finditer(r"[a-z0-9]+", folded)
        if not _inside_said_text(folded, found.start()) and not _inside_a_path(folded, found.start(), found.end())
    ]
    words = tuple(found.group(0) for found in tokens)
    mentions = _application_mentions()
    for size in range(1, 6):
        for start in range(len(words) - size + 1):
            run = words[start:start + size]
            if run in mentions:
                return True
            if run[0] in _NAME_FUNCTION_WORDS or run[-1] in _NAME_FUNCTION_WORDS or len(" ".join(run)) < 3:
                continue
            key = _catalog_key(" ".join(run), catalog) if catalog.occurrence_pattern is not None else None
            if key is not None and not re.fullmatch(_ASSISTANT_NAME, key):
                return True
    return False


def engine_destination_said(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    prior_requests: Iterable[str] = (),
) -> bool:
    """Ronda 20 P3, revisión 3 (hallazgo 2): whether the place the engine would act in (``free_form_arguments`` with
    the conversation) is one the message itself gives — the window in front it names, or the application it says,
    read from its own words alone. The conversation's application is never the place of an order handed over from a
    typed route: «recargá la página de chrome», «cerrá la ventana de spotify», «cerrá esta pestaña» after a turn in
    the Bloc de notas would act in the person's Bloc de notas. Those keep their typed route."""

    arguments = free_form_arguments(text, application_names, tuple(prior_requests))
    if arguments is None:
        return False
    if arguments.get("frontWindow") is True:
        return True
    if _by_referent(arguments):
        # Ronda 21, destino por contenido: no application at all (neither said nor the conversation's), and the message
        # names what the window shows (a menu, a dialog, a panel, a selection): the place is the window that shows it,
        # which the shell looks for and asks about when it is not one.
        return True
    application = arguments.get("application")
    if application is None:
        return False
    own = free_form_arguments(text, application_names, ())
    return own is not None and own.get("application") == application


def place_said_for_its_pointer(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Ronda 20 P3, revisión 1 (hallazgo 3): whether the message itself says the place its «ahí» points to — the
    application it frames or opens («en el bloc de notas escribí ahí hola», «open notepad and type hello there»), or
    a clause of its own before the one that points back («abrí la carpeta descargas y dejá el archivo ahí»). Then the
    «ahí» is no pointer to the turn before."""

    from .dialogue import only_place_filler, points_back_to_a_place

    if place_application(text, application_names) is not None:
        return True
    said = said_application(text, application_names)
    if said is not None and said.framed:
        return True
    catalog = effect_intent.build_application_catalog_index(application_names)
    folded = fold(" ".join(str(text or "").split())).strip(" .!?")
    segments = _without_remarks(_segments(folded, catalog)) if folded else []
    return (
        len(segments) > 1
        and not points_back_to_a_place(segments[0])
        # Revisión 2 (hallazgo 2): «déjalo ahí y escribí hola ahí» — a clause of filler alone says no place.
        and not only_place_filler(segments[0])
        and any(points_back_to_a_place(segment) for segment in segments[1:])
    )


def framed_in_application(application: str, said: str) -> str:
    """Ronda 20 P3 (v3-11 t3 «ahora subele el zoom a 150»): an order said without its application, framed in the one
    the conversation is in («en <app>, <order>»), the frame every mission reader reads first."""

    return f"en {application}, {' '.join(str(said or '').split())}"


def restatement_for_the_engine(
    restated: str,
    said: str,
    prior_requests: Iterable[str],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """Uso real v3 t2 (c04 «ahi ponle la escala en 125»: the decider restated «En Configuración, pon la escala…» and
    the engine got the bare words): the decider's restatement of an order the person said without its application,
    as the engine's goal, when it frames the application the person's requests named last. None when the person's
    words name one themselves (theirs stay), the restatement frames none, or it frames one nobody said or one the
    conversation already left (a restatement never brings in an application of its own: «abre spotify» → «abre
    configuración…» → «ahí ponle 125» is never Spotify)."""

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    restated = " ".join(str(restated or "").split())
    if not restated or catalog.occurrence_pattern is None or said_application(said, catalog) is not None:
        return None
    named = said_application(restated, catalog)
    if named is None or not named.framed:
        return None
    last = next(
        (found.name for text in reversed(tuple(prior_requests))
         if (found := _last_said_application(text, catalog, None)) is not None),
        None,
    )
    return restated if named.name == last else None


def follow_up_for_the_engine(
    said: str,
    prior_requests: Iterable[str],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    *,
    english: bool = False,
    mention_is_a_place: bool = False,
) -> str | None:
    """Uso real v3 ronda 19 (t2-c04 T4 «te dije la escala no el brillo, regresa la escala a 100»: the engine got the
    bare words, reproach included): a follow-up said without its application, as the engine's goal «en <app>, <orden>»
    framed in the application the conversation is in (``conversation_application``: the last one it opened or used,
    never one it already left), without what only corrects the last turn — the contrast «te dije X no Y» (the order
    after it is the goal, ``dialogue.contrastive_correction``) or a preamble («no, …», «ahí …», «espera …»). None when
    the person's words name an application themselves, when the conversation is in none, or when nothing is left to
    do. ``mention_is_a_place`` (ronda 21, v2-s13 «y ahora andá a configuración» after a mission in Discord): a name
    the words only mention, with no frame of their own («andá a configuración», not «en configuración» nor «abrí
    configuración»), is a place inside the conversation's application; the caller passes it only when the decider
    itself kept that application."""

    from .dialogue import calls_off, contrastive_correction, is_assent, is_refusal

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    words = " ".join(str(said or "").split())
    if not words or catalog.occurrence_pattern is None:
        return None
    named = said_application(words, catalog)
    if named is not None and (named.framed or not mention_is_a_place):
        return None
    if is_assent(words) or is_refusal(words) or calls_off(words):
        # Revisión r19 (seguridad): «no, nada», «no, déjalo», «no, para», «no, leave it», «sí, dale» answer BAXY or
        # call off what it was doing; none is an order in the application (the engine would «pause» on «para»).
        # Revisión adversarial 2: nor any call-off with how things stay («no, déjalo así», «no, cancela eso», «no,
        # déjalo como está»), which the cut of «no, » below would hand the engine as an order.
        return None
    if not _inherits_application(words):
        # «¿cuál es la capital de Francia?» after «abrí Spotify» is no order in Spotify (a question, a remark alone).
        return None
    conversation = conversation_application(prior_requests, catalog)
    if conversation is None:
        return None
    body = words
    contrast = contrastive_correction(words)
    if contrast is not None and contrast.rest.strip(" ,;.!?"):
        body = contrast.rest
    else:
        start = _FOLLOW_UP_LINK.match(fold(body))
        cut = start.end() if start is not None else 0
        preamble = cu_tipos.FOLLOW_UP_PREAMBLE.match(fold(body)[cut:])
        cut += preamble.end() if preamble is not None else 0
        # fold keeps the length of the person's words, so the cut is theirs too.
        body = body[cut:] if len(fold(words)) == len(words) else fold(body)[cut:]
    body = body.strip(" ,;:.!?¡¿")
    if not body or is_assent(body) or is_refusal(body) or calls_off(body):
        # «espera, olvidalo», «perdón, cancelá»: what is left after the preamble only calls off or agrees.
        return None
    return f"{'in' if english else 'en'} {conversation[0]}, {body}"


def made_there_before(
    prior_requests: Iterable[str],
    operations: Iterable[str],
    available_operations: Iterable[str],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Ronda 21, revisión 1 (hallazgo 1: «abre discord» → «anotá: llamar a mamá» framed the note in Discord, and the
    engine would have typed it in the person's chat). Whether the conversation's application
    (``conversation_application``) is where the person's own request that named it made the very thing the chosen
    operations make in BAXY's store (``semantic.decider.made_in_an_application``): that request said the application
    as its place (``place_application``) and its typed reading is one of those operations — the order the coverage
    gate handed to the engine there («crea una nota rapida nueva» → Notas rápidas, v3-35). Only then does a follow-up
    that makes the same thing belong to that application. False after a request that only opened the application
    («abre discord», «abre notas rapidas»), that did anything else in it («en Discord abrí el servidor de pruebas»), or
    that made another kind of thing there."""

    from .decider import made_in_an_application
    from .patterns import resolve_explicit_effects

    made = {operation for operation in operations if made_in_an_application((operation,))}
    if not made:
        return False
    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    conversation = conversation_application(prior_requests, catalog)
    if conversation is None:
        return False
    name, said = conversation
    if place_application(said, catalog) != name:
        return False
    read = resolve_explicit_effects(said, tuple(available_operations), catalog)
    return read is not None and bool(set(read.operations) & made)


def made_beside_an_application(
    said: str,
    prior_requests: Iterable[str],
    operation: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    store: str,
) -> str | None:
    """Ronda 21, revisión 2 (g; pasada r18 v3-35: «abre notas rapidas» → «ponle: pagar la luz» became note.create in
    BAXY's own store, told «He creado la nota» with the person looking at the application they opened). The application
    a thing made in ``store`` was asked beside, when the operation makes what applications make
    (``semantic.decider.made_in_an_application``): the place the message says (``place_application``), else, when it
    mentions no application, the conversation's (``conversation_application``). None for any other operation, with no
    such application, or when that application is the store itself («en BAXY anotá…»)."""

    from .decider import made_in_an_application

    if not made_in_an_application((operation,)):
        return None
    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    named = place_application(said, catalog)
    if named is None and not mentions_an_application(said, catalog):
        conversation = conversation_application(prior_requests, catalog)
        named = conversation[0] if conversation is not None else None
    if named is None or fold(named) == fold(store):
        return None
    return named


def _last_said_application(
    text: str, catalog: effect_intent.ApplicationCatalogIndex, similar: Callable[[str], str | None] | None,
) -> SaidApplication | None:
    """The application a request ended in: its last framed one («abre la calculadora y en el bloc de notas escribí el
    resultado» ends in the Bloc de notas, as ``follow_up_in_application``'s chain ends in its last step), else the
    one ``said_application`` reads."""

    if catalog.occurrence_pattern is None or not text:
        return None
    folded = fold(" ".join(str(text).split()))
    unknown_opened: list[bool] = []
    framed = list(_framed_applications(folded, catalog, similar, unknown_opened))
    if framed:
        return framed[-1]
    return None if unknown_opened else _mentioned_application(folded, catalog)


def mission_destination(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    prior_requests: Iterable[str] = (),
    *,
    similar: Callable[[str], str | None] | None = None,
) -> str | None:
    """v3 destino (r5a diseño 2): where a mission happens. The application the request frames; else the one the
    conversation is in (``conversation_application``); else the one the request only mentions. A name the request
    says that was a place of the conversation's previous order («abre edge y andá a la configuración» → «buscá cookies
    ahí en la configuración») is that place, so the conversation's application stays. None: no application is known
    (the mission then acts on no window it did not open or have resolved, unless the person named the one in front)."""

    catalog = (
        application_names if isinstance(application_names, effect_intent.ApplicationCatalogIndex)
        else effect_intent.build_application_catalog_index(application_names)
    )
    if catalog.occurrence_pattern is None:
        return None
    named = said_application(text, catalog, similar=similar)
    conversation = conversation_application(prior_requests, catalog, similar=similar)
    if named is not None and named.framed:
        if (
            conversation is not None
            and conversation[0] != named.name
            and _said_as_place_before(named.said, conversation[1], catalog, similar)
        ):
            return conversation[0]
        return named.name
    if conversation is not None:
        return conversation[0]
    return named.name if named is not None else None


# A verb of going somewhere inside the window and its «a»: «andá a la configuración», «go to settings».
_GO_TO_PLACE = (
    r"(?<![a-z0-9])(?:anda|andate|ve|ir|vaya|vamos|entra|entrar|navega|pasa|go|navigate|head|switch)\s+"
    r"(?:a|al|en|hacia|to|into)\s+(?:(?:la|el|los|las|the)\s+)?"
)


def _said_as_place_before(
    said: str,
    earlier: str,
    catalog: effect_intent.ApplicationCatalogIndex,
    similar: Callable[[str], str | None] | None = None,
) -> bool:
    """The name was said in the earlier order as a place to go to inside its application («andá a la configuración»,
    «go to settings»): after a verb of going, and not read there as an application's own frame («abre paint y pegá la
    imagen en fotos»: Fotos was an application, never a place of Paint). A thing searched or typed is no place."""

    name = " ".join(said.split())
    if not name:
        return False
    folded = fold(" ".join(str(earlier).split()))
    framed = {found.at for found in _framed_applications(folded, catalog, similar, [])}
    return any(
        found.start("name") not in framed
        for found in re.finditer(rf"{_GO_TO_PLACE}(?P<name>{re.escape(name)})(?![a-z0-9])", folded)
    )


def _typing_slip(said: str, form: str) -> bool:
    """A run of words said within a typing slip of a name's words (integración ronda 3: the same word-by-word rule as
    the mission reader's near spelling, ``_near_word``): word for word, every one near, two edits at most in all."""

    said_words, form_words = said.split(), form.split()
    if len(said_words) != len(form_words):
        return False
    edits = [_near_word(word, name) for word, name in zip(said_words, form_words)]
    return all(edit is not None for edit in edits) and sum(edits) <= 2  # type: ignore[arg-type]


def place_misspelled(
    text: str,
    restated: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> str | None:
    """v3-04 «abre powerpint, …»: the person's words with the place they said at the head of a clause and misspelled
    written as the application the decider's restatement names, when what follows the frame is within a typing slip
    of that name (``_typing_slip``: word for word, two edits at most); None otherwise. A time or a thing
    said after «en» («en 10 minutos», «en un rato», «en la primera diapo») is no misspelled place, whatever the
    restatement adds of the conversation's application (D21)."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    if catalog.occurrence_pattern is None or not restated:
        return None
    application = place_application(restated, catalog)
    if application is None:
        return None
    names = {fold(application), *(key for name, key in catalog.entries if name == application)}
    # Erratas r9: its other names too («open the event viewer and …» is the Visor de eventos said whole, never «event»
    # misspelled for «eventos»). An alias that is one ordinary or short word («consola», «calc») is no name said whole
    # (revisión 7): it would hide the misspelled place.
    common = _common_words()
    said_whole = {*names, *(alias for aliases, keys in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES)
                            if names.intersection(keys) for alias in aliases
                            if len(alias) >= 5 and not (len(alias.split()) == 1 and _singular(alias) in common))}
    folded_text = fold(text)
    if any(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", folded_text) for name in said_whole if name):
        # A place the person also says whole («abre la foto paisaje.jpg … en fotos») is not misspelled elsewhere.
        return None
    # A name of several words is also said by its last ones («Microsoft PowerPoint» → «powerpoint»).
    forms = {
        " ".join(words[start:])
        for words in (name.split() for name in names)
        for start in range(len(words))
        if len(" ".join(words[start:])) >= 4
    }
    for clause in _place_heads(text, catalog):
        words = _PLACE_ARTICLE.sub("", _PLACE_HEAD.sub("", clause, count=1), count=1).split()
        for form in sorted(forms, key=len, reverse=True):
            count = len(form.split())
            said = " ".join(word.strip(_SAID_PUNCTUATION) for word in words[:count])
            if len(words) < count or not said or any(character.isdigit() for character in said):
                continue
            if said != form and _typing_slip(said, form):
                return _written_as(text, said, application)
    return None


# The head of a clause that says where it happens: «en Fotos …», «abrí OneNote …», «open Photos …». One rule for
# the clause that has a place (``_HEAD_PLACE``) and for the frame taken off it (``_PLACE_HEAD``); «_HEAD_FRAME» is the
# other reader's «<app>: …» (integración ronda 3: the two branches had given both the same name, and the later one
# silently replaced the earlier).
_PLACE_HEAD_WORDS = r"(?:en|in|on|dentro\s+de|abri|abre|abrime|abra|abrir|open|launch)"
_PLACE_HEAD = re.compile(rf"^{_PLACE_HEAD_WORDS}\s+")
_HEAD_PLACE = re.compile(rf"^{_PLACE_HEAD_WORDS}\s+\S")
_PLACE_ARTICLE = re.compile(r"^(?:el|la|los|las|the)\s+")
_SAID_PUNCTUATION = " ,;:.!?¡¿'\"«»"
# «en OBS Studio …», «in Photos …», «dentro de Steam …»: a clause headed by where it happens, not by opening it.
_LOCATIVE_HEAD = re.compile(r"^(?:en|in|on|dentro\s+de)\s+")


def _written_as(text: str, said: str, application: str) -> str | None:
    """The person's words with the run of words ``said`` (folded) written as ``application``; None when not found."""

    tokens = " ".join(str(text or "").split()).split(" ")
    wanted = said.split()
    for start in range(len(tokens) - len(wanted) + 1):
        run = tokens[start:start + len(wanted)]
        if [fold(token).strip(_SAID_PUNCTUATION) for token in run] == wanted:
            last = run[-1]
            trailing = last[len(last.rstrip(_SAID_PUNCTUATION)):]
            return " ".join((*tokens[:start], application + trailing, *tokens[start + len(wanted):]))
    return None


def doing_said_in_place(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """The order is one clause of doing headed by where it happens, an installed application («en OBS Studio silenciá
    el micrófono de la escena», «en notas rápidas anotá…»): whatever serves it is meant inside that application. An
    order that opens one and goes on («abrime Steam porfa y de paso fijate qué hora es») or chains clauses is not, nor
    one with any link a second clause could hang from («en Fotos girá la imagen y decime la hora»: the segments keep
    it whole)."""

    return _in_place_head(text, effect_intent.build_application_catalog_index(application_names)) is not None


def _in_place_head(text: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    """The one clause of an order said in place (``doing_said_in_place``), headed by its place; None for any other."""

    if catalog.occurrence_pattern is None or doing_clauses(text, catalog) != 1:
        return None
    heads = list(_place_heads(text, catalog))
    if (
        len(heads) == 1
        and _LOCATIVE_HEAD.match(heads[0]) is not None
        and _CLAUSE_LINK.search(heads[0]) is None
        and _named_place_key(heads[0], catalog, head_only=True) is not None
    ):
        return heads[0]
    return None


_CLAUSE_LINK = re.compile(r"[,;]|\s(?:y|e|and|luego|despues|then|tambien|also|ademas)\s")


def said_in_place(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> tuple[str | None, str | None] | None:
    """One pass over an order said in place (``doing_said_in_place``; None for any other order): the application that
    heads it and its clause without that place (None when the place was only told apart by
    one distinctive word). Revisión ruta-tipada 6: the coverage gate reads both from here, without reading the order
    again."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    clause = _in_place_head(text, catalog)
    if clause is None:
        # Pasada r15b2 (v3-35): the one clause whose thing made is said by the application's name is said in it too;
        # the clause keeps that name (no place to take away from it).
        made_in = application_said_as_object(text, catalog)
        return (made_in, None) if made_in is not None else None
    head = _SAID_APPLICATION_FRAME.match(clause)
    resolved = (
        _slot_key(clause, head.start("words"), head.group("words").split(), catalog, frame=head.group("frame"))
        if head is not None and not _inside_said_text(clause, head.start("words"))
        else None
    )
    if resolved is None:
        return place_application(text, catalog), None
    place = _display_name(resolved[0], catalog)
    if resolved[2] == "word":
        return place, None
    rest = clause[head.start("words") + len(resolved[1]):].strip(_SAID_PUNCTUATION)
    return place, rest or None


def _place_heads(text: str, catalog: effect_intent.ApplicationCatalogIndex) -> Iterable[str]:
    folded = fold(" ".join(str(text or "").split())).strip(" .!?")
    for segment in _segments(folded, catalog) if folded else ():
        clause = re.sub(r"^(?:(?:y|e|and)\s+)?(?:(?:por\s+favor|please)\s*[,;:]?\s*)?", "", _LEADING_SEQUENCER.sub(
            "", segment.strip(" ,;:"), count=1,
        ))
        if _HEAD_PLACE.match(clause) is not None:
            yield clause



# «en la web …», «on the internet …»: a place of the web is no place inside an application.
_WEB_PLACE = re.compile(r"^(?:en|in|on)\s+(?:(?:la|el|the)\s+)?(?:web|internet|red|linea|online)(?![a-z0-9])")


def read_only_in_a_place(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    available_operations: Iterable[str],
) -> frozenset[str]:
    """Erratas r9 (revisión 3): the operations the typed readers read in a clause of the order, each read alone, only
    where that clause is headed by a place inside the application (v3-26 «… y en Sistema buscame un evento con ID
    6005» → web.search: the search is the Visor de eventos' own). One a clause said apart reads («buscame en la web
    …», «apaga el wifi») is a request of its own and is not here; nor is one no clause reads («bajame el volumen»
    with no amount)."""

    from .patterns import resolve_explicit_effects

    catalog = effect_intent.build_application_catalog_index(application_names)
    folded = fold(" ".join(str(text or "").split())).strip(" .!?")
    if catalog.occurrence_pattern is None or not folded:
        return frozenset()
    operations = tuple(available_operations)
    in_place: set[str] = set()
    apart: set[str] = set()
    for segment in _without_remarks(_segments(folded, catalog)):
        clause = re.sub(r"^(?:(?:y|e|and)\s+)?", "", _LEADING_SEQUENCER.sub("", segment.strip(" ,;:"), count=1))
        read = resolve_explicit_effects(clause, operations, catalog)
        if read is None:
            continue
        placed = (
            _LOCATIVE_HEAD.match(clause) is not None
            and _WEB_PLACE.match(clause) is None
            and not effect_intent._explicit_google_search_query(clause)
        )
        (in_place if placed else apart).update(read.operations)
    return frozenset(in_place - apart)


def doing_clauses(text: str, application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex) -> int:
    """How many clauses of doing an order chains («abrí X, creá una página y ponele título» → 3); a remark («pero no
    la guardes», «nada más») is no clause of its own."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    folded = fold(" ".join(str(text or "").split())).strip(" .!?")
    return len(_without_remarks(_segments(folded, catalog))) if folded else 0


# «y ahora», «and now», «después»: the spoken link of a follow-up to the turn before it, no part of its clause.
_FOLLOW_UP_LINK = re.compile(
    r"^\s*(?:(?:y|e|and)\s+)?(?:(?:ahora|luego|despues|después|entonces|tambien|también|now|then|also)\s+)?"
    r"(?:mismo\s+)?(?:,\s*)?",
    re.IGNORECASE,
)
# A follow-up that keeps only the place of a going said right before, after a link of sequence: «luego a opciones de
# energía», «and then to Settings». Never a clock («luego a las 5»), «a ver», a person («a vos», «a mi mamá», «a él»), a
# pointing word («a eso») nor an end of what is shown («al final de la lista», «to the top»: a scroll, review of
# finales-buscador finding 4). Folded.
_ELLIPTIC_GO = re.compile(
    r"^(?:a|al|hacia|to|into)\s+(?!(?:ver|vos|ti|mi|usted|ustedes|el|ella|ellos|ellas|nosotros|nosotras|"
    r"you|me|him|her|them|us|it|eso|esto|ese|esa|este|esta|that|this)\b)"
    r"(?!(?:(?:la|el|lo|the)\s+)?(?:final|principio|inicio|comienzo|fondo|arriba|abajo|top|bottom|end|beginning|start)\b)"
    r"(?!(?:las?|the)?\s*\d)\S"
)
_SEQUENCE_LINK = re.compile(r"\b(?:luego|despues|después|then|after\s+that)\b", re.IGNORECASE)
_ACKNOWLEDGEMENT = re.compile(rf"^\s*{alternation(lexicon.ACKNOWLEDGEMENTS)}\b\s*[,;.]?\s*", re.IGNORECASE)


def without_spoken_link(text: str) -> str:
    """Revisión 1 de r28 (tanda c27u2 t4-c04 t3 «vale y ahora en configuracion pon el modo oscuro»: the mission reader
    read nothing, the plan was the whole phrase with no check, and the theme pressed and read selected closed nothing):
    the request without the words that only link it to the turn before («vale y ahora», «ok, también», «and now»), so
    the order after them is read as it is alone («en configuracion pon el modo oscuro» → «activar modo oscuro» with
    its check). The text itself when it opens with no such word."""

    body = text[_FOLLOW_UP_LINK.match(text).end():]  # type: ignore[union-attr]
    body = _ACKNOWLEDGEMENT.sub("", body, count=1)
    return body[_FOLLOW_UP_LINK.match(body).end():].strip()  # type: ignore[union-attr]


def _in_application_step(
    text: str,
    available_operations: tuple[str, ...],
    catalog: effect_intent.ApplicationCatalogIndex,
    went_before: bool = False,
) -> str | None:
    """«ahora ponela en modo científica», «and switch it to dark mode», «y ahora andá a configuración»: the follow-up's
    clause (its link dropped, as said) when it reads alone as a checked step inside an application and names none;
    None otherwise. A step the reader reads without a check («subí el volumen» is a bare doing), one a typed operation
    serves on its own (the airplane mode, an application opened) or one that names a site is not one. ``went_before``:
    the person's request right before went to a place, so a place alone after a link of sequence is going there."""

    from .patterns import MISSION_SUBSUMES, resolve_explicit_effects

    link = _FOLLOW_UP_LINK.match(text).end()  # type: ignore[union-attr]
    body = text[link:].strip()
    read = read_clause(body) if body else None
    if (
        read is None and body and went_before
        and _SEQUENCE_LINK.search(text[:link]) is not None and _ELLIPTIC_GO.match(fold(body))
    ):
        # v3-43 r11 «entra a Sistema y seguridad» → «luego a opciones de energía y dime qué plan está activo»: the verb
        # of going said once is not said again; the place alone after the link is going there.
        body = f"{'go' if fold(body).startswith('to ') else 've'} {body}"
        read = read_clause(body)
    if read is None or read[1] is None:
        return None
    folded = fold(body)
    if _ADDRESS.search(folded) is not None or (
        catalog.occurrence_pattern is not None and catalog.occurrence_pattern.search(folded) is not None
    ):
        return None
    typed = resolve_explicit_effects(body, available_operations, catalog)
    operations = set(typed.operations) if typed is not None else set()
    if operations <= MISSION_SUBSUMES - {"app.open"}:
        return body
    # «andá a configuración» read alone as a site searched and opened: with an application in the conversation and
    # no address said, the place is the application's (live v2-s13).
    if operations <= {"web.search", "browser.navigate"} and read[0].startswith("ir a "):
        return body
    return None


def follow_up_in_application(
    text: str,
    prior_requests: Iterable[str],
    available_operations: Iterable[str],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    *,
    english: bool = False,
) -> str | None:
    """Live v2-x12 «abrí la calculadora» → «ahora ponela en modo científica» (failed: the decider closed it as a limit
    and the engine ran the bare words in no application, «no vi ningún control»). A follow-up that names no
    application and reads alone as a checked step inside one happens in the application the conversation is in: the
    one the person's request right before opened or worked in (``prior_requests``, oldest first; earlier steps of the
    same kind and bare yes/no answers to BAXY's own question are passed over back to it). It comes back as the
    one-turn order «en <app>, <step>», read by the same mission reader with the same checks. None when the
    conversation is in no application, when any other message came after it (review r10: «cuál es la capital de
    Francia» in between does nothing on the screen and still ends it), or when the follow-up names an application of
    its own (that one is read as said), unless that name is the place the request before went to
    (``_in_the_place_gone_to``)."""

    operations = tuple(available_operations)
    catalog = effect_intent.build_application_catalog_index(application_names)
    if "mission.computer.use" not in operations or catalog.occurrence_pattern is None:
        return None
    prior = list(prior_requests)
    own = mission_request(text, catalog)
    # r29 (pasada r27 v3-69 «abre el monitor de recursos» → «ahora anda a la pestaña red»: read alone, the tab was the
    # person's browser's, and the mission clicked seven times in their Opera): a tab said with no browser names no
    # application (``tab_names_no_application``), so in a conversation that is in one it is that application's tab,
    # as any other step, and so are the other clauses of its chain («escribí hola y andá a la pestaña insertar»). Said
    # with the browser («… en el navegador», «en Chrome …») or in a conversation in no application, it stays as said.
    tab_alone = tab_names_no_application(text, catalog)
    if own is not None and not tab_alone:
        return _in_the_place_gone_to(own, prior, catalog, operations, english=english, said=text)
    last = prior[-1][_FOLLOW_UP_LINK.match(prior[-1]).end():].strip() if prior else ""  # type: ignore[union-attr]
    went = read_clause(last) if last else None
    step = (
        without_spoken_link(text) if tab_alone
        else _in_application_step(text, operations, catalog, went_before=went is not None and went[0].startswith("ir a "))
    )
    if step is None:
        # Ronda 20b (v3-50 t2 «decime cuántos archivos tiene adentro» after «en 7zip abrí el prueba.zip…», counted by a
        # typed read on the Desktop): a question that points back at what the mission showed (its inside, what it
        # says: ``lexicon.ANAPHORIC_QUESTION``), with no application or place of its own, is a look in that
        # application, «en <app>, <pregunta>», read by the mission reader (``application_question``).
        if not anaphoric_question(text):
            return None
        conversation = conversation_application(prior, catalog, operations)
        return (
            application_question(text, catalog, conversation[0], english=english)
            if conversation is not None else None
        )
    conversation = conversation_application(prior, catalog, operations)
    if conversation is None:
        return None
    application = conversation[0]
    request = f"{'in' if english else 'en'} {application}, {step}"
    restated = mission_request(request, catalog)
    if restated is None:
        return None
    if tab_alone and restated.steps:
        # The chain a tab was said in: every clause of it happens in the conversation's application, or it is not read.
        return request if all(link.application == application for link in restated.steps) else None
    return request if restated.application == application and restated.success_check else None


def tab_names_no_application(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """r29, the one reader of «is this tab the browser's only because nobody said where?»: the message, as said or
    without the words that link it to the turn before (``without_spoken_link``: «now go to the network tab»), reads as
    a mission in the browser category (``BROWSER_CATEGORY``: ``_bare_tab``, or the chain a tab clause was said in,
    whose other clauses ride with it) and says no browser («en el navegador», ``_BROWSER_CATEGORY_PLACE``). Such a tab
    is the browser's only when the conversation is in no application: the follow-up frames it in the conversation's
    (``follow_up_in_application``) and the conversation stays in its application over it
    (``conversation_application``)."""

    folded = fold(str(text or ""))
    if re.search(rf"(?<![a-z0-9]){_TAB_WORD}", folded) is None or re.search(_BROWSER_CATEGORY_PLACE, folded) is not None:
        return False
    unlinked = without_spoken_link(text)
    read = mission_request(text, application_names) or mission_request(unlinked, application_names)
    if read is not None:
        return read.application == BROWSER_CATEGORY or any(link.application == BROWSER_CATEGORY for link in read.steps)
    # Review 2 of r29: the chain a tab was said in has no reading of its own (the tab's browser is lent to no other
    # clause, ``_read_mission``), so it is told by its words: one of its clauses goes to a tab, and no application is
    # said in it.
    catalog = effect_intent.build_application_catalog_index(application_names)
    clauses = _segments(effect_intent._strip_request_envelope(fold(unlinked)).strip(), catalog)
    return (
        len(clauses) > 1 and any(_bare_tab(clause) is not None for clause in clauses)
        and said_application(text, catalog) is None
    )


def _in_the_place_gone_to(
    own: MissionRequest,
    prior: list[str],
    catalog: effect_intent.ApplicationCatalogIndex,
    operations: tuple[str, ...],
    *,
    english: bool,
    said: str = "",
) -> str | None:
    """Pasada r15b v3-58 «abre edge y anda a la configuracion» → «busca cookies ahi en la configuracion»: the second
    request named «configuración», which is also an installed application (the system's settings), and the engine
    searched there. The place the request right before went to inside the conversation's application is that place
    again, not another application that happens to carry its name: the follow-up is the same one-turn order, going
    there and then doing the step («en <app>, <ir allá> y <paso>»). None when the request before went to no place,
    when the application said is not that place, or when the restated order does not stay in the conversation's
    application.

    Ronda 21, revisión 1 (hallazgo 2: after «abre edge y anda a la configuracion», «en configuración de windows busca
    bluetooth» became a search in Edge's settings): the application is that place only as the request before said it.
    Every word the message names it with (``said``: «configuracion de windows») is a word of the clause that went
    there, and a «de/del <algo>» right after the name qualifies it with no owner but the conversation's application
    («en la configuracion de edge»); a name said with more than that is the application the person named."""

    if not prior or own.steps or not own.clause:
        return None
    conversation = conversation_application(prior, catalog, operations)
    before = mission_request(prior[-1], catalog)
    if conversation is None or before is None or before.application != conversation[0]:
        return None
    went = before.steps[-1] if before.steps else before
    if went.application != before.application or not went.goal.startswith("ir a ") or not went.clause:
        return None
    if own.application == before.application or fold(own.application) != fold(went.goal[len("ir a "):]):
        return None
    if said and not _named_as_the_place_gone_to(said, catalog, went.clause, before.application):
        return None
    request = f"{'in' if english else 'en'} {before.application}, {went.clause} {'and' if english else 'y'} {own.clause}"
    restated = mission_request(request, catalog)
    if restated is None or not restated.steps or any(step.application != before.application for step in restated.steps):
        return None
    return request


_QUALIFIER_AFTER_THE_NAME = re.compile(r"^\s+(?:de|del|of)\s+(?:(?:la|el|los|las|mi|mis|the|my)\s+)?([a-z0-9]+)")


def _named_as_the_place_gone_to(
    said: str, catalog: effect_intent.ApplicationCatalogIndex, went_clause: str, conversation: str,
) -> bool:
    """Whether the message names the application only with the words the clause that went to the place said
    (``_in_the_place_gone_to``, revisión 1 hallazgo 2), and qualifies it with nothing but the conversation's own
    application."""

    named = said_application(said, catalog)
    if named is None:
        return False
    went_words = set(re.findall(r"[a-z0-9]+", fold(went_clause)))
    if not set(re.findall(r"[a-z0-9]+", named.said)) <= went_words:
        return False
    folded = fold(" ".join(str(said).split()))
    at = folded.find(named.said, max(named.at, 0))
    qualifier = _QUALIFIER_AFTER_THE_NAME.match(folded[at + len(named.said):]) if at >= 0 else None
    if qualifier is None:
        return True
    owner = qualifier.group(1)
    return owner in went_words or owner in set(re.findall(r"[a-z0-9]+", fold(conversation)))


# The goal of going to a tab by its name, as ``_bare_tab`` and the chain's reader write it.
_TAB_GOAL = "ir a la pestaña "


def _bare_tab(folded: str) -> tuple[str, str] | None:
    bare = re.sub(rf"^{_BROWSER_CATEGORY_PLACE}\s*[,;:]?\s+|\s+{_BROWSER_CATEGORY_PLACE}(?=[\s.!?]*$)", "", folded, count=1)
    for reading in _clause_readings(bare.strip(" ,;:.!?")):
        named = _tab_named(reading)
        if named is not None:
            return f"{_TAB_GOAL}{named}", f"control:{named}:selected|title:{named}"
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


def _starts_clause(segment: str, catalog: effect_intent.ApplicationCatalogIndex | None = None) -> bool:
    segment = segment.strip(" ,;:.!?")
    if not segment:
        return False
    if _BARE_OPEN.match(segment) is not None or _pronoun_family(segment) is not None or read_clause(segment) is not None:
        return True
    if _compound_reads(segment) is not None:
        return True
    return any(
        read_clause(clause) is not None or _compound_reads(clause) is not None
        for _, clause in _clause_frames(segment, catalog)
    )


def _clause_frames(
    segment: str, catalog: effect_intent.ApplicationCatalogIndex | None
) -> Iterable[tuple[str, str]]:
    """The (application, clause) splits of one clause: one-word names always; a name of several words («en el
    Explorador de archivos andá a Descargas») only when the catalog knows it (measured 2026-10-07, y5: the chain
    left «… y después a Imágenes» glued to the first place because «explorador» alone framed nothing)."""

    yield from _app_frames(segment, longer_names=False)
    if catalog is not None:
        for application, clause in _app_frames(segment):
            if len(application.split()) > 1 and _catalog_key(application, catalog) is not None:
                yield application, clause


def _segments(folded: str, catalog: effect_intent.ApplicationCatalogIndex | None = None) -> list[str]:
    """The clauses of doing a request chains, in order; the whole text when it says one."""

    pieces: list[str] = []
    joiners: list[str] = []
    start = 0
    for found in _JOINER.finditer(folded):
        if found.start() == 0 or found.end() >= len(folded):
            continue
        if _inside_quotes(folded, found.start()):
            # «escribí "casa, roja"»: a joiner inside a quoted literal is part of it (v3 punto 2).
            continue
        pieces.append(folded[start:found.start()])
        joiners.append(found.group())
        start = found.end()
    pieces.append(folded[start:])
    if len(pieces) == 1:
        return pieces
    merged = [pieces[0]]
    for joiner, piece in zip(joiners, pieces[1:]):
        if _starts_clause(piece, catalog):
            merged.append(piece)
            continue
        elliptic = _elliptic(piece, joiner, merged[-1], catalog)
        if elliptic is not None:
            merged.append(elliptic)
            continue
        literal_open = _TYPED_LITERAL_TO_END.search(" ".join(merged)) is not None
        if not literal_open and _dictates(merged[-1]) and "," not in joiner and _SEQUENCER.search(joiner) is None:
            # «buscá Pinta y Colorea», «search New York and New Jersey»: inside what is typed or searched, a word that
            # could start an order is part of the text unless a comma or a sequencer parts it.
            literal_open = True
        if not literal_open and (_free_order(piece) or _is_remark(piece) or ">" in piece):
            # v3 punto 2: an order no reader reads («ponelo en negrita», «draw a rectangle»), a remark («nada más»,
            # «pero no lo abras») or a menu route («View > Zoom») is no part of the clause before it.
            merged.append(piece)
            continue
        if (
            not literal_open and "," in joiner and _SEQUENCER.search(joiner) is None
            and _BARE_NAME.match(piece.strip(" ,;:.!?")) and not _ELLIPTIC_PLACE.match(piece)
            and (_BARE_OPEN.match(merged[-1].strip(" ,;:.!?")) is not None or _family(merged[-1], catalog) == "ir a ")
            and _starts_clause(f"ve a {piece}")
        ):
            # «abrí Configuración, Aplicaciones instaladas», «go to Settings, Personalization, Fonts»: a bare name
            # after a comma that follows an opening or a going is the next place.
            merged.append(f"ve a {piece}")
            continue
        if (_VERB_AND_OBJECT.match(piece) or _CLITIC_ORDER.match(piece)) and _family(merged[-1], catalog) is not None:
            # «andá a la biblioteca y dibujá a Batman»: an order the readers do not know is no part of a place's
            # name; kept apart, it leaves the chain unread (the decider's) instead of glued into the place.
            merged.append(piece)
        else:
            merged[-1] += joiner + piece
    return [segment.strip(" ,;") for segment in merged]


def _dictates(segment: str) -> bool:
    """The clause types, searches or notes a text (``cu_tipos.DICTATION`` at its head, or at the head of its clause
    once the application frame is set apart)."""

    segment = segment.strip(" ,;:.!?")
    return any(
        cu_tipos.DICTATION.match(clause.strip(" ,;:")) is not None
        for clause in (segment, *(clause for _, clause in _app_frames(segment)))
    )


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
_BARE_NAME = re.compile(r"^[a-z0-9][a-z0-9.+-]*(?:\s+(?:&\s+)?[a-z0-9][a-z0-9.+-]*){0,2}$")


def _elliptic(
    piece: str, joiner: str, previous: str, catalog: effect_intent.ApplicationCatalogIndex | None = None
) -> str | None:
    """The clause a piece says with the previous clause's verb left out: «andá a la biblioteca y después a general»,
    «elegí el lápiz y después el color rojo», «hacé clic en Insertar y después en Tabla», «go to System, then
    Display». None when the piece is not such an object, or the previous clause is no go-to, choice or click."""

    family = _family(previous, catalog)
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
    elif family == "seleccionar " and _second_chosen_object(piece, joiner):
        # Ronda 22 (r18 t4-c18): «elegí el balde de pintura y el color rojo» chooses two things, the second said with
        # its own article and kind; never «selecciona Sonido y vídeo», one name.
        candidates.append(f"selecciona {piece}")
    elif family == "hacer clic en " and sequenced:
        candidates.append("haz clic en " + re.sub(r"^(?:en|on)\s+", "", piece))
    return next((candidate for candidate in candidates if _starts_clause(candidate)), None)


def _kind_before_its_colour(before: str, goal: str) -> bool:
    """Estabilización G3: «hacer clic en color» right before «seleccionar rojo»: the click names only the kind of the
    colour chosen next (``colours.names_the_colour_kind``), never a control of its own."""

    return (
        before.startswith("hacer clic en ") and names_the_colour_kind(before[len("hacer clic en "):])
        and goal.startswith("seleccionar ") and is_basic_colour(goal[len("seleccionar "):])
    )


def _second_chosen_object(piece: str, joiner: str) -> bool:
    """A piece joined by a coordinator (``lexicon.OBJECT_COORDINATORS``) that is an object of its own: its article, a
    noun of a kind of choice (``lexicon.CHOICE_KIND_NOUNS``) and a name after it («el color rojo», «the colour red»).
    Review 2 of ronda 22: never a kind with a complement after it (``lexicon.KIND_COMPLEMENT_WORDS``: «el color de
    relleno», «el color de la línea», «el color de énfasis»): the complement is no name of its own, and choosing it
    (the fill tool, the Line tool) would pass for the colour asked."""

    if joiner.strip(" ,;") not in lexicon.OBJECT_COORDINATORS:
        return False
    words = piece.split()
    return (
        len(words) >= 3 and _ARTICLE_OBJECT.match(piece) is not None and words[1] in lexicon.CHOICE_KIND_NOUNS
        and words[2] not in lexicon.KIND_COMPLEMENT_WORDS
    )


def _family(segment: str, catalog: effect_intent.ApplicationCatalogIndex | None = None) -> str | None:
    """The goal head of the act a clause says (``ir a ``, ``seleccionar ``, ``hacer clic en ``, ``buscar ``), or
    None."""

    segment = segment.strip(" ,;:.!?")
    reads = (read_clause(segment), *(read_clause(clause) for _, clause in _clause_frames(segment, catalog)))
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
    if cu_tipos.OPEN_ITS_PAGE.match(segment.strip(" ,;:.!?")):
        # «… scroll down to Times New Roman and open its page»: opening what the clause before showed.
        return "open"
    found = _PRONOUN_CLAUSE.match(segment.strip(" ,;:.!?"))
    if found is None:
        return None
    verb = " ".join(
        (found.group("verb") or found.group("english") or found.group("turn") or found.group("bare") or "").split()
    )
    return next((family for family, verbs in _PRONOUN_FAMILIES if verb in verbs), None)


def _pronoun_read(family: str, referent: str) -> tuple[str, str | None] | None:
    if family == "play":
        return f"reproducir {referent}", _playing_check(referent)
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
    r"seleccionar |activar |desactivar |hacer clic en |reproducir |mostrar )(?P<object>.+)$"
)


def _chained_request(
    folded: str, catalog: effect_intent.ApplicationCatalogIndex, said: str = ""
) -> MissionRequest | None:
    """«abre Steam y andá a la biblioteca, y después en Discord andá a general» → one mission whose ``steps`` are
    the sub-goals in order (contract §4.1). The application is carried forward and switches where a clause names
    another one; each sub-goal has its own goal and check (``read_clause``); a clause whose object is a pronoun
    («buscá Hades y abrilo») acts on what the previous clause named. A clause of the v3 task types reads as several
    sub-goals (``_compound_reads``: a menu route, a form, a file dialog); an order no reader reads is a free sub-goal
    (v3 punto 2, A7) while the chain has at least as many checked sub-goals; a remark («nada más») is no sub-goal.
    None for fewer than two sub-goals (today's reading stays), for a clause that is not doing, or with no
    application named at all."""

    segments = _segments(folded, catalog)
    remarks = [segment for segment in segments if _is_remark(segment)]
    segments = [segment for segment in segments if not _is_remark(segment)]
    forbids = any(cu_tipos.PROHIBITION.match(remark.strip(" ,;:.!?")) for remark in remarks)
    # «…, usa el Abrir de Paint» (t-file-4): the person asks for the window's own Open dialog; a file named to open is
    # then opened through it, never handed over by the shell.
    by_dialog = any(cu_tipos.OPEN_DIALOG_MEANS.match(part.strip(" ,;:.!?")) for part in (*remarks, *segments))
    segments = [segment for segment in segments if not cu_tipos.OPEN_DIALOG_MEANS.match(segment.strip(" ,;:.!?"))]
    if not segments or any(effect_intent._is_negative_effect_clause(segment) for segment in segments):
        return None
    steps: list[MissionStep] = []
    current: str | None = None
    opened: str | None = None
    referent: str | None = None
    merged = False
    for segment in segments:
        segment = cu_tipos.MENU_MEANS.sub("", segment.strip(" ,;:.!?"), count=1).strip(" ,;:.!?") if (
            ">" not in segment and cu_tipos.MENU_LIST.search(segment) is None
        ) else segment.strip(" ,;:.!?")
        # «… y solo mostrame los instalados», «and just sort by name»: the order after the adverb (a remark was
        # already set apart above), never dropped as one.
        segment = cu_tipos.ONLY_ADVERB.sub("", segment, count=1)
        bare = _BARE_OPEN.match(segment)
        bare_key = _catalog_key(bare.group("app"), catalog, loose=True) if bare is not None else None
        if bare_key is not None:
            if opened is not None:
                steps.append(_open_step(opened))
            current = opened = _display_name(bare_key, catalog)
            continue
        family = _pronoun_family(segment)
        reads: list[tuple[str, str | None, bool]] | None = None
        application, clause = current, segment
        framed = False
        if family is None:
            for said_application, said_clause in _app_frames(segment):
                key = _catalog_key(said_application, catalog, loose=_opened_whole(segment, said_application))
                if key is None:
                    continue
                said_clause = said_clause.strip(" ,;:")
                found = _segment_reads(said_clause)
                if found is not None:
                    application, clause, reads = _display_name(key, catalog), said_clause, found
                    framed = True
                    break
        if reads is None:
            if family is not None:
                read = _pronoun_read(family, referent) if referent is not None else None
                reads = [(read[0], read[1], False)] if read is not None else None
            else:
                reads = _segment_reads(segment)
        if reads is None and family is None and current is not None:
            reads = _place_then_order(segment, catalog, said)
        menu_at = next((index for index in range(len(steps) - 1, -1, -1) if not steps[index].free), None)
        if (
            reads is None and menu_at is not None and steps[menu_at].goal.startswith(CONTEXT_MENU_GOAL)
            and _BARE_NAME.match(segment)
        ):
            # «… clic derecho en un espacio vacío, Ordenar por»: an entry of the menu just opened, by its name, right
            # after it (before the order it serves).
            entry = MissionStep(
                steps[menu_at].application, f"hacer clic en {segment}",
                _with_alternatives(segment, ("stepDone:input.visible.click:{}",)), segment,
            )
            steps.insert(menu_at + 1, entry)
            continue
        framed_free: tuple[str, str] | None = None
        if reads is None:
            # An order no reader reads: a free sub-goal in the application it names, else the current one.
            framed_free = next(
                (
                    (_display_name(key, catalog), said_clause.strip(" ,;:"))
                    for said_application, said_clause in _app_frames(segment)
                    if (
                        key := _catalog_key(said_application, catalog, loose=_opened_whole(segment, said_application))
                    ) is not None and _free_order(said_clause)
                ),
                None,
            )
            if framed_free is not None:
                application, clause = framed_free
            elif not _free_order(segment):
                return None
            reads = [(clause, None, True)]
        if (
            not framed and framed_free is None and family is None and reads and all(free for _, _, free in reads)
        ):
            # r15b v3-47 «…, copia el nombre del procesador y pégalo en una página nueva de onenote»: a free clause that
            # says an installed application as the place it happens in happens there, never in the one carried from
            # the clause before. A name the clause only mentions («calcula cuánto cuesta spotify», «dibuja el logo de
            # google chrome») is what it is about, never where (revisión destino del pedido).
            placed = _placed_application(segment, catalog)
            if placed is not None:
                application = placed
        if application is None and family is None:
            # «… desde Archivo > Abrir del Bloc de notas», «in this Word document»: the installed application the
            # clause frames as where it happens, never a name inside what is typed or searched.
            application = _framed_application(segment, catalog)
        route = [read for read in reads if read[0].startswith("hacer clic en ")] if _is_route(clause) else []
        if route and steps and steps[-1].free and _same_act(steps[-1].goal, route[-1][0][len("hacer clic en "):]):
            # «Zoom in twice in Notepad using the View menu, View > Zoom > Zoom in»: the route is how the order before
            # is done; its application and its repetitions go with the route.
            said_before = steps.pop()
            application = application or said_before.application
            times = _times(said_before.goal)
            reads = reads * times if len(reads) * times <= MAX_STEPS else reads
        if route and steps and any(_routed_dialog(step) for step in steps):
            # «ábreme lista.txt …, desde Archivo > Abrir»: the dialog is opened by the route said; a file opened that
            # way is then named in the dialog and opened with its button.
            index = next(i for i, step in enumerate(steps) if _routed_dialog(step))
            dialog = steps[index]
            if dialog.goal.startswith(cu_tipos.OPEN_FILE_GOAL):
                reads = [*reads, *_open_dialog_reads(dialog.goal[len(cu_tipos.OPEN_FILE_GOAL):], dialog.success_check)]
            routed = [MissionStep(application or dialog.application, goal, check, clause) for goal, check, _ in reads]
            steps[index:index + 1] = routed
            current = application or current
            continue
        if (
            reads and reads[0][0].startswith(CONTEXT_MENU_GOAL) and _MEANS_LEAD.match(segment)
            and steps and steps[-1].free
        ):
            # «ordená los archivos por tamaño, con el clic derecho en un espacio vacío»: the means goes first.
            later = steps.pop()
            application = application or later.application
            for goal, check, free in reads:
                steps.append(MissionStep(application, goal, check, clause, free))
            steps.append(later)
            current = application
            continue
        if reads and reads[0][0].startswith("desactivar ") and len(reads) == 1:
            # «… a 800 de ancho por 600 de alto y sacale lo de mantener la relación de aspecto»: a box of the same
            # dialog is set before its values and before accepting it.
            first_field = next(
                (i for i in range(len(steps) - 1, -1, -1) if steps[i].goal.startswith(_FIELD_GOAL)
                 and (i == 0 or not steps[i - 1].goal.startswith(_FIELD_GOAL))),
                None,
            )
            if first_field is not None and steps[-1].goal.startswith("hacer clic en ") and all(
                step.goal.startswith((_FIELD_GOAL, "activar ", "hacer clic en ")) for step in steps[first_field:]
            ):
                goal, check, _ = reads[0]
                steps.insert(first_field, MissionStep(steps[first_field].application, goal, check, clause))
                continue
        for goal, check, free in reads:
            if referent is not None and goal.startswith("ir a ") and goal[len("ir a "):] in _GENERIC_PLACE:
                # «buscá a Mamá y abrí el chat»: the chat, the folder, the result of what was just named.
                read = _pronoun_read("open", referent)
                goal, check = read if read is not None else (goal, check)
            if goal.startswith("ir a ") and steps and steps[-1].goal.startswith(CONTEXT_MENU_GOAL):
                # «clic derecho en notas.txt y abrime las propiedades»: opening an entry of that menu is clicking it.
                entry = goal[len("ir a "):]
                goal, check = f"hacer clic en {entry}", _with_alternatives(entry, ("stepDone:input.visible.click:{}",))
            if goal.startswith("reproducir ") and steps and steps[-1].goal.startswith("buscar "):
                # «buscá Duki y poné la primera»: the result clicked to play it carries the name searched.
                check = _playing_check(steps[-1].goal[len("buscar "):])
            step_application = application
            if step_application is None and goal.startswith(_TAB_GOAL):
                step_application = BROWSER_CATEGORY
            if opened is not None and (
                step_application != opened or (goal.startswith(cu_tipos.OPEN_FILE_GOAL) and not framed)
            ):
                # Review of cu-v3-abrir-archivo (finding 3, «abrí discord y después abrí foto.png»): an application
                # opened by its own order is opened, also when the file said next is to open in it.
                steps.append(_open_step(opened))
            opened = None
            current = step_application
            if steps and steps[-1].application == step_application and _kind_before_its_colour(steps[-1].goal, goal):
                # Estabilización G3 (tanda f2nb t3-c19 «y ponle color rojo», restated «haz clic en color y selecciona
                # rojo»): the click on the kind before the colour named is that one choice; the kind alone names no
                # control, and containment pressed «Editar colores», whose modal dialog hung the read 20 s.
                steps.pop()
                merged = True
            steps.append(MissionStep(step_application, goal, check or None, clause, free))
            named = _REFERENT_GOAL.match(goal)
            if named is not None:
                referent = named.group("object")
    if opened is not None:
        steps.append(_open_step(opened))
    # A sub-goal said before the clause that names the application happens in it («ábreme lista.txt …, desde
    # Archivo > Abrir del Bloc de notas»).
    following: str | None = None
    for index in range(len(steps) - 1, -1, -1):
        if steps[index].application is None and following is not None:
            steps[index] = replace(steps[index], application=following)
        following = steps[index].application or following
    for index in range(1, len(steps)):
        if steps[index].application is None and steps[index - 1].application is not None:
            # … and the sub-goals of that clause said after it stay there.
            steps[index] = replace(steps[index], application=steps[index - 1].application)
    if by_dialog:
        # The file named to open goes through the window's Open dialog the person asked for.
        steps = [
            MissionStep(step.application, goal, check, step.clause, free)
            for step in steps
            for goal, check, free in (
                _open_dialog_reads(step.goal[len(cu_tipos.OPEN_FILE_GOAL):], step.success_check, opener=True)
                if step.goal.startswith(cu_tipos.OPEN_FILE_GOAL) else ((step.goal, step.success_check, step.free),)
            )
        ]
    doing = [step for step in steps if not _is_open_step(step)]
    free = [step for step in steps if step.free]
    checked = [step for step in steps if step.success_check]
    if free and (forbids or (len(free) > len(checked) and any(step.application is None for step in steps))):
        # Free sub-goals never ride beside a prohibition the model could break (``_compound_reads`` and the readers
        # only do what they read). v3 ronda 5 (lectura M6, diseño 5; v3-49 «en 7-zip cambia la vista a detalles y
        # ordena por tamaño», t-form-4, v3-47): with every sub-goal in an application resolved, the clauses the
        # segments split are all sub-goals, the free ones judged by the done judge (``acted_with_effect``) with the
        # budget of a chain, instead of one sentence for the engine with the budget of one goal. Without one, free
        # sub-goals still ride only on a chain of more checked ones.
        return None
    if len(steps) == 1 and steps[0].application and (steps[0].goal.startswith(cu_tipos.OPEN_FILE_GOAL) or merged):
        # cu-v3-abrir-archivo (v3-18 «open paisaje.jpg in photos and tell me …»): a file opened in an application and
        # nothing else is one mission with its own goal and check, never the clause for the engine to search. So is the
        # one choice left of a click on its kind and the colour chosen (``_kind_before_its_colour``).
        return MissionRequest(steps[0].application, steps[0].goal, steps[0].success_check, steps[0].clause)
    if len(steps) < 2 or not doing or len(steps) > MAX_STEPS:
        return None
    if all(step.application is None for step in steps):
        # No application named: no chain of keys, text and clicks is read for the window in front (review of v3 punto
        # 2: with application null nothing binds the steps to a window the person chose, and «guardá esto como …»
        # with VS Code in front would save its file elsewhere). The decider takes it, as before.
        return None
    return MissionRequest(
        steps[0].application,
        "; luego ".join(step.goal for step in steps).encode("utf-8")[:500].decode("utf-8", "ignore"),
        None,
        doing[0].clause,
        tuple(_with_sent_checks(_with_form_checks(steps))),
    )


def _with_sent_checks(steps: list[MissionStep]) -> list[MissionStep]:
    """Ronda 24b (banco r23 c6: the Enter fell on the search that held «prueba BAXY C6» and «enviar» passed): «enviar»
    right after «escribir X» holds when the Enter was pressed and the App sees X sent (``sent:X``). A text with the
    check's own separators cannot ride in an atom and keeps the Enter alone."""

    result = list(steps)
    for index in range(1, len(result)):
        step, before = result[index], result[index - 1]
        if step.goal != SEND_GOAL or step.success_check != SEND_CHECK or not before.goal.startswith("escribir "):
            continue
        text = before.goal[len("escribir "):].strip(" \"'«»“”")
        if text and not any(mark in text for mark in "&|"):
            result[index] = replace(step, success_check=f"{SEND_CHECK}&{messaging.SENT_ATOM}{text}")
    return result


def _with_form_checks(steps: list[MissionStep]) -> list[MissionStep]:
    """Revisión 2 de la ronda 20b (bloqueante 1, t-long-3): a form is one unit. A run of field sub-goals («poner … en
    …», with the boxes of the same dialog between them) accepted by the button that follows it, whose last field holds
    only with the ones before it (``_unit_field_read``: terms that read several fields), gives each of its fields and
    that button the check of the whole form (``form_check``): what the engine reads to switch a link that ties them off
    before the first field and to evaluate every field again before accepting. Independent fields (a replace bar: no
    term reads two fields) carry none."""

    result = list(steps)
    index = 0
    while index < len(result):
        if not result[index].goal.startswith(_FIELD_GOAL):
            index += 1
            continue
        end = index
        while end < len(result) and result[end].goal.startswith((_FIELD_GOAL, "activar ", "desactivar ")):
            end += 1
        fields = [at for at in range(index, end) if result[at].goal.startswith(_FIELD_GOAL)]
        unit = result[fields[-1]].success_check
        if (
            len(fields) >= 2 and unit and any("&" in term for term in unit.split("|"))
            and end < len(result) and result[end].goal.startswith("hacer clic en ")
        ):
            for at in (*fields, end):
                result[at] = replace(result[at], form_check=unit)
        index = end
    return result


def _value_as_said(value: str, said: str) -> str:
    """A field's value as the person wrote it (case, accents): a path piece by piece, its known folder kept."""

    pieces = value.split("\\")
    return "\\".join(_restore(piece, said) if _said_span(piece, said) is not None else piece for piece in pieces)


def _field_as_said(goal: str, said: str) -> str:
    found = re.match(r"^(poner .+? en )(.+)$", goal)
    if found is None:
        return goal
    return found.group(1) + _value_as_said(found.group(2), said)


_PATH_IN_CHECK = re.compile(r"(?:file:|=)(?P<path>[a-zA-Z]:\\[^&|]+)")


def _field_check_as_said(step: MissionStep, said: str) -> str | None:
    """The check of a sub-goal whose value is a path: the path as written, for the shell's file and value atoms."""

    check = step.success_check
    if not check:
        return check
    for path in dict.fromkeys(found.group("path") for found in _PATH_IN_CHECK.finditer(check)):
        check = check.replace(path, _value_as_said(path, said))
    return check


_WORD = re.compile(r"[^\W_]+(?:[.\-'][^\W_]+)*")


def model_clauses_fit(text: str, clauses: Iterable[object]) -> tuple[str, ...] | None:
    """The clauses the local model split a request into (v3 punto 2, A7: a long request said without joiners), kept
    only when they are the request's own words: every word of every clause is a word the person said, no clause is
    empty, and together they say no more words than the request. None otherwise (a plan with an invented word is
    never read: it could add an act the person did not ask for)."""

    said = [word for word in _WORD.findall(fold(text))]
    said_words = set(said)
    pieces = tuple(" ".join(str(clause).split()).strip(" ,;.") for clause in clauses if isinstance(clause, str))
    if not pieces or len(pieces) > MAX_STEPS or any(not piece for piece in pieces):
        return None
    words = [word for piece in pieces for word in _WORD.findall(fold(piece))]
    if not words or any(word not in said_words for word in words) or len(words) > len(said):
        return None
    # v3 ronda 5 (lectura M6, diseño 5): a split that leaves out what was ordered («…y guardalo» dropped) is no split
    # of the request: together the clauses keep nine in ten of its content words, and each one is an order.
    content = [word for word in said if _content_word(word)]
    kept = set(words)
    if content and sum(word in kept for word in content) < SPLIT_COVERAGE * len(content):
        return None
    if not all(_starts_with_order(piece) for piece in pieces):
        return None
    return pieces


# The share of the request's content words a model's split keeps (lectura M6).
SPLIT_COVERAGE = 0.9


def _content_word(word: str) -> bool:
    return len(word) > 2 and word not in cu_tipos.NOT_ORDER_HEADS and word not in _NAME_FUNCTION_WORDS


def _order_head(word: str) -> bool:
    return word in cu_tipos.ORDER_HEADS or _CLITIC_HEAD.match(word) is not None


def _starts_with_order(piece: str) -> bool:
    """A clause of a model's split that is an order: headed by a doing verb, by opening an application, or by the
    application it happens in and then a doing verb («en Paint dibujá un gato»)."""

    folded = fold(piece).strip(" ,;:.!?")
    if not folded:
        return False
    if _free_order(folded) or _BARE_OPEN.match(folded) is not None or read_clause(folded) is not None:
        return True
    framed = _APP_FRAME_FRONT.match(folded)
    if framed is None:
        return False
    words = framed.group("clause").split()
    return any(_free_order(" ".join(words[count:])) for count in range(min(len(words), 4)))


# v3 ronda 5 (lectura, diseño 6): a goal that changes a state through menus or dialogs («filtra», «ordena por X»,
# «cambia X a Y»), and the value it ends in.
_STATE_CHANGE = re.compile(
    r"^(?:cambia|cambiale|cambiar|change|switch|pone|pon|ponele|poner|set|ordena|ordenalos|ordenar|sort|filtra|"
    r"filtrar|filter|agrupa|agrupar|group|configura|configurar|configure|ajusta|ajustar|adjust|muestra|mostra|"
    r"mostrar|show)\b(?P<rest>.*)$"
)
_STATE_VALUE = re.compile(r"(?:^|\s)(?:a|al|en|por|by|to|como|as|que\s+solo\s+(?:salgan|muestre|aparezcan))\s+"
                          r"(?:(?:el|la|los|las|the)\s+)?(?P<value>[^,;]+?)\s*$")


def state_change_value(goal: object) -> str | None:
    """The value a one-clause goal that changes a state through menus or dialogs ends in («cambia la vista a
    detalles» → «detalles», «ordena por tamaño» → «tamaño», «filtra … para que solo salgan los errores» → «errores»),
    folded; None for any other goal, a chain («; luego») or a question."""

    folded = fold(goal).strip(" .!?")
    if not folded or QUESTION_MARK.strip() in folded or "; luego" in folded:
        return None
    found = _STATE_CHANGE.match(folded)
    if found is None:
        return None
    value = _STATE_VALUE.search(found.group("rest"))
    return value.group("value").strip() if value is not None else None


def asks_for_a_model_split(
    text: str, application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """v3 ronda 5 (lectura M6): the local model splits a request (``split_request_clauses``) only when the
    deterministic segments leave one that says two or more order verbs («abrí Paint cambiá el tamaño a 500 dibujá un
    rectángulo»); a request the segments already split, or one order with its modifiers, never calls it."""

    catalog = effect_intent.build_application_catalog_index(application_names)
    folded = fold(" ".join(str(text or "").split())).strip(" .!?")
    if not folded or len(folded) > 512:
        return False
    def unnamed(segment: str) -> str:
        # An application's name is no verb («en Paint dibujá…»: «paint» is also an order head).
        pattern = catalog.occurrence_pattern
        return pattern.sub(" ", segment) if pattern is not None else segment

    return any(
        sum(_order_head(word) for word in _WORD.findall(unnamed(segment))) >= 2
        for segment in _without_remarks(_segments(folded, catalog))
    )


def mission_from_model_clauses(
    text: str,
    clauses: Iterable[object],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> MissionRequest | None:
    """The chain of a request the model split into clauses, each read by the deterministic readers as if the person
    had said them joined (``mission_request`` over «A, luego B, …»); None when the split is not the request's own
    words (``model_clauses_fit``) or no chain reads from it."""

    pieces = model_clauses_fit(text, clauses)
    if pieces is None or len(pieces) < 2:
        return None
    mission = mission_request(", luego ".join(pieces), application_names)
    return mission if mission is not None and mission.steps else None


def _is_open_step(step: MissionStep) -> bool:
    return step.success_check == f"title:{step.application}|process:{step.application}"


# ------------------------------------------------------------ tipos de tarea (v3 punto 2)

_FIELD_GOAL = "poner "
# «con el clic derecho …», «using a right click …»: the means of the order said before.
_MEANS_LEAD = re.compile(r"^(?:con|using|with|usando)\s")
# The short imperatives (pon, haz, ten, di) take their pronoun too: «ponle: pagar la luz», «hazlo» (v3 destino, v3-35).
_CLITIC_HEAD = re.compile(r"^(?:[a-z]{2,}[aei]|pon|haz|ten|di)(?:me|te|se)?(?:lo|la|los|las|le|les)$")


# «del Bloc de notas», «de Paint», «in this Word document», «with Notepad»: an application framed as where the clause
# happens.
_APPLICATION_FRAME = re.compile(
    r"(?<![a-z0-9])(?:del|de\s+la|de|en|in|on|with|con|using|usando|from|desde)\s+"
    r"(?=(?:(?:el|la|the|this|that|este|esta|ese|esa|mi|my)\s+)?(?P<words>[a-z0-9][a-z0-9 .+-]{0,60}))"
)
_QUOTED_SPAN = re.compile(r"\"[^\"]*\"|«[^»]*»|“[^”]*”")


def _framed_application(segment: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    """The installed application a clause names by a frame («del Bloc de notas», «in this Word document»); None for a
    clause that types, searches or notes a text (a name there is text: «escribí que me encanta Discord») or names
    none."""

    if _dictates(segment):
        return None
    unquoted = _QUOTED_SPAN.sub(" ", segment)
    for found in _APPLICATION_FRAME.finditer(unquoted):
        words = found.group("words").split()
        for count in range(min(len(words), 4), 0, -1):
            key = _catalog_key(" ".join(words[:count]), catalog)
            if key is not None:
                return _display_name(key, catalog)
    return None


# A place a clause says («en …», «in …», «dentro de …»), its determiner and a word saying the place is new.
_PLACE_SAID = re.compile(r"(?<![a-z0-9])(?:en|in|on|into|inside|dentro\s+de)\s+")
_PLACE_DETERMINERS = frozenset({
    "un", "una", "el", "la", "los", "las", "este", "esta", "ese", "esa", "mi", "otro", "otra", "a", "an", "the",
    "this", "that", "my", "another",
})
_PLACE_NEW = frozenset({"nuevo", "nueva", "new", "blank", "empty", "vacio", "vacia"})
_PLACE_OWNER = frozenset({"de", "del", "of"})


def _placed_application(segment: str, catalog: effect_intent.ApplicationCatalogIndex) -> str | None:
    """The installed application a clause says as the place it happens in: right after the place («pégalo en
    onenote», «paste it in a new OneNote page»), or as the owner of the place said («en una página nueva de onenote»,
    «into a new page of OneNote»: at most three words before «de»/«of»). None for a name the clause only mentions
    («calcula cuánto cuesta spotify», «dibuja el logo de google chrome», «una tabla comparando excel y onenote») or
    one inside a dictated text."""

    for found in _PLACE_SAID.finditer(segment):
        if _inside_said_text(segment, found.start()):
            continue
        words = segment[found.end():].split()
        at = 1 if words and words[0] in _PLACE_DETERMINERS else 0
        at += 1 if len(words) > at and words[at] in _PLACE_NEW else 0
        owner = next((i for i in range(at + 1, min(at + 4, len(words))) if words[i] in _PLACE_OWNER), None)
        if owner is None:
            spans = [(at, 1)]
        else:
            # «en la configuración de word»: the owner said is where it happens, never the place's own noun even when
            # that noun names an application too; the noun counts only as a whole name that spans the «de» («en el
            # bloc de notas»), and a place whose owner is no application («en la configuración de pantalla») says
            # none (revisión destino del pedido).
            said_owner = owner + 1 + (1 if len(words) > owner + 1 and words[owner + 1] in ("la", "el", "the") else 0)
            spans = [(at, owner - at + 2), (said_owner, 1)]
        for start, shortest in spans:
            for count in range(min(len(words) - start, 4), shortest - 1, -1):
                key = _catalog_key(" ".join(words[start:start + count]).strip(_SAID_PUNCTUATION), catalog)
                if key is not None and not re.fullmatch(_ASSISTANT_NAME, key):
                    return _display_name(key, catalog)
    return None


def _is_remark(piece: str) -> bool:
    return cu_tipos.REMARK.match(piece.strip(" ,;:.!?")) is not None


def _without_remarks(segments: list[str]) -> list[str]:
    return [segment for segment in segments if not _is_remark(segment)]


def _inside_quotes(folded: str, position: int) -> bool:
    before = folded[:position]
    if before.count('"') % 2 == 1:
        return True
    return any(before.count(opening) > before.count(closing) for opening, closing in _PAIRED_QUOTES.items())


def _free_order(piece: str) -> bool:
    """A piece said as an order no reader reads: it starts with a doing verb (one the readers know, one of the screen
    verbs of ``cu_tipos.ORDER_HEADS``, or an imperative with its pronoun, «ponelo», «centralo»), and it is no
    question, remark, prohibition or statement."""

    piece = piece.strip(" ,;:.!?")
    if not piece or "?" in piece or _is_remark(piece) or effect_intent._is_negative_effect_clause(piece):
        return False
    piece = cu_tipos.ONLY_ADVERB.sub("", piece, count=1)
    head = piece.split()[0]
    if head in cu_tipos.NOT_ORDER_HEADS or not head.isalpha():
        return False
    return (
        head in cu_tipos.ORDER_HEADS or _CLITIC_HEAD.match(head) is not None or _is_doing(piece)
    )


def _same_act(goal: str, entry: str, *, whole: bool = False) -> bool:
    """«zoom in twice» and the route's last entry «Zoom in»: the order names the entry the route ends in. ``whole``:
    and says nothing else but articles and pronouns («rotate the image 90 degrees right» says more than «Rotate»)."""

    said = set(re.findall(r"[a-z0-9]+", fold(goal)))
    words = set(re.findall(r"[a-z0-9]+", fold(entry)))
    return bool(words) and words <= said and (not whole or said - words <= _ACT_FILLER)


_ACT_FILLER = frozenset({
    "el", "la", "los", "las", "un", "una", "lo", "esto", "eso", "the", "a", "an", "it", "this", "that",
})


def _times(goal: str) -> int:
    found = cu_tipos.REPETITION.search(fold(goal))
    return cu_tipos.repetitions(found) if found is not None else 1


def _is_route(clause: str) -> bool:
    return ">" in clause or cu_tipos.MENU_LIST.search(fold(clause)) is not None


def clicks_a_route(text: str) -> bool:
    """r15b t-menu-4 «Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar»: the request says a menu route
    of two or more pieces (``_compound_reads``: one click per piece), which one lone click never does: the decider's
    single ``input.visible.click`` on the first piece is a piece of the order, and the order is the engine's."""

    folded = fold(" ".join(str(text or "").split())).strip(" .!?¡¿")
    if not folded or not _is_route(folded):
        return False
    reads = _compound_reads(folded)
    return reads is not None and sum(1 for goal, _, _ in reads if goal.startswith("hacer clic en ")) >= 2


def _route(folded: str) -> tuple[str, list[str], str] | None:
    """(what is said before, the pieces, what is said after) of a menu route: «desde el menú Imagen > Girar»,
    «View > Zoom > Zoom in», «el menú Imagen, Girar». None when the text names no route («Archivo» alone is none)."""

    if ">" in folded:
        parts = [part.strip() for part in folded.split(">")]
        if len(parts) < 2 or any(not part for part in parts):
            return None
        words = parts[0].replace(",", " , ").split()
        first: list[str] = []
        while words and len(first) < cu_tipos.ROUTE_PIECE_WORDS - 1:
            word = words[-1]
            # «… from the Image > Rotate menu»: the article before the route is none of its first piece.
            # «click File > Save as»: the click is none of it either.
            # Ronda 21 (v3-67): «open Library > …»: the opening verb is none of it either.
            if (
                word == "," or word in _ROUTE_LEADS or word in _ROUTE_ARTICLES or _CLICK_ONLY.match(word) is not None
                or (word in cu_tipos.ROUTE_OPEN_VERBS and _opening_heads(words[:-1]))
            ):
                break
            first.insert(0, words.pop())
        introducing = list(words)
        while introducing and introducing[-1] in _ROUTE_ARTICLES:
            introducing.pop()
        if not _route_introduced(introducing, " ".join(first)):
            return None
        while words and (words[-1] in _ROUTE_LEADS or words[-1] in {",", *_ROUTE_ARTICLES}):
            words.pop()
        before = " ".join(words).replace(" ,", ",")
        last = parts[-1]
        end = cu_tipos.ROUTE_END.search(last)
        after = last[end.start():].strip(" ,;.") if end is not None else ""
        last = last[: end.start()].strip() if end is not None else last
        said_last = last.split()
        if len(said_last) > 1 and said_last[-1] in {"menu", "menus"}:
            # «… the Image > Rotate menu»: the menu said after the route, as English says it, is no word of the piece.
            last = " ".join(said_last[:-1])
        pieces = [" ".join(first), *parts[1:-1], last]
    else:
        listed = cu_tipos.MENU_LIST.search(folded)
        if listed is None:
            return None
        before = folded[: listed.start()].strip(" ,")
        before = re.sub(r"\s+(?:desde|from|using|usando|via|con|with|en|in)$", "", before)
        pieces = [piece.strip() for piece in listed.group("list").split(",")]
        after = ""
    pieces = [_unquoted(piece) for piece in pieces]
    if len(pieces) < 2 or any(not piece or len(piece.split()) > cu_tipos.ROUTE_PIECE_WORDS for piece in pieces):
        return None
    return before.strip(), pieces, after


_CLICK_ONLY = re.compile(r"^(?:(?:hace|haz|hacer|da|dale|do)\s+(?:un\s+|a\s+)?)?(?:clic|click|clickea|pulsa|toca)(?:\s+(?:en|on))?$")


def _route_introduced(before: list[str], first: str) -> bool:
    """A «>» names a menu route only where a route is said (v3 punto 2, review): after what introduces one («desde»,
    «using», «el menú»), after a comma, after going or clicking («andá a Archivo > Abrir»), or opening the clause with
    a first piece that is no order. «escribí 5 > 3» or «el precio sube de 5 > 3» name none."""

    if not first:
        return False
    if not before:
        return not _free_order(first) and read_clause(first) is None and first.split()[0] not in cu_tipos.NOT_ORDER_HEADS
    lead = before[-1]
    if lead == "," or lead in cu_tipos.ROUTE_INTRO:
        return True
    if lead in cu_tipos.ROUTE_OPEN_VERBS and any(letter.isalpha() for letter in first):
        # Ronda 21 (v3-67): opening or unfolding a route says it as going to it does. Revision 2 (finding 2): a route's
        # entries are named by words; «abrí 5 > 3» opens no entry named «5».
        return True
    if _CLICK_ONLY.match(" ".join(before)) is not None:
        # «click File > Save as»: the click said with no «en»/«on», as English says it.
        return True
    if lead in cu_tipos.ROUTE_INTRO_AFTER_GOING:
        said = " ".join(before[:-1]).strip(" ,")
        return bool(said) and (_NAVIGATE_ONLY.match(said) is not None or _CLICK_ONLY.match(said) is not None)
    return False


def _opening_heads(before: list[str]) -> bool:
    """Revision 2 (finding 2): an opening verb («abrí», «open») introduces a route only where it heads the clause: at
    the start, after a comma or a colon, or after the application's frame («en el bloc de notas abre Archivo > …»).
    After a click or a going («hacé clic en Abrir reciente > …», «click Open Recent > …», «andá a Abrir reciente > …»)
    it is the first word of the entry the person names."""

    if not before:
        return True
    lead = before[-1]
    if lead == "," or lead.endswith(":"):
        return True
    return not (
        lead in _ROUTE_LEADS or lead in _ROUTE_ARTICLES or _CLICK_ONLY.match(lead) is not None
        or _NAVIGATE_ONLY.match(lead) is not None
    )


_ROUTE_LEADS = frozenset({
    "desde", "from", "using", "usando", "via", "menu", "menus", "a", "al", "to", "en", "in", "on", "por", "con", "with",
    "de",
})
_ROUTE_ARTICLES = frozenset({"el", "la", "the"})


def _route_reads(pieces: list[str]) -> list[tuple[str, str | None, bool]]:
    """One click per piece of a menu route: a piece before the last is open when it shows expanded or when its
    click made the next piece show; the last piece is its verified click."""

    reads: list[tuple[str, str | None, bool]] = []
    for index, piece in enumerate(pieces):
        name = _check_name(piece, known=False) or piece
        if index < len(pieces) - 1:
            following = _check_name(pieces[index + 1], known=False) or pieces[index + 1]
            check = _fit(f"control:{name}:expanded", f"stepDone:input.visible.click:{name}&control:{following}")
        else:
            check = f"stepDone:input.visible.click:{name}"
        reads.append((f"hacer clic en {piece}", check, False))
    return reads


def _field_read(field: str, value: str) -> tuple[str, str | None, bool]:
    """«poner ancho en 800»: the field by any of its names holds the value."""

    names = cu_tipos.field_names(field)
    return f"{_FIELD_GOAL}{field} en {value}", _fit(*(f"value:{name}={value}" for name in names)), False


def _unit_field_read(fields: list[tuple[str, str]]) -> tuple[str, str | None, bool]:
    """The last of ``fields`` set while the ones before it still hold their values (ronda 20b, pasada r18 t-long-3: with
    the aspect lock on, Vertical 500 recalculated Horizontal to 177 and the plan counted both as set). A form is one
    unit: its field closes only when the whole form holds at once. Each term pairs the names of one language first (the
    names of ``cu_tipos.FIELD_NAMES`` go side by side: «ancho»/«alto», «width»/«height», «horizontal»/«vertical»), then
    the other combinations while they fit; a value the window formats («500 px») still holds (``value:`` contains)."""

    field, value = fields[-1]
    goal, own, free = _field_read(field, value)
    if len(fields) < 2:
        return goal, own, free
    named = [[(name, said) for name in cu_tipos.field_names(key)] for key, said in fields]
    span = max(len(names) for names in named)
    aligned = [tuple(names[index % len(names)] for names in named) for index in range(span)]
    others = [combo for combo in itertools.product(*named) if combo not in aligned]
    terms = ["&".join(f"value:{name}={said}" for name, said in combo) for combo in (*aligned, *others)]
    return goal, _fit(*terms), free


def _button_read(names: tuple[str, ...]) -> tuple[str, str | None, bool]:
    return f"hacer clic en {names[0]}", _fit(*(f"stepDone:input.visible.click:{name}" for name in names)), False


def _opener_read(
    head: str, fields: dict[str, str], styles: list[str], unit: re.Match[str] | None,
) -> tuple[str, str | None, bool]:
    """The sub-goal that opens a form (pasada r15b, t-form-1, t-long-3, t-form-3): its goal is the opening said and
    where the values go («en paint cambiale el tamano a la imagen, donde se ponen ancho y alto»), never the values to
    set there (the model typed 800 with the aspect lock on, or picked the 1x1 cell of a table gallery);
    the opening keeps what to open (review of cierre-de-subobjetivos, findings 4 and 6: a bare «abrir …» lost the
    dialog or the table, and made the application opened count as its act). Its check is the form shown by an act of
    its own (``appeared:``): the unit's option, else two of its names side by side in each language, its first fields
    or a field and a style (finding 5: one name alone, «Tamaño», is also a button on another tab). A field the window
    shows from the start (a font box on a ribbon) never closes it."""

    # Ronda 20b (pasada r18 t-long-3): only where the values go, never the values themselves: a part reached by the form
    # shown is never told as the values set («resize the canvas to 500 by 500» over a canvas left at 177×500).
    said = list(fields)
    said += [cu_tipos.style_names(style)[0] for style in dict.fromkeys(styles)]
    listed = said[0] if len(said) == 1 else ", ".join(said[:-1]) + " y " + said[-1]
    goal = f"{head}, donde se ponen {listed}"
    units = cu_tipos.unit_names(unit.group("unit")) if unit is not None else ()
    named = [cu_tipos.field_names(key) for key in list(fields)[:2]]
    span = min((len(names) for names in named), default=0)
    named += [cu_tipos.style_names(style) for style in dict.fromkeys(styles)][: 2 - len(named)]
    pairs = ["&".join(f"appeared:{names[index % len(names)]}" for names in named) for index in range(span)]
    check = _fit(*(f"appeared:{name}" for name in units), *pairs)
    return goal, check or None, not check


_DIALOG_SAID = re.compile(
    r"\b(?:desde|en|from|in|using|con)\s+(?:el|la|the)?\s*(?:cuadro\s+de\s+dialogo|dialogo|ventana|dialog(?:\s+box)?|"
    r"window)\s+(?:de\s+|del\s+|of\s+)?(?:la\s+|el\s+|the\s+)?(?P<name>[a-z][a-z ]{0,30}?)\s*$"
)
_OPENING_TAIL = re.compile(r"\s+(?:a|al|to|with|con|de|en|in|by|por)$")


def _form_reads(clause: str) -> list[tuple[str, str | None, bool]] | None:
    """A form filled by the pairs of field and value it says (v3 punto 2, A5): «cambiale el tamaño a 800 de ancho por
    600 de alto» → the dialog opened by the order (a free sub-goal), «poner ancho en 800», «poner alto en 600», then
    the dialog's default button. «reemplazá «casa» por «hogar»» → the replace bar, both fields and «Reemplazar todo».
    None for anything with fewer than two settings (one value alone is no form)."""

    replaced = cu_tipos.REPLACE.match(clause)
    if replaced is not None:
        everything = replaced.group("all") or cu_tipos.ALL_WORDS.search(replaced.group("rest") or "")
        return [
            (cu_tipos.REPLACE_OPENER, _fit(*(f"control:{name}" for name in cu_tipos.field_names("reemplazar")[:2])), False),
            _field_read("buscar", replaced.group("old")),
            _field_read("reemplazar", replaced.group("new")),
            _button_read(cu_tipos.REPLACE_ALL_BUTTONS if everything else cu_tipos.REPLACE_ONE_BUTTONS),
        ]
    settings: dict[str, str] = {}
    spans: list[tuple[int, int]] = []
    dimensions = cu_tipos.DIMENSIONS.search(clause)
    if dimensions is not None and cu_tipos.SIZE_WORDS.search(clause):
        # «cambiá el tamaño a 500 por 500 píxeles»: width by height; «tamaño a 500» is then no field of its own.
        settings["ancho"], settings["alto"] = dimensions.group("width"), dimensions.group("height")
        spans.append((dimensions.start(), dimensions.end()))
    for pattern in cu_tipos.FIELD_PAIRS:
        for found in pattern.finditer(clause):
            if any(found.start() < end and found.end() > start for start, end in spans):
                continue
            key = cu_tipos.field_key(found.group("field"))
            if key is not None and key not in settings:
                settings[key] = found.group("value")
                spans.append((found.start(), found.end()))
    styles = [cu_tipos.style_key(found.group("style")) for found in cu_tipos.STYLE.finditer(clause)]
    font = None
    if cu_tipos.FONT_CONTEXT.search(clause):
        for found in cu_tipos.FONT_NAME.finditer(clause):
            name = found.group("font").strip()
            if name and cu_tipos.STYLE.fullmatch(name) is None and name.split()[0] not in cu_tipos.NOT_ORDER_HEADS:
                font = name
                spans.append((found.start(), found.end()))
                break
    if len(settings) + len(styles) + (font is not None) < 2:
        return None
    dialog = _DIALOG_SAID.search(clause)
    if not settings and font is None and dialog is None:
        # «poné la letra en negrita y subrayado»: styles alone are the window's own buttons, no dialog to fill.
        return None
    unit = cu_tipos.UNIT.search(clause)
    if unit is not None and "ancho" not in settings and "alto" not in settings:
        unit = None
    reads: list[tuple[str, str | None, bool]] = []
    first = min((start for start, _ in spans), default=len(clause))
    opening = clause[: dialog.start()] if dialog is not None else clause[:first]
    opening = _OPENING_TAIL.sub("", opening.strip(" ,;:")).strip(" ,;:")
    fields = ({"fuente": font} if font is not None else {}) | settings
    if dialog is not None:
        reads.append(_opener_read(f"abrir el dialogo de {dialog.group('name').strip()}", fields, styles, unit))
    elif opening and len(opening.split()) >= 2 and not cu_tipos.FIELD_PAIRS[1].search(opening):
        reads.append(_opener_read(opening, fields, styles, unit))
    if unit is not None:
        # The unit first: the values are said in it (a size dialog opens in percent).
        names = cu_tipos.unit_names(unit.group("unit"))
        reads.append((f"activar {names[0]}", _fit(*(f"control:{name}:{state}" for name in names for state in (
            "on", "selected"))), False))
    # The form is one unit (ronda 20b): each field after the first holds only with the ones before it. A request that
    # keeps the link between them («… manteniendo la proporción») ties them all the same (revisión 1, bloqueante 3:
    # with the link on each field recalculates the other, and only the whole form says whether both values fit); it only
    # keeps the switch on (cu_forms._form_unit_step).
    set_so_far: list[tuple[str, str]] = []
    for key, value in ([("fuente", font)] if font is not None else []) + list(settings.items()):
        set_so_far.append((key, value))
        reads.append(_unit_field_read(set_so_far))
    for style in dict.fromkeys(styles):
        names = cu_tipos.style_names(style)
        reads.append((f"activar {names[0]}", _fit(*(f"control:{name}:on" for name in names)), False))
    reads.append(_button_read(cu_tipos.DEFAULT_BUTTONS))
    return reads


def _dialog_path(place: str | None, name: str) -> str | None:
    """The absolute path a file dialog takes: the known folder said («Documentos», «Documents\\baxy»), its subfolders
    and the name. None when no known folder is said (the dialog's own folder is then used, by the name alone)."""

    if not place:
        return None
    found = cu_tipos.PLACE_FOLDER.match(place.strip(" ,;.").replace("\\ ", "\\"))
    if found is None:
        return None
    from ..known_folders import known_folder

    root = known_folder(cu_tipos.KNOWN_FOLDERS.get(found.group("known"), ""))
    if root is None:
        return None
    parts = [part.strip() for part in re.split(r"[\\/]+", found.group("sub") or "") if part.strip()]
    if found.group("folder"):
        parts.append(found.group("folder"))
    if any(part in {".", ".."} for part in parts) or any(sign in name for sign in "\\/:*?\"<>|"):
        return None
    return "\\".join((root.rstrip("\\/"), *parts, name))


def _located_file(place: str | None, name: str) -> str | None:
    """The one file named so under the known folders, inside the folder the place names («la carpeta
    baxy-prueba-v3»); None when the place names no folder, or there is no such file or more than one."""

    from ..known_folders import locate_file

    if not place:
        return locate_file(name)
    said = place.strip(" ,;.")
    folder = cu_tipos.NAMED_FOLDER.match(said)
    if folder is not None:
        return locate_file(name, folder.group("folder") or folder.group("before"))
    # Ronda 20b (v3-50 «abrí prueba.zip que está en baxy-prueba-v3»): a place of one word, said without «carpeta», is
    # tried as a folder's name under the known folders; only one file there is the file, none or two are not guessed.
    if cu_tipos.FOLDER_TOKEN.fullmatch(said):
        return locate_file(name, said)
    return None


def _file_taken(path: str) -> bool:
    """A file already at the path, or one with that name and any extension when the name has none (the application
    adds its own): saving there would replace it."""

    try:
        target = Path(path)
        if target.exists():
            return True
        return "." not in target.name.strip(".") and target.parent.is_dir() and any(
            sibling.stem.casefold() == target.name.casefold() for sibling in target.parent.iterdir()
        )
    except OSError:
        return True


def _file_reads(clause: str) -> list[tuple[str, str | None, bool]] | None:
    """Saving through the window's dialog (v3 punto 2, A6): «guardá esto como N en C», «save this drawing as N in C» →
    the dialog opened (its key; a route said later replaces it), «Nombre de archivo» set to the absolute path, then
    Guardar: the file on disk (``file:``) with the window titled by it. Opening, «abrí N que está en C»
    (cu-v3-abrir-archivo): one sub-goal, the file opened with the mission's application by the shell (the typed
    file.open), checked by the window titled by the name: the absolute path when the place said or the known folders
    hold exactly one, else the name alone, which the provider looks for and never guesses between two."""

    saved = cu_tipos.SAVE_AS.match(clause)
    opened = None if saved is not None else cu_tipos.OPEN_FILE.match(clause)
    found = saved or opened
    if found is None:
        return None
    name = _unquoted(found.group("name"))
    if not name or _has_deictic_only(name):
        return None
    place = found.group("place")
    path = _dialog_path(place, name)
    if opened is not None and path is None:
        # v3 ronda 3 (lugar M6; v3-17, v3-18): a file opened with no known folder said, or from a folder of the
        # person's that is none, is the one file with that name under the known folders; two are not guessed.
        path = _located_file(place, name)
    if place and path is None:
        # A place said that is no known folder: the dialog cannot be told where by a path this reader trusts.
        return None
    stem = name.rsplit(".", 1)[0] if "." in name.strip(".") else name
    if saved is not None and (path is None or _file_taken(path)):
        # Saving is read only to a new file at a path this reader knows (review of v3 punto 2): with no folder the
        # dialog's own one could hold it, and over a file that exists the dialog asks «¿Desea reemplazarlo?», whose
        # «Sí» overwrites it while ``file:`` already holds. Both are asked.
        return None
    field_names = cu_tipos.FILE_NAME_FIELD
    target = path or name
    title = _check_name(stem, known=False) or stem
    if opened is not None:
        # Review of cu-v3-abrir-archivo (finding 2): the window titled by the name proves the file opened only after
        # the sub-goal's own file.open did (the application's window shows another file, or its name holds the stem).
        return [(f"{cu_tipos.OPEN_FILE_GOAL}{target}", f"title:{title}&{cu_tipos.FILE_OPENED}", False)]
    has_extension = "." in name.strip(".")
    check = f"file:{path}&title:{title}" if path and has_extension else f"title:{title}"
    return [
        (cu_tipos.SAVE_AS_OPENER, _fit(*(f"control:{field}" for field in (field_names[0], field_names[2]))), False),
        (f"{_FIELD_GOAL}nombre de archivo en {target}", _fit(
            *(f"value:{field}={target}" for field in (field_names[0], field_names[2]))
        ), False),
        (f"hacer clic en {cu_tipos.SAVE_BUTTONS[0]}", check, False),
    ]


def _routed_dialog(step: MissionStep) -> bool:
    """A sub-goal a menu route said after it replaces: the Save As dialog opened, or a file opened (by the dialog the
    route opens instead of the shell)."""

    return step.goal == cu_tipos.SAVE_AS_OPENER or step.goal.startswith(cu_tipos.OPEN_FILE_GOAL)


def _open_dialog_reads(
    target: str, title_check: str | None, *, opener: bool = False
) -> list[tuple[str, str | None, bool]]:
    """Opening a file through the window's own Open dialog, once a route said opened it (or, ``opener``, with the
    dialog opened first, as «usá el Abrir de Paint» asks): its name field set to the path, then its Open button,
    checked by the window titled by the file (no file.open is taken that way)."""

    field_names = cu_tipos.FILE_NAME_FIELD
    if title_check:
        title_check = "|".join(
            "&".join(atom for atom in term.split("&") if atom != cu_tipos.FILE_OPENED) for term in title_check.split("|")
        )
    opened: list[tuple[str, str | None, bool]] = [
        (cu_tipos.OPEN_OPENER, _fit(*(f"control:{field}" for field in (field_names[0], field_names[2]))), False)
    ] if opener else []
    return [
        *opened,
        (f"{_FIELD_GOAL}nombre de archivo en {target}", _fit(
            *(f"value:{field}={target}" for field in (field_names[0], field_names[2]))
        ), False),
        (f"hacer clic en {cu_tipos.OPEN_BUTTONS[0]}", title_check, False),
    ]


def _compound_reads(clause: str) -> list[tuple[str, str | None, bool]] | None:
    """The clauses of the v3 task types that are several sub-goals: a menu route (one click per piece, repeated when
    said «dos veces»), saving or opening through the dialog, a form; with the order said before a route kept as a
    free sub-goal after it («girá la imagen 90° desde el menú Imagen > Girar»). None for any other clause."""

    folded = clause.strip(" ,;:.!?")
    if not folded or len(folded) > 300:
        return None
    files = _file_reads(folded)
    if files is not None:
        return files
    dictated = cu_tipos.DICTATION.search(folded)
    if dictated is not None and not _inside_quotes(folded, dictated.start()):
        # «escribí 5 > 3», «buscá mesa de 80 de ancho y 120 de alto», «recordame que mide 3 de ancho»: what is typed,
        # searched or noted is text, never a route or a form (review of v3 punto 2). Only a route or a form said
        # before the dictating verb is read.
        folded = folded[: dictated.start()].strip(" ,;:")
        if not folded:
            return None
    route = _route(folded)
    if route is not None:
        before, pieces, _ = route
        times = 1
        repeated = cu_tipos.REPETITION.search(before)
        if repeated is not None:
            times = cu_tipos.repetitions(repeated)
            before = (before[: repeated.start()] + before[repeated.end():]).strip(" ,")
        reads = _route_reads(pieces) * times
        before = cu_tipos.MENU_MEANS.sub("", before, count=1).strip(" ,")
        # «Rotate the image 90 degrees right from the Image > Rotate menu»: the route's last entry says «rotate», the
        # order says more (which way), so what to do once it is open stays a sub-goal, as «gira…» / «Girar» keeps it.
        # Revision 1 (finding 3): what ends in the opening verb («de tareas abri», the rest of an application named
        # before a colon) is the route's own introduction and the frame's rest, never an order on what opens.
        if (
            before and not _same_act(before, pieces[-1], whole=True) and not _NAVIGATE_ONLY.match(before)
            and before.split()[-1] not in cu_tipos.ROUTE_OPEN_VERBS
        ):
            # What to do once the route is open: the model picks the entry that does it.
            reads.append((before, None, True))
        return reads
    return _form_reads(folded)


# «andá a», «go to», «ve a»: a going said with the route as its place is the route.
_NAVIGATE_ONLY = re.compile(rf"^{_NAVIGATE_HEAD}(?:\s+(?:a|al|to|en))?$")


def _segment_reads(clause: str) -> list[tuple[str, str | None, bool]] | None:
    """The sub-goals one clause says: several for a clause of the v3 task types, one for any clause a reader reads,
    None otherwise."""

    clause = clause.strip(" ,;:")
    compound = _compound_reads(clause)
    if compound is not None:
        return compound
    read = read_clause(clause)
    if read is None:
        return None
    # A doing no reader checks («mové notas.txt adentro») is a free sub-goal like an order no reader reads.
    return [(read[0], read[1], read[1] is None)]


# v3-26 «abrí el Visor de eventos y en Sistema buscame un evento con ID 6005»: inside the application already named,
# «en <lugar> <orden>» goes to that place and does the order there.
_PLACE_FRAME = re.compile(
    r"^(?:en|in|on|dentro\s+de)\s+(?:(?P<article>la|el|los|las|the)\s+)?(?P<rest>\S.+)$"
)
# Review of L2: «en <palabra>» is also how something is done, never a place to go to («abrí Word y en negrita escribí
# hola», «en inglés», «en incógnito», «en silencio», «en serio», «in full screen»). Folded.
_MANNER_AFTER_EN = frozenset({
    "negrita", "negritas", "cursiva", "cursivas", "italica", "subrayado", "mayuscula", "mayusculas", "minuscula",
    "minusculas", "ingles", "espanol", "castellano", "frances", "aleman", "portugues", "italiano", "chino", "japones",
    "silencio", "serio", "privado", "privada", "incognito", "secreto", "voz", "pantalla completa", "modo incognito",
    "modo privado", "bold", "italic", "italics", "uppercase", "lowercase", "caps", "english", "spanish", "french",
    "german", "silence", "private", "secret", "full screen", "fullscreen", "incognito mode", "private mode",
})


def _said_as_place(place: str, article: str | None, said: str) -> bool:
    """Whether «en <place>» was said as a place's name: with an article («en la tienda»), as a name the label tables
    know («en sistema», «en configuración»), or written with a capital («en Sistema»)."""

    if article or label_alternatives(place):
        return True
    return bool(said) and _restore(place, said)[:1].isupper()


def _place_then_order(
    segment: str, catalog: effect_intent.ApplicationCatalogIndex, said: str = ""
) -> list[tuple[str, str | None, bool]] | None:
    """«en Sistema buscame X» inside an application → going to «Sistema», then the order, both checked; None when the
    place is an application (its own frame), a way of doing («en negrita», «en inglés»), no place's name (no article,
    capital or known label), when no checked order follows or when going there is no place read."""

    found = _PLACE_FRAME.match(segment.strip(" ,;:"))
    if found is None:
        return None
    words = found.group("rest").split()
    if any(" ".join(words[:count]) in _MANNER_AFTER_EN for count in range(1, min(3, len(words)) + 1)):
        return None
    for count in range(1, min(4, len(words))):
        place, order = " ".join(words[:count]), " ".join(words[count:])
        if _catalog_key(place, catalog) is not None:
            return None
        if not _said_as_place(place, found.group("article"), said):
            continue
        read = read_clause(order)
        if read is None or read[1] is None:
            continue
        went = read_clause(f"anda a {place}")
        if went is None or went[1] is None or not went[0].startswith("ir a "):
            return None
        return [(went[0], went[1], False), (read[0], read[1], False)]
    return None


def _open_step(application: str) -> MissionStep:
    """«… y abrí Discord» with nothing to do in it: the sub-goal is having it in front."""

    return MissionStep(application, f"abrir {application}", f"title:{application}|process:{application}")


# «abrí Paint y después elegí el lápiz»: the sequencer after the coordinator is no part of the clause.
_LEADING_SEQUENCER = re.compile(r"^(?:(?:y|and)\s+)?(?:luego|despues|entonces|then|after\s+that)\s+(?:de\s+eso\s+)?")


# The goals whose clause may name a place inside the application before the application itself.
_PLACE_GOALS = ("ir a ", "hacer clic en ", "seleccionar ", "activar ", "desactivar ")


def _opened_whole(folded: str, application: str) -> bool:
    """Whether ``application`` is the whole slot an open verb delimits («abre powerpint y …»): the only frame where a
    near spelling names an application (``_catalog_key``'s ``loose``)."""

    opened = _APP_FRAME_OPEN.match(folded)
    return opened is not None and opened.group("app") == application


def _app_frames(folded: str, *, longer_names: bool = True) -> Iterable[tuple[str, str]]:
    """The (application, clause) splits the request frames say; ``longer_names`` also tries names of several words
    after «en», which only the catalog can tell from a statement («en la mañana tengo que ir al banco»)."""

    for pattern in (_APP_FRAME_OPEN, _APP_FRAME_FRONT, _APP_FRAME_BACK):
        found = pattern.match(folded)
        if found is None:
            continue
        clause = _LEADING_SEQUENCER.sub("", found.group("clause"), count=1)
        yield found.group("app"), clause
        if pattern is _APP_FRAME_BACK:
            # «hacé clic en Ajustes en Steam»: the application is after the last «en», the clause keeps the place it
            # names (the first «en» split gave «ajustes en steam» as the application).
            # Only a clause that goes, clicks, chooses or switches names a place before it: «escribí Cuphead en el
            # buscador en Steam» types «Cuphead», never «Cuphead en el buscador».
            last = _APP_FRAME_BACK_LAST.match(folded)
            if last is not None and last.group("app") != found.group("app"):
                last_clause = _LEADING_SEQUENCER.sub("", last.group("clause"), count=1)
                read = read_clause(last_clause)
                if read is not None and read[0].startswith(_PLACE_GOALS):
                    yield last.group("app"), last_clause
        if longer_names and pattern is _APP_FRAME_FRONT:
            # «en el bloc de notas escribí hola»: a name of several words ends where the clause begins.
            words = clause.split()
            for count in range(1, min(len(words), 4)):
                yield f"{found.group('app')} {' '.join(words[:count])}", " ".join(words[count:])


# What the engine never tries on its own when no operation serves the request: undoing or paying (owner's rule:
# destructive or paying steps are asked for; a whole goal of that kind is not handed to the screen loop).
# v3 ronda 3 (v3-08 «creá una página nueva» was kept out as paying): «página»/«page(s)», «comprimí», «comprobá»,
# «comprender» and «formato»/«format» share the stems of paying, buying and formatting but are none of them. «compren» is
# buying; formatting is only a drive's (``_FORMATTING_A_DRIVE``).
_DESTRUCTIVE_OR_PAYING = re.compile(
    r"(?:^|\s)(?:borr|elimin|desinstal|compr(?!ob|im|end|ens)|pag(?!in|es?\b)|transfer|vaci|delete|remove|uninstall|"
    r"buy|"
    r"purchase|pay|wipe|erase|quit|descart|discard|papelera|trash|unsubscri|suscrib|subscrib|alquil|rent|donat|"
    r"sell|vend|restablec|reset|limpi|clear|empt|shutdown|reboot|logoff|logout|hibern)\w*"
    # Corrección ronda 5 (owner rule: never restart, shut down or sign out): the PC's power, said any way.
    r"|(?:^|\s)(?:apag\w*|reinici\w*|suspend\w*|restart|turn\s+off|shut\s+down|power\s+off)\s+"
    r"(?:(?:la|el|mi|the|my|this)\s+)?"
    r"(?:compu\w*|pc|equipo|maquina|ordenador|sistema|windows|computer|laptop|notebook)\b"
    r"|(?:^|\s)(?:cerr\w*|close|sign|log)\s+(?:(?:la|mi|tu|the|my)\s+)?(?:sesion|session|out|off)\b"
    r"|(?:^|\s)(?:dona|donar|donale|saca(?:lo|la|los|las)?\s+(?:a\s+\S+(?:\s+\S+)?\s+)?(?:de|del))\b"
    r"|(?:^|\s)(?:cancela\w*|cancel)\s+(?:(?:la|mi|el|my|the)\s+)?(?:suscripcion|subscripcion|subscription|membresia|membership|plan)"
    r"|(?:^|\s)(?:sali|salir|salite|salirme|abandon\w*|leave)\s+(?:(?:del|de|el|la|this|the)\s+)?"
    r"(?:servidor|server|grupo|group|canal|channel)\b"
    # Revisión seguimiento (owner rule: never restart; «restaura», «regresa», «revert» are order heads since uso real
    # v3 t2): putting the whole PC back — to factory state, to a restore point, an update or Windows rolled back —
    # wipes or restarts it.
    r"|(?:^|\s)(?:de\s+fabrica|factory\s+(?:settings|defaults|reset|state))\b"
    r"|(?:^|\s)(?:puntos?\s+de\s+restauracion|restore\s+points?|system\s+restore)\b"
    r"|(?:^|\s)(?:restaur\w*|restore|regres\w*|devuelve|revert\w*|revierte|roll\s*back|go\s+back)\s+"
    r"(?:(?:el|la|las|mi|a|the|my|to|this|ultim[ao]s?|last|latest)\s+)*"
    r"(?:sistema|pc|equipo|windows|computador\w*|computer|system|actualizacion\w*|updates?|"
    r"previous\s+(?:version|build)\s+of\s+windows)\b"
    r"|" + _FORMATTING_A_DRIVE
    + r"|(?:^|\s)(?:" + _SENDING_MONEY_OR_GIFT + r")"
)


def engine_can_try(
    text: str,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> bool:
    """Owner 2026-10-07 («que use el PC como yo»): a direct order about the PC that no operation serves is tried by
    the computer-use engine with the person's own words as its goal, instead of being told as a limit. Not for a
    question, a place outside this PC's world, a prohibition, or a destructive or paying goal."""

    from .dialogue import calls_off
    from .web import asks_for_information

    folded = fold(text)
    if not folded or len(folded) > 300 or "?" in text or "¿" in text:
        return False
    if calls_off(text):
        # Revisión adversarial 2 r19: «mejor déjalo así», «no, cancela eso» call off what was asked; nothing to try.
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
        or _DESTRUCTIVE_OR_PAYING.search(_order_without_its_dictated_text(folded))
    ):
        return False
    return free_form_arguments(text, application_names) is not None


def _order_without_its_dictated_text(folded: str) -> str:
    """Ronda 21 (pasada r18, v3-35 t2 «ponle: pagar la luz» after «crea una nota rapida nueva» stayed a note in BAXY's
    own store, kept from the engine as «paying»): what the engine must not try is read in the order alone, never in the
    text the person dictates for it to write — what follows a writing or putting verb's colon
    (``_dictated_text_opens``) and what that verb quotes as its object (``_DICTATING_BEFORE_QUOTE``). Contracaso: «en
    Steam pagá el juego», «borrá: el archivo» keep their verb in the order and stay out, and so does the quoted label of
    a click («haz clic en «Restablecer este PC»», revisión 2)."""

    opened = _dictated_text_opens(folded)
    order = folded
    if opened is not None:
        # Revisión 3 de la ronda 21 (seguridad: «en steam pon en el buscador: hades y despues compralo» cut everything
        # after the colon while the mission reader made «compralo» a step of its own, and «… pon en la barra: C:/Users
        # y despues borra la carpeta Documentos» handed the engine a goal of deleting): the dictated text runs to the
        # end only while nothing could part it from another clause. From the first joiner in it on (``_JOINER``: a
        # comma, «y», «y después», «luego», «then», a period), what follows is read as the order again, the same as
        # before the round; only an undoing or paying word there keeps it from the engine.
        joined = _JOINER.search(folded, opened.end())
        order = folded[: opened.end()] + ("" if joined is None else " " + folded[joined.start():])
    blanked = list(order)
    position = 0
    while position < len(order):
        closing = '"' if order[position] == '"' else _PAIRED_QUOTES.get(order[position])
        if closing is None:
            position += 1
            continue
        end = order.find(closing, position + 1)
        end = len(order) if end < 0 else end
        if _DICTATING_BEFORE_QUOTE.search(order[:position]):
            blanked[position + 1:end] = " " * (end - position - 1)
        position = end + 1
    return "".join(blanked)


# --------------------------------------------------- la página de inicio de un editor

# A start page's offer to create a new empty item: the words every application's interface uses for it («Documento en
# blanco», «Libro en blanco», «Blank workbook», «Presentación en blanco», «Empty project»). «Nuevo»/«new» alone is not
# one: «Nueva carpeta» creates on the disk, and the left column's «Nuevo» only opens a page of templates.
_BLANK_ITEM = re.compile(r"(?<!\w)(?:en blanco|blank|vaci[oa]|empty)(?!\w)")
# A file's own name carries its extension; an offer to create one never does.
_FILE_EXTENSION = re.compile(r"\w\.[a-z0-9]{2,5}(?!\w)")
# The lists of the person's own files on a start page: nothing in them is an offer to create.
_OWN_FILES_LIST = re.compile(
    r"^(?:(?:archivos|documentos|libros)\s+)?(?:recientes?|anclad[oa]s|favoritos|compartidos(?:\s+conmigo)?)$"
    r"|^(?:recent|pinned|favorites|favourites|shared(?:\s+with\s+me)?)(?:\s+(?:files|documents|items))?$"
    r"|^(?:abiert[oa]s\s+recientemente|recently\s+opened)$"
)
# The person names a file of their own: a name with its extension, or a file noun not said as a new or blank one
# («el documento informe», «my budget workbook»; «un documento nuevo», «a blank document» name none).
_FILE_NOUN = re.compile(
    r"(?<!\w)(?:archivo|fichero|file|documento|document|libro|workbook|planilla|hoja\s+de\s+calculo|spreadsheet|"
    r"presentacion|presentation)s?(?!\w)"
)
_NEW_OR_BLANK = re.compile(r"(?:nuev[oa]s?|new|en\s+blanco|blank|vaci[oa]s?|empty)")


def names_a_blank_item(name: object) -> bool:
    """A control named as a start page's offer to create a new empty item («Documento en blanco», «Blank workbook»):
    the blank word, at most six words, never a file's name with its extension."""

    folded = fold(name)
    return (
        bool(folded) and len(folded.split()) <= 6 and _BLANK_ITEM.search(folded) is not None
        and _FILE_EXTENSION.search(folded) is None
    )


# Revisión 3 de r24b (B2): the offer to create a whole blank document said as such: a whole document kind
# (``lexicon.WHOLE_DOCUMENT_NOUNS``) with its blank word, nothing else («documento en blanco», «blank workbook»).
_BLANK_DOCUMENT = re.compile(
    r"^(?:(?:un|una|el|la|a|an|the)\s+)?(?:(?:blank|empty)\s+(?P<before>\w+)|(?P<after>\w+)\s+(?:en blanco|vaci[oa]))$"
)


def names_a_blank_document(name: object) -> bool:
    """Revisión 3 de r24b (B2): the person names the offer to create a whole new empty document («documento en
    blanco», «libro en blanco», «presentación en blanco», «blank workbook»): an item in blank (``names_a_blank_item``)
    whose noun is a whole document an editor makes on its New command (``lexicon.WHOLE_DOCUMENT_NOUNS``). A part of a
    document or a folder's item in blank is none: «la carpeta vacía», «la página en blanco», «el diseño en blanco» or
    «la fila vacía» are things the window shows, to choose, never a document to create."""

    folded = " ".join(fold(name).split())
    found = _BLANK_DOCUMENT.match(folded)
    if found is None or not names_a_blank_item(folded):
        return False
    return (found.group("before") or found.group("after")) in lexicon.WHOLE_DOCUMENT_NOUNS


def names_own_files_list(name: object) -> bool:
    """A list of the person's own files on a start page («Recientes», «Compartidos conmigo», «Recent»)."""

    return _OWN_FILES_LIST.match(fold(name)) is not None


# A list that holds offers to create, never the person's files: «Plantillas», «Nueva», «New», «Templates».
_TEMPLATES_LIST = re.compile(r"(?<!\w)(?:plantillas?|templates?|nuev[oa]s?|new)(?!\w)")
# The columns of a file manager's content view («Tamaño», «Fecha de modificación», «Date modified», «Tipo»).
_FILE_COLUMN = re.compile(
    r"^(?:tamano|size|tipo|type|fecha(?:\s+de\s+(?:modificacion|creacion))?|date(?:\s+(?:modified|created))?|"
    r"modificado|modified)$"
)


def names_a_templates_list(name: object) -> bool:
    """A list, grid or tree named as the start page's offers to create («Plantillas», «Nueva», «Templates»)."""

    return _TEMPLATES_LIST.search(fold(name)) is not None


def names_a_file_column(name: object) -> bool:
    """A column header of a file manager's content view («Tamaño», «Fecha de modificación», «Date modified»)."""

    return _FILE_COLUMN.match(fold(name)) is not None


def _without_application(folded: str, application: object) -> str:
    """The request without the application's own name and its other names («explorador de archivos» is no file)."""

    app = fold(application).strip() if application else ""
    app = application_name_without_frame(app) or app
    if not app:
        return folded
    names = {app}
    for spoken, canonical in (*_CATALOG_NAME_ALIASES, *_EXTRA_ALIASES):
        if app in spoken or app in canonical:
            names.update(spoken, canonical)
    for name in sorted(names, key=len, reverse=True):
        folded = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", " ", folded)
    return folded


def names_a_file(objective: object, application: object = None) -> bool:
    """The person's words name a file of their own: a name with its extension, or a file noun that is not said as a
    new or blank one. Then a start page's blank item is never what they meant. The application's own name is no file
    («explorador de archivos»)."""

    folded = _without_application(fold(objective), application)
    if _FILE_EXTENSION.search(folded) is not None:
        return True
    for found in _FILE_NOUN.finditer(folded):
        before = folded[: found.start()].split()[-1:]
        after = folded[found.end():].split()[:2]
        if (before and _NEW_OR_BLANK.fullmatch(before[0])) or (
            after and (_NEW_OR_BLANK.fullmatch(after[0]) or _NEW_OR_BLANK.fullmatch(" ".join(after)))
        ):
            continue
        return True
    return False
