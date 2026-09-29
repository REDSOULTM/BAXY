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
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .normalize import fold

__all__ = ["Measure", "measures", "evaluate", "derived_facts", "underived_figure", "numbers_in", "format_number"]

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
