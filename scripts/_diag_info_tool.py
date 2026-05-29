"""Diagnóstico: ¿POR QUÉ "qué es la fotosíntesis" / "capital de Francia" corren un
tool (events=1) mientras "Python" / "cielo azul" no? Captura, por turno:
  - cada LLM call: tool_calls emitidos + content snippet
  - TODOS los trace events (modo, forced_retry, rescue de tool-as-text, deterministic_*)
  - events finales (tools que realmente corrieron)

Para decidir si el tool post-prosa es ESPURIO (suprimible en info) o genuino.
NO streaming (flujo natural). History reset entre preguntas.

  python scripts/_diag_info_tool.py
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

calls: list[dict] = []
events_trace: list[tuple] = []

orig_chat = llm_client.LLMClient.chat


def wrapped_chat(self, messages, **kw):
    resp = orig_chat(self, messages, **kw)
    tcs = []
    content = ""
    for ch in (resp or {}).get("choices") or []:
        msg = ch.get("message") or {}
        content = (msg.get("content") or "")[:70]
        for tc in (msg.get("tool_calls") or []):
            tcs.append((tc.get("function") or {}).get("name"))
    calls.append({"tcs": tcs, "content": content, "tools_offered": bool(kw.get("tools")),
                  "force": kw.get("force_tool")})
    return resp


llm_client.LLMClient.chat = wrapped_chat
print("[boot] agente...", flush=True)
agent = Gemma4Agent()

# Hook trace.event to capture the decision flow.
_orig_event = agent.trace.event


def wrapped_event(turn_id, _evname, **payload):
    keep = ("mode", "forced", "retry", "rescue", "tool_call_as_text", "deterministic",
            "grounding", "abstain", "router", "intent", "skip", "tool_call")
    if any(k in _evname for k in keep):
        snippet = {k: str(v)[:50] for k, v in list(payload.items())[:3]}
        events_trace.append((_evname, snippet))
    return _orig_event(turn_id, _evname, **payload)


agent.trace.event = wrapped_event

agent.run_content("hola")  # warm

for q in ["qué es la fotosíntesis", "cuál es la capital de Francia", "explicame brevemente qué es Python"]:
    try:
        agent.history.clear()
    except Exception:
        pass
    calls.clear()
    events_trace.clear()
    reply = agent.run_content(q)
    n_ev = len(getattr(reply, "tool_events", []) or [])
    ran = [getattr(e, "name", "?") for e in (getattr(reply, "tool_events", []) or [])]
    print("\n" + "=" * 92, flush=True)
    print(f"Q: {q!r}  -> final tool_events={n_ev} {ran}", flush=True)
    print(f"  reply: {(getattr(reply,'content','') or '')[:90]!r}", flush=True)
    for i, c in enumerate(calls):
        print(f"  call#{i}: tcs={c['tcs']} tools_offered={c['tools_offered']} force={c['force']} content={c['content']!r}", flush=True)
    print("  trace:", flush=True)
    for name, snip in events_trace:
        print(f"    - {name} {snip}", flush=True)
print("\n" + "=" * 92, flush=True)
print("[lee] mirá en qué call aparece el tcs y qué trace lo disparó (rescue/forced/modelo).", flush=True)
