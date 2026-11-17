"""Aid «said_store», DIAX6 (CASX1 H-051, H-053: «busca Montaña Rota en Epic» became game_store_search, which opens
Steam's store; H-052: «abre la página de Montaña Rota en la app de Epic» became game_store_page, Steam's page). A game
store call in a turn whose words name another launcher's store (app_places.v1.json «store») and not Steam is held once
and goes back with the app_open of that launcher's place; the same call again runs as written."""
import json
from pathlib import Path

from test_mind_final import _call, _mind as _bare


def _mind(tmp_path: Path, replies: list):
    mind, server = _bare(tmp_path, replies)
    mind.wire_to_op = {**mind.wire_to_op, "game_store_page": "game.store.page", "game_store_search": "game.store.search",
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


def test_a_search_in_epic_goes_back_with_epics_own_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    opened = {"appId": "Epic Games Launcher", "place": "results", "placeValue": "Montaña Rota", "foreground": True,
              "forControl": True}
    mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": "Montaña Rota"}), _call("app_open", opened)])
    step = mind.decide(1, "busca Montaña Rota en Epic")
    assert step["operation"] == "app.open" and step["arguments"]["place"] == "results"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "store_named" and told[0]["storeNamed"] == "epic"
    assert told[0]["next"].startswith('app_open {"appId":"Epic Games Launcher","place":"results",'
                                      '"placeValue":"Montaña Rota"')


def test_a_page_in_epic_goes_back_with_epics_game_place(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("game_store_page", {"title": "Montaña Rota"}),
                               _call("game_store_page", {"title": "Montaña Rota"})])
    mind.decide(1, "abre la página de Montaña Rota en la app de Epic Games")
    told = _not_run(mind)
    assert len(told) == 1 and '"place":"game","placeValue":"Montaña Rota"' in told[0]["next"]


def test_it_is_told_once_and_steam_or_no_store_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": "Montaña Rota"}),
                               _call("game_store_search", {"query": "Montaña Rota"})])
    assert mind.decide(1, "búscame Montaña Rota en la tienda de Epic")["operation"] == "game.store.search"
    assert len(_not_run(mind)) == 1
    for said, query in (("busca juegos de terror en Steam", "terror"), ("busca Celeste en la tienda", "Celeste"),
                        ("busca Montaña Rota en Steam, no en Epic", "Montaña Rota"),
                        ("busca algo de epic fantasy en steam", "epic fantasy")):
        mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": query})])
        assert mind.decide(1, said)["operation"] == "game.store.search", said
        assert _not_run(mind) == [], said


def test_without_the_aid_or_app_open_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("game_store_search", {"query": "Montaña Rota"})])
    assert mind.decide(1, "busca Montaña Rota en Epic")["operation"] == "game.store.search"
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _bare(tmp_path, [_call("game_store_search", {"query": "Montaña Rota"})])
    mind.wire_to_op = {**mind.wire_to_op, "game_store_search": "game.store.search"}
    assert mind.decide(1, "busca Montaña Rota en Epic")["operation"] == "game.store.search"
    assert _not_run(mind) == []
