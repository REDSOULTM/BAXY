# -*- coding: utf-8 -*-
"""Desglosa el system prompt del modelo que habla (QAT) bajo FG, por sección, para ver
DÓNDE están los ~5.3k tokens si los schemas ya no están. Sin server (solo arma el texto)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_ENCODER_ONNX"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")


def t(s):  # tokens aprox (Gemma ~4 chars/token en es/en mixto)
    return len(s) // 4


rows = []

from gemma4_agent.agent_core.agent_prompt import build_core_only, build_core_tool_rules_stable
core = build_core_only()
core_rules = build_core_tool_rules_stable()
rows.append(("core_only (identidad/honestidad/reglas)", core))
rows.append(("core_tool_rules_stable (15 tools SIEMPRE)", core_rules))

try:
    from gemma4_agent.tools_pkg.skills_registry import scan_skills, build_menu, build_critical_block
    sk = scan_skills()
    rows.append(("skills_menu", build_menu(sk)))
    rows.append(("skills_critical (bodies)", build_critical_block(sk)))
except Exception as e:
    print("skills:", e)

# memoria + microagents para un pedido típico
q = "abre Steam"
try:
    from gemma4_agent.agent_core.agent import Gemma4Agent
    a = Gemma4Agent()
    rows.append(("memory.prompt_summary_for(q)", a.memory.prompt_summary_for(q)))
except Exception as e:
    print("memory:", e)
try:
    from gemma4_agent.memory_pkg.microagents import build_microagents_section
    ma, _ = build_microagents_section(q, cached=None)
    rows.append(("microagents (match al pedido)", ma or ""))
except Exception as e:
    print("microagents:", e)

print(f"\n=== Desglose del system prompt (QAT bajo FG, pedido={q!r}) ===")
print(f"{'sección':45s} {'chars':>8s} {'~tok':>7s}")
print("-" * 64)
total_c = 0
for name, s in rows:
    s = s or ""
    total_c += len(s)
    print(f"{name:45s} {len(s):8d} {t(s):7d}")
print("-" * 64)
print(f"{'TOTAL (sin chat-template overhead)':45s} {total_c:8d} {total_c // 4:7d}")
print(f"\n(el server midió ~5.3-5.9k tok de prompt; el resto es chat-template + el user msg)")
print("schemas JSON de tools en el prompt del QAT: 0 (los tiene FunctionGemma)")
