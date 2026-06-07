"""Verifica que browser.open resuelva el dominio REAL por búsqueda en vez de
abrir el adivinado por el 4B. Prueba el handler directo (sin GUI real, mock del
open físico) — la RESOLUCIÓN (web_search) sí es real."""
import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")
import tempfile
from pathlib import Path
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
_tmp = Path(tempfile.mkdtemp())
reg = ToolRegistry(MemoryStore(_tmp / "mem.json"), _tmp / "captures")
# mockear SOLO la apertura física (web_open_url / _open_url_in_browser) para no
# abrir navegador de verdad; la resolución por búsqueda queda REAL.
_opened = {}
reg.web_open_url = lambda a: (_opened.update(url=a.get("url")), {"ok": True, "status": "dispatched", "url": a.get("url")})[1]
reg._open_url_in_browser = lambda b, u: (_opened.update(url=u, browser=b), {"ok": True, "status": "dispatched", "url": u})[1]

print("=== resolución de sitio (browser.open) ===", flush=True)
for target in ["pivigames", "pivigames.com"]:   # nombre pelado Y dominio adivinado
    _opened.clear()
    r = reg.t_browser({"action": "open", "url": target})
    print(f"  target={target!r:16} -> abrió={_opened.get('url')!r} "
          f"resolved_from={r.get('resolved_from_name')!r}", flush=True)
# control: un dominio real NO debe re-resolverse
_opened.clear()
r = reg.t_browser({"action": "open", "url": "youtube.com"})
print(f"  target='youtube.com'    -> abrió={_opened.get('url')!r} (debe ser youtube.com directo)", flush=True)
