# -*- coding: utf-8 -*-
"""Verifica el fix del reintento-enfocado por el camino REAL fg_emit (gates + subset +
_ask con reintento + to_baxy). 'abre Steam' debe llegar con target; el resto sin regresión."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_ENCODER_ONNX"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ["GEMMA4_FG_AUTOBOOT"] = "1"

from gemma4_agent.routing import fg_router as fg  # noqa: E402

fg.ensure_fg_server()

# query -> (familia esperada, arg que debería venir lleno)
CASES = [
    ("abre Steam", "app", "name"),
    ("open Steam", "app", "name"),
    ("abrí Spotify", "app", "name"),
    ("abre la calculadora", "app", "name"),
    ("subí el volumen a 40", "audio", "level"),
    ("mandale 'hola' a Ana por whatsapp", None, None),
    ("poné música", None, None),
    ("qué hora es", None, None),
]
for q, fam, arg in CASES:
    name, args = fg.fg_emit(q, e2b_emitted=False)
    has = bool(args) and (arg is None or arg in (args or {}))
    flag = "OK " if (name and name != "no_tool" and (arg is None or has)) else ("no_tool" if name == "no_tool" else "MISS-ARG")
    print(f"  [{flag:8s}] {q!r:42s} -> {name} {args}")
