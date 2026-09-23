"""Screen and UI: clipboard, screenshots, calculator, clicks and typing in the visible window. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _match, _has, _REQUEST_PREFIX, _strip_request_envelope, _request_head, _head_is, _is_negative_effect_clause, _KNOWN_APPLICATION, _OPEN, _READ, _SEARCH
from .intent import EffectIntent, _is_negated_match, _append
from .catalog import ApplicationCatalogIndex, _application_name_key, build_application_catalog_index, _catalog_alias_key, _MESSAGING_CLIENT_KEY
from .web import _VISIBLE_CLICK_NAVIGATE, _VISIBLE_CLICK_WEB_DESTINATION


def _clipboard_selection_domain(text: str) -> bool:
    return _has(text, r"\b(?:seleccion|selection)\b") and not _has(
        text,
        (
            r"\b(?:seleccion|selection)\s+(?:nacional|national|electoral|"
            r"deportiva|sports?|de|del|of)\b"
        ),
    )


def _clipboard_copy_domain(text: str) -> bool:
    """Recognize a literal local source copied into the OS clipboard."""

    return _clipboard_selection_domain(text) or (
        _has(text, r"\b(?:copia|copiar|copy)\b")
        and _has(
            text,
            r"\b(?:texto|text)\b.{0,100}\b(?:al|to the)\s+"
            r"(?:portapapeles|clipboard)\b",
        )
    )


def _clipboard_paste_domain(text: str) -> bool:
    """Recognize a paste of the OS clipboard rather than physical gluing.

    ``pegar`` means both "paste" and "glue", so the verb alone proved nothing:
    "pega la etiqueta en el frasco de mermelada" resolved to clipboard.paste
    and would have pasted into whatever had focus. The clipboard has to be
    named, or the pasted thing has to be what was copied, or the target has to
    be the focused control. Its sibling ``_clipboard_copy_domain`` already
    guarded copying this way; only pasting was left open.
    """

    return (
        _has(text, r"\bportapapeles\b|\bclipboard\b")
        or _has(
            text,
            r"\b(?:lo|el\s+texto|la\s+seleccion|what)\s+que\s+"
            r"(?:copie|copiaste|copiamos)\b"
            r"|\b(?:copie|copiaste|copiado|copiada|copied)\b",
        )
        or _has(
            text,
            r"\b(?:pegalo|pegala|paste\s+it)\b.{0,24}"
            r"\b(?:aca|aqui|ahi|here|there)\b|"
            r"\b(?:aca|aqui|ahi|here|there)\b.{0,16}\b(?:pegalo|pegala|paste)\b",
        )
        or _has(
            text,
            r"\b(?:campo|control|cuadro|casilla|field|box)\b"
            r".{0,24}\b(?:enfocad[oa]|activ[oa]|focused|active)\b"
            r"|\b(?:enfocad[oa]|focused)\b.{0,24}\b(?:campo|control|field)\b",
        )
        # A destination that belongs to the machine also settles the sense:
        # "pega esto en el bloc de notas" is a paste, "pega el patch en la
        # mochila" is not.
        or _has(
            text,
            rf"\b(?:en|into|in|on)\b.{{0,24}}\b(?:{_KNOWN_APPLICATION}|"
            r"documento|documentos|document|documents|nota|notas|note|notes|"
            r"archivo|archivos|file|files|chat|navegador|browser|correo|email|"
            r"terminal|consola|console|editor|celda|cell|formulario|form|"
            r"buscador|barra\s+de\s+direcciones|address\s+bar)\b",
        )
    )


_CALC_NUMBER = r"\d{1,12}(?:[.,]\d{1,6})?"


_CALC_MENTION = r"\b(?:calc|calcu|calculadora|calculator)\b"


_CALC_VERB_OPERATORS = (
    (r"(?:multiplic[aá]|multiplicame|multiplicar|multiply)", r"(?:por|x|×|\*|by|times)", "*"),
    (r"(?:sum[aá]|sumame|sumar|add)", r"(?:m[aá]s|mas|y|\+|and|plus|to)", "+"),
    (r"(?:rest[aá]|restame|restar|subtract)", r"(?:menos|-|minus|from)", "-"),
    (r"(?:divid[ií]|divideme|dividir|divide)", r"(?:entre|por|÷|/|by)", "/"),
)


_CALC_INFIX = {"por": "*", "x": "*", "×": "*", "*": "*", "mas": "+", "más": "+", "+": "+", "menos": "-", "-": "-", "entre": "/", "÷": "/", "/": "/", "times": "*", "plus": "+", "minus": "-"}


def calculator_expression_request(text: str) -> str | None:
    """UI1725 «multiplicá 6 por 7 en la calc», «Suma 2 más 2 en la Calculadora»,
    «cuánto es 6 por 7 en la calculadora»: the arithmetic the person wants typed
    into the open Calculator, as an expression over the person's own numbers;
    None without a Calculator mention or a readable binary operation."""

    folded = _strip_request_envelope(_fold(text)).strip()
    if not _has(folded, _CALC_MENTION) or _has(folded, r"\b(?:abre|abrir|abri|cierra|cerra|open|close)\b"):
        return None
    for verb, operator, symbol in _CALC_VERB_OPERATORS:
        found = re.search(
            rf"\b{verb}\s+(?P<a>{_CALC_NUMBER})\s*{operator}\s*(?P<b>{_CALC_NUMBER})\b",
            folded,
        )
        if found is not None:
            a, b = found.group("a"), found.group("b")
            if symbol == "-" and re.search(r"\bfrom\b", found.group(0)):
                a, b = b, a
            return f"{a}{symbol}{b}"
    infix = re.search(
        rf"(?P<a>{_CALC_NUMBER})\s*(?P<op>por|x|×|\*|mas|\+|menos|-|entre|÷|/|times|plus|minus)\s*(?P<b>{_CALC_NUMBER})\b",
        folded,
    )
    if infix is not None and (
        _head_is(_request_head(folded), r"(?:calcula|calculame|calcular|calculate|compute|cuanto|cuanto|resolve|resolvé|resolver)")
        or _has(folded, r"^[¿?¡!\s]*(?:cuanto|cuánto|what)\s+(?:es|is|da|sale)\b")
    ):
        return f"{infix.group('a')}{_CALC_INFIX[infix.group('op')]}{infix.group('b')}"
    return None


_CLIPBOARD_WRITE_HEAD = (
    r"(?:copia|copiar|copiame|copy|pon|pone|poneme|ponme|ponelo|ponlo|put|"
    r"escribe|escribi|escribime|write|guarda|guardame|save|deja|dejame|leave|"
    r"mete|meteme|carga|cargame|load)"
)


_CLIPBOARD_QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|«([^»\n]+)»|‘([^’\n]+)’')


def literal_clipboard_write_text(text: str) -> str | None:
    """Return the literal a person asked to put on the OS clipboard, or None.

    «Copia a mi portapapeles "Hola"», «copiá esto al portapapeles: hola mundo»,
    «Copy "hello" to my clipboard»: the head is a copy/put verb, the clipboard
    is named and the literal is either quoted or introduced by a colon after
    the clipboard noun. The literal keeps its case and accents. Nothing is
    inferred when no literal is given («copiá este texto al portapapeles» stays
    a clarification) or when the clause is a prohibition.
    """

    collapsed = " ".join(text.split())
    folded = _strip_request_envelope(_fold(collapsed))
    if not _has(folded, r"\b(?:portapapeles|clipboard)\b"):
        return None
    if not _head_is(_request_head(folded), _CLIPBOARD_WRITE_HEAD):
        return None
    if _is_negative_effect_clause(folded):
        return None
    quoted = [
        group
        for found in _CLIPBOARD_QUOTED.finditer(collapsed)
        for group in found.groups()
        if group
    ]
    marks = sum(collapsed.count(mark) for mark in '"“”«»‘’')
    if len(quoted) > 1 or (quoted and marks % 2 == 1):
        # Two literals, or one closed and one left open: which one is ambiguous.
        return None
    if quoted:
        literal = quoted[0].strip()
        return literal or None
    # Fase 3.5 (real log): «Copia a mi portapapeles "Hola» — dictation drops the
    # closing quote; one opening quote at the end of the request opens the literal.
    unclosed = re.search(r'["“«‘](?P<literal>[^"“”«»‘’\n]+)$', collapsed)
    if unclosed is not None and marks == 1:
        literal = unclosed.group("literal").strip()
        return literal or None
    colon = re.search(
        r"\b(?:portapapeles|clipboard)\b[^:]*:\s*(?P<literal>.+)$",
        collapsed,
        re.IGNORECASE,
    )
    if colon is None:
        return None
    literal = colon.group("literal").strip()
    if literal.endswith(".") and literal.count(".") == 1:
        # The sentence's own full stop is not part of a dictated fragment.
        literal = literal[:-1].rstrip()
    return literal or None


def _review_input_and_capture_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_capture: bool,
    context_open_application: bool,
) -> None:
    """Append keyboard, clipboard, screenshot, and OCR effects."""

    if _head_is(head, r"(?:dale|press|hit)") and _has(
        folded,
        r"\b(?:dale|press|hit)\s+(?:enter|intro|return)\b",
    ):
        _append(
            matches,
            folded,
            "input.key.press",
            r"\b(?:enter|intro|return)\b",
        )
    if (
        _head_is(head, r"(?:escribe|escribir|escribi|type)")
        and _has(folded, r"\b(?:escribe|escribir|escribi|type)\b")
        and (
            _has(folded, r"\b(?:literalmente|literally)\b")
            or context_open_application
            or _has(
                folded,
                r"\b(?:en|into|in)\s+(?:la\s+|the\s+)?"
                r"(?:busqueda|search|campo|field|cuadro|box|control)\b",
            )
            or _has(
                folded,
                r"\b(?:type|escribe|escribi)\s+\S.{0,80}\b(?:for\s+me|por\s+mi)\b",
            )
        )
    ):
        _append(
            matches,
            folded,
            "input.text.type",
            r"\b(?:escribe|escribir|escribi|type)\b",
        )
    if _head_is(head, r"(?:selecciona|seleccionar|select)") and _has(
        folded, r"\b(?:selecciona|seleccionar|select)\s+(?:todo|all)\b"
    ):
        _append(
            matches,
            folded,
            "input.select.all",
            r"\b(?:selecciona|seleccionar|select)\b",
        )
    if (
        _head_is(head, _OPEN)
        and _has(folded, r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b")
        and _has(folded, rf"\b{_OPEN}\b")
    ):
        _append(
            matches,
            folded,
            "input.keyboard.open",
            r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b",
        )
    if (
        _head_is(head, _READ)
        and _has(folded, r"\b(?:portapapeles|clipboard)\b")
        and _has(folded, rf"\b{_READ}\b")
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:portapapeles|clipboard)\b",
        )
    if _has(folded, r"\b(?:portapapeles|clipboard)\b") and _has(
        folded,
        r"^(?:que hay|que tengo|what(?:'s| is)(?: there)?|dime que hay)\b",
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:portapapeles|clipboard)\b",
        )
    if _has(
        folded,
        r"^(?:what\s+did\s+i\s+copy(?:\s+last)?|"
        r"last\s+(?:thing\s+)?(?:i\s+)?copied|"
        r"que\s+(?:fue\s+lo\s+que\s+)?(?:copie|copié)\s+"
        r"(?:ultimo|ayer|recien|last))\b",
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:copy|copied|copie|copié)\b",
        )
    if (
        _head_is(head, r"(?:pega|pegar|pegalo|pegala|paste)")
        and _has(folded, r"\b(?:pega|pegar|pegalo|pegala|paste)\b")
        and _clipboard_paste_domain(folded)
    ):
        paste = _match(folded, r"\b(?:pega|pegar|pegalo|pegala|paste)\b")
        if paste is not None and _has(
            folded,
            rf"\b(?:en|into)\b.{{0,80}}\b(?:archivo\s+nuevo|new\s+file)\b"
            rf".{{0,80}}\b(?:{_KNOWN_APPLICATION})\b",
        ):
            matches.append((paste.start(), -1, "app.open"))
        _append(
            matches,
            folded,
            "clipboard.paste",
            r"\b(?:pega|pegar|pegalo|pegala|paste)\b",
        )
    if _head_is(head, r"(?:copia|copiar|copy)") and _clipboard_copy_domain(folded):
        _append(matches, folded, "clipboard.copy", r"\b(?:copia|copy)\b")
    active_window_capture = (
        _head_is(head, r"(?:captura|capture|toma|tomar|take)")
        and _has(folded, r"\b(?:captura|capture|toma|tomar|take)\b")
        and _has(
            folded,
            r"\b(?:ventana\s+(?:activa|actual)|active\s+window|current\s+window)\b",
        )
    )
    if active_window_capture:
        _append(
            matches,
            folded,
            "capture.active.window",
            r"\b(?:captura|capture|toma|tomar|take)\b",
        )
    capture_object = _has(
        folded,
        r"\b(?:captura de (?:toda )?la pantalla|captura de pantalla|"
        r"foto de captura|pantallazo|screenshot|screen capture)\b",
    ) or (_has(folded, r"\b(?:captura|capture)\b") and _has(folded, r"\bocr\b")) or _has(
        # Fase 3.5 (layer C: «sacá una captura»): on a PC a bare «captura» taken
        # as the whole request is a screenshot.
        folded,
        r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:haz|hace|haceme|hazme|toma|tomame|saca|sacame|take)\s+(?:una\s+)?captura"
        r"(?:\s+(?:ahora(?:\s+mismo)?|ya|porfa|por\s+favor|please))?[\s.!?]*$",
    )
    capture_requested = (
        capture_object
        and _has(
            folded,
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
                r"(?:puedes|podrias|can you|could you|would you)\s+)?"
                r"(?:haz|hacer|hace|haceme|hazme|toma|tomar|tomame|saca|sacale|sacame|crea|capture|take)\s+"
                r"(?:(?:una|un|a|the)\s+)?"
                r"(?:foto de captura|captura|pantallazo|screenshot|screen capture)\b"
            ),
        )
        and not active_window_capture
    )
    if capture_requested:
        _append(
            matches,
            folded,
            "capture.screenshot",
            r"\b(?:foto de captura|captura|pantallazo|screenshot|screen capture)\b",
        )
        if _has(
            folded,
            r"\b(?:que\s+se\s+ve|what(?:'s| is)\s+visible|"
            r"describe(?:me)?|describe it|que hay en la imagen)\b",
        ) and not _has(folded, r"\blo que ves\b|\bque ves\b|\bwhat you see\b"):
            # SCREEN1485: «describeme lo que ves» after a capture is the
            # screen-content reading below, not an image description.
            _append(
                matches,
                folded,
                "vision.describe",
                r"\b(?:que\s+se\s+ve|what(?:'s| is)\s+visible|"
                r"describe(?:me)?|describe it|que hay en la imagen)\b",
                priority=1,
            )
    # SCREEN1417 «leé la pantalla», «qué hay en la pantalla», «describime la
    # pantalla», «qué ves en mi pantalla»: without a vision provider the truthful
    # reading of a screen is its recognized text, which the composer frames as
    # what it can read. The phone/car exclusion below still applies.
    bare_screen_read = (
        _head_is(head, _READ)
        and _has(folded, r"^[¿?¡!\s]*(?:por favor\s*[,:]?\s*)?(?:lee|leer|leeme|read)\s+(?:me\s+)?(?:la|mi|the|my)\s+(?:pantalla|screen)[\s?!.]*$")
    )
    screen_content_question = _has(
        folded,
        r"^[¿?¡!\s]*(?:(?:decime|dime|contame|cuentame|tell me)\s+)?"
        r"(?:que|what)\s+(?:hay|se ve|aparece|ves|estas viendo|is|is there|do you see|are you seeing|can you see)"
        r"(?:\s+(?:ahora|now))?\s+(?:en|on)\s+(?:mi|la|tu|my|the)\s+(?:pantalla|screen)[\s?!.]*$|"
        r"^[¿?¡!\s]*(?:describe|describi|describime|describeme|describi?la|describila)\s+"
        r"(?:(?:mi|la|my|the)\s+(?:pantalla|screen)|lo que ves(?:\s+(?:en|on)\s+(?:mi|la|my|the)\s+(?:pantalla|screen))?|"
        r"what you see(?:\s+on\s+(?:my|the)\s+screen)?)[\s?!.]*$|"
        # SCREEN1485 «Toma un screenshot de la pantalla ahora mismo y describeme
        # lo que ves»: a capture order followed by the description of what is
        # seen is the same screen-content reading.
        r"^[¿?¡!\s]*(?:toma|tomame|saca|sacame|hace|haceme|haz|hazme|take|capture)\s+(?:(?:un|una|a)\s+)?"
        r"(?:screenshot|screen\s*shot|screen\s+capture|captura(?:\s+de\s+pantalla)?|pantallazo)"
        r"(?:\s+(?:de|of)\s+(?:la|mi|the|my)\s+(?:pantalla|screen))?(?:\s+(?:ahora(?:\s+mismo)?|now|right\s+now))?"
        r"\s*(?:,\s*|\s+(?:y|and)\s+)(?:describe|describi|describime|describeme|decime|dime|contame|cuentame|tell\s+me)\s+"
        r"(?:lo\s+que\s+ves|que\s+ves|que\s+hay|what\s+you\s+see|what(?:'s|\s+is)\s+(?:there|on\s+it))"
        r"(?:\s+(?:en|on)\s+(?:mi|la|my|the)\s+(?:pantalla|screen))?[\s?!.]*$",
    )
    implicit_screen_read = (
        (
            _head_is(head, _READ)
            and _has(folded, r"\b(?:pantalla|screen)\b")
            and _has(
                folded,
                r"\b(?:mensaje|message|error|texto|text|lo que|what)\b",
            )
        )
        or bare_screen_read
        or screen_content_question
    ) and (
        not _has(
            folded,
            r"\b(?:como|how)\s+(?:puedo|podria|can i|could i|to)\b",
        )
        and not _has(
            folded,
            r"\b(?:pantalla|screen)\s+(?:del|de mi|of my)\s+"
            r"(?:telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
        )
    )
    if implicit_screen_read:
        if not any(operation == "capture.screenshot" for _, _, operation in matches):
            # SCREEN1485: an explicit capture order («Toma un screenshot … y
            # describeme lo que ves») already appended the capture above.
            _append(
                matches,
                folded,
                "capture.screenshot",
                rf"\b{_READ}\b|\b(?:que|what|describ\w*)\b",
            )
        _append(
            matches,
            folded,
            "ocr.read",
            r"\b(?:pantalla|screen)\b|\blo que ves\b|\bwhat you see\b",
            priority=1,
        )
    if context_capture and _has(
        folded,
        r"^(?:describe|describelo|describela)"
        r"(?:\s+(?:it|that|the|same|esto|eso|esa|la|misma))?"
        r"(?:\s+(?:scene|image|capture|escena|imagen|captura|vista))?"
        r"[\s?!.]*$",
    ):
        _append(
            matches,
            folded,
            "vision.describe",
            r"\b(?:describe|describelo|describela)\b",
        )
    contextual_capture_read = (
        context_capture
        and _head_is(head, _READ)
        and _has(folded, r"\b(?:text|texto|words?|palabras?)\b")
        and _has(
            folded,
            r"\b(?:image|imagen|capture|captura|screenshot|screen|pantalla)\b",
        )
        and _has(
            folded,
            r"\b(?:that|same|the|esa|misma|la|from|de|en)\b",
        )
    )
    if contextual_capture_read:
        _append(matches, folded, "ocr.read", rf"\b{_READ}\b", priority=1)
    ocr_requested = (
        _head_is(head, _READ)
        and _has(
            folded,
            rf"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            rf"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"{_READ}\b.{{0,80}}\bocr\b",
        )
        and not _has(
            folded,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        )
    ) or (
        capture_requested
        and _has(
            folded,
            r"\b(?:y|and)\s+(?:leela|leelo|leerla|leerlo|read it)\s+"
            r"(?:con|with)\s+ocr\b",
        )
    )
    if ocr_requested and (capture_requested or context_capture):
        _append(matches, folded, "ocr.read", r"\bocr\b", priority=1)


_VISIBLE_CLICK_POINTING = (
    r"(?:haz\s+clic(?:\s+en)?|hace\s+clic(?:k)?(?:\s+en)?|clic(?:k)?\s+en"
    r"|click(?:ea|ear)?(?:\s+(?:on|it))?"
    r"|apreta(?:le|lo|la)?(?:\s+en)?|apretar|aprieta(?:\s+en)?"
    r"|pulsa(?:lo|la|le)?|presiona(?:lo|la|le)?|press(?:\s+it)?)"
)


# «en la calculadora apretá el 5» / «apretá el 5 en la calculadora»: the app
# names where the control lives; the label is the control alone (UI1273).
_VISIBLE_CLICK_APP_CONTEXT = (
    r"(?:en|in|on)\s+(?:la|el|the)\s+(?:calculadora|calc|calculator|app|"
    r"aplicacion|application|ventana|window|pantalla|screen)"
)


_VISIBLE_CLICK_CONTROL_NOUN = (
    r"(?:boton|button|control|enlace|link|pestana|tab|seccion|section)"
)


# H0101 «Hay un diálogo de descarga de doom eternal abierto en steam, completalo
# haciendo click en instalar»: el verbo principal —«completalo»— no nombra
# ninguna operación, y el pedido moría sin leerse. Pero la frase sí dice qué
# hacer: la cláusula de gerundio nombra el clic y su etiqueta. Cuando está, es
# ella el acto de habla, venga el verbo principal que venga.
_GERUND_CLICK = re.compile(
    r"\b(?:haciendo|dando|pulsando|apretando|presionando)\s+(?:un\s+|el\s+)?"
    r"(?:clic|click|clics|clicks)\s+(?:en|sobre|a)\s+"
    r"(?:(?:el|la|los|las)\s+)?"
    r"(?:(?:boton|button|control|enlace|link|pestana|tab|seccion|section)\s+)?"
    r"(?:(?:el|la|los|las)\s+)?"
    r"(?P<label>[^,;.!?]{1,80}?)"
    r"(?:\s+(?:boton|button|control|enlace|link|pestana|tab|seccion|section))?"
    r"[\s?!.]*$"
    r"|\bby\s+clicking\s+(?:on\s+)?"
    r"(?:the\s+)?(?:(?:button|control|link|tab|section)\s+)?(?:the\s+)?"
    r"(?P<label_en>[^,;.!?]{1,80}?)"
    r"(?:\s+(?:button|control|link|tab|section))?"
    r"[\s?!.]*$",
)


def _gerund_click_label(text: str) -> str | None:
    """Name the control of a «haciendo click en X» clause, or nothing."""

    folded = _fold(text)
    if _has(folded, r"\bno\s+(?:lo|la|los|las)?\s*\w*\s*haciendo\s+cl"):
        return None
    found = _GERUND_CLICK.search(folded)
    if found is None:
        return None
    label = (found.group("label") or found.group("label_en") or "").strip(" \t\"'`")
    if (
        not label
        or len(label.split()) > 6
        or _VISIBLE_CLICK_WEB_DESTINATION.search(label) is not None
        or re.search(r"\b(?:tecla|teclas|key|keys|teclado|keyboard)\b", label) is not None
    ):
        return None
    return label


def _visible_click_label(
    text: str,
    *,
    allow_navigate: bool = False,
) -> str | None:
    """Extract the unique visible-control label, or nothing.

    Navigate heads (``ve a`` / ``go to``) are click only after an app is
    already open. Bare web destinations stay with the browser family.
    """

    head = _VISIBLE_CLICK_POINTING
    if allow_navigate:
        head = rf"(?:{head}|{_VISIBLE_CLICK_NAVIGATE})"
    text = re.sub(
        rf"^([¿?¡!\s]*){_VISIBLE_CLICK_APP_CONTEXT}\s+", r"\1", _fold(text), count=1,
    )
    text = re.sub(rf"\s+{_VISIBLE_CLICK_APP_CONTEXT}(?=[\s?!.]*$)", "", text, count=1)
    gerund = _gerund_click_label(text)
    if gerund is not None:
        return gerund
    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{head}\s+"
            r"(?:(?:el|la|los|las|the)\s+)?"
            rf"(?:{_VISIBLE_CLICK_CONTROL_NOUN}\s+)?"
            r"(?P<label>[^,;.!?]{1,80}?)"
            rf"(?:\s+{_VISIBLE_CLICK_CONTROL_NOUN})?"
            r"[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    label = request.group("label").strip(" \t\"'`")
    label = re.sub(
        r"^(?:el|la|los|las|the)\s+",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip()
    if (
        not label
        or len(label.split()) > 6
        or _VISIBLE_CLICK_WEB_DESTINATION.search(label) is not None
        # «pulsá la tecla enter» / «presioná enter» are key presses, not
        # visible controls (UI1273).
        or re.search(r"\b(?:tecla|teclas|key|keys|teclado|keyboard)\b", label, re.IGNORECASE) is not None
        or re.fullmatch(
            r"(?:enter|intro|return|escape|esc|tab|espacio|space|supr|delete|backspace|retroceso|"
            r"ctrl|control|alt|shift|win|windows|inicio|home|fin|end)"
            # «apretá enter en Discord»: the application the key goes to.
            r"(?:\s+(?:en|in|on)\s+\S.*)?",
            label,
            re.IGNORECASE,
        ) is not None
    ):
        return None
    return label[:80]


def _click_in_application(
    folded: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str] | None:
    """UI1735: a click or navigation order framed by «en/in/on <catalog app>»
    at either end of the clause → (catalog key, clause without the frame).
    Generic frames («en la calculadora», «en la app») keep the UI1273 path."""

    catalog = build_application_catalog_index(application_names)
    occurrence = catalog.occurrence_pattern
    if occurrence is None:
        return None
    text = folded.strip()
    for pattern in (
        r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?P<app>.+?)\s*[,;:]?\s+(?P<clause>(?:ve|vete|anda|andate|entra|metete|navega|apreta|pulsa|presiona|hace|haz|toca|clickea|clica|go|navigate|click|press|tap|open)\b.+)$",
        r"^(?P<clause>.+?)\s+(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s?!.]*$",
    ):
        found = re.match(pattern, text)
        if found is None:
            continue
        candidate = found.group("app").strip(" ,.;:!?")
        hit = occurrence.fullmatch(candidate)
        # A catalog name as written, or a bilingual alias of one («Opera» for
        # «Navegador Opera GX», «Epic Games» for «Epic Games Launcher»).
        key = _catalog_alias_key(
            _application_name_key(hit.group("target") if hit is not None else candidate),
            catalog.keys,
        )
        if key is None:
            continue
        clause = found.group("clause").strip(" ,;:")
        if not clause:
            continue
        if _MESSAGING_CLIENT_KEY.search(key) is not None and not _has(
            clause, r"^(?:ve|vete|anda|andate|entra|metete|go|navigate|navega)\b"
        ):
            # LIMITS1681 «apretá enviar en WhatsApp», «en Discord apretá enter»,
            # and the microphone reading of «en Discord apretá silenciar» stay as
            # they are: inside a messaging client only going to a chat or a
            # channel is a click on its interface; pressing its controls is not.
            return None
        return key, clause
    return None


def _visible_click_intent(
    text: str,
    available_operations: frozenset[str],
    *,
    allow_navigate: bool = False,
) -> EffectIntent | None:
    """Resolve find-and-activate as one grounded visible-control effect."""

    if "input.visible.click" not in available_operations:
        return None
    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{_SEARCH}\b\s+"
            r"(?:(?:(?:el|la|the)\s+)?(?:boton|button|control|enlace|link)\b"
            r"[^,;.!?]{1,120}|(?:(?:el|la|the)\s+)?[^,;.!?]{1,100}\s+"
            r"(?:boton|button|control|enlace|link))\s+\b(?:y|and)\b\s+"
            r"(?:presionalo|presionala|pulsa(?:lo|la)?|haz\s+clic|"
            r"click(?:\s+it)?|press(?:\s+it)?)[\s?!.]*$"
        ),
    )
    if request is not None and not _is_negated_match(text, request):
        evidence = request.group(0).strip(" ,;:-")[:240]
        return EffectIntent(("input.visible.click",), (evidence,))
    if _visible_click_label(text, allow_navigate=allow_navigate) is None:
        return None
    if _has(_fold(text), r"\b(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)\b") and _has(
        _fold(text), r"\b(?:enviar|envia|send|submit|mandar|manda|publicar|post)\b"
    ):
        # LIMITS1681 «apretá enviar en WhatsApp»: a send control inside a
        # messaging client is a known limit (never a real message). Going to
        # a channel or a chat («ve a Cotele en Discord») is navigation of the
        # client's interface (UI1735) and stays a click.
        return None
    evidence = text.strip(" ,;:-")[:240]
    # H0096: mirar antes de pulsar. La lectura de controles es de solo lectura,
    # no cruza frontera de efecto y le da al redactor lo que hay delante, que es
    # lo que hace falta para decir la verdad cuando la etiqueta no aparece en
    # ninguna parte —Among Us no esta instalado en este PC—.
    if "input.visible.controls" in available_operations:
        return EffectIntent(
            ("input.visible.controls", "input.visible.click"), (evidence, evidence),
        )
    return EffectIntent(("input.visible.click",), (evidence,))
