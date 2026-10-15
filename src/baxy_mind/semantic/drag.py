"""Arrastrar y dibujar con el mouse: un límite declarado (dueño 2026-10-10, límites de partida).

BAXY no arrastra ni traza: un 4B no ve coordenadas fiables para soltar, y lo medido no llegó a 3/3. ``asks_to_drag``
lee el pedido de hacerlo; el contrato de «sin operación» (``patterns.known_unsupported_effect_request``) lo cierra como
límite y ni el motor ni el lector de misiones lo intentan. La lectura es sólo del acto: un verbo de arrastrar o de
dibujar que encabeza su cláusula, nunca el texto dictado, citado o buscado («escribí: hoy dibujé…», «buscá Drag Me
Down»), ni el nombre de un control («la pestaña Dibujar», «the Draw tab»).

No son arrastrar (contracasos fijados en tests/test_cu_v3_arrastre.py): mover una ventana o la ventana de una
aplicación a un lugar de la pantalla («arrastrá la nota a la otra pantalla», «arrastrá Paint a la derecha»: lo hacen
window.move/window.snap sin puntero), mover el puntero («arrastrá el cursor hasta Aceptar»), un nivel («arrastrá el
volumen al 50») y un dibujo que no es un trazo de una figura («dibujá un gato»: no hay lienzo ni figura).

Estabilización L4 (corrida en vivo limites1, t-drag-3): llevar algo con el gesto dicho como manera («llevala
arrastrando a la esquina de arriba», «move it to Archive by dragging it») pide el gesto mismo, vaya a donde vaya, y es
el límite; sólo una ventana, el puntero o un nivel llevados así no lo son. «drag and drop» y «arrastrar y soltar» son
un solo acto, no dos cláusulas.
"""

from __future__ import annotations

import re

from .normalize import fold

# The clause's joints: what follows one starts another clause, whose head may be the act.
_JOINT = re.compile(r"\s*(?:[,;]|\s(?:y|e|and|then|luego|despues|y\s+despues|y\s+luego)\s)\s*")
# Text the person dictates, quotes or searches is no act of theirs: after a colon, between quotes.
_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")
_DICTATED = re.compile(r":.*$")
# A clause whose head is another act holds the word as that act's object («buscá Drag Race», «abrí draw.io», «andá a
# Dibujar», «escribí que lo dibujé»): the word names something, it is not the act.
_OTHER_HEAD = re.compile(
    r"^(?:(?:por\s+favor|porfa|please)\s+)?(?:busca\w*|search\w*|find|look\s+(?:up|for)|escrib\w*|write|type|tipea\w*|"
    r"pon|pone|poneme|ponme|ponele|reproduc\w*|play|toca|tocame|abr\w*|open|anda|ve|ir|go|entra\w*|selecciona\w*|elegi\w*|"
    r"elige|select|choose|pick|clic\w*|click\w*|mira\w*|watch|lee\w*|read|decime|dime|tell|guarda\w*|save)\b"
)
# A leading frame of the place («en Paint», «en el panel de miniaturas»): the act comes after it.
# Review of L2, C2: «en el word que tengo abierto ponle negrita…» (t4-c13): the place said with the window open.
_FRAME = re.compile(
    r"^(?:en|in|on|desde|from|dentro\s+de)\s+(?:(?:el|la|los|las|the|mi|my)\s+)?\S+(?:\s+de\s+\S+)?"
    r"(?:\s+(?:que\s+(?:tengo|esta|tenes)\s+abiert[oa]|that\s+(?:i\s+have|is)\s+open))?\s+"
)

_DRAG_VERB = re.compile(r"^(?P<verb>arrastr\w*|dragu\w*|drag(?:ging)?)(?:\s+(?P<rest>.*))?$")
_DRAW_VERB = re.compile(
    r"^(?P<verb>dibuj(?:a|ar|ame|ale|alo|ala|en)|traz(?:a|ar|ame|ale|alo|ala|en)|draw|sketch|pinta(?:r|me)?)"
    r"(?:\s+(?P<rest>.*))?$"
)
# What a drawing makes with a stroke, or the canvas and the mouse it is made with.
_STROKE = re.compile(
    r"\b(?:linea|lineas|raya|trazo|circulo|cuadrado|rectangulo|triangulo|curva|flecha|figura|forma|ovalo|elipse|"
    r"line|lines|stroke|circle|square|rectangle|triangle|curve|arrow|shape|oval|ellipse|lienzo|canvas|mouse|raton|"
    r"pincel|pinceles|brocha|lapiz|pencil|brush|pen)\b"
)
_NOT_A_STROKE = re.compile(r"^(?:(?:la|el|una|un|the|a|another|one)\s+)?(?:ruta|route|camino|recorrido|carta|cards?)\b")

_PREPOSITION = re.compile(
    r"\s(?:a|al|hasta|hacia|sobre|encima\s+de|dentro\s+de|adentro\s+de|en|to|onto|into|over|on\s+top\s+of)\s"
)
# «drag and drop», «arrastrá y soltá»: one act, never two clauses joined by «and».
_DRAG_AND_DROP = re.compile(r"\b(?P<verb>drag|arrastr\w*)\s+(?:and|y|e)\s+(?:drop|solt\w*|suelt\w*)\b")
# The gerund that says the drag as the manner of another act («llevala arrastrando», «by dragging it»).
_DRAG_MANNER = ("arrastrand", "dragging")
# The verbs that carry a thing somewhere, whose manner the gerund says.
_CARRY = re.compile(
    r"^(?:lleva\w*|move\w*|mueve\w*|pasa\w*|pone\w*|ponl\w*|coloca\w*|ubica\w*|tira\w*|agarra\w*|"
    r"put|place|bring|take|grab|carry)$"
)
_PRONOUN_VERB = re.compile(r"(?:lo|la|los|las|le)$")
_PRONOUN_OBJECT = re.compile(r"^(?:it|them|this|that|esto|eso)\b")
_WINDOW = re.compile(r"^(?:(?:la|el|una|the|a)\s+)?(?:ventana|window)\b")
_POINTER = re.compile(
    r"^(?:(?:el|la|mi|tu|su|the|my|your)\s+)?(?:mouse|cursor|puntero|raton|flecha|pointer|arrow)(?:\s+del\s+mouse)?$"
)
_LEVEL = re.compile(r"^(?:(?:el|la|the)\s+)?(?:volumen|volume|brillo|brightness|control\s+deslizante|slider)\b")
_LEVEL_PLACE = re.compile(r"^(?:el\s+|un\s+)?\d{1,3}\s*(?:%|por\s*ciento|percent)?$")
_SCREEN_PLACE = re.compile(
    r"^(?:(?:la|el|the)\s+)?(?:otr[oa]\s+|other\s+|segund[oa]\s+|second\s+)?(?:esquina|corner|lado|side|borde|edge|"
    r"izquierda|left|derecha|right|arriba|top|abajo|bottom|centro|center|middle|mitad|pantalla|screen|monitor)\b"
)
_SCREEN_NAMED = re.compile(r"\b(?:pantalla|screen|monitor|escritorio|desktop)\b")
_PLACE_OWNER = re.compile(r"\b(?:del|de|of)\s+(?:(?:la|el|los|las|mi|tu|su|the|my|this|esta|este)\s+)?(?P<owner>[a-z]\w*)")
_SIDE_WORDS = frozenset({
    "izquierda", "left", "derecha", "right", "arriba", "top", "abajo", "bottom", "centro", "center", "centre",
    "medio", "middle", "mitad", "superior", "inferior",
})


def act_clauses(text: object) -> list[str]:
    """The clauses of a request where an act can be said (folded): without what is quoted or dictated after a colon,
    split at its joints, each without the leading frame of its place («en Paint», «en el panel de miniaturas»). Shared
    with the other limits read on the act (semantic.limits)."""

    said = _DICTATED.sub("", _QUOTED.sub(" ", fold(text)))
    return [
        _FRAME.sub("", part.strip(" .!?¡¿"), count=1)
        for part in _JOINT.split(said) if part.strip(" .!?¡¿")
    ]


def _screen_place(where: str) -> bool:
    """A place of the screen: it names the screen or a monitor, or a side with no owner of its own («la esquina de
    arriba»); «el centro del lienzo», «the corner of the window» are places inside the window."""

    if not _SCREEN_PLACE.match(where):
        return False
    if _SCREEN_NAMED.search(where):
        return True
    return all(found.group("owner") in _SIDE_WORDS for found in _PLACE_OWNER.finditer(where))


def _drags(verb: str, rest: str) -> bool:
    parts = _PREPOSITION.split(" " + rest + " ", maxsplit=1)
    what = parts[0].strip()
    where = parts[1].strip() if len(parts) > 1 else ""
    if not what and not _PRONOUN_VERB.search(verb) and not where:
        return False
    if _WINDOW.match(what) or _POINTER.match(what) or (where and _screen_place(where)):
        # A window moved, or the pointer: window.move/window.snap, a pointer move; never a drag of the content.
        return False
    if _LEVEL.match(what) or _LEVEL_PLACE.match(where):
        # «arrastrá el volumen al 50»: a level, set by its own operation.
        return False
    if not what and _PRONOUN_VERB.search(verb):
        return True
    return bool(what) and (_PRONOUN_OBJECT.match(what) is None or bool(where))


def _carried(head: list[str]) -> bool:
    """«llevala arrastrando a la esquina», «move the file to Archive by dragging it»: a carrying verb whose manner is
    the drag asks for the gesture itself, to whatever place; never a window, the pointer or a level carried so."""

    if _CARRY.match(head[0]) is None:
        return False
    what = _PREPOSITION.split(" " + " ".join(head[1:]) + " ", maxsplit=1)[0].strip()
    return not (_WINDOW.match(what) or _POINTER.match(what) or _LEVEL.match(what))


def _draws(rest: str) -> bool:
    return bool(rest) and _NOT_A_STROKE.match(rest) is None and _STROKE.search(rest) is not None


def asks_to_drag(text: object) -> bool:
    """Whether the person asks BAXY to drag something with the mouse or to draw a stroke (see the module)."""

    for clause in act_clauses(_DRAG_AND_DROP.sub(r"\g<verb>", fold(text))):
        if _OTHER_HEAD.match(clause):
            continue
        # «agarrá la nota y llevala arrastrando …», «draw una línea arrastrando el mouse»: the manner after a head.
        words = clause.split()
        for position, word in enumerate(words):
            tail = " ".join(words[position:])
            dragged = _DRAG_VERB.match(tail)
            if dragged is not None:
                if position == 0 and _drags(dragged.group("verb"), dragged.group("rest") or ""):
                    return True
                if position > 0 and dragged.group("verb").startswith(_DRAG_MANNER):
                    if _draws(" ".join(words[:position])) or _carried(words[:position]):
                        return True
            drawn = _DRAW_VERB.match(tail) if position == 0 else None
            if drawn is not None and _draws(drawn.group("rest") or ""):
                return True
    return False
