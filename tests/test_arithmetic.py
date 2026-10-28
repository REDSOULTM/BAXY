"""baxy_mind.arithmetic: the expression the model writes, evaluated exactly rather than recalled. The 4B model said 12
for «do más dos» and could not take the square root of an 18-digit number; a reason it can read when it is no sum."""
import time

import pytest

from baxy_mind.arithmetic import evaluate


def test_exact_sums_and_products_are_exact_integers() -> None:
    assert evaluate("2 + 2") == "4"
    assert evaluate("345 * 2") == "690"
    assert evaluate("25 × 4 - 10 ÷ 2") == "95"
    assert evaluate("2.5 * 2") == "5"
    assert evaluate("123456789012 * 1000000") == "123456789012000000"


def test_precedence_and_parentheses() -> None:
    assert evaluate("2 + 3 * 4") == "14"
    assert evaluate("(2 + 3) * 4") == "20"
    assert evaluate("10 - 4 - 3") == "3"
    assert evaluate("100 / 10 / 5") == "2"


def test_unary_minus() -> None:
    assert evaluate("-5 + 2") == "-3"
    assert evaluate("2 - -3") == "5"
    assert evaluate("-(2 + 3)") == "-5"
    assert evaluate("-2 ^ 2") == "-4"
    assert evaluate("(-2) ^ 2") == "4"
    assert evaluate("1 / -2") == "-0.5"


def test_power_is_right_associative() -> None:
    assert evaluate("2 ^ 10") == "1024"
    assert evaluate("2 ** 10") == "1024"
    assert evaluate("2 ^ 3 ^ 2") == "512"
    assert evaluate("2 ^ -1") == "0.5"
    assert evaluate("2 ^ 100") == "≈ 1.267651e+30"  # 31 digits: past an exact integer


def test_percent_is_a_hundredth() -> None:
    assert evaluate("15% * 200") == "30"
    assert evaluate("15 % * 200") == "30"
    assert evaluate("50%") == "0.5"


def test_square_root_of_an_eighteen_digit_number_is_rounded() -> None:
    value = evaluate("sqrt(567344565230966678)")
    assert value.startswith("≈ 753222785.92") and value == "≈ 753222785.921248"
    assert evaluate("√567344565230966678") == value
    assert evaluate("sqrt(16)") == "4"
    assert evaluate("sqrt(2)") == "≈ 1.414214"


def test_cube_root_of_an_exact_cube_is_exact() -> None:
    assert evaluate("cbrt(27)") == "3"
    assert evaluate("cbrt(-8)") == "-2"
    assert evaluate("∛1000000") == "100"
    assert evaluate("cbrt(2)") == "≈ 1.259921"


def test_decimals_with_point_or_comma() -> None:
    assert evaluate("2,5 + 0,25") == "2.75"
    assert evaluate("2.5 + 0.25") == "2.75"
    assert evaluate("0.1 + 0.2") == "0.3"
    assert evaluate("1 / 3") == "≈ 0.333333"
    assert evaluate("1 / 8") == "0.125"


def test_very_large_and_very_small_results_are_scientific() -> None:
    assert evaluate("10 ^ 40 * 1.2345678") == "≈ 1.234568e+40"
    assert evaluate("1 / 10 ^ 9") == "≈ 1e-9"
    assert evaluate("10 ^ 29") == "100000000000000000000000000000"


@pytest.mark.parametrize(("expression", "reason"), [
    ("5 / 0", "division by zero"),
    ("0 / 0", "division by zero"),
    ("0 ^ -1", "division by zero"),
    ("sqrt(-1)", "square root of a negative number"),
    ("dos más dos", "not an arithmetic expression: dos"),
    ("2 +", "not an arithmetic expression: 2 +"),
    ("import os", "not an arithmetic expression: import"),
    ("(2 + 3", "not an arithmetic expression: (2 + 3"),
    ("2 3", "not an arithmetic expression: 3"),
    ("1,000.5", "not an arithmetic expression: 1,000.5"),
    ("2 ^ 100000", "exponent too large"),
    ("10 ^ 10 ^ 10", "exponent too large"),
    ("(10 ^ 9000) ^ 9000", "number too large"),
    # silent-failure review 2026-10-27: none of these may end the turn, read as 0 or read a thousand as a decimal
    ("(10 ^ -10000) ^ 101", "number too small"),
    ("(" * 300 + "1" + ")" * 300, "expression nested too deep"),
    ("-" * 1000 + "1", "expression nested too deep"),
    ("sqrt " * 1000 + "4", "expression nested too deep"),
    ("2 ^ " * 1000 + "1", "expression nested too deep"),
    ("1.000", "ambiguous separator in 1.000: write a thousand as 1000 and a decimal as 1.5 or 2.3750"),
    ("2,500 * 3", "ambiguous separator in 2,500: write a thousand as 1000 and a decimal as 1.5 or 2.3750"),
    ("", "no expression"),
], ids=lambda text: text[:24])
def test_what_is_no_sum_raises_a_reason(expression: str, reason: str) -> None:
    with pytest.raises(ValueError) as raised:
        evaluate(expression)
    assert str(raised.value) == reason


def test_huge_exponents_fail_quickly() -> None:
    started = time.perf_counter()
    for expression in ("9 ^ 9 ^ 9", "2 ^ 100000", "(10 ^ 9000) ^ 9000"):
        with pytest.raises(ValueError):
            evaluate(expression)
    assert evaluate("2 ^ 10000") == "≈ 1.995063e+3010"
    assert time.perf_counter() - started < 1


def test_logarithms_in_base_ten_and_natural() -> None:
    # noche 2026-10-28 (P2.25): log10(0.00042) answered from memory as -4.376; its value is -3.3768
    assert evaluate("log10(0.00042)") == "≈ -3.376751"
    assert evaluate("log10(1000)") == "3"
    assert evaluate("ln(5)") == "≈ 1.609438"
    assert evaluate("ln(1)") == "0"
    with pytest.raises(ValueError, match="logarithm of a number that is not positive"):
        evaluate("log10(0)")
    with pytest.raises(ValueError, match="logarithm of a number that is not positive"):
        evaluate("ln(-2)")


def test_three_decimals_that_cannot_be_a_thousand_are_decimals() -> None:
    # noche 2026-10-28 (P2.25 review): «0.125» and «log10(0.001)» read as an ambiguous thousands separator
    assert evaluate("0.125 * 8") == "1"
    assert evaluate("log10(0.001)") == "-3"
    assert evaluate("1234.567 * 1000") == "1234567"
    with pytest.raises(ValueError, match="2.3750"):
        evaluate("2.375 * 2")
