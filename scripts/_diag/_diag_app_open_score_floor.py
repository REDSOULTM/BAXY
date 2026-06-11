"""Distribución de scores del top-match de app.open: legítimos vs basura.

Para elegir el PISO de apertura con datos (no intuición): app_open abre
matches[0] con cualquier score>0 — medido en vivo que "abre jitomatador por
favor" abrió una app aleatoria. El piso debe separar:
  - LEGÍTIMOS: nombres exactos, alias builtin localizados (via canonical_query),
    typos de voz/tipeo (primera letra conservada), multi-palabra.
  - BASURA: nombres inexistentes que el fuzzy igual matchea contra ALGO.

Imprime query -> top match + score efectivo (misma semántica del ranking).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.tools_pkg.app_resolver import AppResolver

apps = AppResolver()
apps.find("notepad", limit=1)  # warm de fuentes

LEGIT = [
    # exactos / casi-exactos
    "notepad", "chrome", "steam", "spotify", "discord", "paint", "cmd",
    "explorador de archivos", "whatsapp", "word", "excel",
    # alias builtin localizados (canonical_query los traduce)
    "calculadora", "bloc de notas", "la calculadora", "el bloc de notas",
    "calculatrice", "rechner", "blocco note",
    # typos (primera letra conservada — el contrato del fuzzy)
    "calculadra", "spotfy", "chrme", "notepd", "discrod", "stema",
    "wathsapp", "calcladora",
    # multi-palabra reales
    "google chrome", "visual studio code", "epic games",
]
GARBAGE = [
    "jitomatador", "flurbomatic", "zanguango", "morktul", "el bicho raro",
    "asdfghjkl", "praxomatic 3000", "wexicobula", "tarambolo",
    "fistro pecador", "lampiño veloz", "gorgonzilla",
]


def show(label, queries):
    print(f"== {label} ==", flush=True)
    scores = []
    for q in queries:
        matches = apps.find(q, deep_fallback=False)
        if not matches:
            print(f"  {q!r:28} -> (sin match)", flush=True)
            continue
        s = apps.top_match_score(q, matches[0])
        scores.append((s, q, matches[0].name))
        print(f"  {q!r:28} -> {s:3}  {matches[0].name!r} [{matches[0].source}]", flush=True)
    return scores


legit = show("LEGÍTIMOS", LEGIT)
garbage = show("BASURA", GARBAGE)

print("=" * 72, flush=True)
if legit:
    lmin = min(legit)
    print(f"legítimo MÍNIMO : {lmin[0]:3}  ({lmin[1]!r} -> {lmin[2]!r})", flush=True)
if garbage:
    gmax = max(garbage)
    print(f"basura MÁXIMO   : {gmax[0]:3}  ({gmax[1]!r} -> {gmax[2]!r})", flush=True)
print("piso candidato: > max(basura) y <= min(legítimo)", flush=True)
