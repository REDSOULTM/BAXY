"""A7: a web.fetch whose address ends in «…» or «...» is an address cut where it was copied (every web.fetch of «el último
Mundial» answered web_fetch_status_404). It is not handed to the App: its result says so as data, with the whole address
of the turn's results that begins the same way as its next, and the model decides again."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

WHOLE = "https://www.ejemplo-deportes.example/futbol/argentina-vs-espana-la-final-del-mundial-2026"
SEARCH = json.dumps({"status": "completed", "verification": "observed", "observed": {
    "version": 1, "source": "web", "query": "ganador mundial",
    "results": [{"title": "Otra", "url": "https://otra.example/x", "snippet": "a"},
                {"title": "Final", "url": WHOLE, "snippet": "b"}], "resultCount": 2}})
PAGE = json.dumps({"status": "completed", "verification": "observed", "observed": {"text": "Ganó Argentina"}})


def _told(mind) -> list[dict]:
    out = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("error") == "web_fetch_url_truncated":
                out.append(body)
    return out


def test_a_cut_address_is_held_back_and_the_whole_one_is_the_next(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "ganador mundial"}),
                               _call("web_fetch", {"url": WHOLE[:-8] + "..."}),
                               _call("web_fetch", {"url": WHOLE}),
                               _say("Ganó Argentina.")])
    assert mind.decide(1, "Busca quién ganó el último Mundial")["operation"] == "web_search"
    step = mind.continue_turn(2, SEARCH)
    # The cut address never reached the App: the model tries a second time.
    assert step["kind"] == "action" and step["arguments"]["url"] == WHOLE
    told = _told(mind)
    assert len(told) == 1 and WHOLE in told[0]["observed"]["next"]
    assert mind.continue_turn(3, PAGE)["reply"].startswith("Ganó")


def test_a_cut_address_with_the_ellipsis_character_and_no_match_asks_for_a_whole_one(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_fetch", {"url": "https://nada.example/pagina-larga…"}),
                               _call("web_search", {"query": "pagina larga"})])
    assert mind.decide(1, "lee esa página")["operation"] == "web_search"
    told = _told(mind)
    assert len(told) == 1 and "next" in told[0]["observed"] and "https://" not in told[0]["observed"]["next"]


def test_a_whole_address_goes_to_the_app(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_fetch", {"url": "https://nada.example/a...b"})])
    assert mind.decide(1, "lee esa página")["operation"] == "web_fetch"
    assert _told(mind) == []


# Encargo A11 (R18 en la flota, diag-6f20): the model copied from a results page read in the browser an address in the
# form the page writes under a result's title («host › section › section») and fetched it.
SHOWN = "https://www.cambio-hoy.example › es › convertir › clp-cop"
READ = json.dumps({"status": "completed", "verification": "output_only", "observed": {
    "version": 1, "url": "https://duckduckgo.com/", "title": "CLP a COP hoy",
    "text": "Convertir CLP a COP | Conversor\n" + SHOWN + "\nConvierte CLP a COP."}})


def _shown(mind) -> list[dict]:
    out = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("error") == "url_display_form":
                out.append(body)
    return out


def test_an_address_as_a_results_page_shows_it_is_held_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("browser_page_read", {}),
                               _call("web_fetch", {"url": SHOWN}),
                               _say("No pude leer la página.")])
    assert mind.decide(1, "lee el primer resultado")["operation"] == "browser_page_read"
    step = mind.continue_turn(2, READ)
    # The address with «›» never reached the App: the model decided again.
    assert step["kind"] != "action"
    told = _shown(mind)
    assert len(told) == 1 and "›" in told[0]["observed"]["next"] and "https://" not in told[0]["observed"]["next"]


def test_an_address_as_shown_whose_result_gave_the_whole_one_gets_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    whole = "https://www.cambio-hoy.example/es/convertir/clp-cop?amount=1"
    search = json.dumps({"status": "completed", "observed": {"version": 1, "source": "web", "results": [
        {"title": "Convertir CLP a COP", "url": whole, "snippet": "s"}], "resultCount": 1}})
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "clp cop"}),
                               _call("browser_navigate_set", {"url": SHOWN}),
                               _call("browser_navigate_set", {"url": whole})])
    assert mind.decide(1, "abre el conversor")["operation"] == "web_search"
    step = mind.continue_turn(2, search)
    assert step["kind"] == "action" and step["arguments"]["url"] == whole
    told = _shown(mind)
    assert len(told) == 1 and whole in told[0]["observed"]["next"] and "opens" in told[0]["observed"]["next"]


def test_an_ellipsis_inside_an_address_is_a_cut_too(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_fetch", {"url": "https://nada.example/…/pagina"}),
                               _say("No pude.")])
    assert mind.decide(1, "lee esa página")["kind"] != "action"
    assert len(_told(mind)) == 1


def test_an_address_with_an_angle_quote_that_is_whole_still_goes(tmp_path: Path, monkeypatch) -> None:
    # Only «›» (U+203A) is the page's separator; an address with none goes as it came.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_fetch", {"url": "https://nada.example/a>b"})])
    assert mind.decide(1, "lee esa página")["operation"] == "web_fetch"
    assert _shown(mind) == [] and _told(mind) == []
