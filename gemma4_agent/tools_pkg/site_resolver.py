"""Resolución de NOMBRE de sitio -> URL real por búsqueda web.

Extraído de tools.py (2026-06-07) para bajar el LOC del archivo-dios sin perder
funcionalidad. Toda la lógica es la misma; la dependencia de red (web_search,
backends) y la config (hosts agregadores, fillers) se inyectan como parámetros
para que esto sea testeable y no acople a ToolRegistry.

Núcleo del comportamiento (NO hardcode — mide la FORMA, estado del SO):
  - PREFERIR el dominio que contiene el nombre pedido (es 'su' sitio).
  - DESEMPATAR sitios homónimos de distintos países por el ccTLD del país del
    usuario (estado del SO via GetUserGeoID — NO el idioma). 'portal uniej' existe
    en CL/PE/CO/SV; el del user (.cl) gana el empate.
  - Buscar en TODOS los backends de ddgs cuando el 1er pase no trae el dominio
    (o hay ambigüedad de país): cada motor indexa distinto.
  - NUNCA abrir basura: si nada matchea el nombre -> None (error honesto).

Fuentes/incidentes: 've a pivigames' (pivigames.blog no .com), 've a portal uniej'
(portal2.uniej.cl, no portalunab.mx ni el .pe). Ver CLAUDE.md (resolver por lookup).
"""
from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse

# Allowlist de dominios que SEGURO existen -> abrir directo sin verificar (evita
# latencia + falsos en sitios universales). NO es routing — es "esto existe,
# abrilo". Cualquier dominio fuera de acá que parezca adivinado por el LLM se verifica.
_KNOWN_REAL_DOMAINS = frozenset({
    "google", "youtube", "gmail", "github", "wikipedia", "facebook", "twitter",
    "x", "instagram", "reddit", "amazon", "netflix", "spotify", "twitch",
    "whatsapp", "linkedin", "tiktok", "discord", "stackoverflow", "chatgpt",
    "openai", "microsoft", "apple", "yahoo", "bing", "duckduckgo", "outlook",
    "live", "office", "steampowered", "epicgames", "ebay", "mercadolibre",
    "paypal", "dropbox", "drive", "maps", "translate", "wordpress", "medium",
})


def registrable_label(url: str):
    """Devuelve (SLD, TLD) de una URL/host SIN path real, o None si NO es
    candidata a 'dominio simple a verificar'. Normaliza esquema y www.
      'https://www.pivigames.com/' -> ('pivigames','com'); 'pivigames.com' ->
      ('pivigames','com'); 'https://github.com/u/repo' -> None (path real)."""
    u = (url or "").strip().lower()
    if not u:
        return None
    p = urlparse(u if "//" in u else "//" + u)   # tolera 'pivigames.com' sin esquema
    if (p.path not in ("", "/")) or p.query or p.fragment:
        return None   # path/query/fragment real -> URL deliberada, no tocar
    host = (p.hostname or "").lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 2 or not all(labels):
        return None   # no es etiqueta.tld (IP, host suelto, etc.)
    return labels[-2], labels[-1]


def is_probably_guessed_domain(url: str) -> bool:
    """True si `url` parece un dominio ADIVINADO por el LLM (le pegó .com a un
    nombre) y conviene VERIFICARLO por búsqueda antes de abrirlo. Señal estructural:
    UNA etiqueta + TLD genérico, SIN path, SIN subdominio, etiqueta NO en allowlist.
      'pivigames.com' -> True; 'google.com' -> False (allowlist); 'foo.com/bar' ->
      False (path); 'www.x.com' -> False (subdominio explícito)."""
    u = (url or "").strip().lower()
    if not u or "/" in u or " " in u:
        return False
    u = u.split("//")[-1]
    if "/" in u:
        return False
    parts = u.split(".")
    if len(parts) != 2:
        return False
    label, tld = parts
    if not label or label in _KNOWN_REAL_DOMAINS:
        return False
    _GUESSABLE_TLDS = {"com", "net", "org", "io", "co", "app"}
    return tld in _GUESSABLE_TLDS and label.isalnum() and len(label) >= 3


_USER_COUNTRY_CACHE: list[str | None] = []   # [code] o [None]; lista = memo de 1 slot


def user_country_code() -> str | None:
    """Código ISO-3166 alpha-2 del PAÍS del usuario según el ESTADO DEL SO (no una
    lista hardcoded): en Windows, la REGIÓN configurada (`GetUserGeoID` +
    `GetGeoInfo`). Sirve para DESEMPATAR cuando varios sitios igual de relevantes
    comparten nombre en países distintos ('portal uniej' existe en CL/PE/CO/SV) —
    preferimos el del país del usuario (su .cl). NO es el idioma: medido en esta
    PC el locale es es-MX pero la región es CL (el usuario está en Chile con
    Windows en español de México) -> usamos la REGIÓN, que es la ubicación real.
    Fallback multiplataforma: locale -> sufijo de país. None si no se puede
    determinar (entonces el desempate cae al ranking de búsqueda, sin daño)."""
    if _USER_COUNTRY_CACHE:
        return _USER_COUNTRY_CACHE[0]
    code: str | None = None
    try:
        import ctypes  # Windows: región del usuario (independiente del idioma)
        geo = ctypes.windll.kernel32.GetUserGeoID(16)  # GEOCLASS_NATION
        if geo:
            buf = ctypes.create_unicode_buffer(16)
            # GEO_ISO2 = 4 -> código de país de 2 letras (p.ej. 'CL')
            if ctypes.windll.kernel32.GetGeoInfoW(geo, 4, buf, 16, 0) and buf.value:
                code = buf.value.strip().upper() or None
    except Exception:
        code = None
    if not code:
        try:
            import locale
            loc = (locale.getlocale()[0] or "") or (locale.getdefaultlocale()[0] or "")
            # 'Spanish_Chile' / 'es_CL' -> intentar el sufijo de país
            m = re.search(r"[_-]([A-Za-z]{2})$", loc)
            if m:
                code = m.group(1).upper()
        except Exception:
            code = None
    _USER_COUNTRY_CACHE.append(code if (code and len(code) == 2 and code.isalpha()) else None)
    return _USER_COUNTRY_CACHE[0]


def ddgs_search(query: str, limit: int = 6) -> list[dict[str, str]]:
    """Búsqueda vía la librería `ddgs` (metasearch: Google/Brave/Bing/DDG/...).
    2026-06-07: primario sobre el scraper DDG-HTML (DDG indexa peor sitios chicos
    y rate-limitea). Con backend='google' el #0 coincide con el navegador del user.
    Gratis, sin API key. Fallback de backends google->brave->auto si uno falla."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []   # sin ddgs -> el provider cae a DDG-HTML/Bing (no rompe)
    for backend in ("google", "brave", "auto"):
        try:
            kw: dict[str, object] = {"max_results": limit}
            if backend != "auto":
                kw["backend"] = backend
            raw = DDGS().text(query, **kw) or []
        except Exception:
            raw = []
        if raw:
            out: list[dict[str, str]] = []
            for r in raw:
                url = str(r.get("href") or r.get("url") or "").strip()
                if not url:
                    continue
                item = {"title": str(r.get("title") or "")[:300], "url": url}
                _sn = r.get("body") or r.get("snippet")
                if _sn:
                    item["snippet"] = str(_sn)[:700]
                out.append(item)
                if len(out) >= limit:
                    break
            if out:
                return out
    return []


def ddgs_search_all_backends(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Igual que `_ddgs_search` pero AGREGA (no corta en el primero) los resultados
    de TODOS los backends y deduplica por host. Motivo (2026-06-07, bug 'portal
    uniej'): cada backend indexa distinto — para 'portalunab' el backend google
    devuelve basura (academicjobs) y se queda ahí, pero brave SÍ trae el dominio
    real (portal2.uniej.cl). El primario devuelve el primer backend con CUALQUIER
    resultado, así que nunca veía brave. Esta variante junta todo para que el
    resolvedor de sitio tenga el dominio real disponible. Preserva el orden
    (google primero = ranking que el user ve), el resto agrega lo que falte.
    Solo se usa en la RESOLUCIÓN de sitio (no en web_search general, que prioriza
    velocidad)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    seen_hosts: set[str] = set()
    merged: list[dict[str, str]] = []
    # backends que ddgs expone (NO 'bing' — no existe en ddgs; sí duckduckgo/brave/
    # google). Cada uno indexa distinto -> juntamos para no perder el dominio real.
    for backend in ("google", "brave", "duckduckgo", "auto"):
        try:
            kw: dict[str, object] = {"max_results": limit}
            if backend != "auto":
                kw["backend"] = backend
            raw = DDGS().text(query, **kw) or []
        except Exception:
            raw = []
        for r in raw:
            url = str(r.get("href") or r.get("url") or "").strip()
            if not url:
                continue
            try:
                host = (urlparse(url).hostname or "").lower()
            except Exception:
                host = ""
            if not host or host in seen_hosts:
                continue
            seen_hosts.add(host)
            item = {"title": str(r.get("title") or "")[:300], "url": url}
            _sn = r.get("body") or r.get("snippet")
            if _sn:
                item["snippet"] = str(_sn)[:700]
            merged.append(item)
    return merged


def resolve_site_by_search(
    name: str,
    *,
    web_search: Callable[[dict[str, Any]], dict[str, Any]],
    non_site_hosts: tuple[str, ...],
    fillers: "frozenset[str] | set[str]",
    search_all_backends: Callable[[str, int], list[dict[str, str]]] | None = None,
) -> str | None:
    """Resuelve el NOMBRE de un sitio ('pivigames') a la URL del SITIO vía
    búsqueda web. NO adivina el TLD (lookup real, CLAUDE.md). Heurística para
    no abrir el resultado equivocado:
      1. Filtrar agregadores/redes/estado-de-sitio (no son el sitio).
      2. PREFERIR resultados cuyo DOMINIO contiene el nombre buscado.
      3. Entre esos, preferir PATH más corto (homepage) y NORMALIZAR a la raíz.
      4. DESEMPATAR homónimos por el ccTLD del país del usuario.
      5. Si nada matchea el dominio -> None (error honesto, no abrir basura).

    `web_search` y `search_all_backends` se inyectan (el llamador pasa los suyos,
    así los tests pueden mockearlos sin red). None si no hay nada fiable."""
    name = (name or "").strip()
    if not name:
        return None
    if search_all_backends is None:
        search_all_backends = ddgs_search_all_backends
    try:
        r = web_search({"query": name, "limit": 8})
    except Exception:
        return None
    if not isinstance(r, dict) or not r.get("ok"):
        return None
    results = r.get("results") or []
    tok = re.sub(r"[^a-z0-9]", "", name.lower())
    # tokens individuales del nombre (>=3, sin fillers): 'portal uniej' -> {portal,uniej}.
    # Para el caso multi-palabra cuyo dominio NO concatena los tokens (portal2.uniej.cl):
    # 'portalunab' no es substring de 'portal2unabcl' pero AMBOS tokens sí aparecen.
    name_toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
                 if len(t) >= 3 and t not in fillers]

    def _host(u: str) -> str:
        try:
            return (urlparse(u).hostname or "").lower()
        except Exception:
            return ""

    def _is_agg(host: str, sld_norm: str) -> bool:
        # Es agregador SOLO si NO es el destino pedido (youtube.com para "youtube"
        # NO es agregador -> no filtrar).
        if tok and tok == sld_norm:
            return False
        return any(h in host for h in non_site_hosts)

    # país del usuario (estado del SO) para DESEMPATAR sitios homónimos.
    cc = (user_country_code() or "").lower()

    def _build_cands(res_list: list) -> list[tuple[int, int, int, int, int, str]]:
        cs: list[tuple[int, int, int, int, int, str]] = []
        for _idx, res in enumerate(res_list):
            u = str((res or {}).get("url") or "").strip()
            if not u.startswith(("http://", "https://")):
                continue
            host = _host(u)
            if not host:
                continue
            labels = host.split(".")
            sld = labels[-2] if len(labels) >= 2 else (labels[0] if labels else "")
            sld_norm = re.sub(r"[^a-z0-9]", "", sld)
            host_norm = re.sub(r"[^a-z0-9]", "", host)
            if _is_agg(host, sld_norm):
                continue
            all_toks = bool(name_toks) and all(t in host_norm for t in name_toks)
            if tok and tok == sld_norm:
                match_rank = 2          # el token ES la SLD (youtube.com) — fuerte
            elif (tok and tok in host_norm) or all_toks:
                # el nombre aparece en el host: concatenado o por tokens -> MISMO
                # rango para que el país desempate entre homónimos (.cl vs .pe).
                match_rank = 1
            else:
                match_rank = 0
            # DESEMPATE por país: ccTLD del usuario (.cl) o como label (uniej.edu.CL).
            country_bonus = 1 if (cc and (host.endswith("." + cc) or
                                          ("." + cc + ".") in ("." + host + "."))) else 0
            path = urlparse(u).path or "/"
            path_len = len([p for p in path.split("/") if p])  # 0 = homepage
            cs.append((match_rank, country_bonus, _idx, path_len, len(host), u))
        return cs

    cands = [c for c in _build_cands(results) if c[0] > 0]
    # ¿AMBIGÜEDAD por país? user con país pero ningún candidato del 1er pase en su
    # ccTLD (todos de otros países). El dominio del user puede estar en OTRO backend.
    country_ambiguous = bool(cc and cands and not any(c[1] for c in cands))
    if not cands or country_ambiguous:
        # 2do intento: AGREGAR todos los backends de ddgs. Cada motor indexa
        # distinto. Solo se paga el costo (~4s) cuando hace falta. NO hardcode.
        try:
            broad = search_all_backends(name, 12)
        except Exception:
            broad = []
        if broad:
            broad_cands = [c for c in _build_cands(broad) if c[0] > 0]
            if broad_cands:
                cands = broad_cands if (not cands or any(c[1] for c in broad_cands)) else cands
    if not cands:
        # nada matchea el nombre en su dominio -> NO abrir basura. Error honesto.
        return None
    # match_rank DESC, country_bonus DESC (ccTLD del user desempata homónimos),
    # google_pos ASC (ranking), path_len ASC (homepage), host_len ASC (canónico).
    cands.sort(key=lambda c: (-c[0], -c[1], c[2], c[3], c[4]))
    best_url = cands[0][5]
    p = urlparse(best_url)
    return f"{p.scheme}://{p.netloc}/"


__all__ = [
    "user_country_code", "ddgs_search", "ddgs_search_all_backends",
    "resolve_site_by_search", "registrable_label", "is_probably_guessed_domain",
    "_KNOWN_REAL_DOMAINS",
]
