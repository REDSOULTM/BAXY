"""Windows: focus, minimize/maximize, snap, the other window, a window named by its title. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .grammar import _fold, _has, _strip_request_envelope


_CLOSE_WINDOW_WRAPPER = re.compile(
    r"^(?:(?:la|el|the)\s+)?(?:ventana|window|app|aplicacion|programa|application|program)\s+(?:de|del|of)\s+(?P<name>.+)$"
    r"|^(?:the\s+)?(?P<name_before>.+?)\s+(?:window|app|application)$",
    re.IGNORECASE,
)


_DEICTIC_WINDOW_MUTATION = re.compile(
    r"^[¿?¡!\s]*(?:maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
    r"restaura|restaurar|restore)(?:me|la|lo)?\s+"
    r"(?:"
    r"(?:(?:la|the|esta|this|esa|that)\s+)?(?:ventana|window)"
    r"(?:\s+(?:activa|active|actual|current))?|"
    r"(?:the\s+)?(?:active|current|foreground|front)\s+window|"
    r"(?:la\s+)?ventana\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?"
    r"(?:primer\s+plano|adelante|al\s+frente)|"
    r"(?:the\s+)?window\s+(?:in\s+front|in\s+the\s+foreground|on\s+top)"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


def deictic_window_mutation(folded: str) -> bool:
    """«maximizá esta ventana», «minimize the window»: change the window in front.

    A maximize/minimize/restore whose only referent is «la ventana», «esta
    ventana» or the foreground window binds window.active, never a window
    inventory from which some other window could be chosen. A named window
    («la ventana de Chrome») keeps its named resolution.
    """

    return _DEICTIC_WINDOW_MUTATION.match(folded) is not None


_FOCUS_HEAD_ONLY = r"(?:enfoca|enfocame|enfocar|focus|switch\s+to|cambia\s+a|cambiame\s+a)"


_FOCUS_HEAD_WITH_TAIL = (
    r"(?:trae|traeme|traer|pone|poneme|pon|ponme|poner|lleva|llevame|llevar|"
    r"activa|activame|mostra|mostrame|muestra|muestrame|bring|show|put)"
)


_FOCUS_TAIL = (
    r"(?:al\s+frente|adelante|al\s+primer\s+plano|en\s+primer\s+plano|"
    r"to\s+the\s+front|forward|in\s+front|up\s+front)"
)


_MINIMIZE_HEAD = r"(?:minimiza|minimizame|minimizar|minimise|minimize|minimisa|minimisame)"


_SNAP_HEAD = (
    r"(?:pon|pone|poneme|poner|ponla|ponlo|mueve|mover|moveme|muevela|muevelo|lleva|llevame|llevar|"
    r"coloca|colocame|colocar|acomoda|acomodame|acomodar|arrastra|arrastrame|arrastrar|"
    r"put|move|snap|dock|place|drag)"
)


_SNAP_SIDE = (
    r"(?P<side>(?:a|hacia|en|para)\s+(?:la\s+)?(?:mitad\s+)?(?:izquierda|derecha)(?:\s+de\s+la\s+pantalla)?|"
    r"(?:on|to|at)\s+the\s+(?:left|right)(?:\s+(?:side|half))?(?:\s+of\s+the\s+screen)?|"
    r"(?:left|right))"
)


def explicit_window_title(text: str) -> str | None:
    """Copy one explicitly named window title; never infer a process or HWND."""
    matches = tuple(
        re.finditer(
            r"\b(?:ventana|window)\s+(?:titulada|titled|llamada|called|named|"
            r"(?:con|with)(?:\s+(?:el|the))?\s+(?:t[ií]tulo|title|nombre|name))\s+",
            text,
            re.IGNORECASE,
        )
    )
    if len(matches) != 1:
        return None
    title = text[matches[0].end() :].strip()
    if not title:
        return None
    quotes = {'"': '"', "'": "'", "«": "»", "“": "”", "‘": "’"}
    closing = quotes.get(title[0])
    if closing is not None:
        end = title.find(closing, 1)
        if end < 0 or title[end + 1 :].strip(" .!?"):
            return None
        title = title[1:end]
    return title if title.strip() and len(title) <= 260 and "\0" not in title else None


def has_named_window_target(text: str) -> bool:
    # The same literal relation serves recognition and argument grounding.
    # It supplies a query, never authority over an unobserved window.
    return explicit_window_title(text) is not None


def _window_domain(text: str) -> bool:
    if not _has(text, r"\b(?:ventana|window)\b"):
        return False
    if has_named_window_target(text):
        return True
    if _has(
        text,
        (
            r"\b(?:navegador|browser|aplicacion|application|programa|program|"
            r"spotify|opera|chrome|edge|firefox|notepad|bloc de notas|"
            r"calculadora|calculator)\b"
        ),
    ):
        return True
    if _has(
        text,
        (
            r"\b(?:ventana|window)\s+(?:activa|active|actual|current)\b"
            r"(?!\s+(?:de|del|of|para|for)\b)|"
            r"\b(?:ventana|window)\s+(?:esta|is)\s+(?:activa|active)\b"
            r"|\b(?:ventana|window)\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?"
            r"primer\s+plano\b"
            r"|\bforeground\s+window\b"
        ),
    ):
        return True
    if _has(
        text,
        r"\b(?:esta|this)\s+(?:ventana|window)\b(?!\s+of\s+opportunity)",
    ):
        return True
    return _has(
        text,
        (
            r"\b(?:ventana|window)\b"
            r"(?=\s*(?:[\s?!.]*$|,?\s+(?:y luego|y despues|and then|then)\b))"
        ),
    )


_MINIMIZE_ALL_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:minimiza|minimizame|minimizar|minimise|minimize)\s+(?:me\s+)?"
    r"(?:todas\s+(?:las\s+)?(?:ventanas|apps|aplicaciones)|todas|todo|"
    r"all(?:\s+(?:the|my|of\s+the))?(?:\s+(?:windows|apps|applications))?|everything)"
    r"(?:\s+(?:abiertas|open))?(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*$"
)


# Uso real 2026-09-23 «Ve al homescreen», «Go to the home screen» opened a
# website called homescreen: on a PC the home screen is the desktop, and going
# to it (Win+D) is every window minimized. «abre el escritorio» stays the
# Desktop folder: only a movement or showing verb reads as the desktop view.
PC_HOME_PLACE = r"(?:escritorio|desktop|home\s*screen|pantalla\s+(?:de\s+inicio|principal))"
# Uso real tanda 2 «Ve home.»: said alone after a movement verb, «home» and «inicio» are the PC's home too
# («go home», «vuelve al inicio»). Anywhere else they name other things («home depot», «la página de inicio de
# un sitio», «el inicio de la canción»), so they are home only here, where nothing may follow them.
_BARE_HOME = r"(?:home|inicio)"
_SHOW_DESKTOP_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:(?P<move>ve|vete|anda|andate|vuelve|volve|volvamos|regresa|ir|vamos|llevame|"
    r"go(?:\s+back)?|return|take\s+me(?:\s+back)?|bring\s+me(?:\s+back)?)|"
    r"muestrame|mostrame|muestra|ensename|show(?:\s+me)?)"
    r"\s+(?:(?:a|al|to)\s+)?(?:(?:el|la|the|my|mi)\s+)?"
    rf"(?:{PC_HOME_PLACE}|(?(move){_BARE_HOME}|(?!)))"
    r"(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*$"
)


def minimize_all_request(folded: str) -> bool:
    """MINALL1687 «minimizá todas las ventanas», «minimizá todo»: one order
    over every desktop window, never a named one; going to or showing the
    desktop (the PC's home screen) is the same order."""

    request = _strip_request_envelope(folded)
    return (
        _MINIMIZE_ALL_REQUEST.match(request) is not None
        or _SHOW_DESKTOP_REQUEST.match(request) is not None
    )


# WINDOWS1537 H0263 «cambiá a la otra ventana», H0392 «enfocá la mejor»: a
# window named only by «la otra», «la mejor», «la siguiente» with nothing
# before it; the honest turn asks which. Shared with __main__'s input kinds
# and with the deferred clause reader below.
INDETERMINATE_WINDOW_CLAUSE = re.compile(
    r"[\s¡!¿?]*(?:"
    r"(?:cambia|cambiame|pasa|pasame|anda|andate|ve|salta|volve|vuelve|switch|go|jump|move)"
    r"(?:\s+(?:a|to))?\s+(?:la|the)\s+(?:otra|other|next|siguiente|anterior|previous|ultima|last|mejor|best)"
    r"(?:\s+(?:ventana|window|pestana|tab))?|"
    r"(?:enfoca|enfocame|foca|activa|activame|trae|traeme|pone|poneme|lleva|llevame|focus|bring|put)"
    r"\s+(?:la|the)\s+(?:otra|other|mejor|best|siguiente|next|anterior|previous|ultima|last|"
    r"mas\s+grande|biggest|largest|mas\s+chica|smallest|mas\s+importante|principal|main)"
    r"(?:\s+(?:ventana|window))?(?:\s+(?:al\s+frente|adelante|to\s+the\s+front|forward))?"
    r")[\s.!?¿¡]*"
)


# REOPEN1993 H0263 «cambiá a la otra ventana»: «la otra» (or «la anterior»,
# «la siguiente») with nothing named before it is the window right behind
# the one in front — deterministic, so the turn switches and says to which.
# «la mejor», «la más grande» keep asking (WINDOWS1537).
_OTHER_WINDOW_SWITCH = re.compile(
    r"[\s¡!¿?]*(?:"
    r"(?:cambia|cambiame|pasa|pasame|anda|andate|ve|salta|volve|vuelve|switch|go|jump|move|"
    r"enfoca|enfocame|activa|activame|trae|traeme|pone|poneme|lleva|llevame|focus|bring|put)"
    r"(?:\s+(?:a|to))?\s+(?:la|the)\s+(?:"
    r"(?:otra|other|anterior|previous|siguiente|next)(?:\s+(?:ventana|window))?|"
    r"(?:ventana|window)\s+(?:anterior|previous|siguiente|next))"
    r"(?:\s+(?:al\s+frente|adelante|to\s+the\s+front|forward))?"
    r")[\s.!?¿¡]*"
)


def other_window_switch_request(text: str) -> bool:
    """True for a switch to «la otra/anterior/siguiente ventana» with no other clause."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return bool(folded) and _OTHER_WINDOW_SWITCH.fullmatch(folded) is not None
