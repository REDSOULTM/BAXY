# -*- coding: utf-8 -*-
"""Validación EN VIVO (regla #3.5) de FunctionGemma run9 como router de tool-calling.

Corre contra el agente + LLM REALES con GEMMA4_FG_ROUTER=1 (FunctionGemma :8082
decide el tool-call) + GEMMA4_LEAN_TOOLS=0 (el router necesita las 67 familias para
tool_categories). Inyecta por agent.run_content (= la UI, seguro: NO usa SendInput).

Prueba la cadena REAL: query -> E2B (conversa) -> FunctionGemma (override de tool) ->
bridge a tool COMPUESTO -> ToolRegistry.execute -> reply. Un shim sobre fg_emit captura
exactamente qué decidió FunctionGemma por query (prueba que está en el loop, no el E2B).

Cubre: acción multi-idioma, no_tool (chitchat/agradecimiento/conocimiento), y el bridge
individual->compuesto. NO ejecuta nada físico irreversible.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# DEBE ir ANTES de importar el agente: el flag se lee a nivel módulo.
os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"   # router necesita 67 familias para tool_categories
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")

import urllib.request

for port, name in ((8080, "E2B"), (8082, "FunctionGemma")):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
    except Exception as e:
        print(f"[ABORT] server {name} no responde en :{port} ({type(e).__name__}).")
        sys.exit(2)

# Shim sobre fg_emit para capturar la decisión real de FunctionGemma por query.
from gemma4_agent.routing import fg_router as _fgmod  # noqa: E402

_FG_LOG: list = []
_orig_fg_emit = _fgmod.fg_emit


def _logged_fg_emit(query, **kw):
    t0 = time.time()
    out = _orig_fg_emit(query, **kw)
    _FG_LOG.append((query, out, (time.time() - t0) * 1000))
    return out


_fgmod.fg_emit = _logged_fg_emit
# El agente importa `from ..routing.fg_router import fg_emit` DENTRO del turno (lazy),
# así que toma el símbolo parcheado del módulo. Confirmamos abajo en el primer turno.

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402

agent = Gemma4Agent()


def run(msg: str) -> dict:
    _FG_LOG.clear()
    # Cada caso es independiente: reseteamos el historial para que la confabulación
    # cross-turno del E2B (un turno previo "abrí Spotify" contaminando "gracias") no
    # se confunda con un fallo del router. En uso real la conversación SÍ es coherente.
    try:
        agent.clear()
    except Exception:
        pass
    t0 = time.time()
    try:
        res = agent.run_content(msg)
    except Exception as e:
        import traceback
        return {"msg": msg, "error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc(), "dt": time.time() - t0}
    reply, tools = "", []
    if isinstance(res, dict):
        reply = res.get("reply") or res.get("text") or ""
        tools = res.get("tools_used") or res.get("tool_calls") or []
    else:
        reply = str(res)
    fg = list(_FG_LOG)
    return {"msg": msg, "reply": reply, "tools": tools, "fg": fg, "dt": time.time() - t0}


# (categoria, mensaje, qué esperamos de FunctionGemma)
CASES = [
    ("accion/es",   "subí el volumen a 40",          "FG: audio set_volume level=40"),
    ("accion/es",   "qué hora es",                    "FG: system time"),
    ("accion/es",   "abrí la calculadora",            "FG: app_open / launch"),
    ("accion/es",   "guardá que me gusta el café",    "FG: memory_save"),
    ("accion/es",   "buscá el clima en internet",     "FG: web_search"),
    ("accion/en",   "set the volume to 30",           "FG: audio set_volume level=30"),
    ("accion/en",   "what time is it",                "FG: system time"),
    ("accion/fr",   "quelle heure est-il",            "FG: system time"),
    ("accion/pt",   "abra a calculadora",             "FG: app_open"),
    ("no_tool",     "gracias",                        "FG: no_tool -> responde E2B"),
    ("no_tool",     "hola, cómo estás",               "FG: no_tool -> responde E2B"),
    ("no_tool",     "qué es pytest",                  "FG: no_tool (conocimiento) -> E2B"),
]

print("=" * 74)
print("VALIDACIÓN EN VIVO — FunctionGemma router (GEMMA4_FG_ROUTER=1, regla #3.5)")
print("=" * 74)
results = []
for cat, msg, crit in CASES:
    r = run(msg)
    results.append((cat, msg, crit, r))
    if r.get("error"):
        print(f"\n[{cat}] {msg!r}\n  ❌ ERROR: {r['error']}")
        continue
    reply = (r["reply"] or "").replace("\n", " ").strip()
    fg = r["fg"]
    fg_str = "; ".join(f"{out} ({ms:.0f}ms)" for _, out, ms in fg) if fg else "(FG no se invocó!)"
    print(f"\n[{cat}] {msg!r}  ({r['dt']:.1f}s)")
    print(f"  FG decidió : {fg_str}")
    print(f"  tools_used : {r['tools']}")
    print(f"  reply      : {reply[:150]}")
    print(f"  esperado   : {crit}")

print("\n" + "=" * 74)
errs = [r for *_, r in results if r.get("error")]
no_fg = [r for *_, r in results if not r.get("error") and not r.get("fg")]
print(f"RESUMEN: {len(results)} casos, {len(errs)} con excepción, {len(no_fg)} sin invocar FG.")
if errs:
    for *_, r in results:
        if r.get("error"):
            print(f"  EXC {r['msg']!r}: {r['error']}")
            print(r.get("tb", ""))
if no_fg:
    print("  ⚠ casos donde FG NO se invocó (el override no entró):")
    for *_, r in results:
        if not r.get("error") and not r.get("fg"):
            print(f"    - {r['msg']!r}")
