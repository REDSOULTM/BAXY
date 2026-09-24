"""Output levels: the system volume and the screen brightness, said as a direction, an amount or a target.

Uso real 2026-09-23. «súbele un poco», «bájale», «más bajito», «baja un veinte por ciento», «Volume más alto
please», «Brillo 20%» and «súbelo a 80» reached no reader, and neither did the short answers to «¿cuánto?»
(«un 10», «20», «a 40»). The model asked «¿a qué te refieres?», said it could not do it, or read «a 40» after
«bajá el brillo» as «40 less», which took the brightness from 100 to 60.

The volume and brightness readers read complete requests that name their object. This module reads the other
ways people ask for the same thing: with the object left out, in Spanish, English or both mixed, and with the
level given as a bare answer. It restates the request as the one canonical sentence those readers already
understand (``Level.request``). It decides no effect of its own. The canonical request still goes through the
ordinary readers, their denials and their argument binders.

Owner rule (H0027): a relative change without an amount asks for the amount and uses no default step. An
absolute level («a 40», «al máximo») is acted on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .grammar import _PERCENTAGE_WORD_VALUES, _is_past_or_hypothetical_state, _strip_request_envelope
from .normalize import fold

VOLUME = "volume"
BRIGHTNESS = "brightness"

# The verbs, each with the clitics people fuse to it («súbele», «bajálo», «bájamelo») and its English and
# Spanglish forms. «brighten» and «dim» only apply to the screen.
_UP = (
    r"(?:sub(?:e|a|i|ir)(?:le|lo|la|me|nos|mele|melo)?|aument(?:a|e|ar)(?:le|lo|la|me)?|"
    r"increment(?:a|ar)(?:le|lo)?|alza(?:le|lo)?|raise(?:\s+it)?|increase(?:\s+it)?|"
    r"(?:turn|crank|pump|bump)\s+(?:it\s+|that\s+)?up|brighten(?:\s+it)?)"
)
_DOWN = (
    r"(?:baj(?:a|e|i|ar)(?:le|lo|la|me|nos|mele|melo)?|reduc(?:e|i|ir)(?:le|lo|la|me)?|"
    r"disminu(?:ye|i|ir)(?:le|lo|la|me)?|lower(?:\s+it)?|decrease(?:\s+it)?|"
    r"(?:turn|tone|slow)\s+(?:it\s+|that\s+)?down|dim(?:\s+it)?)"
)
_SET = (
    r"(?:pon(?:e|le|lo|la|elo|ela)?|poner(?:le|lo)?|deja(?:le|lo|la)?|fija(?:lo|la)?|ajusta(?:le|lo|la)?|"
    r"establece|cambia(?:le|lo|la)?|(?:set|put|leave|adjust|change|make)(?:\s+it)?)"
)
# Speaking louder or softer is the output volume (MASSIVE «habla más bajito por favor», «speak softer»).
_SPEAK = r"(?:habla(?:me)?|hable|hablar|speak|talk)"

# A bare object-less verb («baja», «sube») also means going down a street or downloading; it counts only with
# a quantity, a relative word or a comparative. A verb with a dative clitic («súbele», «bájale») or an English
# particle («turn it up») is a level request on its own.
_STANDALONE_VERB = re.compile(
    r"(?:sub|baj|aument|reduc|disminu)\w*le|(?:turn|crank|pump|bump|tone)\s+(?:it\s+|that\s+)?(?:up|down)|"
    r"(?:raise|lower|increase|decrease|brighten|dim)\s+it"
)
_SCREEN_ONLY_VERB = re.compile(r"(?:brighten|dim)\b")

_RELATIVE = (
    r"(?:un\s+(?:poco|poquito|toque|pelin|cacho)(?:\s+mas)?|algo(?:\s+mas)?|bastante|mucho|mas|"
    r"a\s+(?:little|bit)(?:\s+bit)?(?:\s+more)?|slightly|some|a\s+lot|more)"
)
_COMPARATIVE_UP = r"(?:(?:mas|more)\s+(?:alto|fuerte|arriba|loud)|louder|brighter|mas\s+claro)"
_COMPARATIVE_DOWN = (
    r"(?:(?:mas|more)\s+(?:bajo|bajito|despacio|suave|quiet|soft|oscuro)|menos\s+(?:alto|fuerte)|"
    r"quieter|softer|dimmer|darker)"
)
# «más volumen», «menos brillo», «more volume»: the quantifier before the object is the direction.
_QUANTIFIER_UP = r"(?:mas|more)"
_QUANTIFIER_DOWN = r"(?:menos|less)"

_ARTICLE = r"(?:(?:el|la|los|las|the|my|mi|al|a\s+la|a\s+el|a|to\s+the|of\s+the)\s+)"
_DEVICE = (
    r"(?:sistema|equipo|pc|compu|computador(?:a)?|ordenador|system|computer|laptop|notebook|"
    r"altavoz|altavoces|parlantes?|speakers?|bocinas?)"
)
_VOLUME_OBJECT = (
    rf"(?:{_ARTICLE}?(?:(?:speaker|speakers|system|pc|computer)\s+)?(?:volumen|volume|sonido|sound|audio)"
    rf"(?:\s+(?:del?|of|on)\s+{_ARTICLE}?{_DEVICE})?)"
)
_SCREEN = r"(?:pantalla|monitor|screen|display)"
_BRIGHTNESS_OBJECT = (
    rf"(?:{_ARTICLE}?(?:(?:screen|display|monitor)\s+)?(?:brillo|brightness|luminosidad|luz\s+de\s+la\s+pantalla)"
    rf"(?:\s+(?:de\s+(?:la\s+|mi\s+)?|del\s+|al\s+|a\s+la\s+|en\s+la\s+|of\s+(?:the\s+|my\s+)?|on\s+(?:the\s+|my\s+)?){_SCREEN})?)"
)
_OBJECT = rf"(?:(?P<{{name}}_volume>{_VOLUME_OBJECT})|(?P<{{name}}_brightness>{_BRIGHTNESS_OBJECT}))"

# «un» and «uno» are also the indefinite article («un poco», «un 10»): never a quantity here.
_NUMBER_WORDS = {word: value for word, value in _PERCENTAGE_WORD_VALUES.items() if word not in {"un", "uno", "one"}}
_NUMBER = (
    r"(?:\d{1,3}|"
    + "|".join(re.escape(word) for word in sorted(_NUMBER_WORDS, key=len, reverse=True))
    + r")"
)
_UNIT = r"(?:%|por\s*ciento|porciento|percent|puntos?|points?)"
_EXTREMES = {
    "maximo": 100, "max": 100, "tope": 100, "maximum": 100, "full": 100,
    "minimo": 0, "min": 0, "minimum": 0, "mitad": 50, "half": 50,
}
_EXTREME = r"(?:maximo|max|tope|maximum|full|minimo|min|minimum|mitad|half)"
# An amount is relative («un 10», «en 10», «by 10», a bare «10»); a target is where the level ends
# («a 40», «al 40», «to 40», «al máximo»).
_AMOUNT = rf"(?:(?:en|by|un|unos|unas|como|about|around)\s+)?(?P<amount>{_NUMBER})(?:\s*{_UNIT})?"
_TARGET = (
    rf"(?:(?:a|al|hasta(?:\s+el)?|to|at)\s+(?:(?:el|the|un)\s+)?(?P<target>{_NUMBER})(?:\s*{_UNIT})?|"
    rf"(?:(?:al|a|to|at|hasta(?:\s+el)?)\s+(?:(?:the|el)\s+)?)?(?P<extreme>{_EXTREME})|a\s+tope)"
)
_QUANTITY = rf"(?:{_TARGET}|{_AMOUNT})"

_PREFACE = (
    r"(?:(?:por\s+favor|porfa|please|pls|oye|hey|che|dale)\s+)*"
    r"(?:(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you)\s+)?"
)
_CLOSING = r"(?:\s+(?:por\s+favor|porfa|please|pls|plis|ya|ahora|now|mismo|otra\s+vez|again|de\s+nuevo))*"


def _form(body: str) -> re.Pattern[str]:
    return re.compile(rf"{_PREFACE}{body}{_CLOSING}")


# The request forms. Every one is matched against the whole utterance, so anything else said with it (an
# application, a device, a time, a second order) leaves the request to the other readers.
_VERB_FORM = _form(
    rf"(?P<verb>{_UP}|{_DOWN}|{_SET}|{_SPEAK})"
    rf"(?:\s+(?P<rel1>{_RELATIVE}))?"
    rf"(?:\s+{_OBJECT.format(name='o1')})?"
    rf"(?:\s+(?P<rel2>{_RELATIVE}))?"
    rf"(?:\s+{_QUANTITY})?"
    rf"(?:\s+{_OBJECT.format(name='o2')})?"
    rf"(?:\s+(?:(?P<cup>{_COMPARATIVE_UP})|(?P<cdown>{_COMPARATIVE_DOWN})))?"
)
_OBJECT_FORM = _form(
    rf"{_OBJECT.format(name='o1')}"
    rf"(?:\s+(?:(?P<cup>{_COMPARATIVE_UP}|up)|(?P<cdown>{_COMPARATIVE_DOWN}|down)))?"
    rf"(?:\s+{_QUANTITY})?"
)
_COMPARATIVE_FORM = _form(
    rf"(?:{_RELATIVE}\s+)?(?:(?P<cup>{_COMPARATIVE_UP})|(?P<cdown>{_COMPARATIVE_DOWN}))"
    rf"(?:\s+{_OBJECT.format(name='o1')})?"
)
_QUANTIFIER_FORM = _form(
    rf"(?:un\s+poco\s+|a\s+bit\s+|a\s+little\s+)?(?:(?P<qup>{_QUANTIFIER_UP})|(?P<qdown>{_QUANTIFIER_DOWN}))"
    rf"\s+{_OBJECT.format(name='o1')}"
)
_ANSWER_FORM = _form(_QUANTITY)

# «I don't wanna hear it tan alto», «está muy fuerte la música», «no se escucha casi nada»: a complaint about how
# loud it sounds asks for less (or more) volume, without saying how much. It needs a word of hearing or sound, so
# «el edificio es muy alto» says nothing about the volume.
_TOO_LOUD = re.compile(r"\b(?:muy|demasiado|tan|super|re|too|so|really)\s+(?:alto|alta|fuerte|loud)\b")
_TOO_QUIET = re.compile(
    r"\b(?:muy|demasiado|tan|too|so|really)\s+(?:bajo|baja|bajito|despacio|quiet|low)\b|"
    r"\b(?:no\s+se\s+(?:escucha|oye)\s+(?:casi\s+)?nada|barely\s+hear|can'?t\s+hear|cannot\s+hear)\b"
)
_HEARING = re.compile(
    r"\b(?:oir(?:lo|la)?|escuchar(?:lo|la)?|escucha|oye|escucho|oigo|hear|suena|sounds?|sonido|volumen|volume|"
    r"audio|musica|music|ruido|noise)\b"
)
_OTHER_OBJECT = re.compile(
    r"\b(?:brillo|brightness|pantalla|screen|microfono|microphone|mic|micro|tele|tv|television|llamada|call|"
    r"discord|zoom|teams|spotify|youtube|chrome|juego|game|vecino|neighbou?r|voz\s+de)\b"
)
_QUESTION = re.compile(r"^(?:por\s*que|porque|why|como|how|que|what|cual|is|are|does)\b")
# A complaint is said as a state («está muy fuerte», «sounds too loud»), with an excess word («demasiado»,
# «too») or as a refusal to hear it like that («I don't wanna hear it tan alto»). A wish to hear it loud
# («quiero escucharla muy fuerte») is the opposite request and is not read here.
_STATE = re.compile(r"\b(?:esta|estan|suena|suenan|sounds?|is|it'?s|its|anda|va)\b")
_EXCESS = re.compile(r"\b(?:demasiado|too)\b")
_NEGATION = re.compile(r"\b(?:no|don'?t|dont|do\s+not|not|nunca|never)\b")
_DESIRE = re.compile(r"\b(?:quiero|quisiera|queria|want|wanna|like|gusta|prefiero|prefer)\b")


@dataclass(frozen=True)
class Level:
    """One output-level request. ``setting`` is None when the object is left out («súbele», «más bajito»)."""

    setting: str | None
    direction: str | None
    amount: int | None
    target: int | None

    def request(self, setting: str) -> str:
        """The canonical request the ordinary volume and brightness readers read."""

        noun = "el brillo" if setting == BRIGHTNESS else "el volumen"
        if self.target is not None:
            return f"pon {noun} al {self.target}"
        verb = "sube" if self.direction == "up" else "baja"
        return f"{verb} {noun} en {self.amount}" if self.amount is not None else f"{verb} {noun}"


def _clean(text: str) -> str:
    folded = _strip_request_envelope(fold(re.sub(r"[’‘`´]", "'", str(text or ""))))
    return " ".join(re.sub(r"[¿?¡!.,;:]+", " ", folded).split())


def _number(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw)


def _quantity(found: re.Match[str]) -> tuple[int | None, int | None] | None:
    """(amount, target) of a matched form, or None when a number is out of range."""

    amount = target = None
    if found.groupdict().get("extreme"):
        target = _EXTREMES[found.group("extreme")]
    elif found.groupdict().get("target"):
        target = _number(found.group("target"))
        if target is None or not 0 <= target <= 100:
            return None
    elif found.groupdict().get("amount"):
        amount = _number(found.group("amount"))
        if amount is None or not 1 <= amount <= 100:
            return None
    elif re.search(r"\ba\s+tope\b", found.group(0)):
        target = 100
    return amount, target


def _object(found: re.Match[str]) -> str | None | bool:
    """The object named in a form: a setting, None when left out, False when two different ones are named."""

    named = {
        setting
        for name in ("o1", "o2")
        for setting in (VOLUME, BRIGHTNESS)
        if found.groupdict().get(f"{name}_{setting}")
    }
    if len(named) > 1:
        return False
    return next(iter(named), None)


def _verb_level(found: re.Match[str]) -> Level | None:
    verb = found.group("verb")
    quantity = _quantity(found)
    setting = _object(found)
    if quantity is None or setting is False:
        return None
    amount, target = quantity
    comparative = "up" if found.group("cup") else "down" if found.group("cdown") else None
    if re.fullmatch(_SPEAK, verb):
        if comparative is None or setting is not None or amount is not None or target is not None:
            return None
        return Level(VOLUME, comparative, None, None)
    if re.fullmatch(_SET, verb):
        # «ponlo al 50», «set el volumen to 40»: a setting verb takes a target; «en 50» after it is one too.
        # «ponle más volumen» is the quantifier said after the verb: more of the object named.
        if comparative is not None:
            return None
        target = target if target is not None else amount
        if target is not None:
            return Level(setting, None, None, target)
        relative = (found.group("rel1") or found.group("rel2") or "").split()
        if setting is not None and relative and relative[-1] in {"mas", "more"}:
            return Level(setting, "up", None, None)
        return None
    direction = "up" if re.fullmatch(_UP, verb) else "down"
    if comparative is not None and comparative != direction:
        return None
    if _SCREEN_ONLY_VERB.match(verb):
        if setting == VOLUME:
            return None
        setting = BRIGHTNESS
    bare = (
        setting is None
        and amount is None
        and target is None
        and comparative is None
        and not (found.group("rel1") or found.group("rel2"))
    )
    if bare and _STANDALONE_VERB.fullmatch(verb) is None:
        return None
    return Level(setting, direction, amount, target)


def read(text: str) -> Level | None:
    """The output-level request the whole utterance is, or None."""

    cleaned = _clean(text)
    if not cleaned:
        return None
    found = _VERB_FORM.fullmatch(cleaned)
    if found is not None:
        return _verb_level(found)
    found = _OBJECT_FORM.fullmatch(cleaned) or _COMPARATIVE_FORM.fullmatch(cleaned)
    if found is not None:
        quantity = _quantity(found)
        setting = _object(found)
        if quantity is None or setting is False:
            return None
        amount, target = quantity
        direction = "up" if found.group("cup") else "down" if found.group("cdown") else None
        if direction is None:
            # «Brillo 20%», «volumen al 30»: the object and a level with no direction is where to put it.
            if setting is None or (target if target is not None else amount) is None:
                return None
            return Level(setting, None, None, target if target is not None else amount)
        if target is not None and direction is not None:
            return None
        return Level(setting, direction, amount, None)
    found = _QUANTIFIER_FORM.fullmatch(cleaned)
    if found is not None:
        setting = _object(found)
        return None if setting is False else Level(setting, "up" if found.group("qup") else "down", None, None)
    return _complaint(cleaned, question="?" in text or "¿" in text)


def _complaint(cleaned: str, *, question: bool) -> Level | None:
    """«I don't wanna hear it tan alto»: how it sounds, said as a complaint, is a volume request without amount."""

    if (
        question
        or _QUESTION.search(cleaned)
        or _HEARING.search(cleaned) is None
        or _OTHER_OBJECT.search(cleaned)
        or _is_past_or_hypothetical_state(cleaned)
        or re.search(r"\d", cleaned)
    ):
        return None
    loud, quiet = _TOO_LOUD.search(cleaned) is not None, _TOO_QUIET.search(cleaned) is not None
    if loud == quiet:
        return None
    negated, desire = _NEGATION.search(cleaned) is not None, _DESIRE.search(cleaned) is not None
    unheard = re.search(r"\bno\s+se\s+(?:escucha|oye)\b|\b(?:barely|can'?t|cannot)\s+hear\b", cleaned) is not None
    if desire != negated and not unheard:
        # A wish without a refusal, or a denial without a wish («no está muy alto»), is not this complaint.
        return None
    if not (desire or unheard or _STATE.search(cleaned) or _EXCESS.search(cleaned)):
        return None
    return Level(VOLUME, "down" if loud else "up", None, None)


def answer(text: str) -> Level | None:
    """A bare level said as the answer to «¿cuánto?»: «un 10», «20», «10%» (amounts), «a 40», «al máximo» (targets)."""

    found = _ANSWER_FORM.fullmatch(_clean(text))
    if found is None:
        return None
    quantity = _quantity(found)
    if quantity is None:
        return None
    return Level(None, None, *quantity)


def setting_of(text: str | None) -> str | None:
    """The setting an earlier request was about, when it names one: its level request, else its nouns."""

    if not text:
        return None
    level = read(text)
    if level is not None and level.setting is not None:
        return level.setting
    folded = fold(text)
    brightness = re.search(r"\b(?:brillo|brightness|luminosidad)\b", folded) is not None
    volume = re.search(r"\b(?:volumen|volume|sonido|sound|audio|musica|music|cancion|song)\b", folded) is not None
    if brightness == volume:
        return None
    return BRIGHTNESS if brightness else VOLUME


def direction_of(text: str) -> str | None:
    """The direction an earlier request carried, even when its words are not a form read here."""

    level = read(text)
    if level is not None and level.direction is not None:
        return level.direction
    cleaned = _clean(text)
    up = re.search(rf"\b(?:{_UP}|{_COMPARATIVE_UP}|oscurece|aclara)\b", cleaned) is not None
    down = re.search(rf"\b(?:{_DOWN}|{_COMPARATIVE_DOWN})\b", cleaned) is not None
    if up == down:
        return None
    return "up" if up else "down"


def followup_antecedent(text: str, previous_requests: list[str]) -> str | None:
    """The earlier request a level said without its object refers to, newest first, or None.

    «súbelo a 80» after «bajá el brillo» → «a 40» refers to the brightness. The answer «a 40» is skipped on the
    way back, and so is any other request that leaves the object out. A bare answer («20») only ever
    completes the request right before it. When that request left out its own object («bájale»), the
    antecedent is that request restated with the object it inherited. A change of subject ends the chain.
    """

    if not previous_requests:
        return None
    if answer(text) is not None:
        pending = read(previous_requests[0])
        if pending is None or pending.setting is not None:
            return None
        return pending.request(_inherited_setting(previous_requests[1:]) or VOLUME)
    level = read(text)
    if level is None or level.setting is not None:
        return None
    for request in previous_requests:
        if answer(request) is not None:
            continue
        earlier = read(request)
        if earlier is not None and earlier.setting is None:
            continue
        return request if setting_of(request) is not None else None
    return None


def _inherited_setting(previous_requests: list[str]) -> str | None:
    for request in previous_requests:
        if answer(request) is not None:
            continue
        earlier = read(request)
        if earlier is not None and earlier.setting is None:
            continue
        return setting_of(request)
    return None
