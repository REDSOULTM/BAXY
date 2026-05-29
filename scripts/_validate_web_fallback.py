"""B7 validación EN VIVO (HTTP real, sin GPU): ¿mi regex de Bing matchea el HTML
real? + ¿el provider cae a Bing cuando DDG viene vacío? Esto es lo único que los
unit-tests mockeados NO podían cubrir."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.tools_pkg import tools as T

print("=== 1. _bing_search contra HTML REAL (valida el regex) ===")
ok_bing = 0
for q in ["clima en buenos aires", "que es la fotosintesis", "python asyncio tutorial"]:
    try:
        res = T._bing_search(q, limit=5)
        print(f"[bing] '{q}' -> {len(res)} resultados")
        for r in res[:2]:
            print(f"   - {r.get('title','')[:65]!r}")
            print(f"     {r.get('url','')[:70]}")
        if res:
            ok_bing += 1
    except Exception as e:
        print(f"[bing] '{q}' FAIL: {type(e).__name__}: {e}")

print("\n=== 2. _web_search_provider: DDG vacío -> fallback a Bing ===")
os.environ["GEMMA4_WEB_FALLBACK"] = "1"
orig = T._duckduckgo_search
T._duckduckgo_search = lambda q, limit=6: []  # simula DDG bloqueado/rate-limited
try:
    name, res = T._web_search_provider("noticias de hoy", limit=5)
    print(f"[provider] DDG vacío -> motor={name} resultados={len(res)}")
    fallback_ok = (name == "bing_html_fallback" and len(res) > 0)
finally:
    T._duckduckgo_search = orig

print("\n=== 3. _web_search_provider: DDG OK -> NO toca Bing ===")
T._duckduckgo_search = lambda q, limit=6: [{"title": "ddg-real", "url": "http://x"}]
try:
    name, res = T._web_search_provider("x", limit=5)
    print(f"[provider] DDG ok -> motor={name} resultados={len(res)}")
    primary_ok = (name == "duckduckgo_html")
finally:
    T._duckduckgo_search = orig

print("\n=== VEREDICTO B7 ===")
print(f"  bing regex matchea HTML real: {ok_bing}/3 queries con resultados")
print(f"  fallback DDG-vacío -> Bing:   {'OK' if fallback_ok else 'FAIL'}")
print(f"  DDG-ok no toca Bing:          {'OK' if primary_ok else 'FAIL'}")
verdict = ok_bing >= 2 and fallback_ok and primary_ok
print(f"  => B7 {'LISTO PARA DEFAULT-ON' if verdict else 'NECESITA AJUSTE DE REGEX'}")
