"""Smoke EN VIVO: tras needs_confirmation, un reply que YA pide confirmación
no debe ser pisado por el canned (fix frontera-de-palabra del aux multilingüe,
regresión "sto " ⊂ "esto"). 1 turno benigno: cerrar el bloc de notas pide
confirmación y NO cierra nada.
"""
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
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
# abrir primero el bloc (benigno) para que el close tenga objetivo real
agent.run_content("abrí el bloc de notas")
reply = agent.run_content("cerrá el bloc de notas")
content = (reply.content or "").replace("\n", " ")
events = reply.tool_events or []
ev = [f"{getattr(e, 'name', e)}({(getattr(e, 'result', {}) or {}).get('status')})"
      for e in events][:4]
canned = "Esa acción necesita tu confirmación antes de ejecutarla" in content
print(f"events={ev}", flush=True)
print(f"reply={content[:160]!r}", flush=True)
print(f"canned_replacement={canned}", flush=True)
asks = "?" in content or "confirm" in content.lower() or "quer" in content.lower()
print(f"[{'OK' if asks else 'REVISAR'}] el reply {'pide confirmación' if asks else 'NO pregunta'}",
      flush=True)
