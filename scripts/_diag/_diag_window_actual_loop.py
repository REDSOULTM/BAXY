"""Reproduce EN VIVO el loop de "minimiza/maximiza la ventana actual".

Boota el llama-server real, corre el agente via run_content (= la UI, seguro),
con los EFECTOS FISICOS de las tools mockeados (window/input/session devuelven
ok sin tocar nada). Cuenta:
  - cuantas veces se llamo a client.chat (LLM)
  - cuantas veces se ejecuto cada tool
  - el reply final + por que se corto

Para comparar, corre tambien la MISMA frase SIN la palabra 'actual'.
"""
from __future__ import annotations
import os, sys, time, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
# Safety OFF: que no pida confirmacion (no hay nada irreversible, todo mockeado).
os.environ.setdefault("GEMMA4_ENABLE_SAFETY", "0")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile(); apply_profile_to_env(prof)
print(f"[boot] perfil={prof.name}", flush=True)
mgr = get_shared_manager()
t0 = time.time()
mgr.start(prof, wait_health=True, timeout_s=120)
print(f"[boot] OK en {time.time()-t0:.1f}s router={mgr.is_router_mode()}", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra import llm_client as _llm
from gemma4_agent.tools_pkg import tools as _tools_mod

# --- Mock de EFECTOS FISICOS de las tools del loop (sin tocar la PC) ---
_orig_execute = _tools_mod.ToolRegistry.execute
_exec_counter: Counter = Counter()

def _counting_execute(self, name, args):
    action = (args or {}).get("action") or ""
    _exec_counter[f"{name}.{action}"] += 1
    # Mockear SOLO los efectos fisicos de ventana/teclado para no mover nada real.
    if name in {"window", "input"} and action in {
            "minimize", "maximize", "restore", "focus", "close", "move_resize"}:
        return {"ok": True, "verified": True, "action": action, "mocked": True}
    return _orig_execute(self, name, args)

_tools_mod.ToolRegistry.execute = _counting_execute

# --- Contar llamadas a client.chat (LLM): se envuelve la instancia por-agente ---

def run_case(text: str) -> dict:
    _exec_counter.clear()
    cfg = AgentConfig.from_env()
    agent = Gemma4Agent(config=cfg)
    # contador de chat por-agente (envuelve el metodo de instancia del client)
    chat_calls = {"n": 0}
    _client = agent.client
    _real = _client.chat
    def _wrapped(*a, **k):
        chat_calls["n"] += 1
        return _real(*a, **k)
    _client.chat = _wrapped  # type: ignore
    t = time.time()
    reply = agent.run_content(text)
    dt = time.time() - t
    return {
        "text": text,
        "mode_seconds": round(dt, 1),
        "llm_chat_calls": chat_calls["n"],
        "total_tool_execs": sum(_exec_counter.values()),
        "tool_breakdown": dict(_exec_counter.most_common(8)),
        "reply": (reply.content or "")[:300],
        "tool_events": len(reply.tool_events or []),
    }

for txt in ["minimiza la ventana actual", "minimiza la ventana"]:
    print("\n" + "=" * 70, flush=True)
    print(f"CASO: {txt!r}", flush=True)
    try:
        r = run_case(txt)
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)
    except Exception as e:
        import traceback
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()

print("\n[done]", flush=True)
