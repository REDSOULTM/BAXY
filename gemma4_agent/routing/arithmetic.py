"""Evaluador aritmético SEGURO (sin eval/exec — respeta R6). El 4B chico improvisa
aritmética y FALLA (MEDIDO en vivo 2026-05-31: "47 por 8" -> "58.5", es 376). Este
módulo parsea una pregunta aritmética en NL a una expresión y la computa con un WALK
del AST que SOLO permite números + operadores (+, -, *, /, //, %, **). Cualquier otra
cosa (nombres, llamadas) -> rechaza -> None.

Short-circuit determinista de ALTA PRECISIÓN: solo dispara si el texto, tras quitar el
prefijo de pregunta y convertir operadores NL a símbolos, reduce a una expresión
aritmética PURA (fullmatch de [dígitos/operadores/paréntesis]). Si no -> None -> el
turno sigue normal (NO es respuesta enlatada: es COMPUTAR, como una calculadora).

API:
  try_arithmetic(text)    -> str | None   (el resultado formateado, o None)
  arith_expr_for_calc(t)  -> str | None   (la EXPRESIÓN compacta a TIPEAR en la
                                           Calculadora, p.ej. '2+2'; None si no aplica)
"""
from __future__ import annotations

import ast
import operator
import re

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

# Prefijo de PREGUNTA aritmética (multi-idioma). "cuánto es / calculá / how much is…".
_QUESTION_PREFIX = (
    r"cu[áa]nto\s+(?:es|da|dan|son|sería|seria|vale|valen)|"
    r"calcul[áae]\w*|resolv[ée]\w*|dame\s+(?:el\s+resultado\s+de|cuanto\s+es)|"
    r"how\s+much\s+is|what(?:'s|\s+is)|whats|qu[ée]\s+(?:es|da)"
)

# Verbos de ACCIÓN aritmética / tipeo, para el caso "<verbo> <expr> en la calculadora"
# (arith_expr_for_calc). NO se usan en try_arithmetic (que es solo PREGUNTA).
_CALC_VERB_PREFIX = (
    r"sum[áa]\w*|suma|rest[áa]\w*|resta|multiplic[áa]\w*|multiplica|"
    r"divid[íie]\w*|divide|computa\w*|compute|hac[ée]\w*|haz|"
    r"add|subtract|multiply|solve|"
    r"escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|pon[ée]\w*|type|write|enter"
)

# Palabras-número es/en (0-20 + decenas). EXCLUYE cien/ciento/hundred a propósito:
# "15 por ciento" (porcentaje) NO debe volverse "15 * 100". El gate de aritmética-pura
# rechaza cualquier palabra sobrante, así que convertir números sueltos es seguro.
_NUMWORDS = {
    # español
    "cero": "0", "un": "1", "uno": "1", "una": "1", "dos": "2", "tres": "3",
    "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7", "ocho": "8",
    "nueve": "9", "diez": "10", "once": "11", "doce": "12", "trece": "13",
    "catorce": "14", "quince": "15", "dieciseis": "16", "dieciséis": "16",
    "diecisiete": "17", "dieciocho": "18", "diecinueve": "19", "veinte": "20",
    "treinta": "30", "cuarenta": "40", "cincuenta": "50", "sesenta": "60",
    "setenta": "70", "ochenta": "80", "noventa": "90",
    # inglés
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
}


def _ev(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _ev(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_ev(node.left), _ev(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_ev(node.operand))
    raise ValueError("no es aritmética pura")


def _words_to_digits(t: str) -> str:
    """Reemplaza palabras-número sueltas (dos->2, five->5). Las palabras que NO son
    número quedan intactas -> el gate de aritmética-pura las rechaza después."""
    return re.sub(r"[a-záéíóúü]+",
                  lambda m: _NUMWORDS.get(m.group(0), m.group(0)), t)


def _to_symbols(t: str) -> str | None:
    """Convierte operadores NL a símbolos y valida que sea aritmética PURA.
    Devuelve la expresión normalizada ('2 + 2') o None si no es aritmética."""
    t = t.strip(" ?¿.!¡:")
    # MÚLTIPLOS/FRACCIONES en lenguaje natural ANTES de words_to_digits (si no,
    # "un cuarto" -> "1 cuarto" y el patrón no matchea) y ANTES de los operadores
    # (2026-06-10: "el doble de 8"/"la mitad de 10"/"raíz de 16" caían a None -> el
    # 4B respondía mal o "no pude"). "el/la X de N" -> N <op> k. Multilingüe es/en.
    # El número puede ser dígito o palabra (\w por _words_to_digits posterior); acá
    # aceptamos dígitos (lo común tras ASR) y el gate de pureza valida el resultado.
    t = re.sub(r"\b(?:el\s+)?doble\s+de\s+(\d+(?:\.\d+)?)", r"\1 * 2", t)
    t = re.sub(r"\b(?:el\s+)?triple\s+de\s+(\d+(?:\.\d+)?)", r"\1 * 3", t)
    t = re.sub(r"\b(?:el\s+)?cu[áa]druple\s+de\s+(\d+(?:\.\d+)?)", r"\1 * 4", t)
    t = re.sub(r"\b(?:la\s+)?mitad\s+de\s+(\d+(?:\.\d+)?)", r"\1 / 2", t)
    t = re.sub(r"\b(?:un\s+)?tercio\s+de\s+(\d+(?:\.\d+)?)", r"\1 / 3", t)
    t = re.sub(r"\b(?:un\s+)?cuarto\s+de\s+(\d+(?:\.\d+)?)", r"\1 / 4", t)
    t = re.sub(r"\bdouble\s+(?:of\s+)?(\d+(?:\.\d+)?)", r"\1 * 2", t)
    t = re.sub(r"\bhalf\s+(?:of\s+)?(\d+(?:\.\d+)?)", r"\1 / 2", t)
    # RAÍZ cuadrada: "raíz (cuadrada) de N" / "square root of N" -> N ** 0.5
    t = re.sub(r"\b(?:la\s+)?ra[íi]z(?:\s+cuadrada)?\s+de\s+(\d+(?:\.\d+)?)",
               r"\1 ** 0.5", t)
    t = re.sub(r"\bsquare\s+root\s+of\s+(\d+(?:\.\d+)?)", r"\1 ** 0.5", t)
    t = _words_to_digits(t)
    # potencias ANTES de la multiplicación
    t = re.sub(r"\bal\s+cuadrado\b", " ** 2", t)
    t = re.sub(r"\bal\s+cubo\b", " ** 3", t)
    t = re.sub(r"\b(?:elevado\s+a(?:\s+la\s+potencia\s+de)?|a\s+la\s+potencia\s+de|"
               r"to\s+the\s+power\s+of)\b", " ** ", t)
    # DIVISIÓN antes que MULTIPLICACIÓN: si no, el 'por' de "dividido POR" lo agarra
    # la multiplicación como '*' y queda "dividido" suelto -> None (MEDIDO).
    t = re.sub(r"\b(?:dividid[oa]\s+por|dividid[oa]|entre|sobre|divided\s+by)\b", " / ", t)
    t = re.sub(r"\b(?:multiplicad[oa]\s+por|por|times|multiplied\s+by)\b", " * ", t)
    t = re.sub(r"\b(?:m[áa]s|sumad[oa](?:\s+(?:a|con))?|plus)\b", " + ", t)
    t = re.sub(r"\b(?:menos|restad[oa](?:\s+(?:a|de))?|minus)\b", " - ", t)
    t = (t.replace("×", " * ").replace("·", " * ").replace("÷", " / ")
          .replace("^", " ** ").replace("%", " % "))
    # coma decimal -> punto SOLO entre dígitos
    t = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ".", t)
    # GATE: debe quedar PURO (números/operadores/paréntesis/espacios) + tener un
    # número Y un operador. Si no, NO es aritmética -> None (turno sigue normal).
    if not re.fullmatch(r"[\d\.\s\+\-\*/%\(\)]+", t):
        return None
    if not re.search(r"\d", t) or not re.search(r"[\+\-\*/%]\s*\d", t):
        return None
    return t


def _format(val) -> str | None:
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return None
    if isinstance(val, float):
        if val.is_integer():
            val = int(val)
        else:
            val = round(val, 6)
    return str(val)


def try_arithmetic(text: str) -> str | None:
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    # quitar prefijo de PREGUNTA (multi-idioma)
    t = re.sub(r"^\s*(?:" + _QUESTION_PREFIX + r")\s+", "", t)
    expr = _to_symbols(t)
    if expr is None:
        return None
    try:
        val = _ev(ast.parse(expr, mode="eval"))
    except Exception:
        return None
    return _format(val)


def arith_expr_for_calc(text: str) -> str | None:
    """Para "suma 2+2", "2 más 2", "escribí 5 por 3", "dos más dos": devuelve la
    EXPRESIÓN COMPACTA a TIPEAR en la Calculadora ('2+2', '5*3'). None si el texto no
    reduce a aritmética pura. Quita verbos de acción aritmética/tipeo + prefijos de
    pregunta, normaliza NL->símbolos y compacta (sin espacios)."""
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    t = re.sub(r"^\s*gemma[,\s]+", "", t)
    t = re.sub(r"^\s*(?:" + _QUESTION_PREFIX + r"|" + _CALC_VERB_PREFIX + r")\s+", "", t)
    expr = _to_symbols(t)
    if expr is None:
        return None
    return expr.replace(" ", "")
