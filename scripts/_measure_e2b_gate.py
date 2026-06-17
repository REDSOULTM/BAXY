# -*- coding: utf-8 -*-
"""Mide el GATE del E2B (FG OFF): para cada query, ¿el E2B emite tool o abstiene?
Determina si el E2B sirve como gate de acción-vs-conversación para el split FG.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GEMMA4_FG_ROUTER"] = "0"   # FG OFF: medimos el E2B crudo
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")

import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
except Exception as e:
    print(f"[ABORT] E2B :8080 no responde ({type(e).__name__})."); sys.exit(2)

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402
agent = Gemma4Agent()

NOTOOL = ["gracias", "hola, cómo estás", "qué es pytest", "contame un chiste",
          "quién fue Einstein", "obrigado", "thanks a lot"]
ACCION = ["subí el volumen a 40", "qué hora es", "abrí la calculadora",
          "buscame el clima en internet", "guardá que me gusta el café",
          "set the volume to 30", "quelle heure est-il", "abra a calculadora"]


def emit(msg):
    t0 = time.time()
    try:
        res = agent.run_content(msg)
    except Exception as e:
        return f"ERR {type(e).__name__}: {e}", time.time() - t0
    tools = []
    if isinstance(res, dict):
        tools = res.get("tools_used") or res.get("tool_calls") or []
    else:
        te = getattr(res, "tool_events", None)
        if te:
            tools = [getattr(t, "name", str(t)) for t in te]
    return tools, time.time() - t0


print("=" * 64)
print("GATE E2B (FG OFF) — ¿emite tool o abstiene?")
print("=" * 64)
print("-- NO_TOOL (queremos [] = E2B abstiene):")
for q in NOTOOL:
    tools, dt = emit(q)
    flag = "OK   " if tools == [] else "EMITE"
    print(f"  [{flag}] {str(tools):40} ({dt:.1f}s)  {q!r}")
print("-- ACCION (queremos tool emitida):")
for q in ACCION:
    tools, dt = emit(q)
    flag = "OK   " if tools else "MISS "
    print(f"  [{flag}] {str(tools):40} ({dt:.1f}s)  {q!r}")
