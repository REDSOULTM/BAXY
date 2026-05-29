"""Calibra el trigger-inject de skills: similitud (embedding) entre pedidos reales
y la description de cada skill. Decide umbral/margen para inyectar la receta de la
skill correcta sin falsos positivos. Sin LLM (solo embeddings, CPU)."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from gemma4_agent.tools_pkg.skills_registry import scan_skills
from gemma4_agent.routing.semantic_router import embed as _embed

skills = [s for s in scan_skills() if s.priority != "critical"]
print(f"skills non-critical: {[s.name for s in skills]}")

# Pedidos que DEBERÍAN matchear una skill + pedidos que NO (control: charla / acción simple)
CASES = [
    ("investigá en internet qué es Rust y resumime con fuentes", "research-and-summarize"),
    ("quiero instalar un juego de Steam paso a paso", "install-steam-game"),
    ("hacé una limpieza segura de archivos viejos en Descargas", "safe-file-cleanup"),
    ("sacá una captura y analizá qué hay", "screenshot-and-analyze"),
    ("una app me crashea, diagnosticá por qué", "debug-app-crash"),
    ("programá una tarea recurrente cada día a las 9", "schedule-recurring-task"),
    # CONTROLES (no deben matchear ninguna skill fuerte):
    ("qué hora es", None),
    ("subí el volumen", None),
    ("hola cómo estás", None),
]

# Pre-embed descriptions (normalizadas)
def _emb(t):
    v = _embed(t)
    v = np.asarray(v, dtype="float32")
    n = np.linalg.norm(v)
    return v / n if n else v

desc_emb = {s.name: _emb(s.description) for s in skills}

print("\n=== similitud pedido vs description de cada skill ===")
for text, expected in CASES:
    q = _emb(text)
    sims = sorted(((float(q @ desc_emb[s.name]), s.name) for s in skills), reverse=True)
    top_sim, top_name = sims[0]
    second = sims[1][0] if len(sims) > 1 else 0.0
    ok = (expected is None) or (top_name == expected)
    mark = "OK " if ok else "MISS"
    ctrl = " (control)" if expected is None else ""
    print(f"[{mark}] {text[:48]!r}{ctrl}")
    print(f"     top: {top_name} sim={top_sim:.3f} | 2do sim={second:.3f} | margen={top_sim-second:.3f} | esperado={expected}")
