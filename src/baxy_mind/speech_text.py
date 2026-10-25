"""What BAXY's voice reads: the answer as written, turned into the words a Latin-American Spanish speaker would say.

Supertonic reads characters with Spanish rules and normalizes nothing itself (its preprocessing only decomposes
accents, turns «/» into a space and «@» into «at»; Supertone recommends normalizing text before it), so here, before
speaking: abbreviations, dates, times, money, percentages, degrees, units and numbers become words (Chile's
conventions: «1.500» is a thousand five hundred, «1,5» is one point five), and English names are respelled as they are
said (data/speech_respellings.v1.json). Only the voice reads this; the screen shows the answer as written.
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


def cardinal_en(n: int) -> str:
    """A whole number from 0 to 999 in English words («seventy five», «one hundred five»), as a transcript writes it
    without its hyphen."""
    hundreds, rest = divmod(n, 100)
    words = [_UNITS_EN[hundreds], "hundred"] if hundreds else []
    if rest >= 20:
        tens, unit = divmod(rest, 10)
        words += [_TENS_EN[tens]] + ([_UNITS_EN[unit]] if unit else [])
    elif rest or not hundreds:
        words.append(_UNITS_EN[rest])
    return " ".join(words)


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


def spoken(text: str) -> str:
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
