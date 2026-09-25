"""Display: brightness, screen status and inventory, wallpaper. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .grammar import _fold, _has, _strip_request_envelope, _is_negative_effect_clause, _is_past_or_hypothetical_state, _is_meta_or_tool_denial


# Los ojos del computer use: preguntar que hay en la pantalla. Sin esta lectura
# el modelo tiene que adivinar como se llama exactamente el control que quiere
# pulsar, que es justo donde fallan los agentes de interfaz.
_SCREEN_INVENTORY = re.compile(
    r"^[\s¿?¡!]*(?:(?:que|cuales|cuantos|what|which|how\s+many)\s+"
    r"(?:cosas\s+|elementos?\s+|controles?\s+|botones?\s+|opciones?\s+|"
    r"things\s+|elements?\s+|controls?\s+|buttons?\s+|options?\s+)?"
    r"(?:hay|tengo|ves|se\s+ven|aparecen|puedo\s+(?:pulsar|apretar|tocar)|"
    r"are\s+there|do\s+you\s+see|can\s+i\s+(?:click|press))"
    r"\s+(?:en\s+|on\s+|in\s+)?(?:la\s+|the\s+)?"
    r"(?:pantalla|ventana|screen|window)"
    r"|^[\s¿?¡!]*(?:mira|mirate|revisa|lee|leeme|look\s+at|read)"
    r"\s+(?:(?:lo\s+)?que\s+(?:hay|ves|se\s+ve)\s+en\s+|what(?:'s|\s+is)?\s+on\s+)?"
    r"(?:la\s+|the\s+)?(?:pantalla|ventana|screen|window)"
    # «dime la ventana que tiene el foco» names a window, not its contents: a
    # telling verb needs «lo que hay en» / «what's on» before the noun.
    r"|^[\s¿?¡!]*(?:dime|decime|tell\s+me)"
    r"\s+(?:(?:lo\s+)?que\s+(?:hay|ves|se\s+ve)\s+en\s+|what(?:'s|\s+is)?\s+on\s+)"
    r"(?:la\s+|the\s+)?(?:pantalla|ventana|screen|window)"
    # «what's on the screen» sin verbo delante es como la persona lo dice de
    # verdad; el plegado conserva el apostrofo, asi que va escrito.
    r"|^[\s¿?¡!]*what(?:'s)?\s+(?:is\s+)?on\s+(?:the\s+)?(?:screen|window)"
    r")\b",
    re.IGNORECASE,
)


def screen_inventory_request(text: str) -> bool:
    """La persona pregunta que hay delante, no pide tocar nada."""

    folded = _fold(_strip_request_envelope(str(text or "")))
    if _has(folded, r"\b(?:archivo|file|carpeta|folder|nota|note|tarea|task)\b"):
        return False
    return _SCREEN_INVENTORY.search(folded) is not None


_DISPLAY_STATUS_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «qué resolución tengo», «qué resolución de pantalla tengo», «cuál es la resolución de mi pantalla»
    r"(?:que|cual\s+es\s+la|what|what's|whats|dime\s+(?:que|la|cual)|decime\s+(?:que|la|cual))\s+resolucion(?:\s+(?:de|del)\s+(?:la\s+|mi\s+|el\s+|the\s+|my\s+)?(?:pantalla|monitor|screen|display))?(?:\s+(?:tengo|tiene|uso|estoy\s+usando|do\s+i\s+have|is|am\s+i\s+using))?|"
    # «cuántos monitores tengo», «how many monitors do i have»
    r"(?:cuantos|cuantas|how\s+many)\s+(?:monitores|pantallas|monitors|screens|displays)(?:\s+(?:tengo|hay|tiene|do\s+i\s+have|are\s+there|are\s+connected))?|"
    # «qué Hz tiene el monitor», «a cuántos Hz va la pantalla», «qué frecuencia de refresco tiene el monitor»
    r"(?:que|cuantos|a\s+cuantos|what|how\s+many)\s+(?:hz|hertz|hercios|frecuencia(?:\s+de\s+(?:refresco|actualizacion))?|refresh\s+rate)\s+(?:tiene|va|corre|tengo|has|is|does)?\s*(?:el\s+|la\s+|mi\s+|the\s+|my\s+)?(?:monitor|pantalla|screen|display)?(?:\s+(?:have|run\s+at|running\s+at))?"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


def _display_status_question(text: str) -> bool:
    """SYSTEM1459 «qué resolución tengo», «cuántos monitores tengo», «qué Hz tiene el
    monitor»: a display.status read of the attached monitors — never a change."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _DISPLAY_STATUS_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:cambia|cambiar|pone|poner|ajusta|ajustar|sube|baja|set|change|brillo|brightness)\b")
    )


_KNOWN_FOLDER_ENUM = {
    "escritorio": "desktop", "desktop": "desktop",
    "descargas": "downloads", "downloads": "downloads",
    "documentos": "documents", "documents": "documents",
}


_KNOWN_FOLDER_WORDS = r"(?:escritorio|desktop|descargas|downloads|documentos|documents)"


def _without_screen_state_preface(text: str) -> str:
    """SCREEN1807: «hay un diálogo de Steam abierto para instalar X, toca …» /
    «there is a Steam dialog open; take …»: the leading statement of what is
    open frames the request; the clause after it is the speech act."""

    stripped = re.sub(
        r"^[¿?¡!\s]*(?:hay|there\s+is|there's|tengo|i\s+have)\s+(?:un|una|unos|unas|el|la|a|an|the)\b"
        r"[^,.;]*?\b(?:abiert[oa]s?|open)\b[^,.;]*[,.;]\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    return stripped or text


# BRIGHT1283: no brightness literal had a deterministic reader, so «qué brillo
# tengo» became a clarification, «subí el brillo» asked for the direction it
# already carried and «turn the brightness down» denied the capability. The
# readers below mirror the volume grammar: a status question, a relative
# adjustment with an authored amount, and a relative request without amount
# that keeps its direction and asks how much (owner rule on H0027).
_BRIGHTNESS_SCREEN = (
    r"(?:\s+(?:de\s+(?:la\s+|mi\s+)?|del\s+|of\s+(?:the\s+|my\s+)?)"
    r"(?:pantalla|monitor|screen|display))?"
)


_BRIGHTNESS_OBJECT = (
    rf"(?:(?:nivel\s+de\s+)?(?:brillo|brightness){_BRIGHTNESS_SCREEN}"
    rf"(?:\s+actual)?{_BRIGHTNESS_SCREEN})"
)


_BRIGHTNESS_UP_VERB = (
    r"(?:sube(?:me|lo|la)?|subi(?:me|lo|la)?|subir|aumenta(?:me|lo|la)?|aumentar|"
    r"incrementa|incrementar|increase|raise|brighten)"
)


_BRIGHTNESS_DOWN_VERB = (
    r"(?:baja(?:me|lo|la)?|bajar|reduce(?:me|lo|la)?|reducir|disminui(?:me|lo|la)?|"
    r"disminuye|disminuir|decrease|lower|dim)"
)


# Fase 3.5 (layer C «oscurece la pantalla»): darkening or lightening the screen is its brightness.
# The verb carries the meaning, so «la pantalla» is enough; the request is read as the ordinary
# brightness request with the rest of the person's words unchanged.
_SCREEN_LIGHT = re.compile(
    r"\b(?:(?P<down>oscurece(?:me|la|lo)?|oscurecer|atenua(?:me|la|lo)?|atenuar|darken)|"
    r"(?P<up>aclara(?:me|la|lo)?|aclarar|ilumina(?:me|la|lo)?|iluminar|brighten))\s+"
    r"(?:(?:la|el|mi|the|my)\s+)?(?:pantalla|monitor|screen|display)\b"
)


def screen_light_as_brightness(folded: str) -> str:
    """«oscurece la pantalla un 20%» → «baja el brillo de la pantalla un 20%» (folded text in, folded out)."""

    return _SCREEN_LIGHT.sub(
        lambda found: ("baja" if found.group("down") else "sube") + " el brillo de la pantalla",
        folded,
        count=1,
    )


_BRIGHTNESS_ABSOLUTE = (
    r"\b(?:a|al|to|at|hasta)\s*(?:100|[0-9]{1,2})\b|"
    r"\b(?:al\s+|to\s+(?:the\s+)?)?(?:maximo|minimo|max|min|tope|full|maximum|minimum)\b"
)


_BRIGHTNESS_ENGLISH_TURN = r"\bturn\s+(?:the\s+|my\s+)?(?:screen\s+)?brightness\s+(?P<dir>up|down)\b"


_BRIGHTNESS_RELATIVE_WORDS = (
    r"\b(?:un\s+(?:poco|toque|poquito|cacho|pelin)|bastante|mucho|algo|"
    r"a\s+little|a\s+bit|slightly)\b"
)


def brightness_status_request(text: str) -> bool:
    """«qué brillo tengo», «mostrame el brillo», «what's the brightness»: read it."""

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    if re.search(r"\d", folded) or _is_past_or_hypothetical_state(folded):
        return False
    obj = _BRIGHTNESS_OBJECT
    return re.fullmatch(
        rf"(?:(?:y|and)\s+)?(?:"
        rf"(?:que|cual|cuanto|cuanta|como)\s+(?:es\s+|esta\s+|tengo\s+(?:de\s+)?)?"
        rf"(?:el\s+|mi\s+)?{obj}(?:\s+(?:tengo|hay|tiene|esta|puesto|ahora))*|"
        rf"(?:a|en)\s+(?:cuanto|que|que\s+nivel)\s+(?:esta|tengo|tiene)\s+(?:el\s+|mi\s+)?{obj}|"
        rf"(?:dime|decime|mostrame|muestrame|muestra|mostra|ver|quiero\s+ver|"
        rf"show(?:\s+me)?|tell\s+me|check|revisa|chequea|fijate)\s+"
        rf"(?:el\s+|mi\s+|the\s+|my\s+)?(?:nivel\s+(?:actual\s+)?de\s+)?{obj}|"
        rf"what(?:'s|\s+is)\s+(?:the\s+|my\s+)?(?:current\s+)?{obj}(?:\s+(?:level|at|now|set\s+to))*|"
        rf"how\s+bright\s+is\s+(?:the\s+|my\s+)?(?:screen|display|monitor)|"
        # BRIGHT1319 H0674 «tengo el brillo al máximo»: a claim about the
        # present level is answered by reading it, never by agreeing.
        rf"(?:tengo|esta|tiene|is)\s+(?:el\s+|mi\s+|the\s+|my\s+)?{obj}\s+"
        rf"(?:(?:al|a|en\s+el|at|on)\s+(?:maximo|minimo|max|min|tope|full|maximum|minimum)|a\s+tope|alto|bajo|high|low)"
        rf"(?:\s+(?:ahora|now))?|"
        rf"(?:el\s+|mi\s+)?{obj}\s+(?:esta|lo\s+tengo)\s+(?:al|a|en\s+el)\s+(?:maximo|minimo|max|min|tope)"
        rf")(?:\s*,?\s*(?:por\s+favor|please|no|verdad|cierto|right))?",
        folded,
    ) is not None


_BRIGHTNESS_SET_VERB = (
    r"(?:pon(?:me|le|e|elo|ele|lo)?|poner|fija(?:me|lo)?|ajusta(?:me|lo)?|adjust|"
    r"establece|set|cambia(?:me|lo)?|change|deja(?:me|lo)?|leave|"
    rf"{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB}|turn)"
)


_BRIGHTNESS_EXTREME_VALUES = {
    "maximo": 100, "max": 100, "tope": 100, "full": 100, "maximum": 100, "the max": 100,
    "minimo": 0, "min": 0, "minimum": 0,
}


def wallpaper_request(text: str) -> dict[str, str | None] | None:
    """REOPEN1957 H0459 «cambiá el fondo de pantalla a azul»: a solid colour
    or a picture from a known folder as the desktop background."""

    raw = _strip_request_envelope(str(text).strip()).rstrip(".!?")
    folded = _fold(raw)
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    if not _has(folded, r"\b(?:fondo\s+de\s+(?:pantalla|escritorio)|fondo|wallpaper|papel\s+tapiz|desktop\s+background|background)\b"):
        return None
    if not _has(folded, r"\b(?:cambia|cambiar|cambiame|pon|pone|poneme|poner|establece|coloca|usa|change|set|put|use|make)\b"):
        return None
    colour = re.search(
        # WALLPAPER (typed tandas): «poné el fondo de escritorio verde» names the
        # colour right after the noun, without «a» or «de color».
        r"(?:\b(?:a|al|de\s+color|en|to|color)\s+|\b(?:pantalla|escritorio|fondo|wallpaper|background)\s+)"
        r"(?P<color>azul|rojo|verde|negro|blanco|gris|amarillo|naranja|violeta|morado|rosa|celeste|marron|"
        r"blue|red|green|black|white|gray|grey|yellow|orange|purple|pink|lightblue|brown|#?[0-9a-f]{6})\b",
        folded,
    )
    if colour is not None:
        return {"color": colour.group("color"), "folder": None, "name": None}
    picture = re.search(
        rf"(?P<name>[^\s/\\:*?\"<>|]+\.(?:png|jpg|jpeg|bmp|gif|webp))\s+(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}|imagenes|pictures)\b",
        folded,
    )
    if picture is not None:
        return {"color": None, "folder": _KNOWN_FOLDER_ENUM.get(_fold(picture.group("folder")), "pictures"), "name": picture.group("name")}
    return None


def monitor_facts_asked(user_text: str) -> frozenset[str]:
    """What a question about the monitors asks: «resolution», «refresh» (Hz) and/or «count» (how many)."""

    asks = _fold(user_text)
    return frozenset(
        fact
        for fact, pattern in (
            ("resolution", r"\bresoluci"),
            ("refresh", r"\b(?:hz|hertz|hercios|frecuencia|refresh)\b"),
            ("count", r"\b(?:cuantos|cuantas|how\s+many)\b"),
        )
        if re.search(pattern, asks)
    )
