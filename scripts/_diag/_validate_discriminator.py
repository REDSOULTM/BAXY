"""Valida el discriminador estructural _site_resolution_relevant ANTES de codearlo.

Criterio: el HOST resuelto debe guardar relación con el NOMBRE pedido. Señal:
  - algún TOKEN de contenido del nombre (>=3 chars) es substring del host
    normalizado, O
  - la mejor similitud difusa token<->SLD >= 0.75 (typo/variante).
Sin listas de dominios; solo forma. Multilingüe (folding NFKD).
"""
from __future__ import annotations

import re
import unicodedata
import difflib
from urllib.parse import urlparse


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Palabras de ANDAMIAJE genérico que NO identifican un sitio (multi-idioma).
# No es una lista de dominios ni de apps: es vocabulario de pedido ("abrí la
# PÁGINA de X", "la APLICACIÓN Y"). Si el único token que matchea es genérico,
# no cuenta como relevancia real.
_GENERIC_REQUEST_TOKENS = frozenset({
    "app", "apps", "aplicacion", "aplicaciones", "application", "applications",
    "pagina", "paginas", "page", "pages", "sitio", "sitios", "site", "sites",
    "web", "www", "com", "net", "org", "online", "portal",
})


def _site_resolution_relevant(name: str, resolved_url: str) -> bool:
    host = ""
    try:
        host = (urlparse(resolved_url).hostname or "").lower()
    except Exception:
        host = ""
    if not host:
        return False
    host_norm = re.sub(r"[^a-z0-9]", "", host)
    labels = host.split(".")
    sld = labels[-2] if len(labels) >= 2 else (labels[0] if labels else "")
    sld_norm = re.sub(r"[^a-z0-9]", "", sld)
    toks = [t for t in _fold(name).split()
            if len(t) >= 3 and t not in _GENERIC_REQUEST_TOKENS]
    if not toks:
        # nombre todo-genérico o demasiado corto: sin señal estructural fiable.
        return False
    for t in toks:
        if t in host_norm:
            return True
        if sld_norm and difflib.SequenceMatcher(None, t, sld_norm).ratio() >= 0.75:
            return True
    return False


CASES = [
    # (name, resolved_url, expected_relevant)
    ("aplicacion ZxqwInexistente9000", "https://www.softonic.com/downloads/applications", False),
    ("aplicacion ZxqwInexistente9000", "https://es.wikipedia.org/wiki/Aplicaci%C3%B3n", False),
    ("ZxqwInexistente9000", "https://www.softonic.com/downloads/applications", False),
    ("pivigames", "https://pivigames.blog/", True),
    ("gmail.com", "https://www.gmail.com/", True),
    ("gmail.com", "https://mail.google.com/", False),  # host no contiene 'gmail' (token), pero ver nota
    ("instant gaming", "https://www.instant-gaming.com/", True),
    ("portal uniej", "https://www.uniej.cl/", True),
    ("portal uniej", "https://aulavirtual.uniej.cl/login", True),
    ("notion", "https://www.notion.so/", True),
    ("canva", "https://www.canva.com/", True),
    # typo / voz: 'spotfy' -> spotify.com (fuzzy)
    ("spotfy", "https://www.spotify.com/", True),
    # gibberish que cae en agregador genérico
    ("qwzxcvbnm12345", "https://www.softonic.com/", False),
    # nombre genérico solo -> sin señal (debería rechazar, mejor honesto)
    ("la pagina web", "https://example.com/", False),
]

passed = 0
for nm, url, exp in CASES:
    got = _site_resolution_relevant(nm, url)
    ok = "OK " if got == exp else "MISS"
    if got == exp:
        passed += 1
    print(f"  [{ok}] relevant={got!s:5} (exp {exp!s:5}) {nm!r:40} -> {urlparse(url).hostname}")
print(f"\n{passed}/{len(CASES)} expectativas cumplidas")
