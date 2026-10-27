"""Arithmetic computed rather than recalled: the model writes the expression, this evaluates it.

The 4B model did sums from memory and got them wrong (12 for «dos más dos» once the recognizer wrote «do»), and could
not take the square root of an 18-digit number. The model understands the request and passes the expression as a
typed tool argument, digits and symbols only; evaluate() returns the result as data and the model writes the words.
No eval: a recursive-descent parser over tokens, decimal.Decimal at 50 digits, exponents and magnitudes bounded so
nothing hangs. A failure is a ValueError whose short reason the model reads.
"""
from __future__ import annotations

import re
from decimal import Context, Decimal, Inexact, InvalidOperation, Overflow, getcontext, localcontext

_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|\*\*|[^\W\d_]+|\S")
_ALIASES = {"×": "*", "÷": "/", "**": "^", "√": "sqrt", "∛": "cbrt"}
_MAX_EXPONENT = 10000


def _not_arithmetic(part: str) -> ValueError:
    return ValueError(f"not an arithmetic expression: {part}")


class _Parser:
    """expression: term (+ -) | term: unary (* /) | unary: (- +) unary | power
    power: postfix [^ unary] | postfix: primary %* | primary: number | ( expression ) | (sqrt cbrt) primary.
    So -2 ^ 2 is -4, 2 ^ 3 ^ 2 is 2 ^ 9 and 15% is 0.15."""

    def __init__(self, expression: str) -> None:
        self.expression = expression
        self.tokens = [_ALIASES.get(token, token.lower()) for token in _TOKEN.findall(expression)]
        self.pos = 0

    def _take(self, *options: str) -> str | None:
        token = self.tokens[self.pos] if self.pos < len(self.tokens) else None
        if token in options:
            self.pos += 1
            return token
        return None

    def _unexpected(self) -> ValueError:
        return _not_arithmetic(self.tokens[self.pos] if self.pos < len(self.tokens) else self.expression.strip())

    def parse(self) -> Decimal:
        value = self._expression()
        if self.pos < len(self.tokens):
            raise self._unexpected()
        return value

    def _expression(self) -> Decimal:
        value = self._term()
        while op := self._take("+", "-"):
            right = self._term()
            value = value + right if op == "+" else value - right
        return value

    def _term(self) -> Decimal:
        value = self._unary()
        while op := self._take("*", "/"):
            right = self._unary()
            if op == "/" and right == 0:
                raise ValueError("division by zero")
            value = value * right if op == "*" else value / right
        return value

    def _unary(self) -> Decimal:
        if op := self._take("-", "+"):
            value = self._unary()
            return value.copy_negate() if op == "-" else value
        return self._power()

    def _power(self) -> Decimal:
        base = self._postfix()
        if not self._take("^"):
            return base
        exponent = self._unary()
        if abs(exponent) > _MAX_EXPONENT:
            raise ValueError("number too large")
        if base == 0 and exponent < 0:
            raise ValueError("division by zero")
        return base ** exponent

    def _postfix(self) -> Decimal:
        value = self._primary()
        while self._take("%"):
            value = value / 100
        return value

    def _primary(self) -> Decimal:
        if self._take("("):
            value = self._expression()
            if not self._take(")"):
                raise self._unexpected()
            return value
        if function := self._take("sqrt", "cbrt"):
            argument = self._primary()
            if function == "sqrt":
                if argument < 0:
                    raise ValueError("square root of a negative number")
                return argument.sqrt()
            return _cube_root(argument)
        token = self.tokens[self.pos] if self.pos < len(self.tokens) else ""
        if not token[:1].isdecimal():
            raise self._unexpected()
        if token.count(".") + token.count(",") > 1:  # no thousands separators: «1,000.5» is ambiguous
            raise _not_arithmetic(token)
        self.pos += 1
        return Decimal(token.replace(",", "."))


def _cube_root(value: Decimal) -> Decimal:
    magnitude = value.copy_abs()
    with localcontext():  # its rounding flags stay here: an exact cube's root is exact
        root = magnitude ** (Decimal(1) / 3)
        whole = root.to_integral_value()
        exact = whole ** 3 == magnitude
    if exact:
        root = whole
    else:
        getcontext().flags[Inexact] = True
    return root.copy_sign(value)


def _plain(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def evaluate(expression: str) -> str:
    """The value of an arithmetic expression written with digits and symbols: «≈ » marks a rounded result."""
    with localcontext(Context(prec=50, Emax=10 ** 6, Emin=-10 ** 6)) as context:
        try:
            value = _Parser(expression).parse()
        except Overflow:
            raise ValueError("number too large") from None
        except InvalidOperation:
            raise ValueError("undefined result") from None  # 0 ^ 0, a negative number to a fractional power
        if value == 0:
            return "0"
        approximate = "≈ " if context.flags[Inexact] else ""
        if value == value.to_integral_value() and value.adjusted() < 30:
            return approximate + str(int(value))
        if value.adjusted() >= 30 or value.adjusted() < -6:
            mantissa, power = f"{value:.6e}".split("e")
            return f"≈ {_plain(Decimal(mantissa))}e{power}"
        rounded = value.quantize(Decimal("0.000001"))  # the context rounds half to even
        return ("≈ " if approximate or rounded != value else "") + _plain(rounded)
