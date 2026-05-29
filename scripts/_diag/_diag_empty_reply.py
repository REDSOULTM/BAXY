"""¿El cache fix (enable_thinking=True + budget=16 en el summary de éxito) produce
REPLIES VACÍOS a veces? (vi 'abrí el bloc de notas' -> events=1 pero reply=''.)
Corre app-opens con KEEP off vs on y compara: reply vacío? cache hit? calls?
Si vacío SOLO con KEEP on -> regresión del fix (subir budget / fallback).

  python scripts/_diag_empty_reply.py
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

last = {"summary_prompt_n": None}
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    last["summary_prompt_n"] = (resp or {}).get("timings", {}).get("prompt_n")
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("subí el volumen al 50 por ciento")  # warm

CMDS = ["abrí la calculadora", "abrí el bloc de notas", "abrí el explorador de archivos",
        "abrí el paint", "subí el volumen al 45 por ciento"]
print("=" * 88, flush=True)
empties = {"off": 0, "on": 0}
for cmd in CMDS:
    print(f"\n{cmd!r}", flush=True)
    for keep in (False, True):
        if keep:
            os.environ["GEMMA4_SUMMARY_KEEP_TOOLS"] = "1"
        else:
            os.environ.pop("GEMMA4_SUMMARY_KEEP_TOOLS", None)
        try:
            agent.history.clear()
        except Exception:
            pass
        last["summary_prompt_n"] = None
        reply = agent.run_content(cmd)
        content = (getattr(reply, "content", "") or "")
        n_ev = len(getattr(reply, "tool_events", []) or [])
        empty = (n_ev >= 1) and (not content.strip())
        if empty:
            empties["on" if keep else "off"] += 1
        tag = "KEEP" if keep else "off "
        print(f"  [{tag}] events={n_ev} empty={empty} pass2_prefill={last['summary_prompt_n']} reply={content[:70]!r}", flush=True)
print("=" * 88, flush=True)
print(f"[VEREDICTO] replies vacíos (tool corrió pero reply=''): off={empties['off']} KEEP={empties['on']}", flush=True)
print("  si KEEP>off -> el cache fix (enable_thinking=True+budget=16) causa vacíos -> arreglar.", flush=True)
