"""LIVE: el short-circuit de aritmética por run_content (el agente real)."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.agent_core.agent import Gemma4Agent
a = Gemma4Agent()
for cmd in ["cuánto es 47 por 8", "cuánto es 100 dividido por 8", "cuánto es 2 más 3 por 4",
            "qué hora es", "abrí la calculadora"]:
    r = a.run_content(cmd)
    ev = [getattr(e, "name", None) for e in (getattr(r, "tool_events", None) or [])]
    print(f"  {cmd!r:38} tools={ev} -> {(getattr(r,'content','') or '').strip()[:60]!r}", flush=True)
print("[done] (esperado: 376, 12.5, 14; hora y calc NO por calc)", flush=True)
