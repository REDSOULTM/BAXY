"""Verificación EN VIVO (regla #3.5) del cluster terse + edge-cases del router
tras el reentreno FT 3ep + regen del exemplar store + fix S3c-bis.

Corre el AGENTE REAL (agent.run_content = el path de la UI) contra el LLM real
en :8080, y mira la cadena COMPLETA: router subset + qué tool elige el 4B en cada
call + cadena ejecutada + reply.

SEGURIDAD (memoria, ≥3 incidentes): Claude corre como terminal de VS Code; un
gui.type/keypress físico (SendInput) cierra VS Code y pierde el trabajo. Por eso:
  (1) ToolRegistry.execute se intercepta → REGISTRA la llamada (lo que el 4B
      eligió: el dato del routing) y devuelve un success SINTÉTICO sin ejecutar
      NINGÚN efecto físico (ni SendInput, ni cambiar volumen, ni timers sueltos,
      ni abrir ventanas).
  (2) Las primitivas SendInput (gui_type/keypress/click/...) se neutralizan
      directo, por si algún path las llama sin pasar por execute.
El ROUTING (subset + elección del 4B) queda 100% REAL; el reply se basa en el
success sintético (se reporta como tal).

Uso: python scripts/_diag/_diag_live_terse_cluster.py
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; arrancando server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)
print("[boot] server OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.infra import llm_client
from gemma4_agent.routing.planner import select_tool_names, plan_mission

# ---- SAFETY LAYER 1: intercept execute (record + synthetic success) ----
executed: list[tuple[str, dict]] = []
_real_execute = ToolRegistry.execute


def _safe_execute(self, name, args):  # noqa: ANN001
    executed.append((name, dict(args or {})))
    return {"ok": True, "status": "ok", "_eval_mock": True,
            "action": (args or {}).get("action")}


ToolRegistry.execute = _safe_execute

# ---- SAFETY LAYER 2: hard-neutralize the SendInput primitives ----
_PHYS = ["gui_type", "gui_keypress", "gui_click", "gui_type_into",
         "gui_click_button", "gui_hotkey", "gui_scroll", "gui_drag",
         "_send_text_via_sendinput"]
for _m in _PHYS:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m,
                (lambda *a, **k: {"ok": True, "_eval_mock": "phys-noop"}))

# ---- capture every LLM call's tool choices + offered tools ----
llm_calls: list[dict] = []
_real_chat = llm_client.LLMClient.chat


def _wrapped_chat(self, messages, **kw):  # noqa: ANN001
    resp = _real_chat(self, messages, **kw)
    tcs, content = [], ""
    for ch in (resp or {}).get("choices") or []:
        msg = ch.get("message") or {}
        content = (msg.get("content") or "")[:90]
        for tc in (msg.get("tool_calls") or []):
            fn = (tc.get("function") or {})
            tcs.append((fn.get("name"), str(fn.get("arguments"))[:60]))
    offered = [((t.get("function") or {}).get("name")) for t in (kw.get("tools") or [])]
    llm_calls.append({"tcs": tcs, "content": content, "offered": offered})
    return resp


llm_client.LLMClient.chat = _wrapped_chat

from gemma4_agent.agent_core.agent import Gemma4Agent

print("[boot] construyendo agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("hola")  # warm

CASES = [
    # --- cluster terse (handoff / tarea 4) ---
    ("subí el volumen", "audio"),
    ("contá 10 minutos", "timer/reminder/notification"),
    ("escribí 2+2", "gui-type/compute (¡físico mockeado!)"),
    # --- edge-cases (decisión de tests) ---
    ("cuál es mi ip", "network o web"),
    ("qué es pytest", "web o reply directo"),
    # --- regresión confirmada (mis fixes) ---
    ("abre el navegador", "app/browser"),
    ("qué recordás de mí", "memory"),
]

for q, want in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    executed.clear()
    llm_calls.clear()
    subset = [t for t in select_tool_names(q, plan_mission(q), safety_enabled=True)]
    reply = agent.run_content(q)
    content = (getattr(reply, "content", "") or "")
    print("\n" + "=" * 80, flush=True)
    print(f"Q: {q!r}   (esperado: {want})", flush=True)
    print(f"  ROUTER subset: {[t for t in subset if t not in ('session','safety')]}", flush=True)
    for i, c in enumerate(llm_calls):
        if c["tcs"]:
            print(f"  4B call#{i}: ELIGIÓ {c['tcs']}", flush=True)
        else:
            print(f"  4B call#{i}: (sin tool) content={c['content']!r}", flush=True)
    print(f"  CADENA ejecutada (mockeada): {[n for n,_ in executed]}", flush=True)
    print(f"  REPLY (sobre success sintético): {content[:160]!r}", flush=True)

print("\n[done]", flush=True)
