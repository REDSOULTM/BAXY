"""Diagnóstico: ¿qué decide _decide_turn para charla-exclamación vs acción real?
Imprime mode/tools/semantic_fallback para calibrar el gate del confirm filler.
Solo fase decide (no ejecuta el LLM loop); turnos benignos.
"""
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
# NO disparar el app-open net ni nets que ABREN cosas durante el diagnóstico:
# solo queremos la decisión del router para frases que NO son early.

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()

PHRASES = [
    "qué linda mañana",
    "qué tal todo",
    "gracias capo",
    "minimizá la ventana",
    "sube el volumen",
    "buscá el clima de mañana",
]
for p in PHRASES:
    t0 = time.monotonic()
    d = agent._decide_turn(p, None)
    dt = time.monotonic() - t0
    if d.early_reply is not None:
        print(f"{p!r:34} -> EARLY ({dt:.2f}s) reply={getattr(d.early_reply, 'content', '')[:60]!r}", flush=True)
        continue
    print(f"{p!r:34} -> mode={getattr(d.mode, 'name', None):14} tools={d.selected_tool_names!r:28} "
          f"semantic_fallback={d.semantic_fallback} ({dt:.2f}s)", flush=True)
