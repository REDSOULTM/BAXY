"""¿Por qué "abrí la calculadora" da events=0 (el modelo NO emite app.open) mientras
"abrí el bloc de notas" sí? Captura, por variante: tool_calls por call, modo,
reply, y trace (router_reasoning / forced_retry / rescue). Diagnóstico de
fiabilidad de tool-calling para app-open.

  python scripts/_diag_calc_route.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

calls = []
events_trace = []
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    tcs, content = [], ""
    for ch in (resp or {}).get("choices") or []:
        msg = ch.get("message") or {}
        content = (msg.get("content") or "")[:70]
        for tc in (msg.get("tool_calls") or []):
            tcs.append((tc.get("function") or {}).get("name"))
    calls.append({"tcs": tcs, "content": content, "tools": [((t.get("function") or {}).get("name")) for t in (kw.get("tools") or [])]})
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
_orig_event = agent.trace.event


def wrapped_event(turn_id, _evname, **payload):
    if any(k in _evname for k in ("router", "forced", "retry", "rescue", "tool_call", "intent", "skip", "subset")):
        events_trace.append((_evname, {k: str(v)[:60] for k, v in list(payload.items())[:3]}))
    return _orig_event(turn_id, _evname, **payload)


agent.trace.event = wrapped_event
agent.run_content("hola")  # warm

for q in ["abrí la calculadora", "abre la calculadora", "abrime la calculadora",
          "abrí el bloc de notas", "abrí la calculadora de Windows"]:
    try:
        agent.history.clear()
    except Exception:
        pass
    calls.clear()
    events_trace.clear()
    reply = agent.run_content(q)
    n_ev = len(getattr(reply, "tool_events", []) or [])
    ran = [getattr(e, "name", "?") for e in (getattr(reply, "tool_events", []) or [])]
    print("\n" + "=" * 88, flush=True)
    print(f"Q: {q!r} -> events={n_ev} {ran}", flush=True)
    print(f"  reply: {(getattr(reply,'content','') or '')[:80]!r}", flush=True)
    for i, c in enumerate(calls):
        print(f"  call#{i}: tcs={c['tcs']} tools_offered={c['tools']}", flush=True)
        if c["tcs"] == [] and c["content"]:
            print(f"           content={c['content']!r}", flush=True)
    for name, snip in events_trace[:6]:
        print(f"    trace: {name} {snip}", flush=True)
