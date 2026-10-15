"""Las palabras con que el motor de computer use elige qué controles muestra al modelo y adónde va un texto (v3, lugar y
clic M2/M3/M8): las palabras vacías de un objetivo, los botones del marco de una ventana, las piezas de una barra de
desplazamiento, los objetivos cuyo texto es un parámetro (un nombre nuevo, una búsqueda), los selectores rápidos y los
lugares del navegador o del equipo, la parte de un formulario adonde va el texto de un objetivo y la pestaña nueva que
pide el pedido. Sólo datos y lecturas de palabras, sin aplicaciones: ``computer_use`` las usa.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from .account_acts import said_as_not_to_do


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(character for character in text if not unicodedata.combining(character)).split())


# Las palabras de un objetivo que no nombran nada de la ventana: artículos, preposiciones, conjunciones y pronombres
# en los dos idiomas. Una de ellas nunca sube un control al listado del modelo («de» está en medio de cualquier nombre).
_EMPTY_WORDS = frozenset({
    "a", "al", "an", "and", "as", "at", "by", "con", "de", "del", "el", "en", "for", "from", "in", "into", "it", "la",
    "las", "le", "lo", "los", "me", "mi", "my", "of", "on", "or", "para", "por", "su", "sus", "te", "the", "this",
    "to", "tu", "tus", "un", "una", "uno", "unos", "unas", "with", "y", "your", "o", "e", "that", "este", "esta",
    "ese", "esa", "aqui", "here", "there", "alli", "ahi",
})


def naming_words(*texts: object) -> frozenset[str]:
    """Las palabras de ``texts`` (un objetivo y los otros nombres de su lugar) que pueden nombrar un control: tres
    letras o más y ninguna palabra vacía."""

    return frozenset(
        word for text in texts for word in re.findall(r"[a-z0-9]+", _fold(text))
        if len(word) >= 3 and word not in _EMPTY_WORDS
    )


def proof_stems(text: object, drop: Iterable[str] = (), kin: Iterable[Iterable[str]] = ()) -> frozenset[str]:
    """Ronda 22 (pasada r18, t4-c06 y t4-c13): las palabras de contenido de ``text`` (un objetivo dicho por la persona o
    una pieza de lo citado) con que una prueba se relaciona con su objetivo: tres letras o más, cortadas a cinco, nunca
    una de ``drop`` (verbos y palabras de cualquier pedido, en datos); una palabra de un grupo de ``kin`` vale por la
    primera del grupo («blank» y «blanco», «bold» y «negrita»); toda cifra vale «#» y la palabra pegada a ella se lee sin
    la cifra («Libro1» es «libro» y «#»). Gemelo de
    ComputerUseSuccessCheck.ProofStems."""

    dropped = {_fold(word) for word in drop}
    stems: dict[str, str] = {}
    for group in kin:
        cut = [_fold(word)[:5] for word in group if _fold(word)]
        for stem in cut:
            stems.setdefault(stem, cut[0])
    found: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", _fold(text)):
        word = "".join(character for character in token if not character.isdigit())
        if word != token:
            found.add("#")
        if len(word) >= 3 and word not in dropped:
            found.add(stems.get(word[:5], word[:5]))
    return frozenset(found)


# Los botones del marco de una ventana, por su nombre entero: nunca son el lugar de un objetivo dentro de la ventana.
_FRAME_BUTTONS = frozenset({
    "minimizar", "maximizar", "restaurar", "restaurar abajo", "cerrar", "minimize", "maximize", "restore",
    "restore down", "close",
})


def frame_button(name: object) -> bool:
    """El nombre entero de un botón del marco (minimizar, maximizar, restaurar, cerrar)."""

    return _fold(name) in _FRAME_BUTTONS


# El verbo con que empieza el nombre de un botón de leyenda: dentro de la barra de título, el marco lo nombra con el
# título detrás («Minimizar Seguridad de Windows», pasada r18 v3-62). Gemelo de CaptionWords de ComputerUseMission.
_CAPTION_VERBS = frozenset({
    "minimizar", "maximizar", "restaurar", "cerrar", "minimize", "maximize", "restore", "close",
})


def caption_verb(name: object) -> bool:
    """La primera palabra del nombre es la de un botón de leyenda (minimizar, maximizar, restaurar, cerrar)."""

    words = _fold(name).split()
    return bool(words) and words[0] in _CAPTION_VERBS


def closes_by_caption(name: object) -> bool:
    """El botón de leyenda que cierra la ventana (su primera palabra es cerrar o close)."""

    words = _fold(name).split()
    return bool(words) and words[0] in {"cerrar", "close"}


# Un objetivo que sale de la ventana o la descarta sin nombrar el cierre: también lo hace el cierre del marco.
_LEAVING_GOAL = re.compile(
    r"\b(?:sal|salir|salte|salgas?|quit\w*|exit\w*|leave|dismiss\w*|descart\w*|cancel\w*)\b"
)


def leaves_the_window(goal: object) -> bool:
    """El objetivo sale de la ventana, la descarta o la cancela («sal del aviso», «quit the calculator»)."""

    return _LEAVING_GOAL.search(_fold(goal)) is not None


# Las piezas de una barra de desplazamiento por su nombre, cuando la vista no da rectángulos: «Aumento grande vertical»,
# «Disminución pequeña horizontal», «Line down», «Page up», «Flecha arriba».
_SCROLL_PART = re.compile(
    r"^(?:(?:aumento|disminucion)\s+(?:grande|pequeno)\s+(?:vertical|horizontal)"
    r"|(?:line|page|linea|pagina)\s+(?:up|down|left|right|arriba|abajo|izquierda|derecha)"
    r"|(?:flecha|arrow)\s+(?:arriba|abajo|up|down))$"
)


def scroll_part_name(name: object) -> bool:
    """El nombre de un botón de línea o de página de una barra de desplazamiento."""

    return _SCROLL_PART.match(_fold(name)) is not None


# Un objetivo que pide desplazar: sólo entonces una pieza de la barra de desplazamiento es un control posible.
_SCROLLING = re.compile(r"\b(?:desplaz\w*|scroll\w*|baja\w*|sub[ei]\w*|bajar|subir|page\s+(?:up|down))\b")


def asks_to_scroll(goal: object) -> bool:
    return _SCROLLING.search(_fold(goal)) is not None


# El menú de sistema de una ventana (el de su icono: restaurar, mover, tamaño, minimizar, maximizar, cerrar), por los
# nombres que Windows le da en los dos idiomas: el elemento «Sistema» y su barra «Barra de menús del sistema». Medido en
# la pasada r15b: fue la elección equivocada más frecuente del modelo (v3-13, v3-16, v3-32, v3-33, v3-38, v3-39).
_SYSTEM_MENU_NAMES = frozenset({
    "sistema", "system", "menu sistema", "menu del sistema", "system menu", "barra de menus del sistema",
    "system menu bar",
})
# Un objetivo que pide algo de lo que ofrece ese menú: sólo entonces el menú de sistema es un control posible.
_WINDOW_MENU_GOAL = re.compile(
    r"\b(?:mover\w*|move|moving|muev\w*|restaur\w*|restore\w*|minimiz\w*|maximiz\w*|cerra\w*|cierr\w*|close|"
    r"tamano|resize\w*|redimension\w*)\b"
)


def system_menu_name(name: object) -> bool:
    """El nombre entero del menú de sistema de una ventana o de su barra («Sistema», «Barra de menús del sistema»)."""

    return _fold(name).strip() in _SYSTEM_MENU_NAMES


def asks_for_the_window_menu(goal: object) -> bool:
    """El objetivo pide mover, restaurar, minimizar, maximizar, cambiar el tamaño o cerrar la ventana."""

    return _WINDOW_MENU_GOAL.search(_fold(goal)) is not None


# Un objetivo que elige una opción por el verbo con que empieza («cambia el modo a ventana», «pon el tema oscuro»,
# «set the view to list», «selecciona Ventana»): lo pedido es un estado que puede estar ya. Nunca uno que quita, apaga
# o desmarca, ni uno que va a un lugar («ir a X» tiene su propia llegada).
_CHOOSING_GOAL = re.compile(
    r"^(?:(?:y|and|luego|then)\s+)?(?:cambia\w*|pon|pone\w*|poner|set|change|switch|selecciona\w*|select|eleg\w*|"
    r"elig\w*|escoge\w*|choose|pick|usa|usar|use|deja\w*|dejar)\b"
)
_UNDOING_GOAL = re.compile(
    r"\b(?:deseleccion\w*|desmarc\w*|destild\w*|desactiv\w*|quit\w*|remov\w*|deselect\w*|unselect\w*|uncheck\w*|"
    r"untick\w*|turn\s+off|switch\s+off|disable\w*|apag\w*|off)\b"
)


def undoes_a_state(goal: object) -> bool:
    """El objetivo quita, apaga o desmarca algo («desactivá el wifi», «quitá el silencio», «turn off the light»): un
    interruptor que su clic deja apagado va en su dirección; en cualquier otro objetivo, el que queda encendido o
    elegido. Gemelo de la App: dato «computerUse.evidence.undoingGoal» (mismo patrón)."""

    return _UNDOING_GOAL.search(_fold(goal)) is not None


def chooses_an_option(goal: object) -> bool:
    """El objetivo elige una opción o un modo, sin quitar ni apagar nada."""

    folded = _fold(goal)
    return _CHOOSING_GOAL.search(folded) is not None and _UNDOING_GOAL.search(folded) is None


# Revisión 1 de motor-listas-abiertas, hallazgo 1: un objetivo que fija un valor o elige una entrada por el verbo con
# que empieza («activar escala en 125», «pon la escala en 125», «regresa la escala a 100», «set the scale to 125»).
# Nunca uno que quita, apaga o desmarca («desactivar suspender después de 15 minutos», «quitar …»), ni uno que va a un
# lugar («ir a …») o hace clic («hacer clic en …»): una entrada que se ve elegida no dice que eso esté hecho.
_SETTING_A_VALUE_GOAL = re.compile(
    r"^(?:(?:y|and|luego|then)\s+)?(?:activa\w*|cambia\w*|pon|pone\w*|poner|selecciona\w*|eleg\w*|elig\w*|"
    r"escoge\w*|usa|usar|deja\w*|dejar|regresa\w*|devuelve\w*|devolver|vuelve|volver|ajusta\w*|fija\w*|"
    r"establece\w*|subir|sube\w*|bajar|baja\w*|set|change|select|choose|pick|switch|use|adjust|make|enable|"
    r"turn\s+on)\b"
)


def sets_a_value(goal: object) -> bool:
    """El objetivo fija un valor o elige una entrada, sin quitar ni apagar nada (``_SETTING_A_VALUE_GOAL``)."""

    folded = _fold(goal)
    return _SETTING_A_VALUE_GOAL.search(folded) is not None and _UNDOING_GOAL.search(folded) is None


# Las palabras de un objetivo de elegir que no dicen qué opción: artículos y preposiciones, y el nombre de la clase de
# ajuste que se elige («el modo», «el tema», «la vista»). Revisión de sistema-cumplido, hallazgo 1: cualquier otra
# palabra («la canción», «el nombre de», «vacía», «y bórralo», «para mandar hola») pide algo más que la opción elegida.
_OPTION_FILLER = frozenset({
    "el", "la", "los", "las", "lo", "un", "una", "a", "al", "de", "del", "en", "por", "como", "the", "an", "to", "as",
    "in", "on", "of", "for", "into",
})
_OPTION_KINDS = frozenset({
    "modo", "mode", "tema", "theme", "vista", "view", "estilo", "style", "opcion", "option", "ajuste", "setting",
})


def goal_is_only_the_option(goal: object, name: object) -> bool:
    """Un objetivo de elegir (``chooses_an_option``) que no dice más que la opción ``name``: quitado el verbo, cada
    palabra es de la opción, de relleno o la clase de ajuste («cambia el modo a ventana» de «Ventana»), y al menos una
    es de la opción. Nunca un número: «pon el volumen a 50» pide un valor, no una opción ya elegida."""

    folded = _fold(goal)
    verb = _CHOOSING_GOAL.search(folded)
    if verb is None or _UNDOING_GOAL.search(folded) is not None:
        return False
    said = [word for word in re.findall(r"[a-z0-9]+", folded[verb.end():]) if word not in _OPTION_FILLER]
    option = set(re.findall(r"[a-z0-9]+", _fold(name)))
    if not said or not set(said) & option or any(char.isdigit() for word in said for char in word):
        return False
    return all(word in option or word in _OPTION_KINDS for word in said)


# Revisión 3 de motor-listas-abiertas: un objetivo de fijar un número en una lista no dice más que la lista, el número y
# su unidad. El complemento de la lista («escala de la pantalla») es parte de su nombre; cualquier otra palabra («y la
# orientación en vertical», «y después …») pide algo más que esa entrada.
_COMPLEMENT_LINKS = frozenset({"de", "del", "of"})


def goal_is_only_the_number(goal: object, list_name: object, entry_name: object, number: object) -> bool:
    """Un objetivo que fija un valor (``sets_a_value``) que no dice más que la lista ``list_name``, el número ``number``
    y la entrada ``entry_name`` que lo lleva: quitado el verbo, cada palabra es de relleno, del nombre de la lista o de
    la entrada, una cifra del número, o el complemento de la lista («escala de la pantalla»: la palabra que sigue a «de»
    y su artículo justo después de una palabra de la lista). La palabra que acompaña al número (su unidad: «2 horas»)
    tiene que estar en el nombre de la entrada: «2 horas» nunca es «2 minutos»."""

    folded = _fold(goal)
    verb = _SETTING_A_VALUE_GOAL.search(folded)
    if verb is None or _UNDOING_GOAL.search(folded) is not None:
        return False
    words = re.findall(r"[a-z0-9]+", folded[verb.end():])
    listed = set(re.findall(r"[a-z0-9]+", _fold(list_name)))
    entry = set(re.findall(r"[a-z0-9]+", _fold(entry_name)))
    digits = set(re.findall(r"[0-9]+", str(number or "")))
    if not words or not digits or not set(words) & listed:
        return False
    seen_number = False
    for at, word in enumerate(words):
        if word.isdigit():
            if word not in digits:
                return False
            seen_number = True
            following = next((later for later in words[at + 1:] if not later.isdigit()), None)
            if following is not None and following not in _OPTION_FILLER and following not in entry:
                return False
            continue
        if any(char.isdigit() for char in word):
            return False
        if word in _OPTION_FILLER or word in listed or word in entry:
            continue
        # The complement of the list's name: «<lista> de [art] X», right after a word of the list.
        back = at - 1
        while back >= 0 and words[back] in _OPTION_FILLER and words[back] not in _COMPLEMENT_LINKS:
            back -= 1
        if back >= 1 and words[back] in _COMPLEMENT_LINKS and words[back - 1] in listed and not seen_number:
            continue
        return False
    return seen_number


# Un objetivo cuyo texto es un parámetro de algo: renombrar o buscar, por el verbo con que empieza el sub-objetivo
# (``semantic.missions`` los escribe «renombrar X a Y» y «buscar X»). Ese texto sólo va a un campo cuyo papel encaja,
# nunca al documento ni a una consola (medido en v3-40: «pruebas» cayó en la consola). Sólo el verbo inicial: «agregar
# un título al documento», «poner hola en el documento» o «anotar 100 en la celda A1» son el contenido de la persona.
_PARAMETER_GOAL = re.compile(
    r"^(?:(?:y|and|luego|then)\s+)?(?:renombr\w*|rename\w*|cambia\w*\s+(?:el\s+)?nombre|change\s+(?:the\s+)?name|"
    r"busca\w*|buscar|search\w*)\b"
)


def parameter_goal(goal: object) -> bool:
    """El objetivo escribe un parámetro (un nombre nuevo, una búsqueda), no el contenido de la persona."""

    return _PARAMETER_GOAL.search(_fold(goal)) is not None


# Un objetivo que le pone nombre a un elemento (revisión 2 de la ronda 20 P1, hallazgo 3): renombrarlo, cambiarle el
# nombre, ponerle nombre. El cuadro donde se escribe ese nombre suele llamarse «Título» o «Title» (el de una pestaña,
# una ventana, una lista), y ese título es el del elemento, no una parte de un documento. Sólo el verbo inicial, como
# ``_PARAMETER_GOAL``: «escribe el nombre del cliente en el documento» es contenido de la persona.
_NAMES_AN_ITEM = re.compile(
    r"^(?:(?:y|and|luego|then)\s+)?(?:renombr\w*|rename\w*|cambia\w*\s+(?:el\s+)?nombre|change\s+(?:the\s+|its\s+)?name"
    r"|pon\w*\s+(?:(?:de|el|un|como|por)\s+)?nombre|give\s+(?:it\s+|them\s+)?(?:a\s+)?name)\b"
)


def names_an_item(goal: object) -> bool:
    """El objetivo le pone nombre a un elemento (renombrar, cambiar el nombre, ponerle nombre), en los dos idiomas."""

    return _NAMES_AN_ITEM.search(_fold(goal)) is not None


# Un cuadro que elige mientras se escribe (un selector rápido): Enter en él abre el resultado resaltado, que no es el
# objetivo y puede ser un canal de voz que se une sin que RiskPolicy pregunte. Nunca recibe un Enter para «enviar» la
# búsqueda.
_QUICK_SWITCHER = re.compile(
    r"\b(?:a donde quieres ir|ir a|go to|jump to|quick switch\w*|quick open|busqueda rapida|quick search|"
    r"cambio rapido)\b"
)


def quick_switcher_name(name: object) -> bool:
    """El nombre de un selector rápido («¿A dónde quieres ir?», «Ir a», «Búsqueda rápida», «Quick switcher»)."""

    return _QUICK_SWITCHER.search(_fold(name)) is not None


# Los lugares del propio navegador y del equipo: se llega a ellos por el menú o la navegación del navegador, nunca
# escribiendo su nombre en la barra de dirección y búsqueda (eso haría una búsqueda web y un resultado llamado igual
# sería un lugar falso). Un conjunto cerrado, a diferencia de los sitios, que son abiertos.
_BROWSER_OR_COMPUTER_PLACE = frozenset({
    "descargas", "downloads", "historial", "history", "favoritos", "favorites", "marcadores", "bookmarks",
    "configuracion", "ajustes", "settings", "opciones", "options", "extensiones", "extensions", "colecciones",
    "collections", "contrasenas", "passwords", "cartera", "wallet", "privacidad", "privacy", "perfil", "perfiles",
    "profile", "profiles", "pestanas", "tabs", "pestana", "tab", "archivos", "files", "carpeta", "folder",
    "documentos", "documents", "escritorio", "desktop", "imagenes", "pictures", "musica", "music", "videos",
    "papelera", "recycle",
})
_DOMAIN = re.compile(r"^(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,63}(?:/\S*)?$")


def browser_or_computer_place(target: object) -> bool:
    """El destino es un lugar del navegador o del equipo («descargas», «historial», «configuración»), no un sitio
    («wikipedia») ni una dirección («es.wikipedia.org»)."""

    folded = _fold(target)
    if _DOMAIN.match(folded):
        return False
    return any(word in _BROWSER_OR_COMPUTER_PLACE for word in re.findall(r"[a-z0-9]+", folded))


# La parte de un documento o de un formulario que un objetivo nombra como el lugar de su texto («ponle X de título»,
# «en el asunto», «as the subject»): el campo se elige por ese nombre, nunca por dónde esté el teclado.
SLOT_WORDS = (
    "titulo", "title", "subtitulo", "subtitle", "cuerpo", "body", "asunto", "subject", "nombre", "name", "notas", "nota",
    "notes", "note", "descripcion", "description", "comentario", "comment", "encabezado", "heading", "header",
)
# «por nombre» / «by name» es un orden o un filtro, nunca un lugar (revisión r10 campo-texto, hallazgo 1), así que «por»
# no introduce; «de», «del» y «al» nombran un lugar sólo en un objetivo que pone un texto («ponle X de título»), no en
# «los archivos de nombre largo».
_TEXT_SLOT = re.compile(
    r"\b(?P<intro>de|del|como|en\s+(?:el|la|su)|al|a\s+la|as(?:\s+(?:the|its))?|in(?:to)?\s+(?:the|its)|to\s+the"
    r"|for\s+the)\s+(?P<slot>" + "|".join(SLOT_WORDS) + r")\b"
)
_LOOSE_INTRO = frozenset({"de", "del", "al"})
# La parte dicha como el rótulo del texto, con dos puntos (ronda 20 P1: «escribe el título: Lista del super», «type the
# title: Groceries»): el verbo de poner, el artículo y la parte, y el texto después de los dos puntos.
_LABELLED_SLOT = re.compile(
    r"\b(?:pon\w*|escrib\w*|ingres\w*|complet\w*|llen\w*|rellen\w*|cambi\w*|asign\w*|put|write|type|set|enter|fill)"
    r"(?:\s+(?:el|la|su|the|its|in|into))+\s+(?P<slot>" + "|".join(SLOT_WORDS) + r")\s*:\s*(?P<text>\S.*)$"
)
# Un objetivo que pone un texto en algún lado («ponle», «escribí», «llená», «cambiá», «put», «set»).
_PUTS_TEXT = re.compile(
    r"\b(?:pon\w*|escrib\w*|ingres\w*|complet\w*|llen\w*|rellen\w*|cambi\w*|titul[ae]\w*|asign\w*|llam[ae]\w*|put"
    r"|write|type|set|enter|fill)\b"
)
# Un objetivo que ordena, filtra o agrupa lo que lista una ventana: «por nombre» es su clave, nunca un campo a escribir.
_ARRANGE_GOAL = re.compile(r"\b(?:filtr\w*|filter\w*|orden[ae]\w*|ordenar|sort\w*|agrup\w*|group\s+by)\b")
# Un objetivo que busca: su texto es una búsqueda y el cuadro de búsqueda de la ventana es su lugar.
_SEARCH_GOAL = re.compile(r"^(?:busc\w*|search\w*|find|look\s+(?:for|up)|encontr\w*)\b|\b(?:buscador|search\s+box)\b")


def text_slot(goal: str | None) -> str | None:
    """La parte adonde va el texto de un objetivo («ponle 'Proyecto final' de título» → «titulo»), plegada; None para
    el objetivo de una búsqueda (su lugar es el cuadro de búsqueda), uno que ordena o filtra una lista («ordená la lista
    por nombre») o uno que no nombra ninguna parte."""

    folded = _fold(goal or "")
    if not folded or _SEARCH_GOAL.search(folded) or _ARRANGE_GOAL.search(folded):
        return None
    labelled = _LABELLED_SLOT.search(folded)
    if labelled is not None:
        return labelled.group("slot")
    puts = _PUTS_TEXT.search(folded) is not None
    for found in _TEXT_SLOT.finditer(folded):
        if found.group("intro") not in _LOOSE_INTRO or puts:
            return found.group("slot")
    return None


# El texto de un objetivo entre comillas de cualquier clase («…», "…", '…', “…”).
_QUOTED_TEXT = re.compile(r"«(?P<a>[^«»]+)»|\"(?P<b>[^\"]+)\"|“(?P<c>[^“”]+)”|'(?P<d>[^']+)'|‘(?P<e>[^‘’]+)’")
# Lo que entre el verbo y la parte no es el texto: el objeto dicho como pronombre («ponle eso de título», «put it as»).
_PRONOUN_ONLY = frozenset({"", "it", "le", "les", "lo", "la", "eso", "esto", "this", "that"})
# La primera palabra de un texto sin comillas que lo dice como una descripción y no como el texto mismo: un artículo,
# un determinante, un posesivo, un indefinido o una preposición («la fecha de hoy», «algo gracioso», «el nombre del
# archivo», «lo mismo que el anterior», «tu nombre», «a summary», «del correo que llego tarde»). Ese texto lo escribe
# el modelo, que sabe qué describe; el texto literal va entre comillas o empieza por su propia palabra (revisión de
# paro-campo, hallazgo 2).
_DESCRIBED_TEXT_START = frozenset({
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas", "algo", "algun", "alguna", "alguno", "algunos",
    "algunas", "cualquier", "cualquiera", "mi", "mis", "tu", "tus", "su", "sus", "nuestro", "nuestra", "este", "esta",
    "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "otro", "otra", "otros", "otras", "que", "lo",
    "del", "de", "al", "a", "an", "the", "some", "something", "anything", "my", "your", "his", "her", "its", "our",
    "their", "what", "whatever", "another", "any", "these", "those",
})


def _aligned_fold(text: str) -> str:
    """``text`` plegado letra por letra (minúsculas, sin acentos) con su largo intacto: una posición del plegado es
    la misma en el original."""

    folded = []
    for character in text:
        base = "".join(
            part for part in unicodedata.normalize("NFKD", character) if not unicodedata.combining(part)
        ).casefold()
        folded.append(base[:1] if len(base) >= 1 else character)
    return "".join(folded)


def slot_text(goal: str | None) -> str | None:
    """El texto que un objetivo pone en su parte («ponele de título Lista del super» → «Lista del super», «ponle
    'Proyecto final' de título» → «Proyecto final», «escribí Hola en el asunto» → «Hola»), tal como se dijo; None si
    el objetivo no nombra una parte (``text_slot``), no tiene verbo de poner un texto, o el texto queda dudoso (dicho
    a los dos lados de la parte, o sólo como un pronombre)."""

    original = str(goal or "").strip()
    slot = text_slot(original)
    if slot is None:
        return None
    # «no le pongas de título Hola»: el texto dicho como lo que no se pone (revisión de paro-campo, hallazgo 2).
    said = _fold(original)
    if any(said_as_not_to_do(said, verb.start()) for verb in _PUTS_TEXT.finditer(said)):
        return None
    quoted = _QUOTED_TEXT.search(original)
    if quoted is not None:
        return next(group for group in quoted.groups() if group is not None).strip() or None
    folded = _aligned_fold(original)
    labelled = _LABELLED_SLOT.search(folded)
    if labelled is not None:
        # «escribe el título: Lista del super»: the text after the colon, as said.
        return original[labelled.start("text"):].strip() or None
    verb = _PUTS_TEXT.search(folded)
    found = next((match for match in _TEXT_SLOT.finditer(folded) if match.group("slot") == slot), None)
    if verb is None or found is None or verb.end() > found.start():
        return None
    between = original[verb.end():found.start()].strip(" ,.:;")
    after = original[found.end():].strip(" ,.:;")
    if _fold(between) in _PRONOUN_ONLY:
        between = ""
    if bool(between) == bool(after):
        return None
    text = between or after
    first = _fold(text).split(" ", 1)[0]
    if first in _DESCRIBED_TEXT_START:
        return None
    return text


# Una pestaña o ventana nueva: el nombre de un control que la abre («Nueva pestaña», «Open in new window») o la frase
# con que el pedido la pide. La ventana de la misión dejaría de ser la del frente (medido en Opera: el modelo pulsó «Nueva
# pestaña» buscando una página y la misión siguió en una pestaña vacía).
OPENS_ELSEWHERE = re.compile(
    r"\b(?:(?:nueva|nuevo|new)\s+(?:pestana|ventana|tab|window)|(?:pestana|ventana)\s+nueva|open\s+in\s+new)\b"
)
_OPENING_VERB = re.compile(r"\b(?:abr\w*|abre|open\w*|cre[ae]\w*|create\w*|agreg\w*|anad\w*|add|lanz\w*|launch\w*)\b")
_CLAUSE_BREAK = re.compile(r"[,;.]|\b(?:y|e|and|luego|despues|then|pero|but)\b")
_ELSEWHERE_PHRASE_WORDS = frozenset({"pestana", "ventana", "nueva", "nuevo", "window", "otra", "otro", "another"})
_NEW_WORD = re.compile(r"\b(?:nueva|nuevo|new)\b")


def asks_a_new_tab(objective: str | None, goal: str | None = None) -> bool:
    """El pedido mismo de la persona pide abrir una pestaña o ventana nueva (r9, v3-37: «abrí una pestaña nueva de
    símbolo del sistema» quedó como el objetivo «ir a nueva de simbolo del sistema», sin la palabra «pestaña») y este
    sub-objetivo es esa parte del pedido.

    La parte lo pide con un verbo de abrir antes de la frase («cerrá la pestaña nueva» no pide ninguna); el sub-objetivo
    es esa parte cuando dice «nueva/new» o comparte una palabra de para qué es la pestaña («símbolo del sistema»), así
    otro sub-objetivo de la misma cadena («ir a configuración») nunca recibe la pestaña nueva."""

    goal_words = set(re.findall(r"\w+", _fold(goal or "")))
    for clause in _CLAUSE_BREAK.split(_fold(objective or "")):
        phrase = OPENS_ELSEWHERE.search(clause)
        verb = _OPENING_VERB.search(clause)
        if phrase is None or verb is None or verb.start() > phrase.start():
            continue
        subject = {
            word for word in re.findall(r"\w+", clause[verb.end():])
            if len(word) >= 4 and word not in _ELSEWHERE_PHRASE_WORDS
        }
        if goal is None or _NEW_WORD.search(_fold(goal)) or subject & goal_words:
            return True
    return False
