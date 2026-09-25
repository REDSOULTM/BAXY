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

from . import lexicon
from .grammar import _PERCENTAGE_WORD_VALUES, _is_past_or_hypothetical_state, _strip_request_envelope
from .normalize import fold

VOLUME = "volume"
BRIGHTNESS = "brightness"

# The verbs, each with the clitics people fuse to it («súbele», «bajálo», «bájamelo») and its English and
# Spanglish forms. «brighten» and «dim» only apply to the screen. Tanda 2 «Turn dowm poquito la musica»: the
# English particle is typed with its neighbour key or its letters swapped.
_DOWN_PARTICLE = r"(?:down|dowm|donw|dwon)"
# Tanda 6 «Dale up al Sonido» was asked «¿Cuánto y en qué dirección?»: in Spanglish the English particle takes a
# Spanish light verb with its dative clitic («dale up al sonido», «ponle down al volumen», «métele up»); the
# particle is the direction.
_LIGHT_VERB = r"(?:dale|dele|denle|ponle|pongale|hazle|metele|echale)"
_UP = (
    r"(?:sub(?:e|a|i|ir)(?:le|lo|la|me|nos|mele|melo)?|aument(?:a|e|ar)(?:le|lo|la|me)?|"
    r"increment(?:a|ar)(?:le|lo)?|alza(?:le|lo)?|raise(?:\s+it)?|increase(?:\s+it)?|"
    r"(?:turn|crank|pump|bump)\s+(?:it\s+|that\s+)?up|brighten(?:\s+it)?|aclar(?:a|ar)(?:la|lo)?|"
    rf"ilumin(?:a|ar)(?:la|lo)?|{_LIGHT_VERB}\s+up)"
)
_DOWN = (
    r"(?:baj(?:a|e|i|ar)(?:le|lo|la|me|nos|mele|melo)?|reduc(?:e|i|ir)(?:le|lo|la|me)?|"
    r"disminu(?:ye|i|ir)(?:le|lo|la|me)?|lower(?:\s+it)?|decrease(?:\s+it)?|"
    rf"(?:turn|tone|slow)\s+(?:it\s+|that\s+)?{_DOWN_PARTICLE}|dim(?:\s+it)?|oscurec(?:e|er)(?:la|lo)?|darken(?:\s+it)?|"
    rf"{_LIGHT_VERB}\s+{_DOWN_PARTICLE})"
)
# Tanda 3, a screen asked to be made brighter («ponme la pantalla más clara»): making the object more or
# less of something is setting it in that direction, the same as «ponlo más bajito» or «make it louder».
_SET = (
    r"(?:pon(?:e|le|lo|la|elo|ela|me|mela|melo)?|poner(?:le|lo)?|deja(?:le|lo|la|me)?|fija(?:lo|la)?|"
    r"ajusta(?:le|lo|la)?|establece|cambia(?:le|lo|la)?|coloca(?:le|lo|la)?|haz(?:me|lo|la|mela|melo)?|"
    r"hace(?:lo|la|me)?|(?:set|put|leave|adjust|change|make)(?:\s+it)?)"
)
# Speaking louder or softer is the output volume (MASSIVE «habla más bajito por favor», «speak softer»), and so
# is making it sound louder or softer.
_SPEAK = r"(?:habla(?:me)?|hable|hablar|speak|talk|haz\s+que\s+(?:suene|se\s+(?:escuche|oiga))|make\s+it\s+sound)"
# A verb whose object is a clitic or «it» («ponlo», «déjala», «make it») refers to something already named.
_PRONOUN_VERB = re.compile(r"\w+(?:lo|la|melo|mela)|\w+\s+it")

# A bare object-less verb («baja», «sube») also means going down a street or downloading; it counts only with
# a quantity, a relative word or a comparative. A verb with a dative clitic («súbele», «bájale») or an English
# particle («turn it up») is a level request on its own.
_STANDALONE_VERB = re.compile(
    rf"(?:sub|baj|aument|reduc|disminu)\w*le|(?:turn|crank|pump|bump|tone)\s+(?:it\s+|that\s+)?(?:up|{_DOWN_PARTICLE})|"
    r"(?:raise|lower|increase|decrease|brighten|dim)\s+it"
)
_SCREEN_ONLY_VERB = re.compile(r"(?:brighten|dim|aclar|ilumin|oscurec|darken)")

# «bájale poquito», «súbele tantito»: the diminutive said without its article is the same small amount. Tanda
# 3, a brightness lowered «un nivel»: a step («un nivel», «a notch», «dos niveles») gives the
# direction and no amount either, since how much a step is was never said.
STEP_NOUN = (
    r"(?:nivel(?:es)?|paso(?:s)?|escalon(?:es)?|rayita(?:s)?|raya(?:s)?|notch(?:es)?|levels?|steps?|ticks?)"
)
_STEP_COUNT = r"(?:un\s+par\s+de|un|una|uno|dos|tres|cuatro|cinco|a|one|two|three|four|five|\d)"
_RELATIVE = (
    r"(?:(?:un\s+)?(?:poquito|poquitito|tantito|pelin)(?:\s+mas)?|un\s+(?:poco|toque|cacho|chin)(?:\s+mas)?|"
    rf"(?:(?:en|by)\s+)?{_STEP_COUNT}\s+{STEP_NOUN}(?:\s+(?:mas|more))?|"
    r"algo(?:\s+mas)?|bastante|mucho|mas|"
    r"a\s+(?:little|bit|tad|touch)(?:\s+bit)?(?:\s+more)?|slightly|some|a\s+lot|more)"
)
# Comparatives. «más alto/bajo» fit both levels; «más fuerte», «louder» only the sound; «más brillante», «más
# oscura», «brighter» only the screen.
_COMPARATIVE_UP = r"(?:(?:mas|more)\s+(?:alto|fuerte|arriba|loud)|louder|higher)"
_COMPARATIVE_DOWN = (
    r"(?:(?:mas|more)\s+(?:bajo|bajito|despacio|suave|quiet|soft)|menos\s+(?:alto|fuerte)|quieter|softer)"
)
_BRIGHTER = (
    r"(?:(?:mas|more)\s+(?:brillante|claro|clara|luminoso|luminosa|iluminado|iluminada|bright)|"
    r"menos\s+(?:oscuro|oscura)|brighter|lighter)"
)
_DARKER = (
    r"(?:(?:mas|more)\s+(?:oscuro|oscura|tenue|dark|dim)|"
    r"menos\s+(?:brillante|claro|clara|luminoso|luminosa)|less\s+bright|dimmer|darker)"
)
_SOUND_ONLY_COMPARATIVE = re.compile(r"\b(?:fuerte|loud|louder|bajito|despacio|suave|quiet|quieter|soft|softer)")
_COMPARISON = (
    rf"(?:(?P<cup>{_COMPARATIVE_UP})|(?P<cdown>{_COMPARATIVE_DOWN})|(?P<bup>{_BRIGHTER})|(?P<bdown>{_DARKER}))"
)
# «más volumen», «menos brillo», «more volume»: the quantifier before the object is the direction.
_QUANTIFIER_UP = r"(?:mas|more)"
_QUANTIFIER_DOWN = r"(?:menos|less)"

_ARTICLE = r"(?:(?:el|la|los|las|the|my|mi|al|a\s+la|a\s+el|a|to\s+the|of\s+the)\s+)"
_DEVICE = (
    r"(?:sistema|equipo|pc|compu|computador(?:a)?|ordenador|system|computer|laptop|notebook|"
    rf"{lexicon.SPEAKER_NOUN})"
)
# AUDIO1461 «bajá la música», tanda 2 «Turn dowm poquito la musica»: raising or lowering the music is the volume;
# MASSIVE audio_volume_up (dev corpus 2026-09-24) «sube el volumen de la música a noventa»: so is its volume.
_VOLUME_OBJECT = (
    rf"(?:{_ARTICLE}?(?:(?:speaker|speakers|system|pc|computer)\s+)?(?:volumen|volume|sonido|sound|audio|musica|music)"
    rf"(?:\s+(?:del?|of|on)\s+{_ARTICLE}?(?:{_DEVICE}|musica|music))?)"
)
_SCREEN = r"(?:pantalla|monitor|screen|display)"
_BRIGHTNESS_OBJECT = (
    rf"(?:{_ARTICLE}?(?:(?:screen|display|monitor)\s+)?(?:brillo|brightness|luminosidad|luz\s+de\s+la\s+pantalla)"
    rf"(?:\s+(?:de\s+(?:la\s+|mi\s+)?|del\s+|al\s+|a\s+la\s+|en\s+la\s+|of\s+(?:the\s+|my\s+)?|on\s+(?:the\s+|my\s+)?){_SCREEN})?)"
)
# «pon la pantalla al 50%», «haz la pantalla más brillante»: the screen itself names its brightness, but only
# with a level or a brightness word; «baja la pantalla» on its own says nothing about the brightness.
_SCREEN_OBJECT = rf"(?:{_ARTICLE}?{_SCREEN}(?:\s+(?:del?|of)\s+{_ARTICLE}?{_DEVICE})?)"
_OBJECT = (
    rf"(?:(?P<{{name}}_volume>{_VOLUME_OBJECT})|(?P<{{name}}_brightness>{_BRIGHTNESS_OBJECT})|"
    rf"(?P<{{name}}_screen>{_SCREEN_OBJECT}))"
)

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
# An amount is relative («un 10», «en 10», «en un 10», «by 10», a bare «10»); a target is where the level ends
# («a 40», «al 40», «a un 40», «to 40», «on 40», «al máximo»). After a setting verb an amount is a target too
# (tanda 3: «deja el brillo en un 45%» was asked which way).
_AMOUNT = (
    rf"(?:(?:en|by)\s+)?(?:(?:un|unos|unas|como|about|around)\s+)?(?P<amount>{_NUMBER})(?:\s*{_UNIT})?"
)
# Tanda 4 «Incrementa el brightness al level 8» was stepped up by 8 from 100: «al nivel 8», «to level 8» name
# where the level ends, the same as «al 8».
_TARGET = (
    rf"(?:(?:a|al|hasta(?:\s+el)?|to|at|on)\s+(?:(?:el|the|un)\s+)?(?:(?:nivel|level)\s+)?"
    rf"(?P<target>{_NUMBER})(?:\s*{_UNIT})?|"
    rf"(?:(?:al|a|to|at|hasta(?:\s+el)?)\s+(?:(?:the|el)\s+)?)?(?P<extreme>{_EXTREME})|a\s+tope)"
)
_QUANTITY = rf"(?:{_TARGET}|{_AMOUNT})"

_PREFACE = (
    r"(?:(?:por\s+favor|porfa|please|pls|oye|hey|che|dale)\s+)*"
    r"(?:(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you)\s+)?"
    r"(?:(?:quiero|quisiera|i\s+want|i\s+would\s+like|i'?d\s+like)\s+)?"
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
    rf"(?:\s+{_COMPARISON})?"
)
# «turn the volume down a notch», «bring the brightness up to 80»: the English particle after the object.
_PARTICLE_FORM = _form(
    rf"(?:turn|crank|bump|pump|tone|dial|bring|knock)\s+{_OBJECT.format(name='o1')}\s+"
    rf"(?:(?P<pup>up)|(?P<pdown>{_DOWN_PARTICLE}))"
    rf"(?:\s+(?P<rel1>{_RELATIVE}))?(?:\s+{_QUANTITY})?"
)
_OBJECT_FORM = _form(
    rf"{_OBJECT.format(name='o1')}"
    rf"(?:\s+(?P<rel1>{_RELATIVE}))?"
    rf"(?:\s+(?:{_COMPARISON}|(?P<pup>up)|(?P<pdown>down)))?"
    rf"(?:\s+{_QUANTITY})?"
)
_COMPARATIVE_FORM = _form(
    rf"(?:(?P<rel1>{_RELATIVE})\s+)?{_COMPARISON}"
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
# Tanda 8 «the screen is way too bright» was asked what it meant: the same complaint about the screen's light asks
# for less (or more) brightness. It needs the screen or its brightness named, so «the sun is too bright» and «esta
# película es muy oscura» say nothing about it; «alto/bajo» count only with the brightness itself («el brillo está
# muy alto»), since «la pantalla está muy alta» is its height.
_INTENSE = r"(?:muy|demasiado|tan|super|re|too|so|really)"
_TOO_BRIGHT = re.compile(
    rf"\b{_INTENSE}\s+(?:brillantes?|bright|clar[oa]|luminos[oa])\b|\bbrilla\s+(?:demasiado|mucho|too\s+much)\b|"
    rf"\b(?:demasiado|mucho|too\s+much)\s+(?:brillo|brightness)\b|"
    rf"\b(?:brillo|brightness)\b.*\b{_INTENSE}\s+(?:alto|alta|high)\b"
)
_TOO_DARK = re.compile(
    rf"\b{_INTENSE}\s+(?:oscur[oa]s?|dark|dim|tenue)\b|\b(?:muy\s+poco|poco|not\s+enough)\s+(?:brillo|brightness)\b|"
    rf"\b(?:brillo|brightness)\b.*\b{_INTENSE}\s+(?:bajo|baja|low)\b"
)
_SEEING = re.compile(r"\b(?:pantalla|screen|display|monitor|brillo|brightness)\b")
_OTHER_SCREEN = re.compile(r"\b(?:celular|movil|telefono|phone|tele|tv|television|tablet|ipad|consola|console)\b")
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

    groups = found.groupdict()
    named = {
        BRIGHTNESS if kind == "screen" else kind
        for name in ("o1", "o2")
        for kind in (VOLUME, BRIGHTNESS, "screen")
        if groups.get(f"{name}_{kind}")
    }
    if len(named) > 1:
        return False
    return next(iter(named), None)


def _only_the_screen(found: re.Match[str]) -> bool:
    """«la pantalla» is the only object named: it is the brightness only when a level or a brightness word says so."""

    groups = found.groupdict()
    return any(groups.get(f"{name}_screen") for name in ("o1", "o2")) and not any(
        groups.get(f"{name}_brightness") for name in ("o1", "o2")
    )


def _screen_level_said(found: re.Match[str], verb: str = "") -> bool:
    """A level said of the screen itself: a target, a percentage, a brightness word or a brightness verb."""

    groups = found.groupdict()
    return bool(
        groups.get("target")
        or groups.get("extreme")
        or re.search(rf"\b{_UNIT}|%", found.group(0))
        or groups.get("bup")
        or groups.get("bdown")
        or _SCREEN_ONLY_VERB.match(verb)
    )


def _comparative(found: re.Match[str], setting: str | None) -> tuple[str | None, str | None] | None:
    """(direction, setting) a comparative or a particle says, or None when it contradicts the object named."""

    groups = found.groupdict()
    if groups.get("bup") or groups.get("bdown"):
        if setting == VOLUME:
            return None
        return ("up" if groups.get("bup") else "down"), BRIGHTNESS
    said = groups.get("cup") or groups.get("cdown")
    if said:
        if setting == BRIGHTNESS and _SOUND_ONLY_COMPARATIVE.search(said):
            return None
        return ("up" if groups.get("cup") else "down"), setting
    if groups.get("pup") or groups.get("pdown"):
        return ("up" if groups.get("pup") else "down"), setting
    return None, setting


def _verb_level(found: re.Match[str]) -> Level | None:
    verb = found.group("verb")
    quantity = _quantity(found)
    named = _object(found)
    if quantity is None or named is False:
        return None
    if _only_the_screen(found) and not _screen_level_said(found, verb):
        return None
    compared = _comparative(found, named)
    if compared is None:
        return None
    amount, target = quantity
    comparative, setting = compared
    if re.fullmatch(_SPEAK, verb):
        if comparative is None or setting is not None or amount is not None or target is not None:
            return None
        return Level(VOLUME, comparative, None, None)
    if re.fullmatch(_SET, verb):
        if comparative is not None:
            # «haz la pantalla más brillante», «ponlo más bajito», «make it louder»: something named, or referred
            # to by its pronoun, made more or less. «pon algo más fuerte» names nothing (a song, maybe).
            if amount is not None or target is not None:
                return None
            if named is None and _PRONOUN_VERB.fullmatch(verb) is None:
                return None
            return Level(setting, comparative, None, None)
        # «ponlo al 50», «set el volumen to 40»: a setting verb takes a target; «en 50» after it is one too.
        # «ponle más volumen» is the quantifier said after the verb: more of the object named.
        target = target if target is not None else amount
        if target is not None:
            return Level(setting, None, None, target)
        relative = (found.group("rel1") or found.group("rel2") or "").split()
        # «ponle más música» asks for more songs, not more volume.
        music = re.search(r"\b(?:musica|music)\b", found.group(0)) is not None
        if setting is not None and relative and relative[-1] in {"mas", "more"} and not music:
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


def _stated_level(found: re.Match[str]) -> Level | None:
    """A level said around its object («Brillo 20%», «la pantalla más clara», «turn the volume down a notch»)."""

    quantity = _quantity(found)
    named = _object(found)
    if quantity is None or named is False:
        return None
    if _only_the_screen(found) and not _screen_level_said(found):
        return None
    compared = _comparative(found, named)
    if compared is None:
        return None
    amount, target = quantity
    direction, setting = compared
    if direction is None:
        # «Brillo 20%», «volumen al 30»: the object and a level with no direction is where to put it.
        if setting is None or (target if target is not None else amount) is None:
            return None
        return Level(setting, None, None, target if target is not None else amount)
    if target is not None and not (found.groupdict().get("pup") or found.groupdict().get("pdown")):
        # «el volumen más alto al 50» says two things; «turn the volume down to 20» says where it ends.
        return None
    return Level(setting, direction, amount, target)


# Tanda 9 «bajale un poco que está al palo» was answered «No bajé nada»: an order followed by why it is asked («que
# está muy fuerte», «porque no se escucha», «it's way too loud») is the order; the reason is a state, said after it.
_REASON = re.compile(
    r"\s+(?:(?:que|porque|pq|ya\s+que)\s+(?:esta|estan|es|son|suena|suenan|se|no|me|ya|anda|quedo)|because|cause|"
    r"since|it'?s|its)\b.*$"
)


def read(text: str) -> Level | None:
    """The output-level request the whole utterance is, or None; an order said with its reason is the order."""

    cleaned, question = _clean(text), "?" in str(text or "") or "¿" in str(text or "")
    level = _read(cleaned, question)
    reason = _REASON.search(cleaned) if level is None else None
    return _read(cleaned[: reason.start()], question) if reason is not None and reason.start() else level


def _read(cleaned: str, question: bool) -> Level | None:
    if not cleaned:
        return None
    found = _VERB_FORM.fullmatch(cleaned)
    if found is not None:
        return _verb_level(found)
    found = (
        _PARTICLE_FORM.fullmatch(cleaned) or _OBJECT_FORM.fullmatch(cleaned) or _COMPARATIVE_FORM.fullmatch(cleaned)
    )
    if found is not None:
        return _stated_level(found)
    found = _QUANTIFIER_FORM.fullmatch(cleaned)
    if found is not None and not re.search(r"\b(?:musica|music)\b", cleaned) and not _only_the_screen(found):
        # «más música» asks for more songs; «más volumen» for more volume.
        setting = _object(found)
        return None if setting is False else Level(setting, "up" if found.group("qup") else "down", None, None)
    return _complaint(cleaned, question=question)


def _complaint(cleaned: str, *, question: bool) -> Level | None:
    """«I don't wanna hear it tan alto», «the screen is way too bright»: how it sounds or how the screen looks,
    said as a complaint, is a volume or brightness request without amount."""

    if (
        question
        or _QUESTION.search(cleaned)
        or _is_past_or_hypothetical_state(cleaned)
        or re.search(r"\d", cleaned)
    ):
        return None
    if _SEEING.search(cleaned) is not None:
        if _HEARING.search(cleaned) is not None or _OTHER_SCREEN.search(cleaned) is not None:
            return None
        setting, more, less = BRIGHTNESS, _TOO_BRIGHT, _TOO_DARK
    elif _HEARING.search(cleaned) is not None and _OTHER_OBJECT.search(cleaned) is None:
        setting, more, less = VOLUME, _TOO_LOUD, _TOO_QUIET
    else:
        return None
    loud, quiet = more.search(cleaned) is not None, less.search(cleaned) is not None
    if loud == quiet:
        return None
    negated, desire = _NEGATION.search(cleaned) is not None, _DESIRE.search(cleaned) is not None
    unheard = re.search(r"\bno\s+se\s+(?:escucha|oye|ve)\b|\b(?:barely|can'?t|cannot)\s+(?:hear|see)\b", cleaned) is not None
    if desire != negated and not unheard:
        # A wish without a refusal, or a denial without a wish («no está muy alto»), is not this complaint.
        return None
    if not (desire or unheard or _STATE.search(cleaned) or _EXCESS.search(cleaned)):
        return None
    return Level(setting, "down" if loud else "up", None, None)


def answer(text: str) -> Level | None:
    """A bare level said as the answer to «¿cuánto?»: «un 10», «20», «10%» (amounts), «a 40», «al máximo» (targets)."""

    found = _ANSWER_FORM.fullmatch(_clean(text))
    if found is None:
        return None
    quantity = _quantity(found)
    if quantity is None:
        return None
    return Level(None, None, *quantity)


# Tanda 8 «40 percent» after «How bright should the screen be adjusted to?» lowered the brightness by 40: a bare
# number answers the question BAXY asked. «¿cuánto (menos)…?», «how much…?» ask for an amount; a level («¿a qué
# nivel…?», «what level…?», «a cuánto…?»), any other question or none is answered with where the level ends.
_ASKS_AMOUNT = re.compile(r"\b(?:cuant[oa]s?|how\s+(?:much|many)|by\s+how)\b")
_ASKS_LEVEL = re.compile(r"\b(?:a\s+cuant[oa]|nivel|level|porcentaje|percentage|to\s+what)\b")
_SAYS_AMOUNT = re.compile(r"\b(?:en|by)\s+\S|\S\s+(?:mas|menos|more|less)$")


def answers_with_amount(question: str | None, answer_text: str) -> bool:
    """A bare level said after ``question`` is how much to change (True) or where to end (False)."""

    folded = fold(question or "")
    return bool(
        _SAYS_AMOUNT.search(_clean(answer_text))
        or ("?" in str(question or "") and _ASKS_AMOUNT.search(folded) and not _ASKS_LEVEL.search(folded))
    )


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
    up = re.search(rf"\b(?:{_UP}|{_COMPARATIVE_UP}|{_BRIGHTER})\b", cleaned) is not None
    down = re.search(rf"\b(?:{_DOWN}|{_COMPARATIVE_DOWN}|{_DARKER})\b", cleaned) is not None
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
