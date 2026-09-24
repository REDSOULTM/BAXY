"""Games: launch, install, uninstall and query games in the Steam and Epic libraries. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _match, _has, _strip_request_envelope, _is_negative_effect_clause, _is_meta_or_tool_denial, _COVERAGE_ACTION_HEAD
from .intent import EffectIntent, _entity_key, _is_negated_match
from .catalog import GameCatalogIndex, build_game_catalog_index


def _corrected_game_launch_title(text: str) -> str | None:
    """Extract the final positive game title from one explicit self-correction."""

    corrected = re.fullmatch(
        (
            r"[¿?¡!\s]*(?:quitar|quita|remove|delete|uninstall)\b[^.;!?]{0,64}"
            r"\b(?:quiero\s+decir|i\s+mean|meant|mejor)\b\s*[,;:]?\s*"
            r"(?:poner|pon|play|launch|lanza|abrir|abre)\s+"
            r"(?:(?:el|the)\s+)?(?:(?:juego|game)\s+)?"
            r"(?P<title>[^.;!?]{1,120})[\s.!?]*"
        ),
        _fold(text),
        re.IGNORECASE,
    )
    if corrected is None:
        return None
    title = corrected.group("title").strip()
    return title if title else None


def _edit_distance(left: str, right: str) -> int:
    """Levenshtein distance with adjacent transpositions counted once."""

    previous = list(range(len(right) + 1))
    rows = [previous]
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            cost = 0 if a == b else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and a == right[j - 2] and left[i - 2] == b:
                value = min(value, rows[i - 2][j - 2] + 1)
            current.append(value)
        rows.append(current)
        previous = current
    return previous[-1]


_NEAR_GAME_ORDER = re.compile(
    r"^[\s¡!¿?]*(?:abre|abri|abrime|abris|lanza|lanzame|inicia|iniciame|pone|pon|poneme|juga|jugar\s+a|jugar|"
    r"ve\s+a|anda\s+a|andate\s+a|entra\s+a|vamos\s+a|open|launch|play|go\s+to|start)\s+"
    r"(?:(?:el|la|los|las|the|a|al)\s+)?(?P<target>[a-z0-9][a-z0-9 .'+-]{1,40}?)[\s.!?,]*$"
)


def near_catalog_game_candidates(
    text: str,
    games: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> tuple[str, ...]:
    """GAMES1533 «Ve a Mad de Rivals.»: the installed game names (at most two)
    that an open, launch or go-to order almost names — a word of five or more
    letters shared with the title, or the whole target one or two edits away —
    when the target matches no game exactly. Empty for anything else."""

    index = build_game_catalog_index(games)
    if not index.entries:
        return ()
    folded = _strip_request_envelope(_fold(text))
    if not folded or _has(folded, r"\b(?:no|nunca|jamas|never|don't|do\s+not)\b|\b(?:si|if|cuando|when)\b.{0,20}\b(?:termine|acabe|finish)\b"):
        return ()
    folded = re.sub(r"^(?:si|ok|dale|bueno|y|and)\s*[,.]?\s*(?:quema\s*,?\s*)?", "", folded, count=1).strip()
    request = _NEAR_GAME_ORDER.match(folded)
    if request is None:
        return ()
    target = request.group("target").strip(" ¿?¡!,:;.-")
    target = re.sub(r"\s*,?\s*(?:por\s+favor|porfa|please|pls)$", "", target).strip(" ,.")
    key = _entity_key(target)
    if not key or len(key) < 3 or len(key.split()) > 3:
        return ()
    if key in {"eso", "esto", "aquello", "ese", "esa", "este", "esta", "algo", "todo", "that", "this", "it"}:
        # «abrí eso» is a deictic, never a near miss of a short title (DSX).
        return ()
    if any(entry[0] == key for entry in index.entries):
        return ()
    target_tokens = {token for token in key.split() if len(token) >= 5}
    scored: list[tuple[int, str]] = []
    for normalized, _provider, _app_id, display in index.entries:
        name_tokens = set(normalized.split())
        if target_tokens & name_tokens:
            score = 0
        else:
            if len(key) < 5:
                continue
            distance = _edit_distance(key, normalized)
            if distance > 2:
                continue
            score = distance
        scored.append((score, display))
    scored.sort(key=lambda item: (item[0], item[1]))
    names: list[str] = []
    for score, name in scored:
        if score <= scored[0][0] and name not in names:
            names.append(name)
    return tuple(names[:2])


_STEAM_LIBRARY_VERB = (
    r"(?:descarga|descargar|descargame|descargate|baja|bajar|bajame|bajate|"
    r"instala|instalar|instalame|instalate|instalaes|install|download|"
    r"desinstala|desinstalar|desinstalame|desinstalate|uninstall|remove|"
    # «sacá X de Steam», «quitá X de Steam», «borrá X de Steam»: the same
    # removal named with the everyday verbs (the store after the title keeps a
    # screenshot or a photo out: see steam_library_title).
    r"saca|sacar|sacame|quita|quitar|quitame|elimina|eliminar|eliminame|borra|borrar|borrame|"
    # INSTALL1625 H0083 «lanzá Mortal Kombat en Steam»: launching a game the
    # library does not hold is answered by the same read.
    r"lanza|lanzar|lanzame|launch|run|juega|jugar|play|start|abre|abrir|abrime|open)"
)


_STEAM_LIBRARY_REQUEST = re.compile(
    r"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|podria|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
    rf"(?:me\s+)?{_STEAM_LIBRARY_VERB}\s+(?:(?:el|la|the)\s+)?(?:(?:juego|game)\s+)?"
    r"(?P<title>[a-z0-9][a-z0-9 .:'&+-]{0,80}?)"
    # INSTALL1625 H0387/H0721 «… en Teams»: the owner's transcriptions write
    # Steam as «Teams» (H0386/H0522); a game platform, never the meeting app.
    # H0578 «Descarga Fall guys en epic games»: the Epic Games launcher keeps the
    # same two facts locally; the store named after the title picks the library.
    r"\s+(?:en|de|desde|por|from|on|in|via|through)\s+"
    r"(?:(?:el|la|the)\s+)?(?P<store>steam|seam|stim|estim|teams|team|epic(?:\s+games)?(?:\s+(?:store|launcher))?|egs)"
    r"(?:\s+(?:por\s+favor|please|ahora|now))?[\s.!?]*"
)


def steam_library_verb(text: str) -> str | None:
    """REOPEN1993 grupo S: what a library request asks for — «install»
    (descarga, instala, baja), «uninstall» (desinstala, remove) or «launch»
    (lanza, abre, juega); None when the text is not a library request."""

    if steam_library_title(text) is None:
        return None
    folded = _strip_request_envelope(_fold(text)).strip()
    head = re.search(rf"\b{_STEAM_LIBRARY_VERB}\b", folded)
    if head is None:
        return None
    verb = head.group(0)
    if verb.startswith(("desinstal", "uninstall", "remove", "saca", "quita", "elimina", "borra")):
        return "uninstall"
    if verb.startswith(("descarg", "baja", "instal", "install", "download")):
        return "install"
    return "launch"


def game_library_store(text: str) -> str:
    """The store a library request names after the title: «epic» or «steam»."""

    folded = _strip_request_envelope(_fold(text)).strip()
    match = _STEAM_LIBRARY_REQUEST.fullmatch(folded.rstrip(".!?").strip())
    if match is None:
        for boundary in re.finditer(r"\. ", folded):
            match = _STEAM_LIBRARY_REQUEST.fullmatch(folded[: boundary.start()].rstrip(".!?").strip())
            if match is not None:
                break
    store = (match.group("store") if match is not None else "") or ""
    return "epic" if store.startswith(("epic", "egs")) else "steam"


def steam_library_title(text: str) -> str | None:
    """The game named by a Steam download/install/uninstall request.

    INSTALL1617 H0482 «Descarga Worms Rumble en Steam», H0049 «… en seam»,
    H0118 «Descarga doom eternal de steam», H0643 «Necesito que instalaes worms
    rumble en steam»: one verb, one title, Steam named after it. The title is
    returned with the person's own spelling and case; instructions after the
    request (AppIDs, URLs, a second sentence) keep the request out of this
    reader. Negations and meta talk abstain.
    """

    folded = _strip_request_envelope(_fold(text)).strip()
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    match = _STEAM_LIBRARY_REQUEST.fullmatch(folded.rstrip(".!?").strip())
    if match is None:
        # INSTALL1627 H0396/H0456: the request is followed by instructions
        # about the same install (an AppID, a steam:// URL, the store page);
        # the first sentence is the request, the rest names no other effect.
        # The sentence boundary is the first «. » after which the request
        # matches: «Plants vs. Zombies» carries a dot of its own (D13).
        for boundary in re.finditer(r"\. ", folded):
            head, rest = folded[: boundary.start()], folded[boundary.end():]
            if not _has(rest, r"\bapp\s*id\b|steam://|store\.steampowered\.com") or _has(
                rest, r"\b(?:luego|despues|then|y\s+(?:abre|lanza|abri|ejecuta|open|launch|run)|cierra|close)\b",
            ):
                continue
            match = _STEAM_LIBRARY_REQUEST.fullmatch(head.rstrip(".!?").strip())
            if match is not None:
                break
        if match is None:
            # INSTALL1633 H0608 «lanzá Mortal Kombat»: a launch of a bare name
            # with no platform; games are launched from Steam here, so the
            # library read answers when no installed game or catalog entry
            # claims the name (the caller checks those before reading).
            match = re.fullmatch(
                r"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
                r"(?:me\s+)?(?:lanza|lanzame|lanzar|launch|juega|juga|jugar|jugame|jugemos)\s+"
                r"(?:(?:el|la|the|a|al)\s+)?(?:(?:juego|game)\s+)?"
                r"(?P<title>[a-z0-9][a-z0-9'&+-]*(?:\s+[a-z0-9][a-z0-9'&+-]*){0,3})"
                r"(?:[\s,]+(?:por\s+favor|please|ahora|now))?",
                folded.rstrip(".!?").strip(),
            )
            if match is not None and _has(
                match.group("title"),
                r"^(?:todo|todos|todas|eso|esto|aquello|algo|nada|lo|la|el|ese|esa|este|esta|los|las|un|una|mi|mis|"
                r"it|this|that|them|my|the|something|anything|un\s+juego|a\s+game|algun\s+juego|any\s+game)$|"
                # Uso real 2026-09-24 «jugar un juego de carreras», «quiero jugar un partida de trivial»: a kind
                # of game names no title; «puedes jugar póker conmigo» asks BAXY to play, not to launch a game.
                r"^(?:un|una|unos|unas|a|an|algun|alguna|some|any)\s|\b(?:conmigo|with\s+me|contra\s+mi|against\s+me)$",
            ):
                match = None
        if match is None:
            return None
    title = match.group("title").strip(" .")
    if not title or _has(title, r"^(?:el|la|the|un|una|a|an|juego|game|algo|something)$"):
        return None
    if _has(folded, r"^[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|podria|please)\s+(?:que\s+)?)?(?:me\s+)?(?:saca|sacar|sacame|quita|quitar|quitame|elimina|eliminar|eliminame|borra|borrar|borrame)\b") and _has(
        title, r"^(?:un|una|unos|unas|los|las|mi|mis|tu|tus|captura|foto|screenshot|pantallazo|imagen|dinero|plata|fondos|saldo)\b"
    ):
        # «sacá una captura de Steam», «sacá la plata de Steam»: not a game.
        return None
    raw = str(text)
    folded_raw = _fold(raw)
    if len(folded_raw) == len(raw):
        position = folded_raw.find(title)
        if position >= 0:
            return raw[position:position + len(title)]
    return title


def _steam_install_status_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Read installation status only for one literal Steam AppID."""

    if "game.install.status" not in available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:comprueba|comprobar|verifica|verificar|consulta|"
            r"check|verify|show|read)\b\s+"
            r"(?:(?:el|the)\s+)?"
            r"(?:estado|status)\s+(?:de\s+|of\s+)?"
            r"(?:la\s+|the\s+)?(?:instalacion|installation)\s+"
            r"(?:del?|of\s+the)\s+(?:appid|app id)\s+\d{1,16}[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("game.install.status",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _steam_install_cancel_active_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Stop the download Steam is already running, not a torrent or a listing."""

    if "game.install.cancel.active" not in available:
        return None
    if _has(text, r"\b(?:torrent|series|pelicula|movie)\b"):
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:para|cancela|cancelar|cancel|stop|detene|"
            r"detener)\b.{0,96}\b(?:descarga|download|instalacion|install)"
            r"\b.{0,96}\bsteam\b.{0,48}$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("game.install.cancel.active",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _steam_catalog_list_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """List the authenticated local Steam catalog from an explicit clause."""

    if "game.catalog.list" not in available:
        return None
    request = _match(
        text,
        (
            # GAMES1531 H0274 «Ver la biblioteca de Steam»: seeing or being shown
            # the library is the same read-only listing of the local manifests.
            r"^[¿?¡!\s]*(?:(?:primero|first)\s+)?"
            r"(?:enumera|enumerar|enumerate|lista|listar|list|muestra|show|"
            r"ver|mirar|mostrame|muestrame|ensename|dame|quiero\s+ver|see|view)\b"
            r"(?P<scope>[^.;!?]{0,100})"
            r"\b(?:catalogo|catalog|biblioteca|library)\b"
            r"[^.;!?]{0,80}\bsteam\b[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    if _has(
        request.group("scope"),
        rf"\b(?:y|and)\s+(?:{_COVERAGE_ACTION_HEAD})\b",
    ):
        return None
    return EffectIntent(
        ("game.catalog.list",),
        (request.group(0).strip(" ,;:-")[:240],),
    )
