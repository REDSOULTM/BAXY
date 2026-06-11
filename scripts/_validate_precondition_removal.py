"""Validación EN VIVO: retiro de la precondición app_resolvable.

BEFORE (medido a nivel dispatcher, 2026-06-10): execute(app.open,"pivigames")
-> needs_user "No encuentro esa aplicación" SIN resolver el sitio (el fallback
de t_app, fix 47e6c14, nunca corría por esta ruta). AFTER: el site-fallback
revive; la honestidad para basura la cubre el piso de apertura.

GATES:
  G1 sitio   : "abrí pivigames" termina abriendo el sitio (delegated_from) o,
               como mínimo, NO muere en needs_user de precondición.
  G2 divert  : "abrí gmail.com" abre en browser (web-divert intacto).
  G3 basura  : "abrí jitomatador" no abre ninguna app instalada; reply honesto.
  G4 reales  : "abrí la calculadora" / "abrí spotfy" abren como siempre.
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
    # (cmd, expect: "site" | "app" | "none")
    ("abrí pivigames", "site"),
    ("abrí gmail.com", "site"),
    ("abrí jitomatador", "none"),
    ("abrí la calculadora", "app"),
    ("abrí spotfy", "app"),
]
print("=" * 96, flush=True)
fails = []
for cmd, expect in CASES:
    t0 = time.monotonic()
    reply = agent.run_content(cmd)
    dt = time.monotonic() - t0
    content = (reply.content or "").replace("\n", " ")
    events = reply.tool_events or []
    got = "none"
    for e in events:
        res = getattr(e, "result", {}) or {}
        if not res.get("ok"):
            continue
        if res.get("delegated_from") or res.get("navigated_url") or res.get("url"):
            got = "site"
            break
        if res.get("opened"):
            got = "app"
            break
    ok = got == expect
    if not ok:
        fails.append(f"{cmd} (got={got}, esperado {expect})")
    ev = [f"{getattr(e, 'name', e)}(ok={(getattr(e, 'result', {}) or {}).get('ok')},"
          f" st={(getattr(e, 'result', {}) or {}).get('status')})" for e in events][:3]
    print(f"[{'OK ' if ok else 'FAIL'}] {cmd!r}  got={got} (esperado {expect})  {dt:.1f}s",
          flush=True)
    print(f"       events={ev}", flush=True)
    print(f"       reply={content[:120]!r}", flush=True)
    print("-" * 96, flush=True)

print(f"[VEREDICTO] {'TODO OK' if not fails else 'FALLAS: ' + '; '.join(fails)}", flush=True)
