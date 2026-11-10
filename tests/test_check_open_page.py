"""Rule ``unopened_page`` of the answer check and aid ``check_open_page`` (encargo A10, U31 with the fleet's receipts,
diag-b5bd): a navigation of the turn failed, a search ran after it, and nothing opened another page before the answer.
The note says that fact and keeps the tools; the model decides whether to open a page."""
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from test_answer_check import _r
from test_mind_final import _call, _mind, _say

GUESS = "https://docs.ejemplo.test/3/guia-inventada.html"
SEARCH_PAGE = "https://duckduckgo.com/?q=docs%20ejemplo%20guia&kl=ue-es"
REAL = "https://docs.ejemplo.test/3/guia.html"


def _not_found(url: str = GUESS) -> dict:
    return _r("browser.navigate", {"status": "failed", "error": "page_not_found", "cause": "external_effect_ambiguous",
                                   "effectUncertain": True,
                                   "observed": {"requestedUrl": url, "finalUrl": url, "httpStatus": 404,
                                                "next": "web_search {\"query\":\"docs ejemplo guia\"} finds the page's "
                                                        "real address"}}, {"url": url})


def _refused() -> dict:
    return _r("web.search", {"status": "failed", "error": "web_search_unavailable",
                             "observed": {"query": "docs ejemplo guia", "searchPageUrl": SEARCH_PAGE,
                                          "next": f"browser_navigate_set {{\"url\":\"{SEARCH_PAGE}\"}} does this "
                                                  "search in the person's browser instead"}}, {"query": "docs ejemplo guia"})


def _searched() -> dict:
    return _r("web.search", {"status": "completed", "verification": "output_only",
                             "observed": {"query": "docs ejemplo guia", "resultCount": 1, "answeredBy": "DuckDuckGo",
                                          "results": [{"title": "Guía", "url": REAL, "snippet": "La guía."}]}},
              {"query": "docs ejemplo guia"})


def _opened(url: str) -> dict:
    return _r("browser.navigate", {"status": "completed", "verification": "readback",
                                   "observed": {"requestedUrl": url, "finalUrl": url}}, {"url": url})


def _read() -> dict:
    return _r("browser.page.read", {"status": "completed", "verification": "output_only",
                                    "observed": {"url": SEARCH_PAGE, "title": "docs ejemplo guia at DuckDuckGo",
                                                 "text": "Guía\nhttps://docs.ejemplo.test › 3 › guia.html",
                                                 "links": ["Guía"]}})


def _click() -> dict:
    return _r("input.visible.click", {"status": "completed", "verification": "readback", "observed": {"label": "Guía"}},
              {"label": "Guía"})


ANSWER = "The page I tried doesn't exist; DuckDuckGo found the guide page instead."


def _flagged(receipts: list[dict], answer: str = ANSWER, request: str = "Open the guide page") -> list[dict]:
    return [f for f in check(answer, request, receipts, []) if f["rule"] == "unopened_page"]


@pytest.mark.parametrize("receipts", [
    [_not_found(), _refused(), _opened(SEARCH_PAGE), _read()],  # U31 as the fleet ran it
    [_not_found(), _refused(), _opened(SEARCH_PAGE + "/"), _read()],
    [_not_found(), _searched()],  # the search answered and nothing opened its result
    [_opened("https://otra.test/"), _not_found(), _searched()],  # a page opened before the failure is not this one
])
def test_a_failed_page_searched_for_and_never_opened_is_flagged(receipts: list[dict]) -> None:
    findings = _flagged(receipts)
    assert len(findings) == 1
    assert GUESS in findings[0]["fact"] and "page_not_found" in findings[0]["fact"]


@pytest.mark.parametrize("receipts", [
    [_not_found(), _refused(), _opened(SEARCH_PAGE), _read(), _opened(REAL)],  # it opened the page
    [_not_found(), _searched(), _opened(REAL)],
    [_not_found(), _refused(), _opened(SEARCH_PAGE), _read(), _click()],  # it opened the result by its link
    [_refused(), _opened(SEARCH_PAGE), _read()],  # nothing failed to open
    [_searched()],
    [_not_found(), _searched(), _not_found(REAL)],  # it tried the result: that try failed, and the rule is about the last
])
def test_nothing_is_said_when_the_page_opened_or_nothing_failed_before_a_search(receipts: list[dict]) -> None:
    assert not _flagged(receipts)


U31 = [_not_found(), _refused(), _opened(SEARCH_PAGE), _read()]


# INT10: since srch1 a refused search opens nothing and gives no page to read its results in (WebSearchRefused: no next,
# no searchPageUrl), and an engine that answered with nothing gives none either. Nothing was found to open, so «I could
# not find it» is the answer, not a page left unopened: the note asked the model to open «the address the results bring»
# that no result brought (family u31 with srch1's receipts: 32 notes, then guessed addresses and search loops).
def _refused_srch1(error: str = "web_search_unavailable") -> dict:
    return _r("web.search", {"status": "failed", "error": error,
                             "observed": {"version": 1, "source": "web", "query": "docs ejemplo guia",
                                          "asked": [{"endpoint": "html.duckduckgo.com", "outcome": "challenge",
                                                     "httpStatus": 202}]}}, {"query": "docs ejemplo guia"})


@pytest.mark.parametrize("receipts", [
    [_not_found(), _refused_srch1()],
    [_not_found(), _refused_srch1(), _refused_srch1()],
    [_not_found(), _refused_srch1("web_search_no_results")],
])
def test_a_search_that_found_nothing_to_open_leaves_no_page_unopened(receipts: list[dict]) -> None:
    assert not _flagged(receipts, answer="La página no existe y no pude buscar su dirección real.")


def test_a_search_that_answered_after_one_refused_still_leaves_its_result_unopened() -> None:
    assert len(_flagged([_not_found(), _refused_srch1(), _searched()])) == 1




# Held-out uso-105: 404 and «Netflix no tiene esa página», with the search its next offered never made. Not of an address
# the person said themselves: its 404 is what they asked (controls A10-K404, e35-K-U31).
def test_a_failed_page_nobody_searched_for_is_flagged_unless_the_person_said_the_address() -> None:
    found = _flagged([_not_found()])
    assert found and found[0]["unsearched"] is True
    assert not _flagged([_not_found()], request=f"Abre {GUESS} tal cual; sólo quiero saber si existe.")
    assert not _flagged([_not_found()], request=f"open {GUESS.upper()}")
    assert not _flagged([_not_found()], request="abre docs.ejemplo.test/3/guia-inventada.html, a ver si está")
    unconfirmed = _r("browser.navigate", {"status": "failed", "error": "user_browser_navigation_unconfirmed",
                                          "observed": {"requestedUrl": GUESS}}, {"url": GUESS})
    assert not _flagged([unconfirmed]), "it may have opened: only a page its site says does not exist"


def test_the_note_keeps_the_tools_once_and_the_model_may_open_the_page(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("browser_navigate", {"url": GUESS}), _call("web_search", {"query": "x"}),
                                    _say(ANSWER), _call("browser_navigate", {"url": REAL})])
    mind.wire_to_op = {"browser_navigate": "browser.navigate", "web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "Open the guide page")
    mind.continue_turn(2, _not_found()["observation"])
    result = mind.continue_turn(3, _searched()["observation"])
    assert result["kind"] == "action"
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "Nota interna" in note and GUESS in note
    assert "«Open the guide page»" in note, "the person's words, as they said them"
    # Measured on the bench (u31_real, u31_heldout, uso-105): their words before the fact, and «do what they said, no more
    # no less» with no word for what they may have said against it (a list of verbs did not generalize, A12: 33/33→17/32).
    assert note.index("La persona dijo") < note.index(GUESS) < note.index("Haz lo que la persona dijo")
    assert note.index("si dijo que la abrieras") < note.index("responde igual")


def test_an_answer_after_the_note_is_the_models_and_is_not_asked_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    second = "Its address is https://docs.ejemplo.test/3/guia.html."
    mind, server = _mind(tmp_path, [_call("browser_navigate", {"url": GUESS}), _call("web_search", {"query": "x"}),
                                    _say(ANSWER), _say(second)])
    mind.wire_to_op = {"browser_navigate": "browser.navigate", "web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "What is the guide page's address?")
    mind.continue_turn(2, _not_found()["observation"])
    assert mind.continue_turn(3, _searched()["observation"])["reply"] == second
    assert len(server.bodies) == 4


def test_the_rule_is_an_aid_that_can_be_switched_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    mind, _ = _mind(tmp_path, [_call("browser_navigate", {"url": GUESS}), _call("web_search", {"query": "x"}),
                               _say(ANSWER)])
    mind.wire_to_op = {"browser_navigate": "browser.navigate", "web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "Open the guide page")
    mind.continue_turn(2, _not_found()["observation"])
    assert mind.continue_turn(3, _searched()["observation"])["reply"] == ANSWER
