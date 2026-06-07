"""Anti-regresión del detector _is_local_state_question (BUG B).

DEBE ser True solo para PREGUNTAS de estado local del SO. NO debe matchear:
acciones (cerrá/abrí ventana), smalltalk, ni preguntas del mundo (web).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.routing.planner import _is_local_state_question as q

POSITIVES = [
    "¿qué juego estoy jugando?",
    "Que juego estoy jugando?",
    "qué aplicación está abierta",
    "what game am I playing",
    "qué ventana está activa",
    "cuál es la app en foco",
    "che gioco sto giocando?",
    "what app is open right now",
]
NEGATIVES = [
    # acciones, NO preguntas -> NO matchear (siguen su ruta normal)
    "cerrá la ventana",
    "abrí el juego",
    "minimizá la aplicación",
    "abrí Steam",
    # smalltalk / charla -> session
    "hola qué tal",
    "gracias",
    "contame un chiste",
    # preguntas del MUNDO (web/knowledge), no estado local
    "qué juegos salieron este año",
    "cuál es el mejor juego de 2026",
    "qué app me recomendás para editar fotos",
    "qué hora es",
]

print("=== POSITIVOS (deben ser True) ===")
okp = 0
for t in POSITIVES:
    r = q(t)
    okp += r
    print(f"  [{'OK' if r else 'XX'}] {t!r}")
print(f"  -> {okp}/{len(POSITIVES)}")

print("\n=== NEGATIVOS (deben ser False) ===")
okn = 0
for t in NEGATIVES:
    r = q(t)
    okn += (not r)
    print(f"  [{'OK' if not r else 'XX FALSO+'}] {t!r}")
print(f"  -> {okn}/{len(NEGATIVES)}")

print("\nVEREDICTO:", "PASS" if okp == len(POSITIVES) and okn == len(NEGATIVES)
      else f"REVISAR (pos {okp}/{len(POSITIVES)}, neg {okn}/{len(NEGATIVES)})")
