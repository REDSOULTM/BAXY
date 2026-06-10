"""Desglose del turno "abrí jitomatador" (miss): ¿dónde se van los segundos?
Envuelve decide / execute(tool) / client.chat con timers e imprime cada paso.
Tras los fixes de tool (deep scan paralelo+memo, site cache) el turno vivo
seguía en 26.6s — este diag separa LLM vs tools vs decide para el siguiente corte.
"""
import functools
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
agent.tools.apps.find("notepad", limit=1)  # warm fuentes (como el boot real)


def timed_method(obj, name, label=None, describe=None):
    orig = getattr(obj, name)

    @functools.wraps(orig)
    def w(*a, **k):
        t0 = time.monotonic()
        try:
            return orig(*a, **k)
        finally:
            desc = ""
            if describe:
                try:
                    desc = describe(*a, **k)
                except Exception:
                    desc = "?"
            print(f"    [t] {label or name:18} {time.monotonic()-t0:6.2f}s  {desc}",
                  flush=True)
    setattr(obj, name, w)


timed_method(agent, "_decide_turn", "decide")
timed_method(agent.tools, "execute", "tool.execute",
             describe=lambda tool, args=None, **k: f"{tool} {str(args)[:70]}")
timed_method(agent.client, "chat", "llm.chat",
             describe=lambda msgs, *a, **k: f"msgs={len(msgs)} tools={len(k.get('tools') or [])}")
# capas internas del miss de app.open (¿dónde viven los ~10s del execute?):
timed_method(agent.tools, "app_open", "    app_open")
timed_method(agent.tools.apps, "find", "      apps.find",
             describe=lambda q, *a, **k: repr(q))
timed_method(agent.tools, "_resolve_site_by_search", "      resolve_site",
             describe=lambda n, *a, **k: repr(n))
timed_method(agent.tools, "verify_app_opened", "      verify_opened")
timed_method(agent.tools, "t_browser", "    t_browser",
             describe=lambda a, *aa, **k: str(a)[:60])
# execute() despacha por _impls (refs guardadas) -> envolver el dict directo;
# y los pasos PRE-dispatch son funciones del módulo -> envolver sus globals.
import gemma4_agent.tools_pkg.tools as _T


def timed_fn(mod, fname, label):
    orig = getattr(mod, fname)

    @functools.wraps(orig)
    def w(*a, **k):
        t0 = time.monotonic()
        try:
            return orig(*a, **k)
        finally:
            print(f"    [t] {label:24} {time.monotonic()-t0:6.2f}s", flush=True)
    setattr(mod, fname, w)


timed_fn(_T, "classify_tool_call", "pre.classify_safety")
timed_fn(_T, "_coerce_and_validate_tool_args", "pre.coerce_validate")
timed_fn(_T, "_normalize_tool_result", "post.normalize")
_orig_app_impl = agent.tools._impls["app"]
def _timed_app_impl(args):
    t0 = time.monotonic()
    try:
        return _orig_app_impl(args)
    finally:
        print(f"    [t] {'impl t_app':24} {time.monotonic()-t0:6.2f}s", flush=True)
agent.tools._impls["app"] = _timed_app_impl

print("[warm] turno descartado...", flush=True)
agent.run_content("abrí la calculadora")

print("== turno miss: 'abrí jitomatador' ==", flush=True)
t0 = time.monotonic()
reply = agent.run_content("abrí jitomatador")
print(f"  TOTAL {time.monotonic()-t0:.2f}s  reply={(reply.content or '')[:90]!r}",
      flush=True)
