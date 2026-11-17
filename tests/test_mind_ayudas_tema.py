"""DIAX6B (REVX2 D6-1, D6-2, D6-3): the search engine, the store or the title the model writes is what the person spoke
of, not where. «said_engine» held a web_search whenever the turn named an engine anywhere («busca quién fundó Google»
→ «their words name google as where to search», a browser window nobody asked for); «said_store» did the same with a
store word («busca Epic Mickey en la tienda» → Epic's launcher); «said_title» held the real title the model wrote for a
short or half-heard name («instala el GTA cinco» → «Grand Theft Auto V»). The reviewer's probes, as the mind sees them:
none of these is held; the cases the aids were for still are."""
import json
from pathlib import Path

import pytest

from test_mind_final import _call, _mind as _bare


def _mind(tmp_path: Path, replies: list):
    mind, server = _bare(tmp_path, replies)
    mind.wire_to_op = {**mind.wire_to_op, "web_search": "web.search", "browser_navigate": "browser.navigate",
                       "game_store_page": "game.store.page", "game_store_search": "game.store.search",
                       "game_install_named": "game.install.named", "game_entitlement_named": "game.entitlement.named",
                       "app_open": "app.open"}
    return mind, server


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


# D6-1: the engine is the topic; the query the model wrote carries it as many times as their words do.
ENGINE_TOPIC = [
    ("busca cuánto cuesta el Google Pixel 9", "precio Google Pixel 9"),
    ("búscame qué es Google Gemini", "qué es Google Gemini"),
    ("busca quién fundó Google", "quién fundó Google"),
    ("busca quién dirigió la película Brave", "director película Brave"),
    ("¿quién hizo de Chandler Bing?", "actor Chandler Bing"),
    ("busca cuántos suscriptores tiene el canal de la NASA en YouTube", "suscriptores canal NASA YouTube"),
    ("busca cuándo cerró Yahoo Respuestas", "cuándo cerró Yahoo Respuestas"),
    ("search for a summary of Brave New World", "Brave New World summary"),
    ("what is the Google stock price today", "Google stock price today"),
]


@pytest.mark.parametrize(("said", "query"), ENGINE_TOPIC)
def test_an_engine_that_is_the_topic_of_the_search_runs(tmp_path: Path, monkeypatch, said: str, query: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": query, "source": "web"})])
    assert mind.decide(1, said)["operation"] == "web.search"
    assert _not_run(mind) == []


def test_an_engine_named_both_as_where_and_as_topic_is_still_where(tmp_path: Path, monkeypatch) -> None:
    # «en Google» once more than the query carries it: Google is also where to search.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "qué es Google Gemini", "source": "web"}),
                               _call("browser_navigate", {"url": "https://google.com/search?q=x"})])
    mind.decide(1, "busca en Google qué es Google Gemini")
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["engineNamed"] == "google"
    assert "q=qu%C3%A9+es+Google+Gemini" in told[0]["next"]


def test_the_owners_search_in_google_is_still_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "top 3 películas de terror", "source": "web"}),
                               _call("browser_navigate", {"url": "https://google.com/search?q=x"})])
    mind.decide(1, "búscame en Google un top 3 de películas de terror")
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "engine_named"


# D6-2: «epic» is part of the title or the words searched for in the store.
STORE_TOPIC = [
    ("busca Epic Mickey en la tienda", "game_store_search", {"query": "Epic Mickey"}),
    ("abre la página de Epic Battle Fantasy 5", "game_store_page", {"title": "Epic Battle Fantasy 5"}),
    ("quiero ver la ficha de Ultimate Epic Battle Simulator en la tienda", "game_store_page",
     {"title": "Ultimate Epic Battle Simulator"}),
    ("find me an epic fantasy RPG in the store", "game_store_search", {"query": "epic fantasy RPG"}),
    # The model shortened the name: «Epic» glued to a capitalized word of what it wrote is part of that name.
    ("búscame en la tienda el juego Epic Río Seco", "game_store_search", {"query": "Río Seco"}),
    ("abre la ficha de Epic Torre Gris en la tienda", "game_store_page", {"title": "Torre Gris"}),
]


@pytest.mark.parametrize(("said", "wire", "args"), STORE_TOPIC)
def test_a_store_word_that_is_in_the_title_runs(tmp_path: Path, monkeypatch, said: str, wire: str, args: dict) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call(wire, args)])
    assert mind.decide(1, said)["operation"] == ("game.store.search" if wire.endswith("search") else "game.store.page")
    assert _not_run(mind) == []


def test_a_store_named_as_where_besides_the_title_is_still_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": "Epic Mickey"}),
                               _call("game_store_search", {"query": "Epic Mickey"})])
    mind.decide(1, "busca Epic Mickey en la tienda de Epic")
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "store_named" and '"placeValue":"Epic Mickey"' in told[0]["next"]
    # Shortened, and Epic named again as where.
    mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": "Río Seco"}),
                               _call("game_store_search", {"query": "Río Seco"})])
    mind.decide(1, "busca Epic Río Seco en la tienda de Epic")
    assert len(_not_run(mind)) == 1


# D6-3: the real title the model writes for a short or half-heard name goes to the tool as written.
TITLE_SHORT = [
    ("instala el GTA cinco", "game_install_named", {"title": "Grand Theft Auto V"}),
    ("abre la página del CS2 en Steam", "game_store_page", {"title": "Counter-Strike 2"}),
    ("instala el RDR2", "game_install_named", {"title": "Red Dead Redemption 2"}),
    ("¿tengo el LoL?", "game_entitlement_named", {"title": "League of Legends"}),
    ("instala el cod", "game_install_named", {"title": "Call of Duty"}),
    ("instala el fornai", "game_install_named", {"title": "Fortnite"}),
    ("abre la página de sáiberpan", "game_store_page", {"title": "Cyberpunk 2077"}),
    ("busca juegos de miedo en Steam", "game_store_search", {"query": "horror"}),
]


@pytest.mark.parametrize(("said", "wire", "args"), TITLE_SHORT)
def test_the_real_title_of_a_short_or_misheard_name_runs(tmp_path: Path, monkeypatch, said: str, wire: str,
                                                          args: dict) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call(wire, args)])
    step = mind.decide(1, said)
    assert step["kind"] == "action" and step["arguments"] == args
    assert _not_run(mind) == []
