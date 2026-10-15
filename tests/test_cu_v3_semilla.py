"""Semilla del goal v3 («Podrias buscarme en google un top 3 peliculas de suspenso del 2026» → «si pero quiero buscar
un top 3» → «ok pero lo puedes buscar en google no me importa the ice»), corrida en vivo el 2026-10-08 (fix2): the
search opened is named, nothing is said of a page nobody read, the search already on show is read instead of opened
again, and the decider's restatement leaves no period in the query."""

from __future__ import annotations

import pytest

from baxy_mind import compose_instructions
from baxy_mind import deterministic_finals
from baxy_mind import visible_defect
from baxy_mind.semantic import claims, dialogue
from baxy_mind.semantic.grammar import _explicit_google_search_query
from baxy_mind import compose_facts

_T1 = "Podrias buscarme en google un top 3 peliculas de suspenso del 2026"
_URL = "https://www.google.com/search?q=un+top+3+peliculas+de+suspenso+del+2026"
_OPENED = {
    "kind": "operation", "operation": "browser.navigate", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "requestedUrl": _URL, "finalUrl": _URL.replace("www.", ""), "browser": "Opera GX"},
}
_RESTATED = "Busca en Google un top 3 de películas de suspenso del 2026."
_TOOLS = {"browser.page.read": object(), "browser.navigate": object()}


# ------------------------------------------------------------------------------------------ (4) the query's period

def test_the_restatements_sentence_end_is_no_part_of_the_query() -> None:
    assert _explicit_google_search_query(_RESTATED) == "un top 3 de películas de suspenso del 2026"
    assert _explicit_google_search_query("¿Puedes buscar en Google qué es node.js?") == "qué es node.js"


@pytest.mark.parametrize("text, query", [("busca en google node.js", "node.js"), ("busca en google C++", "C++")])
def test_a_query_that_ends_in_its_own_signs_keeps_them(text: str, query: str) -> None:
    assert _explicit_google_search_query(text) == query


# --------------------------------------------------------------------------- (5) the floor names the search opened

def test_a_results_page_opened_is_told_as_the_search_it_is() -> None:
    final = deterministic_finals._told_result_final(_OPENED, {}, _T1, "es")
    assert final == "Abrí en Google la búsqueda de «un top 3 peliculas de suspenso del 2026» en tu navegador."
    assert "Google search for «un top 3" in deterministic_finals._told_result_final(_OPENED, {}, _T1, "en")


def test_another_page_opened_keeps_its_own_floor() -> None:
    other = {**_OPENED, "observed": {"requestedUrl": "https://www.wikipedia.org/", "finalUrl": "https://www.wikipedia.org/"}}
    assert "búsqueda" not in deterministic_finals._told_result_final(other, {}, "abre wikipedia", "es")


# ------------------------------------------------------------- (1) nothing is said of a page that nobody read

@pytest.mark.parametrize(
    "draft",
    [
        "No hay películas de suspenso del 2026 disponibles en Google porque aún no se han estrenado.",
        "He abierto en Google la búsqueda de «un top 3 de películas de suspenso del 2026» y el resultado confirma que "
        "aún no hay películas disponibles porque ese año no ha llegado.",
        "Abrí la búsqueda; aparecen Sinners, Weapons y Bring Her Back.",
        "I opened the search; there are three films listed.",
    ],
)
def test_a_navigation_never_tells_what_the_page_holds(draft: str) -> None:
    said = "yes but I want to search for a top 3" if draft.startswith("I ") else "si pero quiero buscar un top 3"
    assert claims.tells_page_content(draft)
    assert visible_defect.compose_visible_defect(draft, "status", said, {"situation": _OPENED}, said=said) == (
        "navigation_content_claim"
    )


@pytest.mark.parametrize(
    "draft",
    [
        "Abrí en Google la búsqueda de «un top 3 peliculas de suspenso del 2026» en tu navegador.",
        "Listo, ya tienes en tu navegador la búsqueda de Google de «un top 3 peliculas de suspenso del 2026».",
        "I opened the Google search for «un top 3 peliculas de suspenso del 2026» in your browser.",
    ],
)
def test_naming_the_search_opened_is_no_claim_of_its_content(draft: str) -> None:
    """Contracaso: the quoted query and the search opened are the facts."""

    assert not claims.tells_page_content(draft)


# ---------------------------------------- (2)(3) the search on show is read, never opened again after a correction

def _state() -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(_T1, ["browser.navigate"])
    state.told(_OPENED, "Abrí en Google la búsqueda de «un top 3 peliculas de suspenso del 2026» en tu navegador.")
    return state


def _decided(text: str, objective: str = _RESTATED) -> dict:
    return {
        "type": "turn.result", "id": "9", "kind": "action", "operation": "browser.navigate",
        "intentOperations": ["browser.navigate"], "effectOperations": ["browser.navigate"], "objective": objective,
        "question": "", "reply": "",
    }


@pytest.mark.parametrize(
    "said", ["si pero quiero buscar un top 3", "ok pero lo puedes buscar en google no me importa the ice"],
)
def test_a_correction_decided_as_the_search_on_show_reads_it(said: str) -> None:
    state = _state()
    result = compose_facts._read_the_page_on_show(_decided(said), {"id": "9", "text": said}, state, _TOOLS)
    assert result["operation"] == "browser.page.read"
    assert result["effectOperations"] == ["browser.page.read"]
    assert state.reading_on_show == _URL


@pytest.mark.parametrize(
    "said, objective",
    [
        ("otra vez", _RESTATED),  # asked again: opened again
        ("si pero quiero buscar un top 3", "Busca en Google un top 3 de series de terror del 2026."),  # another search
    ],
)
def test_asking_again_or_another_search_is_opened(said: str, objective: str) -> None:
    state = _state()
    result = compose_facts._read_the_page_on_show(_decided(said, objective), {"id": "9", "text": said}, state, _TOOLS)
    assert result["operation"] == "browser.navigate"
    assert state.reading_on_show is None


def test_after_another_act_nothing_is_held_on_show() -> None:
    state = _state()
    state.expect("cierra opera", ["app.close"])
    state.told(
        {"kind": "operation", "operation": "app.close", "verified": True, "succeeded": True, "observed": {"app": "Opera"}},
        "Cerré Opera.",
    )
    said = "si pero quiero buscar un top 3"
    result = compose_facts._read_the_page_on_show(_decided(said), {"id": "9", "text": said}, state, _TOOLS)
    assert result["operation"] == "browser.navigate"


def test_the_read_tells_the_top_asked_or_says_the_search_is_open() -> None:
    state = _state()
    said = "si pero quiero buscar un top 3"
    compose_facts._read_the_page_on_show(_decided(said), {"id": "9", "text": said}, state, _TOOLS)
    read = {
        "kind": "operation", "operation": "browser.page.read", "polarity": "success", "verified": True,
        # The receipt carries the address it read (UserBrowserSurface.ReadPageAsync); a read without it and titled
        # only «Google» is no proof the search is the page in front (review r10a finding 2, test_cu_v3_honestidad).
        "succeeded": True, "observed": {"url": _URL, "title": "Google", "text": "1. Sinners 2. Weapons 3. Bring Her Back"},
    }
    facts = compose_facts._with_listing_and_repetition_facts({"situation": read}, read, state, said, said)
    situation = facts["situation"]
    assert situation["openSearch"] == {"site": "Google", "query": "un top 3 peliculas de suspenso del 2026"}
    assert situation["askedCount"] == 3
    assert "top 3" in compose_instructions._compose_shape_instruction(situation, "es", said)
    failed = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed",
        "reason": {"kind": "operation", "operation": "browser.page.read", "polarity": "failure", "verified": False,
                   "succeeded": False, "error": "user_browser_page_unreadable"},
    }
    facts = compose_facts._with_listing_and_repetition_facts({"situation": failed}, failed, state, said, said)
    final = deterministic_finals._told_result_final(facts["situation"], {}, said, "es")
    assert "está abierta en tu navegador" in final and "¿quieres que intente leerla" in final


def test_a_search_read_that_told_nothing_says_it_is_open_and_never_the_same_words_twice() -> None:
    """Semilla fix3: Google answered the read with its 502 page and every draft was refused; t2 and t3 both said
    «Leí la página «Error 502 (Server Error)!!1».»."""

    search = {"site": "Google", "query": "un top 3 peliculas de suspenso del 2026"}
    read = {
        "kind": "operation", "operation": "browser.page.read", "polarity": "success", "verified": True,
        "succeeded": True, "openSearch": search,
        "observed": {"title": "Error 502 (Server Error)!!1", "text": "502. That's an error."},
    }
    first = deterministic_finals._told_result_final(read, {}, "si pero quiero buscar un top 3", "es")
    assert "está abierta en tu navegador" in first and "Error 502" not in first
    again = {**read, "correctedFinal": {"previousReply": first}}
    second = deterministic_finals._told_result_final(again, {}, "ok pero lo puedes buscar en google", "es")
    assert second != first and "«un top 3 peliculas de suspenso del 2026»" in second
