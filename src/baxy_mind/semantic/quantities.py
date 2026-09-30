"""Quantities said with their units, and the figures a reply may derive from them (M53 design B, D35).

F-s097 «He recorrido 5 kilómetros en 1 hora, en realidad 1 hora 10 minutos» was answered «4,54 km/h»: the model read
«1 h 10 min» as 1,1 h (5 / 1,1). Evaluating «5/1,1» exactly would still give 4,54; the mistake is in reading the
duration, so the quantities are read here — durations with the same unit words the temporal readers use
(``grammar._RELATIVE_DURATION_UNIT``) — and the arithmetic is done on exact fractions with units:

- ``measures``           the quantities a text states (value, dimension, unit), a correction («en realidad …»)
                         replacing what it corrects;
- ``evaluate``           a closed evaluator over ``ast`` (numbers with units, + - * / ** and parentheses, round, min,
                         max, sum, mean, sqrt), on ``Fraction``; never ``eval``;
- ``derived_facts``      what BAXY computes from the person's quantities (speed and pace from a distance and a time,
                         the total of several of one kind), declared to the writer before it writes;
- ``underived_figure``   a figure in a talk reply that neither the conversation states nor the declared calculation
                         gives: a derived measure («4,54 km/h»), or an aggregate («el promedio es 3,14», F-w12-t3)
                         with no data to aggregate. Other numbers («669 primos», years) are not judged.
- ``priced_totals``      M62: what the quantity the person asks about costs at a unit price a read states («40 litros»
                         at «el litro … $1.460» → $58.400), computed here;
- ``underived_price``    the amount of money a report gives for that quantity that is neither the unit price read nor
                         the computed total (v3e2-final F-w13-t2: «$73.000 por 40 litros» from a full tank's price).
- ``conversion_asked``   M88: a pure conversion between two units of one kind («2 cucharadas en cucharaditas»),
                         computed; a kitchen quantity that depends on what is measured is looked up instead
                         (``semantic.knowledge``).
- ``unsure_figures``     M88: the figures of an answer from memory given more precisely than memory holds (D-s111
                         «1.080 km en línea recta», «2 horas y 15 minutos»); since M92 judged on recipes only.
- ``unsaid_figures``     M92 (D52): the figures of a prose or list answer from memory the person did not say, which
                         memory never gives; ``without_listed_years`` drops the bracketed years of such a list.
- ``rated_totals``       M92: the quantity the request states under a per-unit rule a read states («3 litros» ×
                         «10 g por litro» = 30 g), computed; ``gives_a_total`` says whether a reply states it.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .normalize import fold

__all__ = [
    "Measure", "measures", "evaluate", "derived_facts", "underived_figure", "numbers_in", "format_number",
    "PricedTotal", "priced_totals", "underived_price", "Conversion", "conversion_asked", "unsure_figures",
    "unsaid_figures", "without_listed_years", "RatedTotal", "rated_totals", "gives_a_total",
]

# dimension: (length, time, mass, volume) exponents
_LENGTH, _TIME, _MASS, _VOLUME = (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)
_SPEED = (1, -1, 0, 0)
_PACE = (-1, 1, 0, 0)

# unit word (folded) → (factor to the base unit: metre, second, gram, millilitre; dimension)
_UNITS: dict[str, tuple[Fraction, tuple[int, int, int, int]]] = {}


def _unit(words: str, factor: Fraction | int, dimension: tuple[int, int, int, int]) -> None:
    for word in words.split():
        _UNITS[word] = (Fraction(factor), dimension)


_unit("km kms kilometro kilometros kilometer kilometers kilometre kilometres", 1000, _LENGTH)
_unit("m mt mts metro metros meter meters metre metres", 1, _LENGTH)
_unit("cm centimetro centimetros centimeter centimeters", Fraction(1, 100), _LENGTH)
_unit("mm milimetro milimetros millimeter millimeters", Fraction(1, 1000), _LENGTH)
_unit("milla millas mile miles", Fraction(1609344, 1000), _LENGTH)
_unit("s seg segs segundo segundos sec secs second seconds", 1, _TIME)
_unit("min mins minuto minutos minute minutes", 60, _TIME)
_unit("h hr hrs hora horas hour hours", 3600, _TIME)
_unit("dia dias day days", 86400, _TIME)
_unit("g gr grs gramo gramos gram grams", 1, _MASS)
_unit("kg kgs kilo kilos kilogramo kilogramos kilogram kilograms", 1000, _MASS)
_unit("lb lbs libra libras pound pounds", Fraction(45359237, 100000), _MASS)
_unit("ml mililitro mililitros milliliter milliliters", 1, _VOLUME)
_unit("l lt lts litro litros liter liters litre litres", 1000, _VOLUME)
_unit("galon galones gallon gallons gal", Fraction(3785411784, 1000000), _VOLUME)

_SPEED_UNITS = {"km/h": Fraction(1000, 3600), "kmh": Fraction(1000, 3600), "km por hora": Fraction(1000, 3600),
                "kilometros por hora": Fraction(1000, 3600), "m/s": Fraction(1), "mph": Fraction(1609344, 3600000),
                "millas por hora": Fraction(1609344, 3600000), "miles per hour": Fraction(1609344, 3600000),
                "kilometers per hour": Fraction(1000, 3600)}
_PACE_UNITS = {"min/km": Fraction(60, 1000), "minutos por kilometro": Fraction(60, 1000),
               "minutes per kilometer": Fraction(60, 1000), "min por km": Fraction(60, 1000)}

_NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3, "cuatro": 4,
    "four": 4, "cinco": 5, "five": 5, "seis": 6, "six": 6, "siete": 7, "seven": 7, "ocho": 8, "eight": 8, "nueve": 9,
    "nine": 9, "diez": 10, "ten": 10, "once": 11, "eleven": 11, "doce": 12, "twelve": 12, "quince": 15,
    "fifteen": 15, "veinte": 20, "twenty": 20, "treinta": 30, "thirty": 30, "cuarenta": 40, "forty": 40,
    "cincuenta": 50, "fifty": 50, "sesenta": 60, "sixty": 60, "cien": 100, "hundred": 100,
}
_NUMBER = r"\d+(?:[.,]\d+)?(?:\s+\d+/\d+)?|\d+/\d+|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_UNIT_WORD = "|".join(sorted((re.escape(word) for word in _UNITS), key=len, reverse=True))
_MEASURE = re.compile(
    rf"(?<![\w.,/])(?P<number>{_NUMBER})\s*(?P<unit>{_UNIT_WORD})(?![\w/])"
    r"(?P<half>\s+y\s+media|\s+and\s+a\s+half)?"
)
_HALF_HOUR = re.compile(r"\b(?:media\s+hora|half\s+an?\s+hour)\b")
# «en realidad», «mejor dicho», «actually»: what follows corrects the quantity of the same kind said before.
_CORRECTION = re.compile(r"\b(?:en\s+realidad|mejor\s+dicho|o\s+sea|digo|perdon|actually|i\s+mean|rather|or\s+rather)\b")
_JOINED = re.compile(r"^\s*(?:,|y|and|con)?\s*$")


@dataclass(frozen=True)
class Measure:
    value: Fraction  # in the base unit of its dimension
    dimension: tuple[int, int, int, int]
    start: int
    end: int


def _number(raw: str) -> Fraction | None:
    raw = raw.strip()
    if raw in _NUMBER_WORDS:
        return Fraction(_NUMBER_WORDS[raw])
    try:
        if " " in raw:
            whole, fraction = raw.split(None, 1)
            return Fraction(whole.replace(",", ".")) + Fraction(fraction)
        return Fraction(raw.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


def _raw_measures(folded: str) -> list[Measure]:
    found: list[Measure] = []
    for match in _MEASURE.finditer(folded):
        number = _number(match.group("number"))
        unit = _UNITS.get(match.group("unit"))
        if number is None or unit is None:
            continue
        factor, dimension = unit
        value = number * factor
        if match.group("half"):
            value += factor / 2
        found.append(Measure(value, dimension, match.start(), match.end()))
    for match in _HALF_HOUR.finditer(folded):
        if not any(item.start <= match.start() < item.end for item in found):
            found.append(Measure(Fraction(1800), _TIME, match.start(), match.end()))
    found.sort(key=lambda item: item.start)
    # «1 hora 10 minutos», «1 h y 10 min»: adjacent durations are one duration.
    merged: list[Measure] = []
    for item in found:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.dimension == item.dimension == _TIME
            and _JOINED.match(folded[previous.end:item.start]) is not None
            and item.value < previous.value
        ):
            merged[-1] = Measure(previous.value + item.value, _TIME, previous.start, item.end)
        else:
            merged.append(item)
    return merged


def measures(text: str) -> list[Measure]:
    """The quantities the text states, in order; a corrected quantity is replaced by its correction."""

    folded = fold(text)
    found = _raw_measures(folded)
    kept: list[Measure] = []
    for item in found:
        corrected = next(
            (
                earlier
                for earlier in reversed(kept)
                if earlier.dimension == item.dimension and _CORRECTION.search(folded[earlier.end:item.start])
            ),
            None,
        )
        if corrected is not None:
            kept.remove(corrected)
        kept.append(item)
    return kept


# ------------------------------------------------------------------ the evaluator


@dataclass(frozen=True)
class _Quantity:
    value: Fraction
    dimension: tuple[int, int, int, int] = (0, 0, 0, 0)


def _combine(left: _Quantity, right: _Quantity, operator: ast.operator) -> _Quantity:
    if isinstance(operator, (ast.Add, ast.Sub)):
        if left.dimension != right.dimension:
            raise ValueError("sumar cantidades de distinta clase")
        value = left.value + right.value if isinstance(operator, ast.Add) else left.value - right.value
        return _Quantity(value, left.dimension)
    if isinstance(operator, ast.Mult):
        return _Quantity(left.value * right.value, tuple(a + b for a, b in zip(left.dimension, right.dimension)))
    if isinstance(operator, ast.Div):
        if right.value == 0:
            raise ValueError("división por cero")
        return _Quantity(left.value / right.value, tuple(a - b for a, b in zip(left.dimension, right.dimension)))
    if isinstance(operator, ast.Pow):
        if right.dimension != (0, 0, 0, 0) or right.value.denominator != 1 or abs(right.value) > 8:
            raise ValueError("potencia no admitida")
        exponent = int(right.value)
        return _Quantity(left.value ** exponent, tuple(part * exponent for part in left.dimension))
    raise ValueError("operador no admitido")


def _evaluate(node: ast.AST, units: dict[str, _Quantity]) -> _Quantity:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, units)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return _Quantity(Fraction(str(node.value)))
    if isinstance(node, ast.Name) and node.id in units:
        return units[node.id]
    if isinstance(node, ast.BinOp):
        return _combine(_evaluate(node.left, units), _evaluate(node.right, units), node.op)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = _evaluate(node.operand, units)
        return _Quantity(-operand.value if isinstance(node.op, ast.USub) else operand.value, operand.dimension)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        arguments = [_evaluate(argument, units) for argument in node.args]
        name = node.func.id
        if name in {"min", "max", "sum", "mean"} and arguments:
            if len({argument.dimension for argument in arguments}) != 1:
                raise ValueError("cantidades de distinta clase")
            values = [argument.value for argument in arguments]
            value = (
                min(values) if name == "min" else max(values) if name == "max" else sum(values, Fraction(0))
                if name == "sum" else sum(values, Fraction(0)) / len(values)
            )
            return _Quantity(value, arguments[0].dimension)
        if name == "round" and len(arguments) in {1, 2}:
            digits = int(arguments[1].value) if len(arguments) == 2 else 0
            scale = Fraction(10) ** digits
            return _Quantity(Fraction(round(arguments[0].value * scale)) / scale, arguments[0].dimension)
        if name == "sqrt" and len(arguments) == 1 and arguments[0].value >= 0:
            dimension = arguments[0].dimension
            if any(part % 2 for part in dimension):
                raise ValueError("raíz de una unidad impar")
            return _Quantity(Fraction(math.sqrt(arguments[0].value)), tuple(part // 2 for part in dimension))
    raise ValueError("expresión no admitida")


def evaluate(expression: str) -> tuple[Fraction, tuple[int, int, int, int]]:
    """Evaluate «5 km / (1 h + 10 min)» exactly: value in base units (m, s, g, ml) and its dimension.

    Each «number unit» becomes a quantity; only arithmetic, parentheses and a few functions are accepted.
    """

    units: dict[str, _Quantity] = {}

    def quantity(match: re.Match[str]) -> str:
        number = _number(match.group("number"))
        unit = _UNITS.get(match.group("unit"))
        if number is None or unit is None:
            raise ValueError("cantidad ilegible")
        name = f"_q{len(units)}"
        units[name] = _Quantity(number * unit[0], unit[1])
        return name

    folded = fold(expression)
    source = re.sub(rf"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_WORD})(?![\w])", quantity, folded)
    source = re.sub(r"(\d),(\d)", r"\1.\2", source)
    tree = ast.parse(source, mode="eval")
    result = _evaluate(tree, units)
    return result.value, result.dimension


# ------------------------------------------------------------------ what a reply may derive

def format_number(value: Fraction | float, decimals: int = 2, language: str = "es") -> str:
    rounded = round(float(value), decimals)
    text = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if language == "es" else text


def _clock_minutes(seconds: Fraction) -> str:
    total = round(float(seconds))
    return f"{total // 60} min {total % 60:02d} s"


def derived_facts(text: str, language: str = "es") -> list[tuple[str, Fraction, tuple[int, int, int, int]]]:
    """What BAXY computes from the quantities the person states: (sentence, value in base units, dimension)."""

    stated = measures(text)
    facts: list[tuple[str, Fraction, tuple[int, int, int, int]]] = []
    distances = [item for item in stated if item.dimension == _LENGTH]
    times = [item for item in stated if item.dimension == _TIME]
    if len(distances) == 1 and len(times) == 1 and times[0].value > 0 and distances[0].value > 0:
        distance, duration = distances[0].value, times[0].value
        speed = distance / duration
        pace = duration / distance
        km = format_number(distance / 1000, 3, language)
        minutes = format_number(duration / 60, 2, language)
        speed_text = format_number(speed / _SPEED_UNITS["km/h"], 2, language)
        pace_text = _clock_minutes(pace * 1000)
        facts.append((
            (f"{km} km en {minutes} min = {speed_text} km/h" if language == "es" else f"{km} km in {minutes} min = {speed_text} km/h"),
            speed, _SPEED,
        ))
        facts.append((
            (f"ritmo {pace_text} por km" if language == "es" else f"pace {pace_text} per km"),
            pace, _PACE,
        ))
    for dimension in (_LENGTH, _TIME, _MASS, _VOLUME):
        same = [item for item in stated if item.dimension == dimension]
        if len(same) >= 2:
            total = sum((item.value for item in same), Fraction(0))
            facts.append(("total " + format_number(total, 2, language), total, dimension))
    # M88: a pure conversion asked («¿cuántas cucharaditas son 2 cucharadas?») is BAXY's arithmetic too.
    conversion = conversion_asked(text, language)
    if conversion is not None:
        facts.append((conversion.sentence, conversion.value, (0, 0, 0, 0)))
    return facts


_READ_SPEED = re.compile(
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>km/h|kmh|km\s+por\s+hora|kilometros\s+por\s+hora|kilometers\s+per\s+hour|"
    r"m/s|mph|millas\s+por\s+hora|miles\s+per\s+hour)(?!\w)"
)
_READ_PACE = re.compile(
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>min/km|min\s+por\s+km|minutos\s+por\s+kilometro|minutes\s+per\s+kilometer)(?!\w)"
)
_AGGREGATE = re.compile(
    r"\b(?:promedio|media|average|mean)\b[^.;:\n]{0,40}?"
    r"\b(?:es|son|da|seria|sera|queda|is|would\s+be|equals|comes\s+to|=)\s+(?:de\s+|of\s+)?"
    r"(?P<number>-?\d+(?:[.,]\d+)?)"
)
_DIGITS = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)?(?![\w])")


def numbers_in(texts: Iterable[str]) -> list[Fraction]:
    """Every number written with digits in the texts («3,14» and «3.14» alike)."""

    found: list[Fraction] = []
    for text in texts:
        for raw in _DIGITS.findall(fold(text)):
            number = _number(raw)
            if number is not None:
                found.append(number)
    return found


def _close(value: Fraction, expected: Fraction, decimals_shown: int) -> bool:
    tolerance = Fraction(1, 2 * 10 ** decimals_shown) + abs(expected) / 1000
    return abs(value - expected) <= tolerance


def _decimals(raw: str) -> int:
    return len(re.split(r"[.,]", raw)[1]) if re.search(r"[.,]", raw) else 0


def underived_figure(reply: str, request: str, prior_requests: Iterable[str] = (), evidence: str = "") -> str:
    """The figure of a talk reply that nothing grounds, or "" when every judged figure is grounded.

    Judged: a speed or pace when the person states a distance and a time (it must be the computed one), a measure of
    the kind the person gave more than one of (their total), and an aggregate («el promedio es …») that is neither
    written in the conversation nor computable from the numbers it gives.
    """

    earlier = [str(item) for item in prior_requests]
    conversation = [request, *earlier]
    folded = fold(reply)
    facts = [fact for text in (request, *reversed(earlier)) for fact in derived_facts(text)][:8]
    stated = [item for text in conversation for item in measures(text)]
    for pattern, units, dimension in ((_READ_SPEED, _SPEED_UNITS, _SPEED), (_READ_PACE, _PACE_UNITS, _PACE)):
        for match in pattern.finditer(folded):
            computed = [value for _, value, kind in facts if kind == dimension]
            if not computed:
                continue
            said = _number(match.group("number"))
            unit = units.get(re.sub(r"\s+", " ", match.group("unit")))
            if said is None or unit is None:
                continue
            if not any(_close(said * unit, value, _decimals(match.group("number"))) for value in computed):
                return match.group(0)
    totals = [(value, kind) for sentence, value, kind in facts if sentence.startswith("total")]
    for item in measures(reply):
        if not any(kind == item.dimension for _, kind in totals):
            continue
        grounded = any(said.dimension == item.dimension and said.value == item.value for said in stated) or any(
            kind == item.dimension and abs(item.value - value) <= abs(value) / 200 for value, kind in totals
        )
        if not grounded:
            return fold(reply)[item.start:item.end]
    written = numbers_in([*conversation, evidence])
    for match in _AGGREGATE.finditer(folded):
        said = _number(match.group("number"))
        if said is None or any(_close(said, value, _decimals(match.group("number"))) for value in written):
            continue
        if len(written) >= 2:
            mean = sum(written, Fraction(0)) / len(written)
            total = sum(written, Fraction(0))
            if any(_close(said, value, _decimals(match.group("number"))) for value in (mean, total)):
                continue
        return match.group(0)
    return ""


# ------------------------------------------------------------------ what a quantity costs at a price read (M62)

# v3e2-final F-w13-t2 «y si cargo 40 litros cuanto me sale» after the fuel price was asked: the page said «el litro de
# nafta súper se ubica en $1.460 … lo que equivale a $73.000 … por un tanque completo», and the report said «$1.460 el
# litro, lo que suma $73.000 por 40 litros» (40 × 1.460 = 58.400). The unit price is read here, the total is computed
# here on exact fractions, and a report may give for that quantity only the unit price or that total.
_CURRENCY = r"(?:us\$|u\$s|\$|€|£)"
_CURRENCY_WORD = r"(?:pesos?|dolares|dolar|dollars?|euros?|soles|bolivares|reales)"
_MONEY_NUMBER = r"\d[\d.,]*\d|\d"
# A price unit is a volume or a mass: a word of three letters or more before the price («el litro de nafta … $1.460»),
# any of its words after it («$1.460/l», «$1.460 el litro», «1.460 pesos por litro»).
_PRICE_UNIT_WORD = "|".join(
    sorted((re.escape(word) for word, (_, dimension) in _UNITS.items() if dimension in {_VOLUME, _MASS}),
           key=len, reverse=True)
)
_LONG_PRICE_UNIT_WORD = "|".join(
    sorted((re.escape(word) for word, (_, dimension) in _UNITS.items()
            if dimension in {_VOLUME, _MASS} and len(word) >= 3), key=len, reverse=True)
)
_UNIT_THEN_PRICE = re.compile(
    rf"\b(?P<unit>{_LONG_PRICE_UNIT_WORD})\b[^\d$€£\n.;]{{0,40}}?"
    rf"(?:(?P<sign>{_CURRENCY})\s?(?P<amount>{_MONEY_NUMBER})|(?P<worded>{_MONEY_NUMBER})\s*(?P<word>{_CURRENCY_WORD})\b)"
)
_PRICE_THEN_UNIT = re.compile(
    rf"(?:(?P<sign>{_CURRENCY})\s?(?P<amount>{_MONEY_NUMBER})|(?P<worded>{_MONEY_NUMBER})\s*(?P<word>{_CURRENCY_WORD}))"
    rf"\s*(?:/|el|la|por|per|a|each|cada|the|an?)\s*(?:(?:un|una|1)\s+)?(?P<unit>{_PRICE_UNIT_WORD})\b"
)
_MONEY = re.compile(
    rf"{_CURRENCY}\s?(?P<amount>{_MONEY_NUMBER})|(?<![\w.,])(?P<worded>{_MONEY_NUMBER})\s*{_CURRENCY_WORD}\b"
)


@dataclass(frozen=True)
class PricedTotal:
    sentence: str  # «40 litros × $1.460 por litro = $58.400»
    total: Fraction
    unit_price: Fraction


def _money(raw: str) -> Fraction | None:
    """«1.460» and «1,460» as thousands, «3.99» and «3,5» as decimals, «1.460,50» and «1,460.50» both ways."""

    raw = raw.strip()
    try:
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
            return Fraction(raw.replace(".", "").replace(",", "."))
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", raw):
            return Fraction(raw.replace(",", ""))
        return Fraction(raw.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


def _money_said(value: Fraction, like: str, language: str = "es") -> str:
    """``value`` written the way the page wrote its price ``like`` («$1.460» → «$58.400»; «$1,460» → «$58,400»;
    «1.200 pesos» → «2.400 pesos»); a price without separators is written in the reply's language."""

    whole = round(float(value), 2).is_integer()
    text = f"{float(value):,.0f}" if whole else f"{float(value):,.2f}"
    number = re.search(_MONEY_NUMBER, like)
    written = number.group(0) if number else ""
    dotted = re.search(r"\d\.\d{3}(?!\d)", written) or (re.search(r"\d,\d{1,2}(?!\d)", written) and "." not in written)
    unseparated = not re.search(r"[.,]", written)
    if dotted or (unseparated and language == "es"):
        text = text.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return like[:number.start()] + text + like[number.end():] if number else text


def _unit_prices(evidence: str) -> list[tuple[Fraction, Fraction, tuple[int, int, int, int], str, str, str]]:
    """(price, unit size in base units, dimension, the price as written, the unit word, the words around it) of each
    unit price the evidence states."""

    folded = fold(evidence)
    found: list[tuple[Fraction, Fraction, tuple[int, int, int, int], str, str, str]] = []
    for pattern in (_UNIT_THEN_PRICE, _PRICE_THEN_UNIT):
        for match in pattern.finditer(folded):
            raw = match.group("amount") or match.group("worded")
            price = _money(raw) if raw else None
            unit = _UNITS.get(match.group("unit"))
            if price is None or price <= 0 or unit is None:
                continue
            said = (match.group("sign") or "") + raw + (" " + match.group("word") if match.group("word") else "")
            around = folded[max(0, match.start() - 40):match.end()]
            entry = (price, unit[0], unit[1], said, match.group("unit"), around)
            if all(entry[:3] != other[:3] for other in found):
                found.append(entry)
    return found


# Words of a request that do not say what is priced («¿cuánto me sale cargar 40 litros…?»).
_PRICE_FRAME_WORDS = frozenset(
    {
        "cuanto", "cuanta", "cuesta", "cuestan", "sale", "salen", "saldria", "vale", "valen", "precio", "cargar",
        "cargo", "echar", "echo", "llenar", "comprar", "compro", "pagar", "pago", "hoy", "ahora", "aqui", "much",
        "cost", "costs", "would", "price", "fill", "buy", "pay", "today", "for", "the", "que", "con", "por", "para",
        "unos", "unas", "como", "esta", "estan",
    }
)


def _priced_words(request: str) -> set[str]:
    """What the request prices: its words of four letters or more that are neither a unit nor its frame."""

    return {
        word for word in re.findall(r"[a-z]{4,}", fold(request))
        if word not in _PRICE_FRAME_WORDS and word not in _UNITS
    }


def priced_totals(request: str, evidence: str, language: str = "es") -> list[PricedTotal]:
    """What the one volume or mass the request states costs at each unit price the evidence states."""

    asked = [item for item in measures(request) if item.dimension in {_VOLUME, _MASS}]
    if len(asked) != 1 or asked[0].value <= 0:
        return []
    quantity = asked[0]
    said_quantity = fold(request)[quantity.start:quantity.end]
    prices = [entry for entry in _unit_prices(evidence) if entry[2] == quantity.dimension]
    # «40 litros de nafta súper» next to «el litro de Diésel … $755»: when the request names what it prices and some
    # price is said next to those words, only those prices are its.
    named = _priced_words(request)
    about = [entry for entry in prices if any(re.search(rf"\b{word}\b", entry[5]) for word in named)]
    totals: list[PricedTotal] = []
    for price, size, _dimension, written, unit_name, _around in about or prices:
        total = quantity.value / size * price
        per = (" por " if language == "es" else " per ") + unit_name
        sentence = f"{said_quantity} × {written}{per} = {_money_said(total, written, language)}"
        if all(total != other.total for other in totals):
            totals.append(PricedTotal(sentence, total, price))
    return totals


def underived_price(reply: str, request: str, evidence: str) -> str:
    """The amount of money the reply gives that is neither a unit price read nor a computed total, when the request
    states a quantity and the evidence a price for its unit; "" otherwise."""

    totals = priced_totals(request, evidence)
    if not totals:
        return ""
    allowed = [item.total for item in totals] + [item.unit_price for item in totals]
    for match in _MONEY.finditer(fold(reply)):
        raw = match.group("amount") or match.group("worded")
        value = _money(raw) if raw else None
        if value is None:
            continue
        if not any(abs(value - expected) <= expected / 100 for expected in allowed):
            return match.group(0).strip()
    return ""


# ------------------------------------------------------------------ kitchen measures and pure conversions (M88)

# M88 (step 6 of goal v3: figures and recipes are looked up): a conversion between two units of the same kind with a
# fixed factor is pure arithmetic and BAXY computes it; any other kitchen quantity (how much salt per litre, how many
# grams a cup of a named flour weighs) depends on the thing measured and needs a source. The metric spoons are 15 and
# 5 ml (their ratio, 3, is the same in the US spoons); a cup is 240, 250 or 236 ml depending on the country, and a
# «cucharón» is no measure at all: neither is converted here.
_SPOONS: dict[str, tuple[Fraction, tuple[int, int, int, int]]] = {
    **dict.fromkeys("cucharada cucharadas tablespoon tablespoons tbsp".split(), (Fraction(15), _VOLUME)),
    **dict.fromkeys("cucharadita cucharaditas teaspoon teaspoons tsp".split(), (Fraction(5), _VOLUME)),
}
_CONVERSION_UNITS = {**_UNITS, **_SPOONS}
_CONVERSION_UNIT_WORD = "|".join(sorted((re.escape(word) for word in _CONVERSION_UNITS), key=len, reverse=True))
_CONVERTED = rf"(?P<number>{_NUMBER})\s*(?P<source>{_CONVERSION_UNIT_WORD})"
_CONVERSION_ASKED = (
    # «¿cuántas cucharaditas son 2 cucharadas?», «how many ml are in 3 tablespoons»
    re.compile(
        rf"\b(?:cuant[oa]s|how\s+many)\s+(?P<target>{_CONVERSION_UNIT_WORD})\s+(?:son|serian|seria|hay\s+en|hay|"
        r"tiene|tienen|caben\s+en|entran\s+en|equivalen\s+a|equivale\s+a|are\s+there\s+in|are\s+in|in|is|are|make)\s+"
        rf"(?:(?:un|una|a|an)\s+)?{_CONVERTED}(?![\w/])"
    ),
    # «3 litros en ml», «convierte 2 cucharadas a cucharaditas», «2 tbsp to tsp»
    re.compile(rf"(?<![\w.,/]){_CONVERTED}\s+(?:en|a|in|to|into)\s+(?P<target>{_CONVERSION_UNIT_WORD})(?![\w/])"),
)


@dataclass(frozen=True)
class Conversion:
    sentence: str  # «2 cucharadas = 6 cucharaditas»
    value: Fraction  # in the unit asked


def conversion_asked(text: str, language: str = "es") -> Conversion | None:
    """The pure conversion the text asks (a quantity said in one unit, asked in another of the same kind), computed;
    None when the text asks none (see above)."""

    folded = fold(text)
    for pattern in _CONVERSION_ASKED:
        for found in pattern.finditer(folded):
            number = _number(found.group("number"))
            source = _CONVERSION_UNITS.get(found.group("source"))
            target = _CONVERSION_UNITS.get(found.group("target"))
            if number is None or source is None or target is None or source[1] != target[1] or source == target:
                continue
            value = number * source[0] / target[0]
            said = f"{found.group('number')} {found.group('source')}"
            return Conversion(f"{said} = {format_number(value, 3, language)} {found.group('target')}", value)
    return None


# ------------------------------------------------------------------ figures memory cannot vouch for (M88)

# M88 (DEV-D v3r D-s111 «¿Cuál es la distancia de Barcelona a París?», nothing pertinent read): the answer from memory
# (D35) said «1.080 km en línea recta … 1.100 por carretera … el tren tarda 10 horas y 30 minutos, el avión 2 horas y 15
# minutos» (about 830 km, 1 030 km and 6 h 30 in fact). A notice that it may not be exact does not make a figure given
# to three digits or to the quarter hour an approximation: memory keeps orders of magnitude, not digits. A figure of a
# memory answer is said round — two significant digits at most, a duration to the half hour — and what the person said
# is theirs. Judged: a figure followed by a unit or a percentage, preceded by a currency, or written with thousands.
_MEMORY_UNIT_WORDS = frozenset(
    set(_CONVERSION_UNITS)
    | {
        "%", "por", "percent", "grados", "degrees", "habitantes", "inhabitants", "personas", "people", "anos", "years",
        "tazas", "taza", "cups", "cup", "calorias", "calories", "kcal", "millones", "million", "millions", "mil",
        "thousand", "billones", "billion", "billions", "peso", "pesos", "dolar", "dolares", "dollar", "dollars",
        "euro", "euros", "soles", "reales",
    }
)
_MEMORY_FIGURE = re.compile(
    rf"(?P<sign>{_CURRENCY}\s?)?(?<![\w.,:/])(?P<number>\d{{1,3}}(?:[.,]\d{{3}})+(?![.,]?\d)|\d+(?:[.,]\d+)?)"
    r"(?![\w/]|[.,]\d|:\d)(?P<after>\s*(?:%|[a-z]+))?"
)
_HOURS_AND_MINUTES = re.compile(
    r"(?<![\w.,])(?P<hours>\d{1,3})\s*(?:h|hr|hrs|horas?|hours?)\b\s*(?:y|and|,)?\s*(?P<minutes>\d{1,2})"
    r"(?:\s*(?:min|mins|minutos?|minutes?)\b)?"
)
_LIST_ORDINAL = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def _significant_digits(raw: str) -> int:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        return len(re.sub(r"[.,]", "", raw).strip("0")) or 1
    if re.search(r"[.,]", raw):
        return len(re.sub(r"[.,]", "", raw).lstrip("0")) or 1
    return len(raw.strip("0")) or 1


def unsure_figures(reply: str, said: Iterable[str] = ()) -> list[str]:
    """The figures of an answer from memory given more precisely than memory holds (see above), as written (folded)."""

    folded = _LIST_ORDINAL.sub(lambda found: " " * len(found.group(0)), fold(reply))
    person = numbers_in(said)
    unsure: list[str] = []
    for found in _MEMORY_FIGURE.finditer(folded):
        raw = found.group("number")
        after = (found.group("after") or "").strip()
        separated = re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw) is not None
        if not (found.group("sign") or separated or after in _MEMORY_UNIT_WORDS):
            continue
        value = _money(raw) if separated else _number(raw)
        if value is None or value in person or _significant_digits(raw) <= 2:
            continue
        figure = found.group(0).strip()
        if figure not in unsure:
            unsure.append(figure)
    for found in _HOURS_AND_MINUTES.finditer(folded):
        if int(found.group("minutes")) % 30 and found.group(0).strip() not in unsure:
            unsure.append(found.group(0).strip())
    return unsure


# M92 (D52; DEV-D v3u D-s111 «…unos 1.100 kilómetros… unas 2 horas y media… entre 8 y 9 horas», D-p29-t2 «6. It (1982)»,
# D-w01-t3 «unas 600 cucharaditas»): said round, memory's figures were still wrong. An answer from memory in prose or as a
# list says no figure the person did not say: no quantity, distance, duration, date, year or count. A number that is
# part of a name («Apollo 11», «Scary Movie 3», «28 Days Later») is the name; a year never is.
_ANY_FIGURE = re.compile(
    r"(?<![\w.,/:-])(?P<number>\d{1,3}(?:[.,]\d{3})+(?![\w]|[.,]\d)|\d+(?:[.,]\d+)?(?![\w/]|[.,]\d))"
)
_WORDED_FIGURE = re.compile(
    r"\b(?:(?P<word>" + "|".join(sorted((w for w in _NUMBER_WORDS if _NUMBER_WORDS[w] > 1), key=len, reverse=True))
    + r")\s+(?P<unit>[a-z%]+)|(?:cientos|miles|millones|decenas|docenas|hundreds|thousands|millions|dozens)\s+(?:de|of)\b)"
)
_LISTED_YEAR = re.compile(r"[ \t]*\(\s*\d{4}(?:\s*[-–]\s*\d{2,4})?\s*\)", re.MULTILINE)


def _part_of_a_name(text: str, start: int, end: int, listed: bool) -> bool:
    """A number next to a capitalized word that does not open its sentence («Apollo 11», «28 Days Later»); an item of a
    list is a name even when its first word is that capitalized one."""

    before = re.search(r"([^\W\d_][\w'’-]*)[ \t]+$", text[:start])
    after = re.match(r"[ \t]+([^\W\d_][\w'’-]*)", text[end:])
    opens = before is not None and re.search(r"(?:\A|[.!?:\n])\s*$", text[:before.start(1)]) is not None
    return (before is not None and before.group(1)[:1].isupper() and (listed or not opens)) or (
        after is not None and after.group(1)[:1].isupper()
    )


def unsaid_figures(reply: str, said: Iterable[str] = ()) -> list[str]:
    """M92 (D52): the figures of an answer from memory that the person did not say (see above), as written."""

    original = str(reply or "")
    items = [
        (line.start(), line.end()) for line in re.finditer(r"(?m)^[ \t]*(?:\d+[.)]|[-•*])[ \t].*$", original)
    ]
    text = _LIST_ORDINAL.sub(lambda found: " " * len(found.group(0)), original)
    person = numbers_in(said)
    unsaid: list[str] = []
    for found in _ANY_FIGURE.finditer(text):
        raw = found.group("number")
        separated = re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw) is not None
        value = _money(raw) if separated else _number(raw)
        if value is None or value in person:
            continue
        year = re.fullmatch(r"1\d{3}|20\d{2}", raw) is not None
        listed = any(start <= found.start() < end for start, end in items)
        if not year and _part_of_a_name(text, found.start(), found.end(), listed):
            continue
        if raw not in unsaid:
            unsaid.append(raw)
    folded = fold(text)
    for found in _WORDED_FIGURE.finditer(folded):
        if found.group("word") and found.group("unit") not in _MEMORY_UNIT_WORDS:
            continue
        if found.group(0) not in unsaid:
            unsaid.append(found.group(0))
    return unsaid


def without_listed_years(reply: str) -> str:
    """M92 (D-p29-t2 «6. It (1982)»): the years a list from memory wrote in brackets after each name, dropped."""

    return _LISTED_YEAR.sub("", str(reply or ""))


# ------------------------------------------------------------------ a per-unit rule read, applied (M92)

# M92 (D52; DEV-D v3u D-w01-t3 «ya y pa 3 litros cuántas cucharaditas serían» over «La medida ideal de sal por litro de
# agua para pasta es de 10 gramos»): the three drafts computed 1,5, «entre 30 y 75» and 150 and were refused, and memory
# said «600 cucharaditas». A rule the read states per unit («10 g por litro», «por litro … es de 10 gramos») applied to
# the one quantity the request states of that unit's kind is BAXY's own calculation, like a price (M62). A spoon count
# is given only when the read states what that spoon weighs; otherwise the total stays in the rule's unit.
_RATE_NUMBER = r"\d+(?:[.,]\d+)?"
_RATE_UNIT = r"(?:" + _UNIT_WORD + r")"
_RATE_THEN_UNIT = re.compile(
    rf"(?<![\w.,/])(?P<number>{_RATE_NUMBER})\s*(?P<unit>{_RATE_UNIT})(?:\s+de\s+[a-z]+(?:\s+[a-z]+)?)?"
    rf"(?:\s*/\s*|\s+(?:por|per|each|a|al|every)\s+)(?:cada\s+)?(?:(?:un|una|1)\s+)?(?P<per>{_RATE_UNIT})(?![\w/])"
)
_UNIT_THEN_RATE = re.compile(
    rf"\b(?:por|per)\s+(?:cada\s+)?(?:(?:un|una|1)\s+)?(?P<per>{_RATE_UNIT})\b[^.;\n\d]{{0,60}}?"
    rf"\b(?:es|son|seria|serian|is|are|=|:)\s+(?:de\s+|of\s+)?(?:(?:unos|unas|about|around)\s+)?"
    rf"(?P<number>{_RATE_NUMBER})\s*(?P<unit>{_RATE_UNIT})(?![\w/])"
)
_SPOON_ASKED = re.compile(
    r"\b(?:cuant[oa]s|how\s+many|en|in)\s+(?P<spoon>cucharaditas?|cucharadas?|teaspoons?|tablespoons?|tsp|tbsp)\b"
)
_SPOON_KIND = {
    "cucharadita": "tsp", "cucharaditas": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp",
    "cucharada": "tbsp", "cucharadas": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp",
}
_SPOON_WEIGHT = (
    re.compile(
        r"\b(?:una|1|a|one)\s+(?P<spoon>cucharaditas?|cucharadas?|teaspoons?|tablespoons?|tsp|tbsp)\b[^.;\n\d]{0,40}?"
        rf"(?P<number>{_RATE_NUMBER})\s*(?P<unit>g|gr|gramos?|grams?)\b"
    ),
    re.compile(
        rf"(?<![\w.,/])(?P<number>{_RATE_NUMBER})\s*(?P<unit>g|gr|gramos?|grams?)\b[^.;\n\d]{{0,40}}?"
        r"\b(?:una|1|a|one)\s+(?P<spoon>cucharaditas?|cucharadas?|teaspoons?|tablespoons?|tsp|tbsp)\b"
    ),
)


@dataclass(frozen=True)
class RatedTotal:
    sentence: str  # «3 litros × 10 gramos por litro = 30 gramos»
    values: tuple[Fraction, ...]  # the total, and the spoons when the read gives what one weighs


def rated_totals(request: str, evidence: str, language: str = "es") -> list[RatedTotal]:
    """What the one quantity the request states comes to under each per-unit rule the evidence states (see above)."""

    stated = measures(request)
    folded = fold(evidence)
    spoon = _SPOON_ASKED.search(fold(request))
    weights = [
        (_number(found.group("number")), _UNITS[found.group("unit")][0])
        for pattern in _SPOON_WEIGHT for found in pattern.finditer(folded)
        if spoon is not None and _SPOON_KIND.get(found.group("spoon")) == _SPOON_KIND.get(spoon.group("spoon"))
        and found.group("unit") in _UNITS
    ]
    totals: list[RatedTotal] = []
    for pattern in (_RATE_THEN_UNIT, _UNIT_THEN_RATE):
        for found in pattern.finditer(folded):
            number = _number(found.group("number"))
            unit = _UNITS.get(found.group("unit"))
            per = _UNITS.get(found.group("per"))
            if number is None or number <= 0 or unit is None or per is None or unit[1] == per[1]:
                continue
            asked = [item for item in stated if item.dimension == per[1] and item.value > 0]
            if len(asked) != 1:
                continue
            total = asked[0].value / per[0] * number
            said_quantity = fold(request)[asked[0].start:asked[0].end]
            per_word = " por " if language == "es" else " per "
            sentence = (
                f"{said_quantity} × {found.group('number')} {found.group('unit')}{per_word}{found.group('per')} = "
                f"{format_number(total, 1, language)} {found.group('unit')}"
            )
            values: tuple[Fraction, ...] = (total,)
            weight = next((value * size for value, size in weights if value), None)
            if weight and unit[1] == _MASS and spoon is not None:
                spoons = total * unit[0] / weight
                sentence += f" = {format_number(spoons, 1, language)} {spoon.group('spoon')}"
                values += (spoons,)
            if all(sentence != other.sentence for other in totals):
                totals.append(RatedTotal(sentence, values))
    return totals


def gives_a_total(reply: str, totals: Iterable[RatedTotal]) -> bool:
    """The reply states one of the computed totals (to about a tenth)."""

    written = numbers_in([reply]) + [_money(raw) for raw in re.findall(r"\d{1,3}(?:\.\d{3})+", fold(reply))]
    return any(
        value is not None and abs(value - expected) <= max(abs(expected) / 10, Fraction(1, 10))
        for item in totals for expected in item.values for value in written
    )
