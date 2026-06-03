# -*- coding: utf-8 -*-
"""Validación EN VIVO (regla #3.5) del ctx 12288: corre turnos reales por
run_content (seguro, sin SendInput) con el server ya booteado en vram4=12288.
Confirma que (a) el agente responde sin exceed_context_size, (b) el tool-calling
sigue funcionando (comandos crispos rutean a su tool), (c) el modo compact sigue
activo (ctx 12288 >= umbral 12288)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
except Exception as e:
    print(f"[ABORT] server no responde ({type(e).__name__})")
    sys.exit(2)

from gemma4_agent.infra.config import AgentConfig  # noqa: E402
print("config.context_size (compaction) =", AgentConfig.from_env().context_size)

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402
agent = Gemma4Agent()

# Confirmar el modo de schemas que resuelve a este ctx.
try:
    hint = agent._tool_schemas_hint(selected_tool_names=["audio", "window", "app"])
    print(f"tool_schemas_hint a ctx 12288: {len(hint)} chars (>0 = compact ACTIVO, no OFF)")
except Exception as e:
    print(f"hint check falló: {e}")

CASES = [
    ("mutea", "audio"),
    ("abre steam", "steam"),
    ("subí el volumen al 50", "audio"),
    ("que es pytest", None),  # pregunta: no acción espuria
]

print("=" * 60)
print("VALIDACIÓN EN VIVO — ctx 12288 (turnos reales)")
print("=" * 60)
fails = 0
for msg, expect_tool in CASES:
    try:
        res = agent.run_content(msg)
    except Exception as e:
        print(f"\n[{msg!r}] ❌ EXCEPCIÓN: {type(e).__name__}: {e}")
        if "context" in str(e).lower() or "exceed" in str(e).lower():
            print("   ↑ ESTO sería el exceed_context_size que tememos")
        fails += 1
        continue
    reply = getattr(res, "content", str(res)) if not isinstance(res, dict) else (res.get("reply") or "")
    tools = [getattr(t, "name", "?") for t in getattr(res, "tool_events", []) or []]
    print(f"\n[{msg!r}]")
    print(f"  tools: {tools}")
    print(f"  reply: {reply[:120]}")
    if expect_tool and expect_tool not in tools:
        print(f"  ⚠ esperaba tool {expect_tool} (no determinista, revisar)")

print("\n" + "=" * 60)
print(f"RESUMEN: {len(CASES)} turnos, {fails} excepciones (0 = sin exceed_context).")
print("Si 0 excepciones y los comandos ejecutan → ctx 12288 funciona en vivo.")
