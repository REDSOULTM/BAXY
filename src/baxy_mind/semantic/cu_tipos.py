"""Las palabras de los tipos de tarea de computer use (v3 punto 2): formularios, diálogos de archivo, rutas de menú,
clic derecho, revelar un elemento de una lista y las colas que cierran un objetivo. Sólo datos y lecturas de palabras,
sin aplicaciones: ``missions`` las usa para leer el pedido (diag_tipos §2.A).
"""

from __future__ import annotations

import re
from typing import Callable

# Lo que sigue al nombre de lo que se elige, busca o revela y ya no es el nombre: un comentario («, pero no lo
# abras», «, nada más», «, solo seleccionado») o el modo de hacerlo («bajando en la lista», «desde el menú», «using
# the View menu»).
TARGET_TAIL = re.compile(
    r"\s*,\s*(?:pero|but|nada\s+mas|nothing\s+else|solo|only|just|sin|without|porfa|por\s+favor|please)\b.*$"
    r"|\s+(?:bajando|subiendo|desplazando(?:te)?|scrolling|desde|from\s+the|using|usando|via|con\s+el\s+clic|"
    r"with\s+the\s+right|porfa|por\s+favor|please)\b.*$"
)
# Lo que se busca es la consulta entera: «desde», «using», «sin» o «, pero en español» son parte de ella («vuelos desde
# Santiago», «recetas sin gluten»). Sólo se quita el modo de recorrer la lista dicho al final («, bajando en la lista»)
# y una aposición de una palabra que repite el nombre («la omega mayúscula, la Ω»).
SEARCH_TAIL = re.compile(
    r"(?:\s*,)?\s+(?:bajando|subiendo|desplazando(?:te)?|scrolling(?:\s+down)?)\s+(?:en|por|in|through|down)\b.*$"
)
SEARCH_APPOSITION = re.compile(r"\s*,\s*(?:el|la|los|las|the)\s+[^\s,]+\s*,?\s*$")
# v3-58 «busca cookies ahí en la configuración» typed «cookies ahi»: the adverb that points at the place where the search
# happens is no part of the query (a quoted query keeps it whole).
SEARCH_HERE = re.compile(r"(?<=\S)\s+(?:ah[ií]|all[ií]|ac[aá]|aqu[ií]|there|here)$", re.IGNORECASE)
# The preposition before it makes the adverb the query's own place («cerca de acá», «near here», «por aquí»).
SEARCH_HERE_OWN = re.compile(
    r"\b(?:de|desde|por|cerca|hasta|para|hacia|a|near|from|around|of|in|to|over|out)$", re.IGNORECASE
)
# Una aposición que repite el nombre con otras palabras («la omega mayúscula, la Ω»): el nombre es lo de antes.
TARGET_APPOSITION = re.compile(r"\s*,\s*(?:el|la|los|las|the|o\s+sea|i\.?e\.?)\s+\S.*$")

# Una pieza del pedido que no es una orden sino un comentario sobre ella: «nada más», «pero no lo abras eh», «solo
# seleccionado», «no desinstales nada», «quiero ver cuánto pesa», «porfa». Se deja fuera de la cadena.
REMARK = re.compile(
    r"^(?:nada\s+mas|nothing\s+else|eso\s+es\s+todo|that'?s\s+(?:it|all)|porfa|por\s+favor|please|eh|ok|dale)$"
    # «solo seleccionado», «just once», «solo eso»: «solo» with a participle or alone is a remark; before an order
    # («solo mostrame los instalados», «just sort by name») it is that order (``ONLY_ADVERB``).
    r"|^(?:pero\s+|but\s+)?(?:solo|solamente|only|just)(?:\s+(?:eso|esto|that|this|una\s+vez|once|"
    r"[a-z]+(?:ado|ada|ados|adas|ido|ida|idos|idas|ed)))?$"
    r"|^(?:pero|but)\s+(?:no|don'?t|do\s+not|not)\b.*$"
    r"|^no\s+(?:(?:me|te|lo|la|los|las|le|les)\s+)?[a-z]+(?:\s+(?:nada|ninguno|ninguna|eh|porfa))*$"
    r"|^(?:quiero|i\s+want\s+to)\s+(?:ver|saber|see|know)\b.*$"
    r"|^(?:todas|todos|all\s+of\s+them)\s+(?:de\s+una|at\s+once)$"
    # «usa el Abrir de Paint», «using the Save dialog»: the dialog the reading already opens.
    r"|^(?:usa|usando|using|use|con|with|desde|from)\s+(?:el|la|the|su|its)\s+(?:dialogo\s+(?:de\s+)?)?"
    r"(?:abrir|open|guardar(?:\s+como)?|save(?:\s+as)?)\b.*$"
)
# «solo» o «just» delante de una orden: la orden es lo que sigue.
ONLY_ADVERB = re.compile(r"^(?:pero\s+|but\s+)?(?:solo|solamente|only|just)\s+(?=\S)")
# Una pieza que prohíbe algo («no desinstales nada»): sólo se deja fuera cuando todos los pasos son lecturas con
# comprobación determinista, que nunca hacen otra cosa que la leída.
PROHIBITION = re.compile(r"^(?:pero\s+|but\s+)?(?:no|don'?t|do\s+not|never|nunca)\b")

# Cuántas veces: «dos veces», «twice», «3 veces», «three times».
_TIMES_WORDS = {"dos": 2, "tres": 3, "twice": 2, "two": 2, "three": 3, "thrice": 3}
REPETITION = re.compile(
    r"\s*\b(?:(?P<word>dos|tres|two|three)\s+(?:veces|times)|(?P<bare>twice|thrice)|(?P<digit>[2-5])\s+(?:veces|times))\b"
)
MAX_REPETITIONS = 3


def repetitions(found: re.Match[str]) -> int:
    word = found.group("word") or found.group("bare")
    count = _TIMES_WORDS[word] if word else int(found.group("digit"))
    return min(count, MAX_REPETITIONS)


# Un pedido que dicta texto: lo que se escribe, se busca, se anota o se recuerda. Su objeto nunca es una ruta de menú
# ni un formulario («escribí 5 > 3», «buscá mesa de 80 de ancho», «recordame que mide 3 de ancho»), y una palabra de
# orden dentro de él sin coma ni secuenciador es parte del texto («buscá Pinta y Colorea»).
DICTATION = re.compile(
    r"(?<![\w])(?:escribi|escribe|escribime|escriba|escribir|tipea|tipeame|teclea|type|write|"
    r"busca|buscar|buscame|buscale|busque|search(?:\s+for)?|search\s+up|look\s+(?:up|for)|find|encontra|encuentra|"
    r"recordame|recuerdame|recorda|recordar|remind(?:\s+me)?|anota|anotame|anotar|apunta|apuntame|note\s+down|"
    r"dicta|dictale|manda|mandale|envia|enviale|send|deci|decile|dile|say|tell)(?![\w])"
)

# Ruta de menú: «Archivo > Abrir», «View > Zoom > Zoom in»; lo que la introduce («desde el menú», «using», «en»).
ROUTE_LEAD = re.compile(
    r"^(?P<before>.*?)(?:\s*,\s*|\s+|^)(?:(?:desde|from|using|usando|via|por|con|with|en|in|a|al|to|go\s+to|anda\s+a|ve\s+a)\s+)?"
    r"(?:(?:el|la|the)\s+)?(?:(?:menu|menus)\s+(?:de\s+)?)?$"
)
# Lo que cierra la última pieza de una ruta («Abrir del Bloc de notas porfa»).
ROUTE_END = re.compile(
    r"\s+(?:del|de\s+la|of\s+the|porfa|por\s+favor|please)(?:\s+.*)?$|\s+(?:in|en|y|and)\s+(?:el\s+|la\s+|the\s+)?\S+.*$"
    r"|\s*[,;.].*$"
)
# «el menú Imagen, Girar, Girar a la derecha»: el menú y sus piezas separadas por comas.
MENU_LIST = re.compile(r"(?:^|\s)(?:el\s+|the\s+)?(?:menu|menus)\s+(?P<list>[^,;]{1,40}(?:\s*,\s*[^,;]{1,40}){1,4})$")
# «using the View menu», «desde el menú Ver»: el menú nombrado como medio, que la ruta ya recorre.
MENU_MEANS = re.compile(
    r"\s*,?\s*\b(?:desde|from|using|usando|via|con|with|en|in)\s+(?:el\s+|la\s+|the\s+)?"
    r"(?:(?:menu\s+(?:de\s+)?(?P<es>[^\s,]+(?:\s+[^\s,]+)?))|(?P<en>[^\s,]+)\s+menu)\b"
)
ROUTE_PIECE_WORDS = 5
# Lo que introduce una ruta de por sí («desde Archivo > Abrir», «using View > Zoom», «el menú Imagen > Girar»): una
# ruta sin esto empieza la cláusula o va tras una coma; «a», «en» o «de» sólo la introducen tras ir o hacer clic.
ROUTE_INTRO = frozenset({"desde", "from", "using", "usando", "via", "menu", "menus"})
ROUTE_INTRO_AFTER_GOING = frozenset({"a", "al", "to", "en", "in", "on"})
# Ronda 21 (v3-67 «open library > microsoft > windows > defrag»): abrir o desplegar una ruta la introduce como ir a
# ella; el verbo no es parte de la primera pieza. Plegados (sin tildes).
ROUTE_OPEN_VERBS = frozenset({
    "open", "abre", "abri", "abrir", "abrime", "abrile", "expand", "expandi", "expande", "expandir", "despliega",
    "desplega", "desplegar", "despliegame", "desplegame", "unfold",
})

# Clic derecho: «haceme clic derecho en notas.txt», «con el clic derecho en un espacio vacío», «right-click X».
RIGHT_CLICK = re.compile(
    r"^(?P<means>(?:con|using|with|usando)\s+(?:el|un|a|the)?\s*)?(?:(?:haz|hace|haceme|hazme|hacer|da|dale|daale|"
    r"do)\s+(?:un\s+|a\s+)?)?(?:clic|click|clickeo)\s+(?:derecho|secundario)\s+(?:en|sobre|a)\s+(?P<what>\S.*)$"
    r"|^(?P<emeans>(?:using|with)\s+(?:a\s+|the\s+)?)?right[\s-]?click(?:\s+on)?\s+(?P<ewhat>\S.*)$"
)
# Un espacio vacío de una lista: el menú del contenedor, no de un elemento.
EMPTY_SPACE = re.compile(r"^(?:un|una|el|la|a|an|the)?\s*(?:espacio|lugar|zona|parte|area|space|spot)\s+(?:vaci[oa]|en\s+blanco|empty|blank)$"
                         r"|^(?:empty|blank)\s+(?:space|spot|area)$")
EMPTY_SPACE_TARGET = "espacio vacio"

# Revelar: «bajá en la lista hasta el Bloc de notas», «scroll down to Times New Roman».
REVEAL = re.compile(
    r"^(?:baja|bajale|bajar|desplazate|desplaza|desplazar|deslizate|recorre|scroll(?:\s+down)?|scroll\s+through|"
    r"go\s+down|move\s+down)(?:\s+(?:en|por|in|through)\s+(?:(?:el|la|los|las|the)\s+)?[a-z]+(?:\s+de\s+[a-z]+)?)?"
    r"\s+(?:hasta|to|until|till)\s+(?:(?:que\s+(?:veas|aparezca)|you\s+see|(?:it\s+)?shows?)\s+)?"
    r"(?:(?:el|la|los|las|the)\s+)?(?P<what>\S.*)$"
)
# Estabilización L4 (en vivo t-scroll-2 «búscame la omega mayúscula, la Ω, bajando en la lista»: tecleó «omega
# mayúscula» en el buscador de la ventana): lo buscado bajando por una lista («bajando en la lista», «scrolling down»)
# se revela como «bajá hasta X», nunca se teclea en un buscador. Una aposición tras la coma («, la Ω») no es el nombre.
LOOKED_FOR_BY_SCROLLING = re.compile(
    r"^(?:busca|buscar|buscame|buscale|busque|encontra|encontrame|encuentra|encontrar|ubica|ubicame|localiza|"
    r"search(?:\s+for)?|find(?:\s+me)?|look\s+for|locate)\s+(?:(?:el|la|los|las|the)\s+)?(?P<what>[^,]+?)"
    r"(?:\s*,[^,]*)?,?\s+(?:bajando|desplazandote|deslizando|scrolleando|(?:by\s+)?scrolling(?:\s+down)?)\b"
)
# «abrí su página», «open its page»: abrir lo que el paso anterior reveló.
OPEN_ITS_PAGE = re.compile(r"^(?:abri|abre|abrir|open)\s+(?:su|its|their)\s+(?:pagina|ficha|page|entry)$")

# Formularios: los campos que la gente nombra y los nombres que el campo puede llevar en la pantalla.
FIELD_NAMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ancho", ("ancho", "width", "horizontal")),
    ("alto", ("alto", "height", "vertical")),
    ("tamano", ("tamano", "size", "tamano de fuente", "font size")),
    ("columnas", ("columnas", "columns", "numero de columnas", "number of columns")),
    ("filas", ("filas", "rows", "numero de filas", "number of rows")),
    ("fuente", ("fuente", "font")),
    ("buscar", ("buscar", "find what", "find", "buscar que")),
    ("reemplazar", ("reemplazar con", "replace with", "reemplazar", "replace")),
)
# El cuadro donde la ventana busca («el buscador de chats», «the search box»): el proveedor lo reconoce en la vista por
# lo que es (un campo de búsqueda, nunca la barra de direcciones), no por una palabra suelta de su nombre («Research»).
SEARCH_FIELD = "busqueda"
_FIELD_WORD = {
    "ancho": "ancho", "width": "ancho", "wide": "ancho",
    "alto": "alto", "altura": "alto", "height": "alto", "high": "alto", "tall": "alto",
    "tamano": "tamano", "size": "tamano",
    "columnas": "columnas", "columna": "columnas", "columns": "columnas", "column": "columnas",
    "filas": "filas", "fila": "filas", "rows": "filas", "row": "filas",
}
FIELD_WORDS = r"(?:" + "|".join(sorted(_FIELD_WORD, key=len, reverse=True)) + r")"


def field_key(word: str) -> str | None:
    return _FIELD_WORD.get(word)


def field_names(key: str) -> tuple[str, ...]:
    return next((names for field, names in FIELD_NAMES if field == key), (key,))


# Un formulario es una unidad (ronda 20b, pasada r18 t-long-3: con «Mantener la relación de aspecto» encendido, poner
# Vertical en 500 recalculó Horizontal a 177 y el final contó 500 por 500). Cada campo después del primero se cumple sólo
# con los anteriores todavía en su valor (missions._form_reads); un campo que la ventana cambió al escribir otro se
# vuelve a poner una vez, antes con el vínculo apagado si la vista lo muestra encendido (cu_forms._form_unit_step).
# LINK_LOCK_NAMES: los nombres (plegados) del interruptor que ata dos campos de un par. LINK_KEPT: el pedido que dice
# mantener ese vínculo («800 por 600 manteniendo la proporción»): el interruptor no se apaga, pero los campos se atan
# igual (revisión 1, bloqueante 3: con el vínculo encendido cada campo recalcula el otro, y sólo el formulario entero
# dice si los dos valores caben; si no caben, la misión para con linked_fields en vez de aceptar).
LINK_LOCK_NAMES = (
    "mantener la relacion de aspecto", "mantener relacion de aspecto", "mantener las proporciones",
    "mantener proporciones", "bloquear proporciones", "bloquear relacion de aspecto", "maintain aspect ratio",
    "keep aspect ratio", "lock aspect ratio", "constrain proportions",
)
LINK_KEPT = re.compile(
    r"\b(?:manten\w*|conserv\w*|respet\w*|sin\s+(?:perder|cambiar|deformar)|keep\w*|maintain\w*|preserv\w*)\s+"
    r"(?:(?:la|las|el|su|sus|the|its)\s+)?(?:relacion\s+de\s+aspecto|proporcion\w*|aspect\s+ratio|proportions?)\b"
)
# La nota del paso que vuelve a poner un campo cambiado (para la traza y el modelo, nunca para la persona).
LINKED_NOTE = "{changed} cambió a {shown} al escribir {typed}: campos vinculados"
LINK_OFF_NOTE = "{changed} cambió a {shown} al escribir {typed}: campos vinculados; apago {lock}"
# Revisión 2 (bloqueante 1): el pedido fija los campos que el vínculo ata; se apaga antes de escribir el primero.
LINK_FIRST_NOTE = "el pedido fija {fields}: apago {lock} antes de escribir"


def keeps_link(clause: str) -> bool:
    """«cambiá el tamaño a 500 por 500 manteniendo la proporción»: the request keeps the link between the fields (folded
    text): the switch that ties them is never switched off."""

    return LINK_KEPT.search(clause) is not None


# Un valor numérico se sostiene en un campo sólo con límites de dígito (revisión 1, bloqueante 4: con el vínculo
# encendido, alto 500 llevó el ancho de una imagen de 3000×1000 a 1500, y «1500» contenía «500»): «500 px» y «500px» lo
# sostienen, «1500», «500,5» y «2.500» no. Un valor con letras se sostiene por contención, como el átomo ``value:`` del
# shell (ComputerUseSuccessCheck.ValueHolds). Revisión 2 (bloqueante 2): los ceros decimales que la ventana pone al
# formatear el número («5,00 cm», «500,00», «500.0 px») lo sostienen, como lo sostenía la contención.
_NUMERIC_VALUE = re.compile(r"[0-9]+(?:[.,][0-9]+)?")


def value_holds(shown: str, value: str) -> bool:
    """Whether a field's value (folded) holds ``value`` (folded): a number within digit bounds, with the decimal zeros
    the window formats it with («5» in «5,00 cm», «12,5» in «12,50»), a text contained."""

    number = value.strip()
    if _NUMERIC_VALUE.fullmatch(number):
        zeros = "0*" if re.search(r"[.,]", number) else "(?:[.,]0+)?"
        return re.search(
            rf"(?<![0-9])(?<![0-9][.,]){re.escape(number)}{zeros}(?![.,]?[0-9])", shown) is not None
    return value in shown


# «800 de ancho», «tamaño 20», «4 columns», «width 800».
FIELD_PAIRS = (
    re.compile(rf"(?<![\w.])(?P<value>\d+(?:[.,]\d+)?)\s+(?:de|of|in)\s+(?P<field>{FIELD_WORDS})\b"),
    re.compile(rf"\b(?P<field>{FIELD_WORDS})\s+(?:(?:de|of|a|to|en|=|:)\s+)?(?P<value>\d+(?:[.,]\d+)?)(?![\w.])"),
    re.compile(rf"(?<![\w.])(?P<value>\d+(?:[.,]\d+)?)\s+(?P<field>{FIELD_WORDS})\b"),
)
# «500 por 500 píxeles», «500 by 500 pixels»: ancho por alto cuando el pedido habla de un tamaño.
DIMENSIONS = re.compile(r"(?<![\w.])(?P<width>\d+)\s*(?:x|×|by|por)\s*(?P<height>\d+)(?![\w.])")
SIZE_WORDS = re.compile(r"\b(?:tamano|size|resize|redimensiona\w*|cambia\w*\s+(?:el\s+)?tamano|lienzo|canvas|dimensiones|dimensions)\b")
# La unidad de un formulario de tamaño («en píxeles», «500 por 500 pixels»): una opción del diálogo que se elige antes
# de los valores (un diálogo de tamaño abre en porcentaje, y 800 % no es 800 píxeles).
UNIT = re.compile(r"(?:\b(?:en|in)\s+|(?<=\d)\s*)(?P<unit>pixeles|pixels|pixel|px|porcentaje|percentage|percent)\b")
UNIT_NAMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pixeles", ("pixeles", "pixels")), ("porcentaje", ("porcentaje", "percentage")),
)
_UNIT_KEY = {"pixeles": "pixeles", "pixels": "pixeles", "pixel": "pixeles", "px": "pixeles", "porcentaje": "porcentaje",
             "percentage": "porcentaje", "percent": "porcentaje"}


def unit_names(word: str) -> tuple[str, ...]:
    key = _UNIT_KEY.get(word, word)
    return next((names for unit, names in UNIT_NAMES if unit == key), (key,))


# Estilos que se encienden en un diálogo de formato («en cursiva», «bold»).
STYLE_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cursiva", ("cursiva", "italic")), ("negrita", ("negrita", "bold")), ("subrayado", ("subrayado", "underline")),
)
STYLE = re.compile(r"\b(?:en\s+)?(?P<style>cursiva|italica|negrita|subrayad[oa]|italic|italics|bold|underlined?)\b")
_STYLE_KEY = {"cursiva": "cursiva", "italica": "cursiva", "italic": "cursiva", "italics": "cursiva", "negrita": "negrita",
              "bold": "negrita", "subrayado": "subrayado", "subrayada": "subrayado", "underline": "subrayado",
              "underlined": "subrayado"}


def style_key(word: str) -> str:
    return _STYLE_KEY.get(word, word)


def style_names(key: str) -> tuple[str, ...]:
    return next((names for style, names in STYLE_WORDS if style == key), (key,))


# Una fuente nombrada en un pedido que habla de la fuente («en Arial», «in Times New Roman»).
FONT_CONTEXT = re.compile(r"\b(?:fuente|font|tipo\s+de\s+letra|tipografia|typeface)\b")
FONT_NAME = re.compile(r"(?:^|,\s*|\s)(?:en|in)\s+(?P<font>[a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*){0,2}?)(?=\s*(?:,|$|\s+(?:y|and|tamano|size)\b))")
# «reemplazá todas las «casa» por «hogar»», «replace cat with dog».
REPLACE = re.compile(
    r"^(?:reemplaza|reemplazar|reemplace|reemplazame|cambia|cambiar|sustitui|sustituye|replace|swap)\s+"
    r"(?:(?P<all>todas|todos|all)\s+)?(?:(?:las|los|el|la|the)\s+)?(?:(?:palabras?|words?|apariciones\s+de)\s+)?"
    r"[\"'«“](?P<old>[^\"'»”]{1,80})[\"'»”]\s+(?:por|con|with|by|for)\s+[\"'«“](?P<new>[^\"'»”]{1,80})[\"'»”]"
    r"(?P<rest>.*)$"
)
ALL_WORDS = re.compile(r"\b(?:todas|todos|todo|all|every|everything)\b")
# Los botones que cierran un diálogo aceptando lo puesto, por el acto.
DEFAULT_BUTTONS = ("aceptar", "ok")
REPLACE_ALL_BUTTONS = ("reemplazar todo", "replace all")
REPLACE_ONE_BUTTONS = ("reemplazar", "replace")
SAVE_BUTTONS = ("guardar", "save")
OPEN_BUTTONS = ("abrir", "open")
FILE_NAME_FIELD = ("nombre de archivo", "nombre", "file name")

# El lugar donde se escribe, dicho detrás del texto (cu-v3 texto-webview, wa-1 «escribí baxyprueba en el buscador de
# chats» escribió la frase entera). El texto es lo de antes. Dos clases de lugar, porque la frase sola no distingue un
# campo de un lugar del mundo («nos vemos en el campo de fútbol», «te espero en la barra del hotel», «see you on the
# soccer field»):
# * el cuadro de búsqueda («en el buscador de chats», «en la barra de búsqueda», «in the search box», y su spanglish
#   «en el search box», «in the buscador»): nombra un campo de la pantalla por sí mismo y se separa al leer;
# * un campo por su nombre («en el campo Nombre», «in the Name field»): se separa sólo donde la vista tiene un campo
#   escribible con ese nombre (lo hace el proveedor); sin él, la frase entera es el texto.
_TYPE_PLACE_HEAD = r"^(?P<text>\S.*?)\s+(?:en|dentro\s+de|in|into|inside|on)\s+(?:(?:el|la|the|this|that|ese|esa|este|esta)\s+)?"
_PLACE_NOUN = r"(?:campo|casilla|cuadro|recuadro|caja|barra)"
_PLACE_WORDS = r"[a-z0-9]+(?:\s+[a-z0-9]+){0,2}"
_PLACE_END = r"[\s.!?]*$"
# «buscador (de chats)», «barra/campo/cuadro de (la) búsqueda», «(chat) search box», «searchbox»: nunca «la búsqueda» ni
# «the search» solos (sin el cuadro que la hace un campo: «type stay on the search» es del texto).
SEARCH_PLACE = re.compile(
    _TYPE_PLACE_HEAD
    + r"(?:buscador|" + _PLACE_NOUN + r"\s+de\s+(?:la\s+)?busqueda)(?:\s+(?:de|del|para)\s+" + _PLACE_WORDS + r")?"
    + _PLACE_END
    + r"|"
    + _TYPE_PLACE_HEAD.replace("?P<text>", "?P<english>")
    + r"(?:[a-z0-9]+\s+){0,2}(?:search\s*(?:box|bar|field|input)|searchbox|searchbar)" + _PLACE_END
)
# «campo (de|llamado) Nombre», «Name field», «field named Name»: el nombre que la vista tiene que mostrar en un campo.
NAMED_PLACE = (
    re.compile(
        _TYPE_PLACE_HEAD + _PLACE_NOUN
        + r"(?:\s+(?:de|del|para|llamad[oa]))?(?:\s+(?:la|el|las|los))?\s+(?P<name>" + _PLACE_WORDS + r")" + _PLACE_END
    ),
    re.compile(_TYPE_PLACE_HEAD + r"(?P<name>" + _PLACE_WORDS + r")\s+(?:field|box|textbox|input)" + _PLACE_END),
    re.compile(_TYPE_PLACE_HEAD + r"(?:field|box|textbox|input)\s+(?:named|called|labeled)\s+(?P<name>" + _PLACE_WORDS + r")" + _PLACE_END),
)


def split_typing_place(text: str) -> tuple[str, str] | None:
    """«baxyprueba en el buscador de chats» → («baxyprueba», ``SEARCH_FIELD``): the text to type and the search box
    the place after it names; None when the place is no search box (a named field is grounded in the view by the
    provider, ``named_typing_place``)."""

    found = SEARCH_PLACE.match(text.strip())
    if found is None:
        return None
    typed = (found.group("text") or found.group("english") or "").strip(" ,;:")
    return (typed, SEARCH_FIELD) if typed else None


def named_typing_place(text: str) -> tuple[str, str] | None:
    """«hola en el campo nombre» → («hola», «nombre»), «hi in the Name field» → («hi», «name»): the text and the name
    of the field the place after it names, still to be found in the view (``computer_use`` types the whole text when
    no writable field of the view carries that name: «nos vemos en el campo de fútbol»)."""

    for reading in NAMED_PLACE:
        found = reading.match(text.strip())
        if found is None:
            continue
        typed = found.group("text").strip(" ,;:")
        if typed:
            return typed, found.group("name")
    return None

# Guardar y abrir por el diálogo: «guardá esto como N en C», «save this drawing as N in C», «abrí N que está en C».
SAVE_AS = re.compile(
    r"^(?:guarda|guardar|guardalo|guardala|guardame|guarde|save|save\s+it|save\s+this(?:\s+[a-z]+)?|"
    r"guarda\s+(?:esto|este\s+[a-z]+|esta\s+[a-z]+|el\s+[a-z]+|la\s+[a-z]+))"
    r"(?:\s+(?:esto|this|it))?\s+(?:como|as)\s+(?P<name>[^\s,;]+(?:\s+[^\s,;]+){0,3}?)"
    r"(?:\s+(?:en|in|inside|dentro\s+de)\s+(?P<place>\S.*?))?[\s.!?]*$"
)
OPEN_FILE = re.compile(
    r"^(?:abri|abre|abreme|abrime|abrir|abra|open)\s+(?:(?:el|la|the)\s+)?(?:(?:archivo|fichero|foto|imagen|documento|"
    r"file|photo|picture|image|document)\s+)?(?P<name>[^\s,;\\/]+\.[a-z0-9]{2,5})"
    r"(?:\s+(?:en|in)\s+(?P<app>[a-z][a-z0-9 ]{1,30}?))?"
    r"(?:\s*,?\s*(?:que\s+esta|que\s+se\s+encuentra|esta|which\s+is|that'?s|it'?s)?\s+(?:en|in|de|del|from)\s+"
    r"(?P<place>\S.*?))?[\s.!?]*$"
)
# v3 ronda 3 (v3-17 «… de la carpeta baxy-prueba-v3»): a folder of the person's named by its own name, no known one.
NAMED_FOLDER = re.compile(
    r"^(?:(?:la|el|mi|esa|the|my|that)\s+)?(?:carpeta|folder)\s+(?P<folder>[^\s\\/,;:*?\"<>|]+)$"
    r"|^(?:(?:la|el|mi|the|my)\s+)?(?P<before>[^\s\\/,;:*?\"<>|]+)\s+(?:folder|carpeta)$"
)
# Ronda 20b (v3-50 «… que está en baxy-prueba-v3»): a place of one word, which may be a folder's own name.
FOLDER_TOKEN = re.compile(r"[^\s\\/,;:*?\"<>|]+")
# Las carpetas conocidas, por su nombre en los dos idiomas.
KNOWN_FOLDERS = {
    "documentos": "documents", "documents": "documents", "mis documentos": "documents", "my documents": "documents",
    "escritorio": "desktop", "desktop": "desktop", "descargas": "downloads", "downloads": "downloads",
    "imagenes": "pictures", "pictures": "pictures", "musica": "music", "music": "music", "videos": "videos",
}
# «en Documentos, en la carpeta baxy-prueba-v3», «in Documents\baxy», «in the X folder inside Documents».
PLACE_FOLDER = re.compile(
    r"^(?:(?:la|el|mi|the|my)\s+)?(?:carpeta\s+|folder\s+)?(?P<known>mis\s+documentos|my\s+documents|documentos|documents|"
    r"escritorio|desktop|descargas|downloads|imagenes|pictures|musica|music|videos)"
    r"(?P<sub>(?:\s*[\\/]\s*[^\s\\/,;]+)*)"
    r"(?:\s*,?\s*(?:en|in|dentro\s+de|inside)\s+(?:la|el|the)\s+(?:carpeta|folder)\s+(?P<folder>[^\s,;]+))?"
    r"(?:\s+(?:folder|carpeta))?$"
)
# Abrir cada diálogo es un sub-objetivo con su comprobación (el campo del diálogo a la vista), no un atajo fijo: el
# atajo cambia con la aplicación (Guardar como es F12 en un procesador de textos, donde Ctrl+Shift+S abre los estilos)
# y el modelo usa el menú o la tecla que la ventana muestre. Una ruta de menú dicha lo reemplaza.
SAVE_AS_OPENER = "abrir el dialogo de guardar como"
REPLACE_OPENER = "abrir el dialogo de reemplazar"
# cu-v3-abrir-archivo (r9 v3-15, v3-17, v3-18): abrir un archivo nombrado no pasa por el diálogo de la ventana (una
# galería como la de Fotos no tiene ninguno): el sub-objetivo «abrir el archivo <ruta o nombre>» es el file.open tipado,
# con la aplicación de la misión, por el shell. Sólo una ruta de menú dicha («desde Archivo > Abrir») usa el diálogo.
OPEN_FILE_GOAL = "abrir el archivo "
# Review of cu-v3-abrir-archivo (finding 2): the check atom that asks for the sub-goal's own file.open, done.
FILE_OPENED = "stepDone:file.open"
# Review (finding 5, t-file-4 «…, usa el Abrir de Paint»): a means that names the window's own Open dialog asks for
# it: the dialog opened (its key or menu, as the window shows), its name field and its button.
OPEN_OPENER = "abrir el dialogo de abrir"
OPEN_DIALOG_MEANS = re.compile(
    r"^(?:usa|usar|use|usando|using|con|with|desde|from|via|por)\s+(?:el\s+|la\s+|the\s+|its\s+|su\s+)?"
    r"(?:(?:dialogo|cuadro|ventana)\s+(?:de\s+)?)?(?:abrir|open)(?:\s+dialog)?"
    r"(?:\s+(?:de|del|of|in|en)\s+(?:el\s+|la\s+|the\s+)?[a-z][a-z0-9 ]{0,30})?$"
)

# Una pieza de un pedido largo que dice una orden que ningún lector lee («ponelo en negrita», «centralo», «draw a red
# rectangle», «zoom in»): pasa a sub-objetivo libre de la cadena (diag_tipos §2.A7). Una orden empieza por un verbo:
# los verbos de hacer que la gente usa con la pantalla y no tienen lector propio.
ORDER_HEADS = frozenset({
    "zoom", "draw", "dibuja", "dibujar", "traza", "trazar", "insert", "inserta", "insertar", "agrega", "agregar",
    "anade", "resize", "redimensiona", "rotate", "gira", "girar", "voltea", "flip", "sort", "ordena", "ordenar",
    "center", "centre", "centra", "centrar", "alinea", "align", "drag", "arrastra", "arrastrar", "lleva", "llevar",
    "close", "cierra", "cerrar", "print", "imprimi", "imprime", "imprimir", "fill", "rellena", "pinta", "paint",
    "colorea", "make", "set", "pon", "pone", "ponme", "poneme", "ponele", "sube", "subi", "subele", "baja", "bajale",
    "cambia", "cambiale", "change", "add", "aplica", "apply", "marca", "check", "mueve", "move", "corta", "cut",
    "recorta", "crop", "copia", "pega", "duplica", "duplicate", "agranda", "achica", "enlarge", "shrink",
    "aumenta", "reduce", "increase", "decrease", "ajusta", "adjust", "usa", "use", "crea", "create", "new",
    "abri", "abre", "open", "guarda", "save", "selecciona", "select", "elegi", "elige", "choose", "pick",
    "mostra", "mostrame", "muestra", "muestrame", "show", "filtra", "filter",
    # v3 destino (v3-40 «split the pane vertical», «y renombra la tab a pruebas»).
    "split", "divide", "dividi", "rename", "renombra", "renombrar",
    # Uso real v3 t2 (c04 «regresa la escala a 100»): volver algo a como estaba también es hacer en la pantalla.
    "regresa", "devuelve", "restaura", "restore", "revert", "revierte",
    # Ronda 21 (v3-68 «en el programador de tareas esconde el panel de acciones de la derecha»): esconder, plegar y
    # desplegar algo de la ventana también es hacer en la pantalla.
    "esconde", "escondeme", "oculta", "ocultame", "hide", "contrae", "colapsa", "collapse", "pliega", "expandi",
    "expande", "expand", "despliega",
})

# Lo que se dice delante de la orden de un seguimiento sin ser parte de ella (uso real v3 t2, c04): un deíctico del
# lugar donde ya se está («ahí ponle la escala en 125», «there, set it to 125») o el arranque de una corrección («no
# espera …», «no, …», «wait, …»). Un «no» sólo cuenta seguido de una pausa o de otro arranque: «no la cierres» es una
# prohibición, nunca una orden.
FOLLOW_UP_PREAMBLE = re.compile(
    r"^(?:(?:ahi|alli|aca|aqui|there|here|espera|esperate|pera|perate|wait|hold\s+on|oops|ups|perdon|sorry|"
    r"mejor|actually|bro|man|che|wey|guey|loco)(?:\s+mismo)?(?![a-z0-9])[\s,;:.!]*"
    r"|no(?:\s*[,;.!]+\s*|\s+(?=(?:espera|esperate|pera|perate|wait|bro|man|che|wey|guey|loco|mejor|perdon)"
    r"(?![a-z0-9]))))+"
)
# Las palabras con que nunca empieza una orden: artículos, pronombres, preposiciones, conjunciones, preguntas.
NOT_ORDER_HEADS = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas", "the", "a", "an", "que", "si", "no", "pero", "porque",
    "cuando", "donde", "como", "cual", "quien", "what", "when", "where", "how", "why", "who", "which", "is", "are",
    "es", "esta", "son", "hay", "there", "it", "i", "yo", "tengo", "have", "quiero", "want", "me", "te", "se", "lo",
    "le", "de", "del", "en", "in", "on", "con", "with", "por", "para", "for", "to", "y", "and", "o", "or", "mi",
    "tu", "su", "my", "your", "this", "that", "esto", "eso", "ese", "esa", "este", "ok", "dale", "gracias", "thanks",
})

# Ronda 21, destino por contenido (pasada r18: t-menu-4, t-form-4, t-drag-2): lo que el pedido nombra de la ventana donde
# ocurre, cuando no nombra la aplicación. Un menú, un cuadro de diálogo, un panel o una pestaña por su nombre («desde el
# menú Imagen > Girar», «desde el cuadro de diálogo de Fuente», «en el panel de miniaturas», «from the Format menu»);
# la ruta de un menú da cada pieza. Sobre el texto plegado (minúsculas, sin acentos).
REFERENT_CONTAINER = re.compile(
    r"(?<![a-z0-9])(?:menu|cuadro\s+de\s+dialogo|dialogo|panel|pestana|ficha)\s+(?:de\s+(?:la\s+|el\s+|los\s+|las\s+)?)?"
    r"(?P<name>[a-z0-9]+(?:\s*>\s*[a-z0-9]+)*)"
    r"|(?<![a-z0-9])the\s+(?P<en>[a-z0-9]+(?:\s*>\s*[a-z0-9]+)*)\s+(?:menu|dialog(?:\s+box)?|pane|panel|tab)(?![a-z0-9])"
)
# Lo que sigue a «menú», «panel»… y no es su nombre: un artículo, un adjetivo de tipo o de estado («el menú contextual»,
# «el panel lateral», «una pestaña nueva», «la pestaña actual»), un deíctico, o el menú Inicio, que no es de ninguna
# ventana.
REFERENT_NOT_A_NAME = frozenset({
    "la", "el", "los", "las", "un", "una", "the", "a", "an", "de", "del", "y", "o", "and", "or", "que", "con", "en",
    "contextual", "emergente", "desplegable", "lateral", "principal", "superior", "inferior", "izquierdo", "derecho",
    "este", "esta", "ese", "esa", "this", "that", "context", "side", "main", "top", "bottom", "left", "right", "pop",
    "popup", "dropdown", "inicio", "start", "control", "nueva", "nuevo", "nuevas", "nuevos", "new", "actual", "current",
    "abierta", "abierto", "open", "activa", "activo", "active", "siguiente", "next", "anterior", "previous", "otra", "otro",
    "other", "privada", "private", "incognito", "primera", "primer", "first", "ultima", "ultimo", "last",
}) | frozenset({
    # Revisión 3 de r21 (B2): una palabra de posición o de relación, en sus dos géneros y en plural, o una preposición,
    # no es el nombre de nada («el panel de la izquierda», «la pestaña de la derecha», «la pestaña de al lado», «el
    # menú de arriba»): dice dónde está, no cómo se llama.
    "izquierda", "derecha", "izquierdas", "derechas", "izquierdos", "derechos", "al", "a", "lado", "costado",
    "arriba", "abajo", "encima", "debajo", "delante", "detras", "adelante", "atras", "dentro", "fuera", "afuera",
    "adentro", "cerca", "lejos", "junto", "centro", "central", "medio", "fondo", "frente", "alli", "ahi", "aqui", "aca",
    "por", "para", "desde", "hacia", "hasta", "sobre", "entre", "segun", "sin", "como", "donde", "cual",
    "superiores", "inferiores", "laterales", "principales", "siguientes", "anteriores", "otras", "otros", "primeras",
    "primeros", "ultimas", "ultimos", "segunda", "segundo", "tercera", "tercero", "proxima", "proximo", "previa",
    "previo", "mismo", "misma", "su", "sus", "mi", "mis", "tu", "tus",
    "on", "in", "at", "of", "to", "from", "by", "for", "with", "beside", "near", "next", "above", "below", "under",
    "over", "upper", "lower", "middle", "center", "centre", "same", "its", "my", "your", "second", "third",
    "leftmost", "rightmost", "adjacent", "neighbouring", "neighboring",
})
# Una selección del contenido de la ventana: «el texto seleccionado», «lo seleccionado», «the selected text», «la
# selección»; está en una ventana que muestra un documento o un campo.
REFERENT_SELECTION = re.compile(r"(?<![a-z0-9])(?:seleccionad[oa]s?|seleccion|selected|selection)(?![a-z0-9])")
# Un nombre entre comillas («Tres», "Tres") dicho junto a lo anterior: otro nombre que la ventana muestra.
REFERENT_QUOTED = re.compile(r"[«\"“](?P<name>[^«»\"“”]{1,40})[»\"”]")


def referent_names(folded: str, said_as_verb: Callable[[str], bool] | None = None) -> tuple[str, ...]:
    """Los nombres de un menú, un cuadro de diálogo, un panel o una pestaña que dice el texto plegado, en orden, sin
    repetir; cada pieza de una ruta de menú («imagen > girar») por separado.

    Revisión 3 de r21 (B2): la palabra que sigue a «menú», «panel», «pestaña»… y que ``said_as_verb`` lee como la orden
    que empieza ahí («en el diálogo escribí hola») no es su nombre; sólo en la forma que pone el nombre detrás del
    contenedor: en «the Insert menu» el nombre va delante y ninguna orden empieza en él."""

    return tuple(name for name, _dialog in referent_names_by_container(folded, said_as_verb))


# Ronda 24 (pasada r23 t-form-4): el contenedor que es un cuadro de diálogo («el cuadro de diálogo de Fuente», «the Font
# dialog box»): un diálogo todavía cerrado no se ve en ninguna ventana, así que su nombre no es lo que la ventana ya
# muestra sino un lugar que la misión abre en su camino.
REFERENT_DIALOG = re.compile(r"(?<![a-z0-9])(?:cuadro\s+de\s+dialogo|dialogo|dialog)(?![a-z0-9])")


def referent_names_by_container(
    folded: str, said_as_verb: Callable[[str], bool] | None = None
) -> tuple[tuple[str, bool], ...]:
    """Ronda 24: ``referent_names`` con el tipo de su contenedor — cada nombre y si lo nombra un cuadro de diálogo
    (``REFERENT_DIALOG``) o un menú, un panel o una pestaña. Un nombre dicho por los dos queda con el primero."""

    names: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for found in REFERENT_CONTAINER.finditer(folded):
        after = found.group("name")
        route = after or found.group("en") or ""
        dialog = REFERENT_DIALOG.search(found.group(0)) is not None
        for piece in route.split(">"):
            name = " ".join(piece.split())
            if not name or name in REFERENT_NOT_A_NAME or name in seen:
                continue
            if after and said_as_verb is not None and said_as_verb(name):
                continue
            seen.add(name)
            names.append((name, dialog))
    return tuple(names)


# Revisión 1 de r23 (b): lo que una meta que crea pide crear es el objeto que introduce un determinante indefinido justo
# detrás del verbo («crea una nota rápida nueva», «add a new slide», «crea otra página»); un artículo definido o un
# nombre sin determinante habla de algo que ya existe o lo nombra («haz la nota morada», «crear nota morada»).
_CREATED_INDEFINITE = frozenset({"un", "una", "uno", "otro", "otra", "nuevo", "nueva", "an", "another", "new"})
_CREATED_ENGLISH_HEAD = re.compile(r"^(?:create|make|add|insert)\b")
# Lo que sigue al objeto y ya no es él: un complemento de lugar, destino o pertenencia («a la nota», «en el escritorio»,
# «para el correo de juan», «de compras»), un nombre o una compañía («llamada pan», «con el título Ventas»), otra orden.
_CREATED_TAIL = frozenset({
    "a", "al", "en", "para", "de", "del", "con", "sobre", "dentro", "desde", "hacia", "entre", "bajo", "junto",
    "to", "in", "on", "into", "inside", "for", "of", "with", "at", "from", "under", "onto",
    "llamado", "llamada", "named", "called", "que", "that", "which", "y", "and", "e",
})


def created_object(folded_goal: str, creating_goal: str, creating_quantity: str) -> str | None:
    """The words of the one thing a creating goal (data «creatingGoal», no «creatingQuantity») asks to create, when
    they are the object right after the verb, introduced by an indefinite determiner, with nothing after it: «crea una
    nota rapida nueva» → «nota rapida nueva». None when the goal creates more than one, modifies or names something that
    exists («agrega pan a la nota», «haz la nota morada», «crear nota morada») or says another place or more than the
    thing («crea una carpeta en el escritorio», «crea una regla para el correo de juan»)."""

    text = str(folded_goal or "").strip(" ,;:.!?")
    head = re.match(creating_goal, text)
    if head is None or re.search(creating_quantity, text):
        return None
    words = re.findall(r"[a-z0-9]+", text[head.end():])
    determiners = _CREATED_INDEFINITE | ({"a"} if _CREATED_ENGLISH_HEAD.match(text) else frozenset())
    if not words or words[0] not in determiners:
        return None
    while words and words[0] in determiners:
        words = words[1:]
    if not words or any(word in _CREATED_TAIL for word in words):
        return None
    return " ".join(words)


# Revisión 2 de r23 (b): el mando que crea dice su objeto con el mismo contrato que la meta: un determinante definido,
# demostrativo o posesivo («Agregar esta página a favoritos», «Add this page», «Agregar la nota») habla de algo que ya
# existe, y lo que va detrás del objeto en _CREATED_TAIL lo lleva a otro sitio («Agregar contacto a favoritos», «Agregar
# nota al contacto»). El atajo entre paréntesis del final («(Ctrl+D)») no es parte del nombre.
_COMMAND_EXISTING = frozenset({
    "el", "la", "los", "las", "lo", "este", "esta", "estos", "estas", "esto", "ese", "esa", "esos", "esas", "eso",
    "aquel", "aquella", "mi", "mis", "tu", "tus", "su", "sus", "nuestro", "nuestra",
    "the", "this", "that", "these", "those", "my", "your", "its", "our", "their",
})
_COMMAND_ENGLISH_HEAD = re.compile(r"^(?:create|new|add|insert)\b")
_COMMAND_SHORTCUT = re.compile(r"\s*\([^()]*\)\s*$")


def creating_command_object(folded_name: str, creating_command: str) -> str | None:
    """The words of the new thing a command that creates (data «creatingCommand») makes, by its folded name, when it
    says a new one and nothing after it: «Nueva nota» → «nota», «Crear una nueva sección» → «seccion», «Add a slide» →
    «slide». None for a command whose object is introduced as one that exists («Agregar esta página a favoritos
    (Ctrl+D)», «Add this page to favorites») or goes somewhere («Agregar contacto a favoritos», «Agregar evento a mi
    calendario»), and for a Spanish verb followed by «a» (a preposition there, never an article)."""

    text = _COMMAND_SHORTCUT.sub("", str(folded_name or "")).strip(" ,;:.!?")
    found = re.match(creating_command, text)
    if found is None:
        return None
    before = re.findall(r"[a-z0-9]+", text[: found.start("object")])[1:]
    words = re.findall(r"[a-z0-9]+", found.group("object"))
    if not words or any(word in _COMMAND_EXISTING for word in (*before, words[0])):
        return None
    if "a" in before and not _COMMAND_ENGLISH_HEAD.match(text):
        return None
    if any(word in _CREATED_TAIL for word in words):
        return None
    return " ".join(words)
