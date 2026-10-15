"""Colours: the shades a window's palette may carry for a basic colour the person names (cu-r8, live e2).

Measured 2026-10-07 on a drawing window («abrí Paint y pick the blue color»): its palette has no swatch called «Azul»
or «Blue», only «Añil», «Turquesa», «Gris azulado»…; a person picks the closest shade of blue there. The table below
is data, in both languages: for each basic colour, the names a swatch of that colour carries, the closest shade first.
The names keep their written spelling (accents included): a click by label alone matches the control's name whole.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from .lexicon import COLOUR_NOUNS


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.split())


# (the words a person says for the colour, (Spanish names, English names)): each list the colour's own written name
# first, then its shades, closest first.
_FAMILIES: tuple[tuple[frozenset[str], tuple[str, ...], tuple[str, ...]], ...] = (
    (
        frozenset({"azul", "blue"}),
        ("Azul", "Añil", "Índigo", "Azul oscuro", "Azul marino", "Azul claro", "Celeste", "Turquesa", "Cian"),
        ("Blue", "Indigo", "Dark blue", "Navy", "Navy blue", "Light blue", "Sky blue", "Turquoise", "Cyan"),
    ),
    (
        frozenset({"rojo", "red"}),
        ("Rojo", "Rojo oscuro", "Carmesí", "Escarlata", "Granate", "Bermellón"),
        ("Red", "Dark red", "Crimson", "Scarlet", "Maroon"),
    ),
    (
        frozenset({"verde", "green"}),
        ("Verde", "Verde oscuro", "Verde claro", "Lima", "Esmeralda", "Verde oliva"),
        ("Green", "Dark green", "Light green", "Lime", "Emerald", "Olive"),
    ),
    (
        frozenset({"amarillo", "yellow"}),
        ("Amarillo", "Amarillo claro", "Amarillo oscuro", "Dorado", "Oro"),
        ("Yellow", "Light yellow", "Dark yellow", "Gold"),
    ),
    (
        frozenset({"naranja", "anaranjado", "orange"}),
        ("Naranja", "Naranja oscuro", "Anaranjado", "Ámbar"),
        ("Orange", "Dark orange", "Amber"),
    ),
    (
        frozenset({"violeta", "morado", "purpura", "lila", "purple", "violet"}),
        ("Púrpura", "Morado", "Valeria", "Lavanda", "Lila"),
        ("Purple", "Violet", "Lavender", "Lilac"),
    ),
    (
        frozenset({"rosa", "rosado", "pink"}),
        ("Rosa", "Rosa claro", "Rosado", "Fucsia", "Magenta"),
        ("Pink", "Light pink", "Hot pink", "Fuchsia", "Magenta"),
    ),
    (
        frozenset({"gris", "gray", "grey"}),
        ("Gris", "Gris oscuro", "Gris claro", "Plata", "Plateado"),
        ("Gray", "Grey", "Dark gray", "Dark grey", "Light gray", "Light grey", "Silver"),
    ),
    (
        frozenset({"marron", "cafe", "castano", "brown"}),
        ("Marrón", "Marrón oscuro", "Café", "Castaño", "Chocolate"),
        ("Brown", "Dark brown", "Chocolate", "Tan"),
    ),
    (frozenset({"negro", "black"}), ("Negro",), ("Black",)),
    (frozenset({"blanco", "white"}), ("Blanco", "Marfil"), ("White", "Ivory")),
)

# A control that changes the tool or opens a mode instead of being a colour: the colour picker, the eyedropper.
_TOOL_NOT_COLOUR = re.compile(r"\b(?:selector|picker|cuentagotas|eyedropper|eye\s+dropper|gotero)\b")

# A few words of a window's own controls, by language, to tell which language its palette writes.
_SCREEN_WORDS = {
    "es": frozenset({
        "de", "del", "colores", "archivo", "inicio", "ver", "vista", "herramientas", "formas", "pinceles", "pincel",
        "lapiz", "texto", "seleccionar", "seleccion", "guardar", "cerrar", "ayuda", "edicion", "editar", "insertar",
        "borrador", "relleno", "capas", "imagen", "minimizar", "maximizar", "deshacer", "rehacer",
    }),
    "en": frozenset({
        "of", "the", "colors", "colours", "file", "home", "view", "tools", "shapes", "brushes", "brush", "pencil",
        "text", "select", "selection", "save", "close", "help", "edit", "insert", "eraser", "fill", "layers", "image",
        "minimize", "maximize", "undo", "redo",
    }),
}


def _family(name: object) -> tuple[frozenset[str], tuple[str, ...], tuple[str, ...]] | None:
    key = _fold(name)
    return next((family for family in _FAMILIES if key in family[0]), None)


def is_basic_colour(name: object) -> bool:
    """``name`` is a basic colour a person names («azul», «red», «gris»)."""

    return _family(name) is not None


def colour_shades(name: object, language: str | None = None) -> tuple[str, ...]:
    """The swatch names of the colour ``name``, its own written name and then its shades, closest first, as windows write them; only
    the window's language when it is known (``es``/``en``), both interleaved otherwise. Empty for a word that is no
    basic colour."""

    family = _family(name)
    if family is None:
        return ()
    _, spanish, english = family
    if language == "es":
        return spanish
    if language == "en":
        return english
    mixed: list[str] = []
    for position in range(max(len(spanish), len(english))):
        mixed.extend(names[position] for names in (spanish, english) if position < len(names))
    return tuple(dict.fromkeys(mixed))


def colour_check_words(name: object, covered: Iterable[str] = ()) -> tuple[str, ...]:
    """The folded words a click on a shade of ``name`` carries whole, fewest first, beyond the ``covered`` words a
    check already names: «azul oscuro» needs no word of its own beside «azul»."""

    family = _family(name)
    if family is None:
        return ()
    own = sorted(family[0])
    words = [_fold(word) for word in covered if _fold(word)]
    start = len(words)
    for shade in (*own, *colour_shades(name)):
        folded = _fold(shade)
        if any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", folded) for word in words):
            continue
        words.append(folded)
    return tuple(words[start:])


def shade_of(name: object, control_name: object) -> bool:
    """``control_name`` is a swatch of the colour ``name`` other than the colour's own words: one of its shades,
    whole («Añil» for azul; never «Gris azulado», a grey, nor «Azul» itself)."""

    family = _family(name)
    folded = _fold(control_name)
    if family is None or not folded or folded in family[0]:
        return False
    return any(_fold(shade) == folded for shade in colour_shades(name))


def names_the_colour_kind(name: object) -> bool:
    """«color», «colores», «colour»: the kind of the choice alone (``lexicon.COLOUR_NOUNS``, singular or plural), no
    colour of it. Estabilización G3 (tanda f2nb t3-c19 «y ponle color rojo», planned «hacer clic en color; luego
    seleccionar rojo»): containment took «Editar colores» for it, a button whose modal dialog hung the read 20 s."""

    folded = _fold(name)
    return any(folded == noun or folded in (f"{noun}s", f"{noun}es") for noun in COLOUR_NOUNS)


def names_a_colour(text: object) -> bool:
    """The text says a basic colour (``is_basic_colour``) among its words: «y ponle color rojo», «pick the blue one»."""

    return any(is_basic_colour(word) for word in re.findall(r"[^\W\d_]+", _fold(text)))


def changes_the_tool(control_name: object) -> bool:
    """A control that picks a colour from the canvas or changes the tool (a colour picker, an eyedropper): choosing it
    is never choosing a colour."""

    return _TOOL_NOT_COLOUR.search(_fold(control_name)) is not None


def screen_language(names: Iterable[object]) -> str | None:
    """The language the window's own names are written in (``es``/``en``), from a few of its words; None when they
    do not tell."""

    names = [str(name or "") for name in names]
    tokens = [token for name in names for token in re.findall(r"[a-z]+", _fold(name))]
    spanish = sum(token in _SCREEN_WORDS["es"] for token in tokens)
    english = sum(token in _SCREEN_WORDS["en"] for token in tokens)
    if any(re.search(r"[áéíóúñ¿¡]", name.casefold()) for name in names):
        spanish += 2
    if spanish >= 2 and spanish > 2 * english:
        return "es"
    if english >= 2 and english > 2 * spanish:
        return "en"
    return None
