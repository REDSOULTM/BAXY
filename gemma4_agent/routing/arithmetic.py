"""Evaluador aritmético SEGURO (sin eval/exec — respeta R6). El 4B chico improvisa
aritmética y FALLA (MEDIDO en vivo 2026-05-31: "47 por 8" -> "58.5", es 376). Este
módulo parsea una pregunta aritmética en NL a una expresión y la computa con un WALK
del AST que SOLO permite números + operadores (+, -, *, /, //, %, **). Cualquier otra
cosa (nombres, llamadas) -> rechaza -> None.

Short-circuit determinista de ALTA PRECISIÓN: solo dispara si el texto, tras quitar el
prefijo de pregunta y convertir operadores NL a símbolos, reduce a una expresión
aritmética PURA (fullmatch de [dígitos/operadores/paréntesis]). Si no -> None -> el
turno sigue normal (NO es respuesta enlatada: es COMPUTAR, como una calculadora).

API: try_arithmetic(text) -> str | None  (el resultado formateado, o None).
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


def try_arithmetic(text: str) -> str | None:
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    # 1) quitar prefijo de pregunta (multi-idioma)
    t = re.sub(
        r"^\s*(?:cu[áa]nto\s+(?:es|da|dan|son|sería|seria|vale|valen)|"
        r"calcul[áae]\w*|resolv[ée]\w*|dame\s+(?:el\s+resultado\s+de|cuanto\s+es)|"
        r"how\s+much\s+is|what(?:'s|\s+is)|whats|qu[ée]\s+(?:es|da))\s+",
        "", t)
    t = t.strip(" ?¿.!¡:")
    # 2) operadores NL -> símbolos (potencias ANTES de la multiplicación)
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
    # 3) GATE: debe quedar PURO (números/operadores/paréntesis/espacios) + tener un
    #    número Y un operador. Si no, NO es aritmética -> None (turno sigue normal).
    if not re.fullmatch(r"[\d\.\s\+\-\*/%\(\)]+", t):
        return None
    if not re.search(r"\d", t) or not re.search(r"[\+\-\*/%]\s*\d", t):
        return None
    try:
        val = _ev(ast.parse(t, mode="eval"))
    except Exception:
        return None
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return None
    if isinstance(val, float):
        if val.is_integer():
            val = int(val)
        else:
            val = round(val, 6)
    return str(val)
