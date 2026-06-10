"""Validación EN VIVO de la latencia del miss de app.open (fix 2026-06-10).

BASELINE medido (pre-fix): "abrí jitomatador" = 19.9-31.2s por turno (decide
~14s por deep scan secuencial agotando budget + resolve_site secuencial 8.6-11s,
ambos REPAGADOS si el 4B re-llama la tool).

GATE (definido en el backlog): turno miss <8s; hits siguen ~1s; honestidad
intacta ("no lo encontré", sin abrir basura).

Correr: python scripts/_validate_app_open_miss.py
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

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print("[boot] arrancando llama-server...", flush=True)
st = mgr.start(prof, wait_health=True, timeout_s=120)
print(f"[boot] status={st!r}", flush=True)

from gemma4_agent.agent_core.agent import Gemma4Agent

print("[boot] cargando agente...", flush=True)
agent = Gemma4Agent()
# warm de fuentes del resolver como hace el runner en boot (agent_runner:431)
t0 = time.monotonic()
agent.tools.apps.find("notepad", limit=1)
print(f"[warm] fuentes del app resolver: {time.monotonic()-t0:.2f}s", flush=True)

print("[warm] turno de calentamiento (descartado)...", flush=True)
try:
    agent.run_content("abrí la calculadora")
except Exception:
    pass

CASES = [
    ("abrí la calculadora", "hit", 4.0),    # early-path: debe seguir rápido
    ("abrí jitomatador", "miss", 8.0),      # GATE backlog: <8s
    ("abrí jitomatador", "miss-rep", 8.0),  # repetido: memos calientes
]
print("=" * 96, flush=True)
fails = []
for cmd, kind, cap_s in CASES:
    t0 = time.monotonic()
    try:
        reply = agent.run_content(cmd)
        err = getattr(reply, "error", None)
    except Exception as e:  # noqa: BLE001
        reply, err = None, f"EXC {type(e).__name__}: {e}"
    dt = time.monotonic() - t0
    content = ((getattr(reply, "content", "") or "") if reply else "").replace("\n", " ")
    events = getattr(reply, "tool_events", []) or [] if reply else []
    ev = [f"{getattr(e, 'name', e)}:{getattr(e, 'args', {})}" for e in events][:3]
    ok = dt < cap_s and not err and bool(content)
    if kind.startswith("miss"):
        # honestidad: el reply NO debe afirmar que abrió jitomatador.
        low = content.lower()
        dishonest = ("abrí jitomatador" in low or "abri jitomatador" in low) \
            and "no" not in low.split("jitomatador")[0][-40:]
        ok = ok and not dishonest
    if not ok:
        fails.append(f"{cmd} ({kind}: {dt:.1f}s vs cap {cap_s}s)")
    print(f"[{'OK ' if ok else 'FAIL'}] {cmd!r} ({kind})  total={dt:.2f}s (cap {cap_s}s)", flush=True)
    print(f"       events={ev}", flush=True)
    print(f"       reply={content[:120]!r}  err={err}", flush=True)
    print("-" * 96, flush=True)

print(f"[VEREDICTO] {'TODO OK' if not fails else 'FALLAS: ' + '; '.join(fails)}", flush=True)
print("[baseline] pre-fix: miss 19.9-31.2s; tool-level t_app miss 24.6s->5.8s "
      "(1ª) / 0.3s (rep), medido en _diag_app_open_miss.py", flush=True)
