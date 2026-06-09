"""EN VIVO (CLAUDE.md 3.5): el resolvedor de sitios sin la lista _NON_SITE_HOSTS,
con la señal estructural. Corre el LLM REAL con "ve a X" y captura la URL que se
abriría, mockeando SOLO el efecto físico (web_open_url) y la búsqueda web (para no
depender de la red), pero dejando vivo TODO el routing + el resolvedor real.
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

import gemma4_agent.tools_pkg.tools as T

# Resultados de búsqueda simulados por nombre (el 1er resultado es el agregador,
# para forzar el peor caso que la lista protegía).
_FAKE = {
    "pivigames": ["https://www.instagram.com/pivigames/", "https://pivigames.blog/"],
    "nasa": ["https://twitter.com/nasa", "https://www.nasa.gov/"],
    # POPULARIDAD: 'insta' -> instagram (popular, #0) gana al nicho insta.com.br.
    "insta": ["https://www.instagram.com/", "https://insta.com.br/"],
}
_orig_ws = T.ToolRegistry.web_search
def _web_search(self, args):
    q = str((args or {}).get("query") or "").strip().lower()
    for key, urls in _FAKE.items():
        if key in q:
            return {"ok": True, "results": [{"url": u, "title": key} for u in urls]}
    return {"ok": True, "results": []}
T.ToolRegistry.web_search = _web_search

_opened = []
_orig_open = T.ToolRegistry.web_open_url
def _web_open_url(self, args):
    _opened.append(str((args or {}).get("url") or ""))
    return {"ok": True, "url": (args or {}).get("url")}
T.ToolRegistry.web_open_url = _web_open_url

from gemma4_agent.agent_core.agent import Gemma4Agent

PHRASES = ["ve a pivigames", "andá a la página de pivigames", "abrí insta"]
print("\n=== resolvedor de sitios SIN lista (señal estructural) ===", flush=True)
for ph in PHRASES:
    agent = Gemma4Agent()
    agent.run_content("hola"); agent.history.clear()
    _opened.clear()
    r = agent.run_content(ph)
    reply = (getattr(r, "content", "") or "")[:80]
    print(f"\n  FRASE: {ph!r}", flush=True)
    print(f"  ABRIÓ: {_opened}", flush=True)
    print(f"  reply: {reply!r}", flush=True)
    # NO debe abrir instagram/twitter (agregador); SÍ el sitio real o nada.
    bad = any(("instagram.com" in u or "twitter.com" in u) for u in _opened)
    print(f"  -> {'MAL abrió agregador' if bad else 'OK (no agregador)'}", flush=True)
