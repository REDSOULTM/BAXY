"""Validación EN VIVO del piso de apertura de app.open (GEMMA4_APP_OPEN_MIN_SCORE).

BUG medido (2026-06-10): "abre jitomatador por favor" -> app.open ok=True (el
fuzzy abrió OTRA app con score>0). Distribución medida en
_diag_app_open_score_floor.py: typos legítimos 46-88, basura <=40 -> piso 45.

GATES:
  G1 basura : ningún turno basura termina con un app-open ok=True (nada se
              abre); reply honesto. Incluye "abrí morktul" (matchea fuzzy a
              'Mortal Kombat 1' score 40 — la precondición PASA y decide el piso).
  G2 legítimos: alias localizado + typo medido siguen abriendo (ok=True).
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
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
agent.tools.apps.find("notepad", limit=1)
print("[warm] turno descartado...", flush=True)
try:
    agent.run_content("abrí la calculadora")
except Exception:
    pass

CASES = [
    # (cmd, expect_app_open: ¿debe abrir una APP INSTALADA?)
    # NOTA: el fallback a SITIO de t_app (label exacto del dominio, contrato
    # 2026-06-09) es OTRO camino y está permitido — "morktul" resuelve a
    # morktul.bandcamp.com (label exacto) y eso NO es el bug del fuzzy. El bug
    # era abrir Mortal Kombat (app instalada, score 40). Se distingue por la
    # FORMA del result: app instalada = opened-candidate sin delegated_from.
    ("abre jitomatador por favor", False),   # el caso medido del bug
    ("abrí morktul", False),                 # fuzzy 40 vs Mortal Kombat -> piso
    ("abrí la calculadora", True),           # alias builtin
    ("abre el bloc de notas", True),         # alias builtin multi-palabra
    ("abrí spotfy", True),                   # typo medido 61 -> Spotify
]
print("=" * 96, flush=True)
fails = []
for cmd, expect_open in CASES:
    t0 = time.monotonic()
    reply = agent.run_content(cmd)
    dt = time.monotonic() - t0
    content = (reply.content or "").replace("\n", " ")
    events = reply.tool_events or []
    app_opens_ok = [e for e in events
                    if getattr(e, "name", "") == "app"
                    and (getattr(e, "args", {}) or {}).get("action") in (None, "open")
                    and (getattr(e, "result", {}) or {}).get("ok")
                    and (getattr(e, "result", {}) or {}).get("opened")
                    and not (getattr(e, "result", {}) or {}).get("delegated_from")]
    site_delegated = [e for e in events
                      if (getattr(e, "result", {}) or {}).get("delegated_from")]
    opened = bool(app_opens_ok)
    ok = opened == expect_open
    if not ok:
        fails.append(f"{cmd} (app_opened={opened}, esperado {expect_open})")
    ev = [f"{getattr(e, 'name', e)}(ok={(getattr(e, 'result', {}) or {}).get('ok')})"
          for e in events][:4]
    print(f"[{'OK ' if ok else 'FAIL'}] {cmd!r}  app_opened={opened} (esperado {expect_open})"
          f"  site_fallback={bool(site_delegated)}  {dt:.1f}s", flush=True)
    print(f"       events={ev}", flush=True)
    print(f"       reply={content[:120]!r}", flush=True)
    print("-" * 96, flush=True)

print(f"[VEREDICTO] {'TODO OK' if not fails else 'FALLAS: ' + '; '.join(fails)}", flush=True)
