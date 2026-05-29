"""Inserta hook en el agent ANTES de llamar al server y mide el tamano REAL
del system message y los messages JSON completos. Asi vemos donde estan
los tokens que no vi en la medicion estatica.
"""
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

CHARS_PER_TOK = 3.6
captured = []

orig_chat = llm_client.LLMClient.chat

def wrapped_chat(self, messages, **kw):
    # Medir
    system = next((m for m in messages if m.get("role") == "system"), None)
    sys_chars = len(system["content"]) if system else 0
    history_chars = sum(
        len(json.dumps(m, ensure_ascii=False)) for m in messages if m.get("role") != "system"
    )
    tools_payload = kw.get("tools") or []
    tools_chars = len(json.dumps(tools_payload, ensure_ascii=False))
    tool_names = [t.get("function", {}).get("name") for t in tools_payload]
    total_chars = sys_chars + history_chars + tools_chars
    total_toks = int(total_chars / CHARS_PER_TOK)
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
    captured.append({
        "user": (last_user.get("content") or "")[:60],
        "sys_chars": sys_chars,
        "sys_toks": int(sys_chars / CHARS_PER_TOK),
        "hist_chars": history_chars,
        "hist_toks": int(history_chars / CHARS_PER_TOK),
        "tools_count": len(tools_payload),
        "tools_names": tool_names,
        "tools_chars": tools_chars,
        "tools_toks": int(tools_chars / CHARS_PER_TOK),
        "total_toks": total_toks,
        "force_tool": kw.get("force_tool", False),
    })
    # Stop antes del POST — devolver respuesta vacia simulada
    return {"choices": [{"message": {"content": ""}}]}

llm_client.LLMClient.chat = wrapped_chat
print("[probe] hook instalado, cargando agente...", flush=True)
agent = Gemma4Agent()

PROMPTS = [
    "Hola, decime algo corto.",
    "Que dia es hoy?",
    "Cuanto es 23 mas 47?",
    "Decime el clima en Buenos Aires.",
    "Que opinas del futbol?",
    "Cual es la capital de Francia?",
]

for p in PROMPTS:
    try:
        agent.run_content(p)
    except Exception as e:
        print(f"[probe] {p!r} -> {type(e).__name__}: {str(e)[:80]}", flush=True)

print("\n" + "=" * 100)
print(f"{'USER MSG':35s} {'SYS':>7s} {'HIST':>7s} {'#T':>3s} {'TOOLS':>7s} {'TOT':>7s}  {'FORCE':>6s}  tool names")
print("=" * 100)
for c in captured:
    print(f"{c['user']:35s} {c['sys_toks']:>7,} {c['hist_toks']:>7,} {c['tools_count']:>3d} {c['tools_toks']:>7,} {c['total_toks']:>7,}  {'YES' if c['force_tool'] else 'no':>6s}  {','.join(c['tools_names'][:10])}")
