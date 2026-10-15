"""Gate screens (v3 limits, M2): an application that shows, instead of its working window, a screen that asks
for something only the person can give or wait for. Measured live 2026-10-07: Outlook on its account wizard
(«Configuración de cuenta de correo electrónico», «¿No tiene ninguna cuenta?»), a notes app asking to sign in, a
repository client that «Can't find» a folder deleted from the disk, a notes app updating itself. The words are data,
in Spanish and English (folded, no accents); which window shows them is never named."""

from __future__ import annotations

import re
import unicodedata

from .account_acts import said_as_not_to_do

# Each kind of gate with the words its screen says.
_GATES: dict[str, tuple[str, ...]] = {
    "account": (
        "configuracion de cuenta", "configurar cuenta", "configurar una cuenta", "configura tu cuenta",
        "agregar cuenta", "agregar una cuenta", "agrega una cuenta", "anadir cuenta", "anadir una cuenta",
        "no tiene ninguna cuenta", "no tienes ninguna cuenta", "no tiene una cuenta", "no tienes una cuenta",
        "iniciar sesion", "inicia sesion", "inicie sesion", "inicio de sesion",
        "account setup", "set up your account", "set up an account", "add account", "add an account",
        "add your account", "sign in", "sign-in", "log in", "don't have an account", "do not have an account",
    ),
    "updating": (
        "actualizando", "se esta actualizando", "instalando actualizaciones", "instalando la actualizacion",
        "descargando la actualizacion", "actualizacion en curso",
        "updating", "installing updates", "installing update", "downloading update", "update in progress",
    ),
    "missing": (
        "no se encuentra", "no se puede encontrar", "no se encontro", "no encuentra", "no pudo encontrar",
        "can't find", "cannot find", "can not find", "couldn't find", "could not find", "was moved or deleted",
        "se movio o se elimino", "no longer exists", "ya no existe",
    ),
}

# The fields of a sign-in form: a screen of few controls that asks for an address or a password, beside an
# address already written, is an account's gate (live v3-05: the wizard read as «correo electrónico» and an address).
_ACCOUNT_FIELDS: tuple[str, ...] = (
    "correo electronico", "direccion de correo", "contrasena", "email", "e-mail", "email address", "password",
)

# The controls that let a person pass a gate without giving anything (named as data, pressed at most once).
_SKIPS: tuple[str, ...] = (
    "ahora no", "mas tarde", "omitir", "saltar", "quizas mas tarde",
    "not now", "later", "maybe later", "skip", "skip for now", "remind me later",
)

# What a request says when the gate itself is what it asks to deal with (sign in, add the account, update): whole
# words, folded, with their plurals and conjugations («busca actualizaciones», «check for updates», «abre mis
# cuentas», «sesiones de concentración»), never a word that only begins alike («cuéntame»).
_ASKS_GATE_ROOTS: tuple[str, ...] = (
    r"actualiz\w*", r"updat\w*", r"cuentas?", r"sesion(?:es)?", r"contrasenas?", r"passwords?", r"accounts?",
    r"log(?:in|on)s?", r"signins?",
)
# The same, said in two words («sign in», «logging in», «log on»).
_ASKS_GATE_PHRASES: tuple[str, ...] = ("sign", "signing", "log", "logging")
_ASKS_GATE_PARTICLES: tuple[str, ...] = ("in", "on", "into")
# Sayings where «cuenta» is no account: «darte cuenta», «me di cuenta», «tener en cuenta», «a fin de cuentas».
_NOT_AN_ACCOUNT: tuple[str, ...] = (
    "dar cuenta", "darte cuenta", "darme cuenta", "darse cuenta", "darnos cuenta", "darle cuenta", "date cuenta",
    "dese cuenta", "di cuenta", "diste cuenta", "dio cuenta", "dimos cuenta", "dieron cuenta", "doy cuenta",
    "das cuenta", "da cuenta", "damos cuenta", "dan cuenta", "en cuenta", "fin de cuentas", "por su cuenta",
    "por tu cuenta", "por mi cuenta", "por cuenta propia",
)

_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("’", "'")
    return " ".join(text.split())


def _words(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?:^|(?<=[^\w]))(?:" + "|".join(re.escape(word) for word in words) + r")(?=$|[^\w])")


_GATE_PATTERNS = {kind: _words(words) for kind, words in _GATES.items()}
_FIELD_PATTERN = _words(_ACCOUNT_FIELDS)
_ASK_PATTERN = re.compile(
    r"(?:^|(?<=[^\w]))(?:(?:" + "|".join(_ASKS_GATE_ROOTS) + r")|(?:" + "|".join(_ASKS_GATE_PHRASES)
    + r")[\s-]+(?:" + "|".join(_ASKS_GATE_PARTICLES) + r"))(?=$|[^\w])"
)
_NOT_AN_ACCOUNT_PATTERN = _words(_NOT_AN_ACCOUNT)
_SKIP_NAMES = frozenset(_SKIPS)


def gate_kind(text: object) -> str | None:
    """The kind of gate a line or a title says («Iniciar sesión» → account), or None."""

    folded = _fold(text)
    if not folded:
        return None
    return next((kind for kind, pattern in _GATE_PATTERNS.items() if pattern.search(folded)), None)


def names_an_account_field(text: object) -> bool:
    """A line that names a sign-in field («correo electrónico», «Password»), never a sentence about it."""

    folded = _fold(text)
    return bool(folded) and len(folded.split()) <= 4 and _FIELD_PATTERN.search(folded) is not None


def is_an_address(text: object) -> bool:
    """A line that is an e-mail address (the person's own: never quoted back)."""

    return _ADDRESS.search(str(text or "")) is not None


def names_a_gate_skip(name: object) -> bool:
    """A control that passes a gate without giving anything («Ahora no», «Skip»)."""

    return _fold(name).strip(" .!?¿¡") in _SKIP_NAMES


def asks_about_the_gate(text: object) -> bool:
    """The request itself is about the gate (sign in, the account, an update): it is never a gate to it. Not when it
    says the gate as what not to do («crea una nota sin iniciar sesión», «without signing in»): that gate is passed
    by its skip or stops the goal (review of r9, finding 4)."""

    folded = _NOT_AN_ACCOUNT_PATTERN.sub(" ", _fold(text))
    return any(not said_as_not_to_do(folded, found.start()) for found in _ASK_PATTERN.finditer(folded))


# A place of a window's navigation written as such: one or two words in capitals («TIENDA», «BIBLIOTECA», «MY GAMES»).
_NAVIGATION_LINE = re.compile(r"^[^\W\d_]{3,}(?: [^\W\d_]{2,})?$")


def is_a_navigation_line(text: object) -> bool:
    """A line that names a place of the window's navigation in capitals (a bar of them is a working window)."""

    line = " ".join(str(text or "").split())
    return bool(_NAVIGATION_LINE.match(line)) and line == line.upper() and line != line.lower()
