"""MEDICIÓN (no fix): ¿la lista _NON_SITE_HOSTS sigue cambiando decisiones del
resolvedor de sitios, o el filtro estructural (match_rank>0, que exige el nombre
en el DOMINIO) ya cubre el caso? Y: ¿una señal 'nombre-en-path-dominio-ajeno'
reemplazaría a la lista de forma universal (incl. agregadores no-occidentales)?

Corre el resolvedor REAL con resultados de búsqueda MOCKEADOS (sin red): para
cada caso inyectamos la lista de URLs que un buscador devolvería y vemos qué URL
elige el resolvedor (a) CON la lista actual y (b) SIN la lista (lista vacía). Si
las decisiones coinciden en todos los casos -> la lista es redundante y se puede
quitar. Donde difieran -> ahí la lista aún aporta; medimos si la señal estructural
las cubre.
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

from gemma4_agent.tools_pkg.site_resolver import resolve_site_by_search

# Lista actual (copiada del código para el harness; el test real la importa).
_NON_SITE_HOSTS = (
    "reddit.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "threads.com", "threads.net", "t.me", "telegram.me", "youtube.com",
    "tiktok.com", "linktr.ee", "patreon.com", "ipaddress.com", "downornot",
    "notopening.com", "shapes.inc", "pinterest.com", "linkedin.com",
    "wikipedia.org", "play.google.com", "apps.apple.com",
)
_FILLERS = frozenset({"el", "la", "los", "las", "de", "del", "a", "al", "y",
                      "the", "to", "go", "ir", "ve", "anda", "anetra"})


def _mk_search(results):
    def _search(args):
        return {"ok": True, "results": [{"url": u} for u in results]}
    return _search


def _resolve(name, results, hosts):
    return resolve_site_by_search(
        name,
        web_search=_mk_search(results),
        non_site_hosts=hosts,  # DEPRECADO: ya no tiene efecto (señal estructural)
        fillers=_FILLERS,
        search_all_backends=lambda q, lim=12: [],
    )


# CASOS: (nombre pedido, [urls que el buscador devuelve en orden], comentario)
# El 1er resultado suele ser el agregador (peor caso para el resolvedor).
CASES = [
    ("pivigames",
     ["https://www.instagram.com/pivigames/", "https://pivigames.blog/"],
     "perfil IG primero, sitio real 2do (caso clásico)"),
    ("pivigames",
     ["https://www.reddit.com/r/pivigames/", "https://www.facebook.com/pivigames",
      "https://pivigames.blog/juegos"],
     "varias redes antes del sitio"),
    ("youtube",
     ["https://www.youtube.com/"],
     "el nombre ES la plataforma (la lista NO debe filtrarla)"),
    ("instagram",
     ["https://www.instagram.com/"],
     "pedir la red en sí (no debe filtrarse)"),
    ("nasa",
     ["https://www.instagram.com/nasa/", "https://twitter.com/nasa",
      "https://www.nasa.gov/"],
     "marca con redes muy posicionadas + sitio .gov"),
    # NO-OCCIDENTALES: agregadores que la lista NO cubre.
    ("algunjuego",
     ["https://vk.com/algunjuego", "https://algunjuego.ru/"],
     "VK (Rusia) NO está en la lista -> ¿se cuela?"),
    ("algunmarca",
     ["https://weibo.com/algunmarca", "https://www.algunmarca.cn/"],
     "Weibo (China) NO está en la lista -> ¿se cuela?"),
    ("algunsitio",
     ["https://cafe.naver.com/algunsitio", "https://algunsitio.co.kr/"],
     "Naver cafe (Corea) NO está en la lista -> ¿se cuela?"),
    # Substring del nombre dentro de un agregador (donde match_rank podría >0).
    ("reddit",
     ["https://www.reddit.com/"],
     "pedir reddit en sí (token==SLD, no filtrar)"),
]

print("=" * 78)
print(f"{'NAME':14} {'CON lista':28} {'SIN lista':28}  ¿IGUAL?")
print("=" * 78)
diffs = []
for name, results, note in CASES:
    with_list = _resolve(name, results, _NON_SITE_HOSTS)
    without = _resolve(name, results, ())
    same = with_list == without
    if not same:
        diffs.append((name, with_list, without, note))
    flag = "sí" if same else "NO <<<"
    print(f"{name:14} {str(with_list)[:27]:28} {str(without)[:27]:28}  {flag}")
    print(f"   {note}")

print("\n" + "=" * 78)
if not diffs:
    print("La lista NO cambia ninguna decisión en estos casos -> el filtro")
    print("estructural (match_rank exige nombre en el DOMINIO) ya cubre todo.")
else:
    print(f"La lista cambia {len(diffs)} decisión(es). Donde SIN-lista elige el")
    print("agregador, hay que ver si la señal 'nombre-en-path' lo descartaría:")
    for name, wl, wo, note in diffs:
        print(f"  - {name!r}: con={wl} sin={wo} ({note})")
