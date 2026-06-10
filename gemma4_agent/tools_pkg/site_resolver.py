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
(portal2.uniej.cl, no portalunab.mx ni el .pe). Ver las reglas del proyecto (resolver por lookup).
"""
from __future__ import annotations

import os
import re
import socket
import unicodedata
from typing import Any, Callable
from urllib.parse import urlparse


def _dns_host_resolves(host: str) -> bool:
    """¿El host existe (DNS resuelve)? Evita abrir un dominio muerto que matcheó
    el nombre pero no existe (incidente real: 'insta' -> insta.com.br, DNS
    ERR_NAME_NOT_RESOLVED). Best-effort y rápido: ante CUALQUIER duda devuelve
    True (fail-open — no descartar un sitio bueno por un timeout de red). Solo un
    NXDOMAIN claro (gaierror) cuenta como 'no existe'."""
    host = (host or "").strip().lower()
    if not host:
        return False
    try:
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2.5)
        try:
            socket.getaddrinfo(host, None)
            return True
        finally:
            socket.setdefaulttimeout(old)
    except socket.gaierror:
        return False        # NXDOMAIN / nombre no resoluble -> no existe
    except Exception:
        return True         # timeout/otro -> fail-open (no penalizar por la red)


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


_WEB_NAVIGATION_PATTERNS = (
    r"\babr(?:e|i|ir|ime|eme)\b",
    r"\b(?:and(?:a|ate)|ve|entra|entrar|visita|visitar|navega|navegar)\s+(?:a|al|la|el|un|una|en)\b",
    r"\b(?:lleva|llevame|ponme|poneme)\s+(?:a|al|en)\b",
    r"\bgo\s+to\b",
    r"\bnavigate\s+to\b",
    r"\bopen\b",
    r"\bvisit\b",
    r"\btake\s+me\s+to\b",
)


def _fold_user_text(text: str) -> str:
    n = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in n if not unicodedata.combining(ch))


def user_requested_web_navigation(user_text: str) -> bool:
    """True when the user's text asks to navigate/open a web page.

    This is an intent-shape guard for tool preconditions, not a target list:
    factual prompts such as "quien es X" should read/synthesize, while
    navigation prompts such as "ve a X" or "open X" may open a visible browser.
    """
    folded = _fold_user_text(user_text)
    if not folded:
        return False
    return any(re.search(pat, folded) for pat in _WEB_NAVIGATION_PATTERNS)


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


def user_requested_open(url: str, user_text: str) -> bool:
    """¿El comando pide ABRIR/VER esta URL (con el dominio dictado), o el 4B la eligió para
    'mostrar' una respuesta? True si la raíz del host aparece en el texto del user
    -> intención explícita de abrir. False si no la dictó (web.open de conocimiento
    -> conviene leer el contenido y responder, no abrir un tab). Sin user_text ->
    True (no inferir; abrir normal en CLI/tests). PROCEDENCIA, no keywords."""
    ut = (user_text or "").strip().lower()
    if not ut:
        return True
    if user_requested_web_navigation(ut):
        return True
    try:
        host = (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    except Exception:
        return True
    root = host[4:] if host.startswith("www.") else host
    if not root:
        return True
    return root in ut


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


def _ddgs_timeout() -> int:
    """Timeout (s) POR backend de ddgs. La librería default a 10 s/petición y
    `ddgs_search` prueba HASTA 3 backends → peor caso 30 s. MEDIDO (2026-06-09,
    con datos móviles/red mala): ese encadenamiento daba 17-32 s y el 2do pase del
    LLM no podía empezar hasta que la búsqueda terminara (lo que el usuario siente
    como 'tarda mucho en arrancar'). Con un timeout corto el peor caso se acota y
    el backend que responde rápido gana. Override `GEMMA4_DDGS_TIMEOUT` (default 5)."""
    try:
        return max(2, min(10, int(os.environ.get("GEMMA4_DDGS_TIMEOUT", "5") or "5")))
    except (TypeError, ValueError):
        return 5


def ddgs_search(query: str, limit: int = 6, timeout: int | None = None) -> list[dict[str, str]]:
    """Búsqueda vía la librería `ddgs` (metasearch: Google/Brave/Bing/DDG/...).
    2026-06-07: primario sobre el scraper DDG-HTML (DDG indexa peor sitios chicos
    y rate-limitea). Con backend='google' el #0 coincide con el navegador del user.
    Gratis, sin API key. Fallback de backends google->brave->auto si uno falla.
    `timeout` (s) por backend acota la espera con red mala (default `_ddgs_timeout`)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []   # sin ddgs -> el provider cae a DDG-HTML/Bing (no rompe)
    _to = timeout if timeout is not None else _ddgs_timeout()
    for backend in ("google", "brave", "auto"):
        try:
            kw: dict[str, object] = {"max_results": limit}
            if backend != "auto":
                kw["backend"] = backend
            raw = DDGS(timeout=_to).text(query, **kw) or []
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
    _to = _ddgs_timeout()   # timeout por backend (red mala: acota el peor caso)
    seen_hosts: set[str] = set()
    merged: list[dict[str, str]] = []
    # backends que ddgs expone (NO 'bing' — no existe en ddgs; sí duckduckgo/brave/
    # google). Cada uno indexa distinto -> juntamos para no perder el dominio real.
    # PARALELO (2026-06-10): los 4 backends son requests HTTP independientes; en
    # serie el peor caso es 4×timeout (MEDIDO 8.6-11s en red móvil, y app.open lo
    # repagaba en cada miss delegado a sitio). En paralelo el wall ≈ el backend
    # más lento (≤1×timeout). El MERGE preserva el orden secuencial (google
    # primero = el ranking que el user ve) y la dedup por host es idéntica.
    backends = ("google", "brave", "duckduckgo", "auto")

    def _one_backend(backend: str) -> list:
        try:
            kw: dict[str, object] = {"max_results": limit}
            if backend != "auto":
                kw["backend"] = backend
            return DDGS(timeout=_to).text(query, **kw) or []
        except Exception:
            return []

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(backends)) as _ex:
        raws = list(_ex.map(_one_backend, backends))
    for raw in raws:
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
    fillers: "frozenset[str] | set[str]",
    search_all_backends: Callable[[str, int], list[dict[str, str]]] | None = None,
    dns_resolves: Callable[[str], bool] | None = None,
    non_site_hosts: tuple[str, ...] = (),  # DEPRECATED: ya no se usa (señal estructural)
) -> str | None:
    """Resuelve el NOMBRE de un sitio ('pivigames') a la URL del SITIO vía
    búsqueda web. NO adivina el TLD (lookup real, las reglas del proyecto). Heurística para
    no abrir el resultado equivocado:
      1. Descartar agregadores/redes/perfiles de tercero por SEÑAL ESTRUCTURAL:
         el nombre debe ser un LABEL COMPLETO del dominio (o, en un resultado TOP
         del buscador, PREFIJO de un label = popularidad), no aparecer solo en el
         path. Reemplaza la vieja lista _NON_SITE_HOSTS (universal, sin hardcode).
      2. POPULARIDAD: entre candidatos válidos, la POSICIÓN del buscador manda
         (insta -> instagram.com #0 le gana a insta.com.br #1, sitio nicho).
      3. PATH más corto (homepage) y NORMALIZAR a la raíz.
      4. DESEMPATAR homónimos por el ccTLD del país del usuario.
      5. NO devolver un dominio que no EXISTE (DNS no resuelve): cae al siguiente.
      6. Si nada matchea el dominio -> None (error honesto, no abrir basura).

    `web_search`/`search_all_backends`/`dns_resolves` se inyectan (el llamador pasa
    los suyos, así los tests mockean sin red). None si no hay nada fiable."""
    if dns_resolves is None:
        dns_resolves = _dns_host_resolves
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
            # labels normalizados del host (sin TLD-only: cada etiqueta del dominio).
            labels_norm = [re.sub(r"[^a-z0-9]", "", lab) for lab in labels]
            # SEÑAL ESTRUCTURAL anti-agregador (2026-06-09, reemplaza la lista
            # _NON_SITE_HOSTS): un nombre pedido identifica AL SITIO solo si es un
            # LABEL COMPLETO del dominio (pivigames == label de pivigames.blog), NO
            # un substring PARCIAL de un label (insta ⊂ 'instagram', reddi ⊂
            # 'reddit', face ⊂ 'facebook'). Esto descarta perfiles/redes de tercero
            # SIN una lista de dominios — universal (cubre VK/Weibo/Naver y lo que
            # se invente). El path con el nombre (instagram.com/foo) ya cae solo:
            # 'foo' no está en NINGÚN label de instagram.com -> match_rank 0. Ver
            # scripts/_diag/_diag_non_site_hosts.py para la medición.
            tok_is_label = bool(tok) and tok in labels_norm
            # CADA token de contenido (post-filler) debe ser un LABEL COMPLETO del
            # host. Esto:
            #  - cubre 'portal uniej' -> portal.uniej.edu.sv (si 'portal' es filler,
            #    queda ['uniej'] y 'uniej' ES un label) y 'portal'+'uniej' explícitos;
            #  - DESCARTA el fragmento de red: 'insta' (1 token) NO es label de
            #    instagram.com (el label es 'instagram') -> no califica como label
            #    exacto; 'insta' SÍ es label de insta.com.br.
            # Universal y sin lista de dominios.
            toks_are_labels = bool(name_toks) and all(t in labels_norm for t in name_toks)
            # POPULARIDAD (2026-06-09): el nombre es PREFIJO de un label del host
            # (insta ⊂ 'instagram', face ⊂ 'facebook') Y ese host está en el TOP
            # del ranking del buscador. Señal de popularidad PURA (posición del
            # motor, no una lista de dominios): si pedís 'insta' e instagram.com
            # sale #0, casi seguro querés Instagram, no un sitio nicho 'insta.com.br'
            # enterrado (que además puede estar muerto). Exigimos PREFIJO de label
            # (no substring en cualquier parte) para no premiar coincidencias
            # accidentales, y TOP del ranking para que sea el canónico que la gente
            # busca. NO aplica al nombre en el PATH (instagram.com/foo): 'foo' no es
            # prefijo de NINGÚN label del host -> sigue cayendo a match_rank 0.
            _TOP_RANK_FOR_POPULARITY = 3   # primeros N resultados del buscador
            tok_prefixes_label = bool(tok) and any(
                lab.startswith(tok) and lab != tok for lab in labels_norm)
            if tok and tok == sld_norm:
                match_rank = 3          # el token ES la SLD (youtube.com) — fuerte
            elif tok_is_label or toks_are_labels:
                # el nombre concatenado es un LABEL completo del host (subdominio/
                # SLD), o cada token de contenido es un label -> país desempata
                # homónimos (.cl vs .pe).
                match_rank = 2
            elif tok_prefixes_label and _idx < _TOP_RANK_FOR_POPULARITY:
                # PREFIJO de un label en un resultado TOP -> popularidad: compite,
                # pero por DEBAJO del label exacto (un label exacto top le gana; un
                # prefijo-top le gana a un label exacto ENTERRADO abajo).
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
    # ORDEN:
    #  1. country_bonus DESC: el ccTLD del país del user desempata homónimos.
    #  2. is_sld DESC: si el nombre ES la SLD (youtube -> youtube.com), ese es EL
    #     sitio canónico y gana SIEMPRE — la popularidad NO lo invierte (no quiero
    #     que blog.youtube #0 le gane a youtube.com).
    #  3. google_pos ASC: POPULARIDAD entre los demás. 'insta' -> instagram.com #0
    #     (prefijo, popular) le gana a insta.com.br #1 (label exacto pero nicho).
    #  4. match_rank DESC: a igual posición, label exacto > prefijo.
    #  5. path_len ASC (homepage) -> host_len ASC (canónico).
    cands.sort(key=lambda c: (-c[1], -(c[0] == 3), c[2], -c[0], c[3], c[4]))
    # NO devolver un dominio que no EXISTE: recorremos los candidatos en orden y
    # devolvemos el PRIMERO cuyo host resuelve por DNS (incidente real: 'insta' ->
    # insta.com.br, ERR_NAME_NOT_RESOLVED). dns_resolves hace fail-open ante
    # timeouts -> solo descarta un NXDOMAIN claro. Si NINGÚN candidato resuelve
    # (todos son dominios muertos), devolvemos None: error honesto, NO abrir una
    # página rota. Las páginas que no existen no deben ganar.
    for c in cands:
        p = urlparse(c[5])
        if dns_resolves(p.hostname or ""):
            return f"{p.scheme}://{p.netloc}/"
    return None


__all__ = [
    "user_country_code", "ddgs_search", "ddgs_search_all_backends",
    "resolve_site_by_search", "registrable_label", "is_probably_guessed_domain",
    "user_requested_open", "user_requested_web_navigation",
    "_KNOWN_REAL_DOMAINS",
]
