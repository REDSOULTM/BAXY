"""Mide el reply post-acción (app.open) en varios idiomas + latencia.
Compara el nuevo path LLM vs el viejo hardcode. run_content (seguro)."""
import sys, os, time
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
ToolRegistry.execute = lambda self, n, a: {"ok": True, "status": "dispatched", "verified": None, "_eval_mock": True}
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")

CASES = [("en","open notepad"),("pt","abre o bloco de notas"),("fr","ouvre le bloc-notes"),
         ("de","öffne den editor"),("it","apri la calcolatrice"),("es","abrí la calculadora")]
print("\n=== reply post-acción por idioma (path LLM) ===")
for lang, msg in CASES:
    try: agent.history.clear()
    except Exception: pass
    t0=time.time(); r=agent.run_content(msg); dt=time.time()-t0
    rep=(getattr(r,"content","") or "")
    es_lead = rep.lower().strip().startswith(("listo","abrí","abrir"))
    print(f"  [{lang}] {dt:4.1f}s {'ES!' if es_lead else 'OK '} {msg!r} -> {rep[:60]!r}", flush=True)
