"""The place of an application a mission's sub-goal goes to, when the application's data declare its address.

Estabilización, encargo C (banco r30 x10 y g1, u1 y y8 inestables): Steam draws its window without an accessible tree
and Spotify moves its navigation, so going to a place by clicks was not 3/3. Their places that have an address of their
own (a protocol the application registered in Windows) live in data/app_places.v1.json, with the names each place is said
by; Baxy.Kernel's ApplicationPlaces reads the same file and composes the address, and the file's examples tie both
readers in their tests. This reads only the sub-goal as semantic.missions writes it («ir a X», «buscar X»), never the
person's words, and names no application: another application gets places by adding them to the data.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .catalog import GameCatalogIndex, build_game_catalog_index
from .drag import act_clauses
from .intent import _entity_key
from .normalize import fold as _fold

_DATA = Path(__file__).resolve().parent.parent / "data" / "app_places.v1.json"
# The sub-goals semantic.missions writes for going to a place and for searching (its _NAVIGATE_CLAUSE and _SEARCH_CLAUSE
# readers); a tab or an address of the browser is no place of an application.
_GO = "ir a "
_NOT_PLACES = ("ir a la pestana ", "ir a la direccion ")
_SEARCH = "buscar "
# A search said as the person says it, when the engine gets their own words («buscá Cuphead en mi biblioteca de Steam»,
# «en mi biblioteca de Steam buscá Cuphead», «search Cuphead in my Steam library»): the search limit reads it too, at
# the head of a clause of acts (semantic.drag.act_clauses: never in a dictated or quoted text).
_SEARCH_SAID = re.compile(r"^(?:(?:por\s+favor|porfa|please)\s+)?(?:buscar|busca|buscame|search(?:\s+for)?|find|look\s+(?:for|up))\s+")
_GAME = "{game}"


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _key(name: object) -> str:
    return _fold(name)


def _application(application: object) -> dict | None:
    wanted = _key(application)
    return next((entry for name, entry in data()["applications"].items() if _key(name) == wanted), None)


def declares(application: object, goal: object) -> bool:
    """The application's data give an address to the place the sub-goal goes to, a game's page whatever its title
    (whether the title is a game of the catalog is the step's to read, ``place_of``). A search is not a place gone to."""

    entry = _application(application)
    target = _place_said(goal)
    if entry is None or target is None:
        return False
    return any(
        _said_with_game(said, target) is not None if _GAME in said else said == target
        for place in entry["places"].values() if "address" in place for said in place.get("names", ())
    )


def place_of(
    application: object,
    goal: object,
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    said: object = "",
) -> dict[str, str] | None:
    """The app.open arguments of the place the sub-goal goes to ({"place"} and, for a slot, {"placeValue"}), or None
    when the application's data give it no address: a search goes to the place whose address takes what is searched
    (``_search``), «ir a X» to the place said X, «ir a la página de T» to the page of the game T of the application's
    game catalog (its identifier fills the slot; a title not in the catalog has no address). ``said``: the person's
    request, which may name the place the search is in."""

    entry = _application(application)
    if entry is None:
        return None
    searched = _search(entry, goal, said)
    if searched is not None:
        return {"place": searched[0], "placeValue": searched[1]}
    target = _place_said(goal)
    for name, place in sorted(entry["places"].items()) if target is not None else ():
        for named in place.get("names", ()) if "address" in place else ():
            if _GAME not in named:
                if named == target:
                    return {"place": name}
                continue
            title = _said_with_game(named, target)
            game = _game_id(title, entry.get("gameCatalog"), game_catalog) if title is not None else None
            if game is not None:
                return {"place": name, "placeValue": game}
    return None


def arrival_term(application: object, goal: object, said: object = "") -> str | None:
    """The check's term for a place opened with a value (what was searched, a game's title): its act and
    «opened:<place>=<value>», which the shell holds only on the value born in the window after that opening, never the
    value anywhere (review H1). For a place said by name whose data name what only its page shows («shows»): that
    control, by its whole name. None for any other place, whose arrival the window's own navigation shows, or one
    ``place_of`` would not open."""

    entry = _application(application)
    if entry is None:
        return None
    searched = _search(entry, goal, said)
    if searched is not None:
        return f"stepDone:app.open&opened:{searched[0]}={_key(searched[1])}"
    target = _place_said(goal)
    for name, place in sorted(entry["places"].items()) if target is not None else ():
        for named in place.get("names", ()) if "address" in place else ():
            title = _said_with_game(named, target) if _GAME in named else None
            if title:
                return f"stepDone:app.open&opened:{name}={title}"
        if target in place.get("names", ()) and place.get("shows"):
            # Estabilización S2 (banco f3 v8 0/3, already on the player's home page: its button keeps no state and its
            # page is titled by the track playing): a control only that place's page shows, whole name, wherever the
            # window came from (data «shows», measured on the window).
            return "|".join(f"control:=={_key(shown)}" for shown in place["shows"])
    return None


def _search(entry: dict, goal: object, said: object) -> tuple[str, str] | None:
    """(place, query) of a search sub-goal («buscar Q») in the place whose address takes the query, unless the request
    or the query names another place of the application (its «within» is where the address searches: «andá a la
    biblioteca y buscá Cuphead» or «… en mi biblioteca» is no search of the store; review of encargo C, H3)."""

    goal = " ".join(str(goal or "").split())
    if not _key(goal).startswith(_SEARCH):
        return None
    query = goal[len(_SEARCH):].strip(" \"'«»“”")
    found = next(((name, place) for name, place in sorted(entry["places"].items())
                  if "{query}" in place.get("address", "")), None)
    if found is None or not query:
        return None
    name, place = found
    # Banco c2 (lug-3: «buscá Los Bunkers» searched «Bunkers»): the sub-goal drops a leading article, which before a
    # name the person capitalized is the name's own («Los Bunkers», «The Beatles»): the query is said whole.
    article = re.search(r"(?<![\w])((?:El|La|Los|Las|The)\s+)" + re.escape(query) + r"(?![\w])", str(said or ""))
    if article is not None:
        query = article.group(1) + query
    words = _words(f"{_key(said)} {_key(query)}")
    for other, entry_place in entry["places"].items():
        if other in (name, place.get("within")):
            continue
        if any(f" {named} " in words for named in entry_place.get("names", ()) if _GAME not in named):
            return None
    return name, query


def search_limit(application: object, goal: object, said: object = "") -> str | None:
    """Estabilización L3 (g1 0/3, 3/3, 0/1): the place of the application, named by the request or the search, whose
    data say searching inside it is a limit («search»: false: Steam draws its library's search box so that typing in
    it is not reliable). None for a search the application can do («buscá Cuphead en Steam», «… en la tienda») or any
    other sub-goal."""

    entry = _application(application)
    goal = " ".join(str(goal or "").split())
    if entry is None or not any(_SEARCH_SAID.match(clause) for clause in act_clauses(goal)):
        return None
    words = _words(f"{_key(said)} {_key(goal)}")
    return next((
        name for name, place in sorted(entry["places"].items())
        if place.get("search") is False and any(f" {named} " in words for named in place.get("names", ()))
    ), None)


def chats_place(application: object, goal: object) -> tuple[str, str] | None:
    """Encargo IMP2 (banco fix1 c6): (place, target) for a sub-goal going to a place the application's data do not
    declare («ir a ron92»: a chat) when the data name where its chats are listed («chats»); None otherwise."""

    entry = _application(application)
    target = _chat_said(entry, goal)
    if target is None or not entry.get("chats"):
        return None
    return entry["chats"], target


def chat_search(application: object, goal: object) -> tuple[dict, str] | None:
    """Encargo TZ-WA2 (banco zu1–zu3): (spec, target) for a sub-goal going to a place the application's data do not
    declare («ir a abuela»: a chat) when the data say how its chat list is searched («chatSearch»: the search field's
    names, the filter that shows every chat, the pattern of a chat's own entry); None otherwise."""

    entry = _application(application)
    target = _chat_said(entry, goal)
    spec = (entry or {}).get("chatSearch")
    if not isinstance(spec, dict) or target is None:
        return None
    return spec, target


def _chat_said(entry: dict | None, goal: object) -> str | None:
    """The place a sub-goal goes to when the application's data declare no place so named: a chat."""

    target = _place_said(goal)
    if entry is None or target is None or any(target in place.get("names", ()) for place in entry["places"].values()):
        return None
    return target


def conversation(application: object) -> dict | None:
    """Encargo IMP4: where the application draws its conversation and how the person's own bubbles look (data
    «conversation»), or None."""

    entry = _application(application)
    found = (entry or {}).get("conversation")
    return dict(found) if isinstance(found, dict) else None


def goes_to(application: object, goal: object, place: str) -> bool:
    """The sub-goal goes to that place of the application («ir a biblioteca»)."""

    entry = _application(application)
    target = _place_said(goal)
    return entry is not None and target is not None and target in entry["places"].get(place, {}).get("names", ())


def first_name(application: object, place: str) -> str | None:
    """The place's first name in the data, the one a sub-goal «ir a X» is written with."""

    entry = _application(application)
    names = (entry or {}).get("places", {}).get(place, {}).get("names", ())
    return names[0] if names else None


def said_as(application: object, place: str | None, lang: str) -> str | None:
    """How a final says the place in the language («la biblioteca», «the library»; data «said»)."""

    entry = _application(application)
    return (entry or {}).get("places", {}).get(place or "", {}).get("said", {}).get(lang)


def search_offer(application: object) -> str | None:
    """The place the application's search address searches in (the «within» of the place that takes {query}): where a
    search the limit stops can be done instead."""

    entry = _application(application)
    return next((
        place.get("within") for place in (entry or {}).get("places", {}).values()
        if "{query}" in place.get("address", "") and place.get("within")
    ), None)


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9]+", text)) + " "


def _place_said(goal: object) -> str | None:
    folded = _key(goal)
    if not folded.startswith(_GO) or folded.startswith(_NOT_PLACES):
        return None
    return folded[len(_GO):].strip() or None


def _said_with_game(named: str, target: str) -> str | None:
    head, _, tail = named.partition(_GAME)
    found = re.fullmatch(re.escape(head) + r"(?P<title>.+?)" + re.escape(tail), target)
    return found.group("title").strip() if found is not None else None


def _game_id(
    title: str, provider: object, game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> str | None:
    key = _entity_key(title)
    games = [
        entry[2] for entry in build_game_catalog_index(game_catalog).entries
        if entry[1] == provider and entry[0] == key
    ]
    return games[0] if len(games) == 1 else None
