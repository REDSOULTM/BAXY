# -*- coding: utf-8 -*-
"""Verifica (sin server) que _tool_schemas_hint se suprime con FG router ON.
Mide el tamaño del bloque de schemas en chars/≈tokens para un subset de acción."""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUBSET = ["audio", "system", "app", "web", "media"]  # subset típico de acción


def hint_len(fg_on: bool) -> int:
    os.environ["GEMMA4_FG_ROUTER"] = "1" if fg_on else "0"
    os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")  # ctx 12288 -> compact hint
    os.environ.setdefault("GEMMA4_DIAG", "1")
    for m in list(sys.modules):
        if m.startswith("gemma4_agent.agent_core.agent"):
            del sys.modules[m]
    mod = importlib.import_module("gemma4_agent.agent_core.agent")
    a = mod.Gemma4Agent()
    s = a._tool_schemas_hint(selected_tool_names=SUBSET)
    return len(s)


off = hint_len(False)
on = hint_len(True)
print(f"_tool_schemas_hint (subset accion, ctx 12288):")
print(f"  FG OFF: {off} chars (~{off // 4} tokens)  <- schemas en el prompt")
print(f"  FG ON : {on} chars  <- suprimido por el split (FunctionGemma hace tools)")
print("LEVER OK" if on == 0 and off > 0 else "REVISAR")
