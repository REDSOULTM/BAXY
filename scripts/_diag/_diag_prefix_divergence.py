"""Por qué keep-tools NO dio cache-hit (medí pass-2 prefill 5919, debió ser ~50).
La research (compass) dice que el prefix-cache YA funciona; algo MÁS en el prefijo
diverge entre pass-1 y pass-2. Este diag captura, por LLM call, lo que el cliente
manda (system content, tools, chat_template_kwargs) para DIFFEAR y encontrar el
punto de divergencia.

  GEMMA4_SUMMARY_KEEP_TOOLS=1 python scripts/_diag_prefix_divergence.py
"""
import os
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_SUMMARY_KEEP_TOOLS"] = "1"  # keep tools in pass-2

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client


def _h(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8", "replace")).hexdigest()[:10]


caps: list[dict] = []
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    sysm = ""
    roles = []
    for m in messages:
        roles.append(m.get("role"))
        if m.get("role") == "system" and not sysm:
            c = m.get("content")
            sysm = c if isinstance(c, str) else str(c)
    tools = kw.get("tools") or []
    tnames = [((t.get("function") or {}).get("name")) for t in tools]
    tim = (orig(self, messages, **kw))
    caps.append({
        "roles": roles,
        "sys_len": len(sysm),
        "sys_hash": _h(sysm),
        "sys_head": sysm[:50],
        "sys_tail": sysm[-50:],
        "tools_n": len(tools),
        "tools_hash": _h("|".join(map(str, tnames))),
        "enable_thinking": kw.get("enable_thinking"),
        "thinking_budget": kw.get("thinking_budget"),
        "prompt_n": (tim or {}).get("timings", {}).get("prompt_n"),
        "cache_n": (tim or {}).get("timings", {}).get("cache_n"),
    })
    return tim


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("subí el volumen al 50 por ciento")  # warm
caps.clear()

agent.run_content("subí el volumen al 40 por ciento")
print("=" * 92, flush=True)
print(f"calls={len(caps)}", flush=True)
for i, c in enumerate(caps):
    tag = "PASS-1" if i == 0 else ("PASS-2" if i == len(caps) - 1 else f"call#{i}")
    print(f"\n{tag}:", flush=True)
    for k in ("roles", "sys_len", "sys_hash", "tools_n", "tools_hash",
              "enable_thinking", "thinking_budget", "prompt_n", "cache_n"):
        print(f"   {k}: {c[k]}", flush=True)
    print(f"   sys_head: {c['sys_head']!r}", flush=True)
    print(f"   sys_tail: {c['sys_tail']!r}", flush=True)

if len(caps) >= 2:
    p1, p2 = caps[0], caps[-1]
    print("\n" + "=" * 92, flush=True)
    print("DIVERGENCIAS pass-1 vs pass-2 (lo que rompe el prefix-cache):", flush=True)
    for k in ("sys_hash", "sys_len", "tools_n", "tools_hash", "enable_thinking", "thinking_budget"):
        mark = "  <-- DIFIERE" if p1[k] != p2[k] else " (igual)"
        print(f"   {k}: {p1[k]} -> {p2[k]}{mark}", flush=True)
    print(f"\n   pass-2 prompt_n={p2['prompt_n']} cache_n={p2['cache_n']} "
          f"(si cache_n~prompt_anterior -> hit; si cache_n~0 -> miss total)", flush=True)
