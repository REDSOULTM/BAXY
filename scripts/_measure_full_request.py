"""Simula el body completo que se manda al server (system + history + tools)
y mide el peso REAL de cada componente. Asi descubrimos quien lleva los
~13.6k tokens al prefill.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.agent_core.agent_prompt import build_system_prompt
from gemma4_agent.tools_pkg.tools import (
    COMPOUND_TOOL_SCHEMAS, compile_tools_to_markdown_exact,
)

CHARS_PER_TOK = 3.6

def stats(label, text):
    chars = len(text)
    toks = int(chars / CHARS_PER_TOK)
    print(f"  {label:50s} {chars:>8,} chars   ~{toks:>6,} toks")
    return chars, toks

print("=" * 75)
print("FULL REQUEST WEIGHT — lo que llega al prefill")
print("=" * 75)

# Subset tipico que el router elige para "Hola, decime algo corto"
subset_smalltalk = []
subset_typical = ["system", "gui", "window", "filesystem", "app"]
subset_wide = ["system", "gui", "window", "filesystem", "app",
               "audio", "browser", "media", "whatsapp", "web_search"]

for subset_label, subset in [
    ("smalltalk []", subset_smalltalk),
    ("typical 5 tools", subset_typical),
    ("wide 10 tools", subset_wide),
]:
    print(f"\n[{subset_label}]")
    sys_prompt = build_system_prompt(subset)
    s_chars, s_toks = stats("system_prompt (rules)", sys_prompt)

    # Tool schemas hint (compact mode, ctx 16k)
    wanted = set(subset)
    sub_schemas = [
        s for s in COMPOUND_TOOL_SCHEMAS
        if isinstance(s, dict)
        and isinstance(s.get("function"), dict)
        and s["function"].get("name") in wanted
    ]
    schemas_md = compile_tools_to_markdown_exact(schemas=sub_schemas, compact=True) if sub_schemas else ""
    sh_chars, sh_toks = stats("tool_schemas_hint (compact md)", schemas_md)

    # Schemas JSON (lo que va al body `tools=[...]` y el jinja serializa)
    schemas_json = json.dumps(sub_schemas, ensure_ascii=False)
    sj_chars, sj_toks = stats("tools[] JSON (body, va al template)", schemas_json)

    # User msg
    user_msg = json.dumps({"role": "user", "content": "Hola, decime algo corto."})
    u_chars, u_toks = stats("user msg", user_msg)

    total_chars = s_chars + sh_chars + sj_chars + u_chars
    total_toks = s_toks + sh_toks + sj_toks + u_toks
    print(f"  {'TOTAL APROX':50s} {total_chars:>8,} chars   ~{total_toks:>6,} toks")

print("\n[SUBSETS QUE ENTRAN BAJO 9k toks PARA EVITAR EL CRASH CUDA]")
limit_tok = 9000
# Greedy: agrego tools hasta cruzar 9k
all_tool_names = [
    s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS
    if isinstance(s, dict) and isinstance(s.get("function"), dict)
]
print(f"  Total tool names: {len(all_tool_names)}")

# Probar subset agresivo: 15 tools (los 'core' del Camino C V3)
for size in [3, 5, 7, 10, 15, 20, 25, 30]:
    subset = all_tool_names[:size]
    sys_prompt = build_system_prompt(subset)
    sub_schemas = [
        s for s in COMPOUND_TOOL_SCHEMAS
        if isinstance(s, dict)
        and isinstance(s.get("function"), dict)
        and s["function"].get("name") in set(subset)
    ]
    schemas_md = compile_tools_to_markdown_exact(schemas=sub_schemas, compact=True) if sub_schemas else ""
    schemas_json = json.dumps(sub_schemas, ensure_ascii=False)
    total_chars = len(sys_prompt) + len(schemas_md) + len(schemas_json) + 60
    total_toks = int(total_chars / CHARS_PER_TOK)
    marker = " <-- LIMITE" if total_toks > limit_tok else " OK"
    print(f"  subset {size:>2d} tools -> {total_toks:>6,} toks{marker}")
