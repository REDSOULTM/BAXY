"""Mide BUG B (turnos 13/14): "¿qué juego estoy jugando?" -> router ofrece solo
[session] -> el 4B elige session.cancel_turn.

Reproduce qué tools ofrece el router (select_tool_names) para la pregunta de
ESTADO LOCAL en varios fraseos (mayúscula/?/wake-leak). La tool correcta es
`window` (action=active -> GetForegroundWindow). El bug: el abstain_head trata la
pregunta como charla y el fallback devuelve ["session"].

Uso: python scripts/_diag/_diag_bugB_router_gamestate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.routing.planner import plan_mission, select_tool_names

CASES = [
    "Bixby, ¿qué juego estoy jugando?",   # log turno 13 (wake leak + acento + ?)
    "Max ¿qué juego estoy jugando?",      # log turno 14
    "¿qué juego estoy jugando?",          # limpio con signos
    "Que juego estoy jugando?",           # May + ? sin ¿
    "que juego estoy jugando",            # minús sin signos
    "qué aplicación está abierta",        # variante app en foco
    "what game am I playing",             # inglés
    "qué ventana está activa",            # variante directa window
]

print("=== Tools ofrecidas por el router (window=correcta) ===")
for text in CASES:
    try:
        names = select_tool_names(text, plan_mission(text))
    except Exception as exc:
        names = f"ERROR {type(exc).__name__}: {exc}"
    has_window = isinstance(names, list) and "window" in names
    only_session = names == ["session"]
    mark = "WINDOW✓" if has_window else ("SOLO-SESSION✗" if only_session else "sin-window")
    print(f"  [{mark:14}] {text!r}\n        -> {names}")
