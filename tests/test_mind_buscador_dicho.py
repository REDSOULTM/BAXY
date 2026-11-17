"""Aid «said_engine», DIAX6 (CASX1 H-032: «búscame en Google un top 3 de películas de terror» and then «búscalo en
Google» became web_search 6 of 9 on the 1.5.5 and the 1.5.4). A web_search of the web in a turn whose words name a
search engine of BAXY's table (search_addresses.v1.json) is held once and goes back to the model as data, with that
engine's results page for the same query; the same call again runs as written. Nothing else is held."""
import json
from pathlib import Path

from test_mind_final import _call, _mind as _bare, _say

QUERY = {"query": "top 3 películas de terror", "source": "web", "limit": 3}


def _mind(tmp_path: Path, replies: list):
    # The catalog's two tools: the search and the one that opens an address (the aid holds only when it is there).
    mind, server = _bare(tmp_path, replies)
    mind.wire_to_op = {**mind.wire_to_op, "web_search": "web.search", "browser_navigate": "browser.navigate"}
    return mind, server


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_a_search_where_they_named_google_goes_back_with_googles_results_page(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", QUERY),
                               _call("browser_navigate", {"url": "https://google.com/search?q=top"})])
    step = mind.decide(1, "búscalo en Google")
    assert step["operation"] == "browser.navigate"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "engine_named" and told[0]["engineNamed"] == "google"
    assert "https://google.com/search?q=top+3+pel%C3%ADculas+de+terror" in told[0]["next"]
    assert told[0]["next"].startswith("call browser_navigate ")


def test_other_engines_of_the_table_are_read_alike(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, engine, address in (("búscalo en Bing", "bing", "https://bing.com/search?q="),
                                  ("búscalo en DuckDuckGo", "duckduckgo", "https://duckduckgo.com/?q=")):
        mind, _ = _mind(tmp_path, [_call("web_search", QUERY), _say("Listo.")])
        mind.decide(1, said)
        told = _not_run(mind)
        assert len(told) == 1 and told[0]["engineNamed"] == engine, said
        assert address in told[0]["next"], said


def test_it_is_told_once_and_the_same_call_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", QUERY), _call("web_search", QUERY)])
    assert mind.decide(1, "búscame en Google un top 3 de películas de terror")["operation"] == "web.search"
    assert len(_not_run(mind)) == 1


def test_no_engine_named_or_another_source_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, args in (("busca cuánto está el dólar hoy", {"query": "dólar hoy"}),
                       ("búscame un top 3 de películas de terror", QUERY),
                       ("busca en internet cuándo abre la biblioteca", {"query": "horario biblioteca", "source": "web"}),
                       ("¿qué es Google Maps?", {"query": "Google Maps", "source": "encyclopedia"}),
                       ("busca en Google cuánto son 100 dólares en pesos",
                        {"query": "100 USD a CLP", "source": "currency", "from": "USD", "to": "CLP", "amount": 100})):
        mind, _ = _mind(tmp_path, [_call("web_search", args)])
        assert mind.decide(1, said)["operation"] == "web.search", said
        assert _not_run(mind) == [], said


def test_a_word_that_only_holds_an_engine_name_is_no_engine(tmp_path: Path, monkeypatch) -> None:
    # Whole words only: «googlear» or «Googleplex» name no engine of the table.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "Googleplex"})])
    assert mind.decide(1, "¿dónde queda el Googleplex?")["operation"] == "web.search"
    assert _not_run(mind) == []


def test_without_a_tool_that_opens_an_address_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _bare(tmp_path, [_call("web_search", QUERY)])
    mind.wire_to_op = {**mind.wire_to_op, "web_search": "web.search"}
    assert mind.decide(1, "búscalo en Google")["operation"] == "web.search"
    assert _not_run(mind) == []


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("web_search", QUERY)])
    assert mind.decide(1, "búscalo en Google")["operation"] == "web.search"
    assert _not_run(mind) == []


def test_query_left_name_does_not_take_the_engine_for_a_name_to_search(tmp_path: Path, monkeypatch) -> None:
    # The 1.5.5 held this search as one that left out «Google» and its next sent the model to web_search «Google».
    monkeypatch.setenv("BAXY_AYUDAS", "query_left_name")
    mind, _ = _mind(tmp_path, [_call("web_search", QUERY)])
    assert mind.decide(1, "búscalo en Google")["operation"] == "web.search"
    assert _not_run(mind) == []


def test_the_held_search_leaves_the_conversation_when_the_next_turn_starts(tmp_path: Path, monkeypatch) -> None:
    # DIAX6C (D6-5): what ran stays (the page it opened and its receipt); the held call and its result do not.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    page = {"url": "https://google.com/search?q=top"}
    mind, _ = _mind(tmp_path, [_call("web_search", QUERY), _call("browser_navigate", page), _say("Abierto."),
                               _say("Dura dos horas.")])
    assert mind.decide(1, "búscame en Google un top 3 de películas de terror")["operation"] == "browser.navigate"
    assert len(_not_run(mind)) == 1
    mind.continue_turn(2, json.dumps({"status": "completed", "observed": page}))
    mind.decide(3, "busca cuánto dura")
    assert _not_run(mind) == []
    names = [c["function"]["name"] for m in mind.conversation for c in m.get("tool_calls") or []]
    assert names == ["browser_navigate"]
    ids = {c["id"] for m in mind.conversation for c in m.get("tool_calls") or []}
    assert all(m["tool_call_id"] in ids for m in mind.conversation if m["role"] == "tool")
