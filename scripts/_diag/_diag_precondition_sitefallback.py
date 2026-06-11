"""BEFORE/AFTER del bloqueo de la precondición de app vs el site-fallback de t_app.

BEFORE (con la precondición): execute(app.open,"pivigames") -> needs_user
"No encuentro esa aplicación" SIN intentar resolver el sitio (el fix medido
47e6c14 nunca corre por esta ruta).
AFTER (sin la precondición): el mismo execute llega a t_app -> app not found ->
_resolve_site_by_search -> abre pivigames.blog (o error honesto si no resuelve).

Nivel dispatcher (sin LLM). ABRE el navegador si el sitio resuelve (benigno).
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState

tmp = Path(tempfile.mkdtemp())
reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap",
                   AgentState(tmp / "s.json"), safety_enabled=False)
reg.apps.find("notepad", limit=1)

for name in ("pivigames", "gmail.com", "jitomatador"):
    r = reg.execute("app", {"action": "open", "name": name})
    print(f"{name!r:14} -> ok={r.get('ok')} status={r.get('status')!r} "
          f"err={r.get('error')!r}", flush=True)
    print(f"               precondition={r.get('precondition')!r} "
          f"delegated={r.get('delegated_from')!r} url={r.get('resolved_url') or r.get('navigated_url')!r}",
          flush=True)
