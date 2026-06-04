"""MIDE el leakage del fix nav_action-asíndeton ANTES de aplicarlo.

El verificador Opus advirtió: aceptar comas (asíndeton) en _AA_NAV_ACTION para
capturar "abre notepad, escribe hola, ciérralo" -> computer_use, TAMBIÉN capturaría
operaciones de FILESYSTEM ("abre la carpeta documentos, borra el archivo viejo")
que NO deben ir a cu. Si el leakage es real, DESCARTAR el fix.

Este script simula el regex asíndeton candidato y mide:
- POSITIVOS (deben ir a cu): cadenas in-app multi-paso con comas.
- LEAKAGE (NO deben ir a cu): operaciones de carpeta/archivo con comas.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gemma4_agent.routing.command_splitter import _AA_NAV, _AA_ACT_NAV, _AA_PREP

# Candidato: igual que _AA_NAV_ACTION pero el conector puede ser COMA o "y".
_CAND = re.compile(
    r"\b(?:" + _AA_NAV + r")\b\s+(?:" + _AA_PREP + r")?\s*\S+.*?"
    r"\s*[,]\s*(?:luego\s+|despu[ée]s\s+|then\s+)?"
    r"(?:" + _AA_ACT_NAV + r")\b", re.IGNORECASE)

POS = [  # cadenas in-app multi-paso (deberían ir a cu)
    "abre notepad, escribe hola",
    "abre notepad, escribe hola, ciérralo",
    "open notepad, type hello, close it",
    "abrí la calculadora, escribí 2+2",
]
LEAK = [  # operaciones de FILESYSTEM/carpeta (NO deben ir a cu)
    "abre la carpeta documentos, borra el archivo viejo",
    "abrí la carpeta descargas, eliminá los temporales",
    "abre la carpeta de fotos, seleccioná las de ayer",
    "andá a la carpeta proyectos, borrá los logs",
]

print("=== POSITIVOS (cadenas in-app -> cu) ===")
for t in POS:
    print(f"  [{'cu' if _CAND.search(t) else '--'}] {t!r}")
print("\n=== LEAKAGE (filesystem -> NO debe ir a cu) ===")
leak = 0
for t in LEAK:
    m = bool(_CAND.search(t)); leak += m
    print(f"  [{'LEAK!' if m else 'ok'}] {t!r}")
print(f"\n  leakage filesystem->cu: {leak}/{len(LEAK)}")
print("VEREDICTO:", "DESCARTAR (hay leakage)" if leak else "el regex asíndeton NO filtra filesystem aquí")
