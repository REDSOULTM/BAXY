"""Application and game catalog indexes: the installed names a request can point at, their aliases and provider ids. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Iterator
from .grammar import _fold, _match, _has, _strip_request_envelope, _OPEN
from .intent import _entity_key, _is_negated_match


MAX_APPLICATION_CATALOG_ENTRIES = 2_048


MAX_APPLICATION_CATALOG_PATTERN_CHARS = 1_048_576


MAX_GAME_CATALOG_ENTRIES = 4_096


@dataclass(frozen=True, slots=True)
class ApplicationCatalogIndex:
    """Bounded, reusable view of one authenticated application snapshot."""

    entries: tuple[tuple[str, str], ...]
    keys: frozenset[str] = field(repr=False)
    entity_identities: tuple[tuple[str, str], ...] = field(repr=False)
    occurrence_pattern: re.Pattern[str] | None = field(
        repr=False,
        compare=False,
    )

    def __iter__(self) -> Iterator[str]:
        return (name for name, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class GameCatalogIndex:
    """Bounded authenticated identities for locally installed games."""

    # normalized name, provider, app id, display name
    entries: tuple[tuple[str, str, str, str], ...] = ()


def build_game_catalog_index(
    entries: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> GameCatalogIndex:
    """Validate and normalize a bounded Core-authenticated game snapshot."""

    if isinstance(entries, GameCatalogIndex):
        return entries
    retained: list[tuple[str, str, str, str]] = []
    identities: set[tuple[str, str]] = set()
    provider_names: set[tuple[str, str]] = set()
    for entry in entries:
        if (
            not isinstance(entry, (tuple, list))
            or len(entry) != 3
            or not all(isinstance(value, str) for value in entry)
        ):
            raise ValueError("invalid game catalog entry")
        provider, app_id, name = entry
        if len(retained) >= MAX_GAME_CATALOG_ENTRIES:
            raise ValueError("game catalog entry limit exceeded")
        if provider not in {"steam", "epic"}:
            raise ValueError("invalid game catalog provider")
        if (
            not app_id
            or len(app_id) > 16
            or re.fullmatch(r"[A-Za-z0-9._-]+", app_id) is None
        ):
            raise ValueError("invalid game catalog app id")
        display_name = name
        key = _entity_key(display_name)
        identity = (provider, app_id)
        provider_name = (provider, key)
        if (
            not display_name.strip()
            or "\ufffd" in display_name
            or any(
                unicodedata.category(character) == "Cc"
                or character.isspace()
                and character != " "
                for character in display_name
            )
            or not key
            or len(display_name.encode("utf-8")) > 512
            or identity in identities
            or provider_name in provider_names
        ):
            raise ValueError("ambiguous game catalog entry")
        identities.add(identity)
        provider_names.add(provider_name)
        retained.append((key, provider, app_id, display_name))
    retained.sort(key=lambda item: (item[0], item[1], item[2]))
    return GameCatalogIndex(tuple(retained))


def _authenticated_game_target(
    text: str,
    game_catalog: GameCatalogIndex,
) -> tuple[str, str, str] | None:
    """Resolve one exact or numeric-edition-prefix installed game title."""

    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:(?:vamos\s+a\s+)?(?:juega|juga|jugar|juguemos|play)|"
            # H0682 «Ve a Mad de Rivals.», H0083 «lanzá Mortal Kombat en Steam»:
            # a go-to or start order on an installed title launches it too.
            r"(?:ve|anda|andate|entra|go)\s+(?:a|al|to)|inicia|iniciame|start|"
            rf"(?:{_OPEN}|lanza|launch|ejecuta|run))\b\s+"
            r"(?:(?:al|el|the)\s+)?(?:(?:juego|game)\s+)?"
            r"(?P<title>.+?)"
            r"(?:\s+(?:modo|mode)\s+(?:multijugador|multiplayer))?"
            r"(?:\s+(?:desde|en|from|on)\s+(?:steam|epic(?:\s+games)?))?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    target_key = _entity_key(request.group("title"))
    if not target_key:
        return None
    exact = [entry for entry in game_catalog.entries if entry[0] == target_key]
    candidates = exact or [
        entry
        for entry in game_catalog.entries
        if entry[0].startswith(target_key + " ")
        and re.fullmatch(r"\d+", entry[0][len(target_key) + 1 :]) is not None
    ]
    if not candidates:
        # A title named without its edition suffix («PICO PARK» for «PICO
        # PARK:Classic Edition», «Plants vs. Zombies» for the GOTY edition) is
        # that game when exactly one installed title starts so (D24: unique
        # candidate → act).
        candidates = [
            entry
            for entry in game_catalog.entries
            if entry[0].startswith(target_key + " ")
            or re.match(re.escape(target_key) + r"\s*[:(\-–]", _fold(entry[3]).strip()) is not None
        ]
    identities = {(entry[1], entry[2]) for entry in candidates}
    if len(identities) != 1:
        return None
    selected = candidates[0]
    return selected[1], selected[2], selected[3]


def resolve_game_catalog_app_id(
    text: str,
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> str | None:
    """Return one authenticated local AppID for a request or exact title."""

    index = build_game_catalog_index(game_catalog)
    request_target = _authenticated_game_target(_fold(text), index)
    if request_target is not None:
        return request_target[1]
    key = _entity_key(text)
    matches = [entry for entry in index.entries if entry[0] == key]
    identities = {(entry[1], entry[2]) for entry in matches}
    return matches[0][2] if len(identities) == 1 else None


def _application_name_key(value: str) -> str:
    """Normalize case/spacing while preserving an app name's punctuation."""

    return _fold(value)


def build_application_catalog_index(
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> ApplicationCatalogIndex:
    """Normalize and compile an authenticated catalog exactly once."""

    if isinstance(application_names, ApplicationCatalogIndex):
        return application_names
    retained: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in application_names:
        if not isinstance(name, str):
            continue
        key = _application_name_key(name)
        if not key or key in seen:
            continue
        if len(retained) >= MAX_APPLICATION_CATALOG_ENTRIES:
            raise ValueError("application catalog exceeds entry limit")
        seen.add(key)
        retained.append((name, key))
    retained.sort(key=lambda item: (-len(item[1]), item[1]))
    escaped_names = tuple(re.escape(key) for _, key in retained)
    pattern_chars = sum(len(name) + 1 for name in escaped_names)
    if pattern_chars > MAX_APPLICATION_CATALOG_PATTERN_CHARS:
        raise ValueError("application catalog exceeds pattern limit")
    occurrence_pattern = (
        re.compile(
            (r"(?<![a-z0-9])(?P<target>" + "|".join(escaped_names) + r")(?![a-z0-9])"),
            re.IGNORECASE,
        )
        if escaped_names
        else None
    )
    return ApplicationCatalogIndex(
        entries=tuple(retained),
        keys=frozenset(seen),
        entity_identities=tuple((_entity_key(name), key) for name, key in retained),
        occurrence_pattern=occurrence_pattern,
    )


_CATALOG_NAME_ALIASES: tuple[tuple[frozenset[str], tuple[str, ...]], ...] = (
    (frozenset({"calc", "calculator", "calculadora"}), ("calculadora", "calculator")),
    (frozenset({"notepad", "bloc de notas", "app de notas", "coso de notas",
                "editor de texto"}), ("bloc de notas", "notepad")),
    (frozenset({"explorador", "explorador de archivos", "explorador de windows",
                "file explorer", "files explorer", "explorer", "windows explorer"}),
     ("explorador de archivos", "file explorer")),
    # UI1731 «Abre Epic Games y navega hasta la biblioteca»: the Start catalog
    # names the client «Epic Games Launcher»; people say «Epic Games» or «Epic».
    (frozenset({"epic", "epic games", "epic launcher", "epic games launcher", "launcher de epic"}),
     ("epic games launcher",)),
    # UI1735 «en Opera hacé clic en …»: the Start catalog names the browser
    # «Navegador Opera GX»; people say «Opera» or «Opera GX».
    (frozenset({"opera", "opera gx", "navegador opera", "navegador opera gx", "opera browser"}),
     ("navegador opera gx", "opera gx", "opera")),
)


def _catalog_alias_key(target_key: str, keys: frozenset[str]) -> str | None:
    """Map a bilingual alias to the one catalog key it names, if installed."""

    if target_key in keys:
        return target_key
    for aliases, catalog_names in _CATALOG_NAME_ALIASES:
        if target_key in aliases:
            for name in catalog_names:
                if name in keys:
                    return name
    return None


def _installed_game_named(name: str, game_catalog: GameCatalogIndex) -> str | None:
    """The display name of the installed game that a bare name matches
    exactly (folded), or None."""

    wanted = _fold(name).strip()
    for normalized, _provider, _app_id, display in game_catalog.entries:
        if normalized == wanted or _fold(display).strip() == wanted:
            return display
    # A title named without its edition suffix («Plants vs. Zombies» for «Plants
    # vs. Zombies: Game of the Year») is that game when exactly one starts so.
    prefixed = [
        display for normalized, _provider, _app_id, display in game_catalog.entries
        if normalized.startswith(wanted + " ") or re.match(re.escape(wanted) + r"\s*[:(\-–]", _fold(display).strip())
    ]
    return prefixed[0] if len(prefixed) == 1 else None


def installed_game_title(text: str) -> str | None:
    """Read the game named by an installed question («dime si X ya está instalado»).

    APPS1613 H0275: the clause is the person's folded surface; the title is
    everything between the question head and the installed predicate, without
    the article, «el juego» or «ya».  Free mentions and other shapes abstain.
    """

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".?!").strip()
    match = re.fullmatch(
        r"(?:[¿?¡!\s]*(?:y|and|luego|then)\s+)?"
        r"(?:decime|dime|contame|cuentame|tell\s+me|fijate|chequea|check|"
        r"comprueba|verifica|revisa|verify|confirm|confirma)\s+"
        r"(?:si|if|whether)\s+"
        r"(?:tengo\s+(?:instalado\s+)?|i\s+have\s+(?:installed\s+)?)?"
        r"(?:(?:el|la|the)\s+)?(?:(?:juego|game)\s+)?"
        r"(?P<title>[a-z0-9][a-z0-9 .:'&+-]{0,80}?)"
        r"(?:\s+(?:ya|already|esta|is)){0,2}"
        r"\s+(?:instalad[oa]|installed)"
        r"(?:\s+(?:en|on)\s+(?:steam|epic(?:\s+games)?))?",
        folded,
    )
    if match is None:
        return None
    title = match.group("title").strip()
    if not title or _has(title, r"^(?:el|la|the|un|una|a|an|ya|already|esta|is)$"):
        return None
    return title


def installed_game_provider(text: str) -> str:
    """The manifest family the installed question names; ``any`` otherwise."""

    folded = _fold(text)
    if _has(folded, r"\bsteam\b"):
        return "steam"
    if _has(folded, r"\bepic\b"):
        return "epic"
    return "any"


_MESSAGING_CLIENT_KEY = re.compile(
    r"\b(?:discord|whatsapp|telegram|teams|slack|skype|zoom|signal|messenger)\b"
)
