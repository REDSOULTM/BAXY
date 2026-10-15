"""Controls whose click changes the person's account or what is installed (live 2026-10-07, z7: going to «Tu biblioteca»
on a music app the model clicked «Seguir a Tu biblioteca», «Siguiendo…» and «Guardar La biblioteca de media noche en Tu
Biblioteca»). Such a click is the person's to ask for: the engine presses one only when the goal names that act.
Pasada v3 r9 (v3-34): creating a note, the engine pressed a notes app's «Iniciar sesión» and took «Iniciando sesión...»
for the note; signing in, signing out, creating an account and changing it are such acts too, each its own: a goal
that asks to sign in never lets the engine sign out or create an account."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Each act with the words its control and a goal that asks for it say, in Spanish and English (folded, no accents):
# one source, in data (data/account_acts.v1.json), whose examples tie it in its test. Encargo S (banco e1/e2 u1, y8):
# playing or pausing is such an act too, said by the control's first word («Reproducir X», «Pausar X»).
_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "account_acts.v1.json"
_DATA = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
_ACTS: dict[str, tuple[str, ...]] = {act: tuple(entry["control"]) for act, entry in _DATA["acts"].items()}
_ASKS: dict[str, tuple[str, ...]] = {act: tuple(entry["asks"]) for act, entry in _DATA["acts"].items()}
_FIRST_WORD_ACTS = frozenset(act for act, entry in _DATA["acts"].items() if entry["where"] == "first")
# The acts of the account's session itself: never the proof of another goal (v3-34: «Iniciando sesión...» cited as
# the note created).
SESSION_ACTS = frozenset({"sign_in", "sign_out", "create_account", "switch_account"})
# «Iniciar sesión de concentración», «cerrar sesión de grabación»: a session of an activity, not the account's. A
# closed list of activities: «Cerrar sesión de Windows», «… de todos los dispositivos», «Iniciar sesión de nuevo» are
# the account's (review of r9, finding 3).
_SESSION_OF_AN_ACTIVITY = re.compile(
    r"\bsesion(?:es)? de (?:concentracion|enfoque|estudio|trabajo|grabacion|entrenamiento|ejercicio|meditacion|"
    r"practica|lectura|respiracion|depuracion|juego|pomodoro|dibujo|escritura)\b"
)
# A place named after the act: «Login settings», «Sign-in options», «Opciones de inicio de sesión / de login».
_PLACE_OF_THE_ACT = re.compile(
    r"\b(?:log ?in|sign[ -]?in|sign[ -]?out|log ?out)\s+(?:settings|options|preferences|methods?|info|activity|history)\b"
    r"|\b(?:opciones|configuracion|ajustes|preferencias|metodos?|historial|actividad) de "
    r"(?:inicio de sesion|login|log in|sign[ -]?in)\b"
)
# A mention said as what not to do: «sin iniciar sesión», «without signing in», «no hagas login», «don't sign in»;
# never «no olvides guardar», «don't forget to save», «not only…», which ask for it, nor «no puedo iniciar sesión»,
# «no me deja iniciar sesión», which ask about it.
_NEGATED_BEFORE = re.compile(
    r"(?:^|\s)(?:sin|no|nunca|ni|jamas|without|never|not|dont|don't|avoid|evita|evitar|evitando)"
    r"(?!\s+(?:te\s+|me\s+|nos\s+)?(?:olvid|forget|fail|solo|only|dejes|deja|stop|pued|logr|consig|funcion))"
    r"(?:\s+[\w']+){0,2}\s*$"
)


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold().replace("’", "'")
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _words(words: tuple[str, ...], first: bool = False) -> re.Pattern[str]:
    return re.compile((r"^" if first else r"(?:^|\b)") + r"(?:" + "|".join(re.escape(word) for word in words) + r")\b")


# Pasada r15b (v3-17): «guárdala como copia», «instálalo», «seguilo»: a Spanish verb of the goal said with its object
# pronouns glued to it (enclíticos). A one-word verb ending as a Spanish imperative or infinitive does (a, e, i, r);
# «save it», «add», «get» keep their own spelling. The glued object (lo, la, los, las) is what the act is done to and
# must be there: an indirect pronoun alone («agrégale un filtro a la foto», «únete al canal», «seguile la pista») gives
# something to the thing or the person and never asks to save, join or follow (review of paro-campo, finding 1).
_ENCLITIC = r"(?:(?:me|te|se|nos|le|les)?(?:lo|la|los|las))?"


def _asked(words: tuple[str, ...]) -> re.Pattern[str]:
    said = [
        re.escape(word) + (_ENCLITIC if " " not in word and word[-1] in "aeir" else "")
        for word in words
    ]
    return re.compile(r"(?:^|\b)(?:" + "|".join(said) + r")\b")


# The acts said by the control's first word go first: «Reproducir Tus me gusta» plays, whatever place it names.
_ACT_PATTERNS = {
    act: _words(_ACTS[act], act in _FIRST_WORD_ACTS)
    for act in sorted(_ACTS, key=lambda name: name not in _FIRST_WORD_ACTS)
}
_ASK_PATTERNS = {act: _asked(words) for act, words in _ASKS.items()}
# What said right after the verb makes it ask for something else («poné el modo oscuro» never asks to play).
_UNLESS = {act: re.compile(entry["unless"]) for act, entry in _DATA["acts"].items() if entry.get("unless")}


def said_as_not_to_do(folded: str, start: int) -> bool:
    """The mention starting at ``start`` of a folded text is said as what not to do («sin iniciar sesión», «without
    signing in», «no hagas login»): a negation at most two words before it, in the same clause."""

    return _NEGATED_BEFORE.search(folded[:start]) is not None


def account_act(label: object) -> str | None:
    """The act in the person's name a control's name performs («Seguir a X» → follow, «Reproducir X» → playback), or
    None."""

    folded = _PLACE_OF_THE_ACT.sub(" ", _SESSION_OF_AN_ACTIVITY.sub("sesion_de", _fold(label)))
    return next((act for act, pattern in _ACT_PATTERNS.items() if pattern.search(folded)), None)


def act_says(act: str) -> str:
    """How the step's refusal says what the act does («cambia tu cuenta», «reproduce o pausa algo»; data «says»)."""

    return str(_DATA["says"].get(act) or _DATA["says"]["default"])


def goal_asks_for(goal: object, act: str) -> bool:
    """The goal itself asks for that act («seguí a X», «guardá la playlist», «instalá Spotify»), never when it says
    the act as what not to do («crea una nota sin iniciar sesión») or names a place after it («ve a las opciones de
    login»)."""

    pattern = _ASK_PATTERNS.get(act)
    if pattern is None:
        return False
    unless = _UNLESS.get(act)
    folded = _PLACE_OF_THE_ACT.sub(" ", _fold(goal))
    return any(
        not said_as_not_to_do(folded, found.start())
        and not (unless is not None and unless.match(folded[found.end():]))
        for found in pattern.finditer(folded)
    )


_ABORT = _DATA["abortsInProgress"]
_ABORT_CONTROL = _words(tuple(_ABORT["control"]), first=True)
_ABORT_ASKS = _asked(tuple(_ABORT["asks"]))


def aborts_unasked(label: object, *said: object) -> bool:
    """Encargo CS (banco fz1 s12: the model's «open» on the only control of Steam's updater pressed «Cancelar» and the
    start was cancelled): the control's first word stops what is in progress («Cancelar», «Salir», «Close»; data
    «abortsInProgress») and nothing said (the goal, the request) asks to cancel, stop, close or leave anything, never
    said as what not to do. «cancelá la descarga» asks for it."""

    if not _ABORT_CONTROL.search(_fold(label)):
        return False
    return not any(
        not said_as_not_to_do(folded, found.start())
        for folded in (_fold(text) for text in said if text)
        for found in _ABORT_ASKS.finditer(folded)
    )


def request_carries(act: str) -> bool:
    """Whether the person's whole request asking for the act counts for a sub-goal the mission reader rewrote without
    its verb (data «requestCarries», revisión S H1: «en Spotify poné Los Bunkers» reaches the engine as «activar
    bunkers»)."""

    return bool(_DATA["acts"].get(act, {}).get("requestCarries"))


# Ronda 29 (pasada r27, v3-53: «Iniciar Transmisión» pressed in OBS for «vuelve a activarlo»; v3-08, v3-09: the list of
# «Compartir» opened blind, which then asked the person to confirm what nobody asked): what a click sends out to the
# world or hands to another person (sending, publishing, sharing, joining, calling, going live). One source, in data
# (data/world_acts.v1.json), read here and by the Kernel's RiskPolicy, which asks before such a click; the file's own
# examples tie both readers in their tests.
_WORLD = json.loads((Path(__file__).resolve().parent.parent / "data" / "world_acts.v1.json").read_text(encoding="utf-8"))
_WORLD_SHAPES = {
    "anywhere": r"\b(?:{words})\b",
    "first": r"^(?:{words})\b",
    "firstShort": r"^(?:{words})(?:\s+\S+){{0,3}}$",
}
_WORLD_FAMILIES = tuple(
    (
        str(family["name"]),
        re.compile(_WORLD_SHAPES[family["where"]].format(words="|".join(re.escape(word) for word in family["words"]))),
        re.compile(family["unless"]) if family.get("unless") else None,
    )
    for family in _WORLD["families"]
)
_WORLD_SHORTCUT_HINT = re.compile(_WORLD["shortcutHint"])
# A word of a label or a goal counts from three letters («a», «la», «de», «to» tell no act; a place may be called
# «Gym»), by its first five.
_WORLD_WORD = 3
_WORLD_STEM = 5


def _world_fold(label: object) -> str:
    """Twin of RiskPolicy.Fold: lower case, no accents, no format characters, no trailing shortcut hint."""

    text = unicodedata.normalize("NFD", str(label or "")).lower()
    text = " ".join("".join(ch for ch in text if unicodedata.category(ch) not in ("Mn", "Cf")).split())
    return _WORLD_SHORTCUT_HINT.sub("", text).strip()


def world_act(label: object) -> str | None:
    """The act by which a control's click leaves the computer or reaches a person («Iniciar Transmisión» → broadcast,
    «Compartir» → publish, «General (canal de voz)» → call), or None («Reproducir», «Iniciar grabación», «Agregar
    página»). The same reading as the Kernel's RiskPolicy.LabelReachesAPerson, over the same data."""

    folded = _world_fold(label)
    if not folded:
        return None
    return next((
        name for name, pattern, unless in _WORLD_FAMILIES
        if pattern.search(folded) and not (unless is not None and unless.search(folded))
    ), None)


def goal_names_act(goal: object, label: object) -> bool:
    """The goal itself says the act the control names: they share a word by its stem («compartí la página» and
    «Compartir», «andá al canal Cotele» and «Cotele (canal de voz)»), or the goal says the act in its other language
    with a word of the same family («share this page» and «Compartir», «go live» and «Iniciar Transmisión»); «vuelve a
    activarlo» says nothing of «Iniciar Transmisión»."""

    def stems(text: object) -> set[str]:
        return {word[:_WORLD_STEM] for word in re.findall(r"[a-z0-9]+", _world_fold(text)) if len(word) >= _WORLD_WORD}

    if stems(goal) & stems(label):
        return True
    family = world_act(label)
    said = _world_fold(goal)
    return any(
        re.search(r"\b" + re.escape(word) + r"\b", said)
        for group in _WORLD["families"] if group["name"] == family for word in group["words"]
    )


def unasked_world_act(goal: object, label: object) -> bool:
    """A control whose click goes out to the world and that the goal does not name: never a rule's own guess (a list
    opened blind, a name suggested or pressed by its likeness). The model may still choose it, and the Kernel asks the
    person before that click."""

    return world_act(label) is not None and not goal_names_act(goal, label)


def form_send_button() -> re.Pattern[str]:
    """A button of a form that hands what was written to someone (data «formSendButton»; every verb of the families
    «formSendFamilies» is one, tied by a test)."""

    return re.compile(_WORLD["formSendButton"])
