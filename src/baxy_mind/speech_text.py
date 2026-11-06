"""What BAXY's voice reads: the answer as written, turned into the words a Latin-American Spanish speaker would say.

Supertonic reads characters with Spanish rules and normalizes nothing itself (its preprocessing only decomposes
accents, turns «/» into a space and «@» into «at»; Supertone recommends normalizing text before it), so here, before
speaking: abbreviations, dates, times, money, percentages, degrees, units and numbers become words (Chile's
conventions: «1.500» is a thousand five hundred, «1,5» is one point five), and English names are respelled as they are
said (data/speech_respellings.v1.json). Only the voice reads this; the screen shows the answer as written.

With the interface in English (the Steam release) the App asks for each utterance in «en» (voice.speak's «lang»), and
the same is done with English conventions and Supertonic's «en» tag: «1,500» is a thousand five hundred, «1.5» one point
five, «$» dollars, «10:30» ten thirty, «Dr.» doctor, «@» at, and no Spanish respelling. A text carries the language it
is said in (Utterance) from the App's message to the synthesis; a plain str is Spanish, as before there was English.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
          "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
          "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho",
          "veintinueve"]
_TENS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_HUNDREDS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos",
             "ochocientos", "novecientos"]
_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"]
_ORDINALS = ["", "primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "séptimo", "octavo", "noveno", "décimo"]
_ABBREVIATIONS = {"Sr.": "señor", "Sra.": "señora", "Srta.": "señorita", "Dr.": "doctor", "Dra.": "doctora",
                  "Ud.": "usted", "Uds.": "ustedes", "etc.": "etcétera", "aprox.": "aproximadamente", "N.º": "número",
                  "Nº": "número", "pág.": "página"}
_UNIT_WORDS = {"km/h": "kilómetros por hora", "km": "kilómetros", "kg": "kilos", "cm": "centímetros",
               "mm": "milímetros", "GB": "gigas", "MB": "megas", "TB": "teras", "KB": "kilobytes", "Hz": "hercios",
               "ms": "milisegundos", "°C": "grados", "ºC": "grados", "°": "grados", "º": "grados", "min": "minutos",
               "seg": "segundos", "h": "horas"}
_WORD = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"


def _below_thousand(n: int) -> str:
    if n == 100:
        return "cien"
    hundreds, rest = divmod(n, 100)
    words = [_HUNDREDS[hundreds]] if hundreds else []
    if rest < 30:
        if rest or not hundreds:
            words.append(_UNITS[rest])
    else:
        tens, unit = divmod(rest, 10)
        words.append(_TENS[tens] + (f" y {_UNITS[unit]}" if unit else ""))
    return " ".join(words)


def cardinal(n: int) -> str:
    """A whole number in words, «uno» form (0 to 999 999 999 999)."""
    if n < 0:
        return "menos " + cardinal(-n)
    if n < 1000:
        return _below_thousand(n)
    parts = []
    for size, one, many in ((10 ** 9, "mil millones", "mil millones"), (10 ** 6, "un millón", "millones"),
                            (10 ** 3, "mil", "mil")):
        count, n = divmod(n, size)
        if count == 1:
            parts.append(one)
        elif count:
            parts.append(f"{_apocope(cardinal(count))} {many}")
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


_UNITS_EN = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
             "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS_EN = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES_EN = ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand"))

# Every word spoken() says a number with, by language: the voice never cuts a take after one, since «uno, dos o tres»
# and «one, two or three» are lists of numbers, not clauses (voice_output.clause_cut). One set per language: in Spanish
# «Xbox One,» ends a clause.
NUMBER_WORDS = {
    "es": frozenset({*_UNITS, *_TENS, *_HUNDREDS, *(word.replace("ientos", "ientas") for word in _HUNDREDS),
                     "un", "una", "veintiún", "veintiuna", "cien", "mil", "millón", "millones"} - {""}),
    "en": frozenset({*_UNITS_EN, *_TENS_EN, "hundred", *(name for _size, name in _SCALES_EN)} - {""}),
}


def _below_thousand_en(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    words = [_UNITS_EN[hundreds], "hundred"] if hundreds else []
    if rest >= 20:
        tens, unit = divmod(rest, 10)
        words += [_TENS_EN[tens]] + ([_UNITS_EN[unit]] if unit else [])
    elif rest or not hundreds:
        words.append(_UNITS_EN[rest])
    return " ".join(words)


def cardinal_en(n: int) -> str:
    """A whole number in English words («seventy five», «one hundred five», «two thousand twenty six»), as a transcript
    writes it: without hyphens and with no «and»."""
    if n < 0:
        return "minus " + cardinal_en(-n)
    parts = []
    for size, name in _SCALES_EN:
        count, n = divmod(n, size)
        if count:
            parts.append(f"{cardinal_en(count)} {name}")
    if n or not parts:
        parts.append(_below_thousand_en(n))
    return " ".join(parts)


def _apocope(words: str) -> str:
    """Before a masculine noun «uno» is «un» and «veintiuno» is «veintiún»."""
    if words.endswith("veintiuno"):
        return words.removesuffix("veintiuno") + "veintiún"
    return words[:-3] + "un" if words.endswith("uno") else words


def _feminine(words: str) -> str:
    """Before a feminine noun: «una», «veintiuna», «doscientas» (hundreds after the last «millón», which is masculine)."""
    head, millions, tail = words.rpartition("millón") if "millones" not in words else words.rpartition("millones")
    tail = re.sub(r"ientos\b", "ientas", tail)
    tail = re.sub(r"\buno$", "una", re.sub(r"veintiuno$", "veintiuna", tail))
    return head + millions + tail


# the noun after a number sets its gender by its ending, but for these
_MASCULINE_A = {"día", "días", "mapa", "mapas", "programa", "programas", "problema", "problemas", "sistema", "sistemas",
                "idioma", "idiomas", "tema", "temas", "planeta", "planetas", "clima", "climas", "dilema", "esquema",
                "esquemas", "pijama", "sofá", "sofás", "telegrama", "diagrama", "diagramas", "lema", "drama", "giga",
                "gigas", "mega", "megas", "tera", "teras"}
_FEMININE_O = {"foto", "fotos", "moto", "motos", "mano", "manos", "radio", "radios", "imagen", "imágenes", "canción",
               "canciones", "red", "redes", "pestaña", "vez", "veces", "notificación", "notificaciones", "versión",
               "versiones", "aplicación", "aplicaciones", "opción", "opciones", "reunión", "reuniones"}


# A word after a number that is not what it counts: the number keeps its own form, «el uno de noviembre», «del uno a
# diez», «uno o dos», «veintiuno en total», «doscientos para ti» (not «un de», «una a», «doscientas para»).
_NOT_COUNTED = {"a", "al", "de", "del", "en", "por", "para", "con", "sin", "y", "e", "o", "u", "ni", "que", "es", "son",
                "era", "fue", "más", "menos", "entre", "hasta", "desde", "sobre", "tras", "según", "hacia", "contra",
                "como", "pero", "si", "se", "lo", "la", "las", "los", "el", "le", "les", "ya", "no", "está", "están",
                "hay", "queda", "quedan", "solo", "sólo"}


def _number(digits: str, decimals: str | None, noun: str = "") -> str:
    words = cardinal(int(digits.replace(".", "")))
    if decimals:
        return f"{words} coma {' '.join(_UNITS[int(d)] for d in decimals) if decimals.startswith('0') else cardinal(int(decimals))}"
    noun = noun.lower()
    if not noun or noun in _NOT_COUNTED:
        return words
    feminine = noun in _FEMININE_O or (noun.endswith(("a", "as")) and noun not in _MASCULINE_A)
    return _feminine(words) if feminine else _apocope(words)


def _counted(match: re.Match, noun: str) -> str:
    """A number with the noun it counts (money, units): one of it is singular, «un kilómetro», «un peso». A unit of
    several words («kilómetros por hora») counts its first: «1 km/h» was «una kilómetros por hora», «21 km/h»
    «veintiuna kilómetros por hora», by the gender of «hora»."""
    digits, decimals = match.group(1), match.group(2) or match.group(3)
    head, space, rest = noun.partition(" ")
    if digits == "1" and not decimals:
        head = head[:-2] if head.endswith("res") else head.removesuffix("s")
    return f"{_number(digits, decimals, head)} {head}{space}{rest}"


def _time(match: re.Match) -> str:
    hour, minute = _feminine(cardinal(int(match.group(1)))), int(match.group(2))  # «la una», «las veintiuna»
    if minute == 0:
        return f"{hour} en punto"
    if minute == 30:
        return f"{hour} y media"
    return f"{hour} y {cardinal(minute)}"


def _date(match: re.Match) -> str:
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return match.group(0)
    said = f"{'primero' if day == 1 else cardinal(day)} de {_MONTHS[month - 1]}"
    return f"{said} de {cardinal(int(year) + (2000 if len(year) == 2 else 0))}" if year else said


@lru_cache(maxsize=1)
def _respellings() -> tuple[re.Pattern, dict[str, str]]:
    path = Path(__file__).with_name("data") / "speech_respellings.v1.json"
    table = json.loads(path.read_text(encoding="utf-8"))["respellings"]
    lowered = {word.lower(): said for word, said in table.items()}
    alternatives = "|".join(re.escape(word) for word in sorted(table, key=len, reverse=True))
    return re.compile(rf"(?<![{_WORD}\w])(?:{alternatives})(?![{_WORD}\w])", re.IGNORECASE), lowered


# --- English (the interface in English) ---------------------------------------------------------------------------

LANGS = ("es", "en")
_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]
_ORDINAL_WORDS_EN = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                     "nine": "ninth", "twelve": "twelfth"}
_ABBREVIATIONS_EN = {"Mr.": "Mister", "Mrs.": "Missus", "Ms.": "Miz", "Dr.": "Doctor", "Prof.": "Professor",
                     "Jr.": "Junior", "Sr.": "Senior", "etc.": "et cetera", "e.g.": "for example", "i.e.": "that is",
                     "vs.": "versus", "approx.": "approximately"}
_UNIT_WORDS_EN = {"km/h": "kilometers per hour", "mph": "miles per hour", "km": "kilometers", "mi": "miles",
                  "kg": "kilograms", "lb": "pounds", "lbs": "pounds", "cm": "centimeters", "mm": "millimeters",
                  "GB": "gigabytes", "MB": "megabytes", "TB": "terabytes", "KB": "kilobytes", "GHz": "gigahertz",
                  "MHz": "megahertz", "Hz": "hertz", "ms": "milliseconds", "°C": "degrees Celsius",
                  "ºC": "degrees Celsius", "°F": "degrees Fahrenheit", "ºF": "degrees Fahrenheit", "°": "degrees",
                  "º": "degrees", "min": "minutes", "sec": "seconds", "h": "hours"}
# «1,500.25»: commas group thousands, a point starts the decimals
_NUMBER_EN = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"


def language(tag: object) -> str:
    """The language an utterance is said in, from the App's tag: «en», «en-US» or «EN» are English; no tag, or any
    other, is Spanish (an App from before English sends none)."""
    primary = str(tag or "").strip().lower().replace("_", "-").partition("-")[0]
    return primary if primary in LANGS else "es"


class Utterance(str):
    """A text with the language it is said in, so what is cut from it is normalized and tagged in that language
    (spoken, voice_output.Speech): the App's voice.speak sets it, and a plain str is Spanish."""
    lang: str

    def __new__(cls, text: str, lang: object = "es") -> "Utterance":
        said = super().__new__(cls, text)
        said.lang = language(lang)
        return said


def lang_of(text: str) -> str:
    """The language a text is said in: an Utterance's own, Spanish for a plain str."""
    return getattr(text, "lang", "es")


def ordinal_en(n: int) -> str:
    """«first», «twenty second», «one hundredth»."""
    head, space, last = cardinal_en(n).rpartition(" ")
    last = _ORDINAL_WORDS_EN.get(last) or (last[:-1] + "ieth" if last.endswith("y") else last + "th")
    return head + space + last


def _year_en(year: int) -> str:
    """A year as it is said: «nineteen eighty four», «nineteen oh five», «nineteen hundred», «two thousand five»,
    «twenty twenty six»."""
    century, rest = divmod(year, 100)
    if not 10 <= century <= 99 or (century % 10 == 0 and rest < 10):
        return cardinal_en(year)
    if not rest:
        return f"{cardinal_en(century)} hundred"
    return f"{cardinal_en(century)} {'oh ' if rest < 10 else ''}{cardinal_en(rest)}"


def _said_year(year: str) -> str:
    return _year_en(int(year) + (2000 if len(year) == 2 else 0))


def _date_en(month: int, day: int, year: str | None, separator: str = ", ") -> str:
    said = f"{_MONTHS_EN[month - 1]} {ordinal_en(day)}"
    return f"{said}{separator}{_said_year(year)}" if year else said


def _slash_date_en(match: re.Match) -> str:
    """«10/17/2026» and «17/10/2026» are both October seventeenth: a number over 12 settles which is the day. With both
    under 13 («11/04/2026») the order is the writer's convention, unknown here: it is said as written, «eleven slash
    four slash twenty twenty six», never a guessed month. Without a year it is not a date: «24/7», «3/4» and «3/3» are a
    span, a fraction, a score, and are left to the numbers (Supertonic says «/» as a space)."""
    first, second, year = int(match.group(1)), int(match.group(2)), match.group(3)
    if not year:
        return match.group(0)
    if 1 <= first <= 12 and 1 <= second <= 31 and (second > 12 or second == first):
        return _date_en(first, second, year)
    if 1 <= second <= 12 and 13 <= first <= 31:
        return _date_en(second, first, year)
    if 1 <= first <= 12 and 1 <= second <= 12:
        return f"{cardinal_en(first)} slash {cardinal_en(second)} slash {_said_year(year)}"
    return match.group(0)


def _iso_date_en(match: re.Match) -> str:
    year, month, day = match.group(1), int(match.group(2)), int(match.group(3))
    return _date_en(month, day, year) if 1 <= month <= 12 and 1 <= day <= 31 else match.group(0)


def _time_en(match: re.Match) -> str:
    """«ten thirty», «ten oh five», «ten o'clock», «ten P M». A 24-hour time is said as English speakers say the hour
    outside the military: «21:00» nine P M, «00:15» twelve fifteen A M (not «twenty one o'clock»)."""
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if not half and hour > 12:
        hour, half = hour - 12, "p"
    elif not half and hour == 0:
        hour, half = 12, "a"
    said = cardinal_en(hour)
    if minute:
        said += f" {'oh ' if minute < 10 else ''}{cardinal_en(minute)}"
    elif not half and match.group(2):
        said += " o'clock"
    return f"{said} {half.upper()} M" if half else said


def _number_en(digits: str, decimals: str | None) -> str:
    words = cardinal_en(int(digits.replace(",", "")))
    return f"{words} point {' '.join(_UNITS_EN[int(d)] for d in decimals)}" if decimals else words


def _dollars(match: re.Match) -> str:
    """«one dollar», «one thousand nine hundred ninety dollars», «four dollars and ninety nine cents», «fifty cents»."""
    digits, decimals = match.group(1), match.group(2)
    if decimals is not None and len(decimals) == 2:
        whole, cents = int(digits.replace(",", "")), int(decimals)
        said = [f"{cardinal_en(whole)} dollar{'' if whole == 1 else 's'}"] if whole or not cents else []
        if cents:
            said.append(f"{cardinal_en(cents)} cent{'' if cents == 1 else 's'}")
        return " and ".join(said)
    return f"{_number_en(digits, decimals)} dollar{'' if digits == '1' and not decimals else 's'}"


def _counted_en(match: re.Match, noun: str) -> str:
    """A number with its unit: one of it is singular, «one kilometer», «one degree Celsius», «one mile per hour»."""
    digits, decimals = match.group(1), match.group(2)
    head, space, rest = noun.partition(" ")
    if digits == "1" and not decimals:
        head = head.removesuffix("s")
    return f"{_number_en(digits, decimals)} {head}{space}{rest}"


def _spoken_en(text: str) -> str:
    # «etc.» closing a sentence keeps its point, so the sentence still ends there («etc. Then»)
    text = re.sub(r"(?<![A-Za-z])etc\.(?=\s+[A-Z]|\s*$)", "et cetera.", text)
    for short, said in _ABBREVIATIONS_EN.items():
        text = re.sub(rf"(?<![A-Za-z]){re.escape(short)}", said, text)
    text = re.sub(r"\bNo\.\s?(?=\d)", "number ", text)
    text = text.replace("@", " at ")
    text = re.sub(r"\s*[—–]\s*", ", ", text.replace("…", "..."))  # as in Spanish: characters Supertonic's index lacks
    # dotted groups (an address, a version) digit by digit: «192.168.1.20» one nine two dot one six eight dot one dot
    # two zero, «1.2.3» one dot two dot three
    text = re.sub(r"(?<![\d.A-Za-z])\d+(?:\.\d+){2,}(?!\d)",
                  lambda m: " dot ".join(" ".join(_UNITS_EN[int(d)] for d in group) for group in m.group(0).split(".")),
                  text)
    # dates and times before numbers: 2026-11-04, 10/17/2026, November 4, 2026, 4 November, 10:30, 10:30 a.m., 5 pm
    months = "|".join(_MONTHS_EN)
    text = re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", _iso_date_en, text)
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b", _slash_date_en, text)
    text = re.sub(rf"\b({months})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:(,?\s+)(\d{{4}})\b)?",
                  lambda m: _date_en(_MONTHS_EN.index(m.group(1)) + 1, int(m.group(2)), m.group(4), m.group(3) or "")
                  if 1 <= int(m.group(2)) <= 31 else m.group(0), text)
    text = re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({months})\b(?:(,?\s+)(\d{{4}})\b)?",
                  lambda m: f"the {ordinal_en(int(m.group(1)))} of {m.group(2)}"
                  + (m.group(3) + _said_year(m.group(4)) if m.group(4) else "")
                  if 1 <= int(m.group(1)) <= 31 else m.group(0), text)
    text = re.sub(rf"\b({months})(,?\s+)(\d{{4}})\b", lambda m: m.group(1) + m.group(2) + _said_year(m.group(3)), text)
    # «a.m.» keeps its last point when it ends the sentence, so the sentence still ends there. Only right after a clock
    # time, and only as one is written: am, a.m., AM, A.M. («Is it 3 Am I» has none)
    half = r"(?:\s?([ap](?=\.?m\b)|[AP](?=\.?M\b))\.?[Mm]\b(?:\.(?=\s+[a-z]))?)"
    text = re.sub(rf"\b([01]?\d|2[0-3]):([0-5]\d)\b{half}?", _time_en, text)
    text = re.sub(rf"\b(1[0-2]|0?[1-9])(){half}", _time_en, text)
    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", lambda m: ordinal_en(int(m.group(1))), text)
    text = re.sub(r"(?<![\dA-Za-z])-(?=\d)", "minus ", text)
    # money and percentages: $1,990, US$5, 5 USD, $4.99, 30 %, 30%
    text = re.sub(rf"(?:US\$|USD\s?)\s?{_NUMBER_EN}", _dollars, text)
    text = re.sub(rf"\${_NUMBER_EN}", _dollars, text)
    text = re.sub(rf"{_NUMBER_EN}\s?USD\b", _dollars, text)
    text = re.sub(rf"{_NUMBER_EN}\s?%", lambda m: _number_en(m.group(1), m.group(2)) + " percent", text)
    units = "|".join(re.escape(unit) for unit in sorted(_UNIT_WORDS_EN, key=len, reverse=True))
    text = re.sub(rf"{_NUMBER_EN}\s?({units})(?![A-Za-z])", lambda m: _counted_en(m, _UNIT_WORDS_EN[m.group(3)]), text)
    # A bare 1100-2099 is said as a year only where it clearly is one: after a word that places it in time (in, since,
    # by, of, until, from, during, before, after, circa, year: «in 2026» twenty twenty six), or closing a clause (before
    # , ; : ! ? a stop or the end: «It was 1984.»). Anywhere else it is a quantity: «2026 files».
    year = r"(1[1-9]\d\d|20\d\d)(?![\d,.]\d)"
    text = re.sub(rf"\b((?i:in|since|by|of|until|till|from|during|before|after|circa|year)\s+){year}\b",
                  lambda m: m.group(1) + _year_en(int(m.group(2))), text)
    text = re.sub(rf"(?<![\dA-Za-z,.$]){year}(?=\s*(?:[,;:!?]|\.(?!\d)|$))", lambda m: _year_en(int(m.group(1))), text)
    # a letter written against the number is said after it: «4K» is «four K», «1080p» «one thousand eighty p»
    return re.sub(rf"(?<![\dA-Za-z]){_NUMBER_EN}", lambda m: _number_en(m.group(1), m.group(2))
                  + (" " if m.string[m.end():m.end() + 1].isalpha() else ""), text)


def spoken(text: str, lang: str | None = None) -> str:
    """What the voice says for text, in lang («es» or «en»); None is the text's own (lang_of: an Utterance's, or
    Spanish)."""
    if (lang or lang_of(text)) == "en":
        return _spoken_en(text)
    for short, said in _ABBREVIATIONS.items():
        text = re.sub(rf"(?<![{_WORD}]){re.escape(short)}", said, text)
    text = text.replace("@", " arroba ")
    # characters Supertonic's index lacks (id -1 in sherpa-onnx 1.13.4), said as what they mark: «…» a trailing pause,
    # a dash an aside
    text = re.sub(r"\s*[—–]\s*", ", ", text.replace("…", "..."))
    # dates and times before numbers: 17/10/2026, 17/10, 10:30
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b", _date, text)
    text = re.sub(r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?:\s?h\b)?", _time, text)  # «10:30 h» is said without its «h»
    # ordinals 1.º 2.ª (up to tenth; «°» is left to degrees)
    text = re.sub(r"\b(10|[1-9])\.?([ºª])(?!C)",
                  lambda m: _ORDINALS[int(m.group(1))][:-1] + ("a" if m.group(2) == "ª" else "o"), text)
    number = r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+)|\.(\d{1,2}|\d{4,}))?"
    # money and percentages: $1.990, 30 %, 30%
    text = re.sub(rf"(?:US\$|USD\s?)\s?{number}", lambda m: _counted(m, "dólares"), text)
    text = re.sub(rf"\${number}", lambda m: _counted(m, "pesos"), text)
    text = re.sub(rf"{number}\s?%", lambda m: _number(m.group(1), m.group(2) or m.group(3)) + " por ciento", text)
    units = "|".join(re.escape(unit) for unit in sorted(_UNIT_WORDS, key=len, reverse=True))
    text = re.sub(rf"{number}\s?({units})(?![{_WORD}])", lambda m: _counted(m, _UNIT_WORDS[m.group(4)]), text)
    text = re.sub(rf"(?<![\d{_WORD}])-(?=\d)", "menos ", text)
    # a letter written against the number is said after it: «4K» is «cuatro K», «1080p» «mil ochenta p»
    text = re.sub(rf"(?<![\d{_WORD}]){number}(?=(\s+[{_WORD}]+)?)",
                  lambda m: _number(m.group(1), m.group(2) or m.group(3), (m.group(4) or "").strip())
                  + (" " if m.string[m.end():m.end() + 1].isalpha() else ""), text)
    pattern, said = _respellings()
    return pattern.sub(lambda m: said[m.group(0).lower()], text)
