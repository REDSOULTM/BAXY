"""Uso real 2026-10-07, official window (goal computer use v3, punto 9): the «top 3» seed.

«Podrias buscarme en google un top 3 peliculas de suspenso del 2026» → one film (The Eyes) from Wikipedia;
«si pero quiero buscar un top 3» → the same search, the same sentence; «ok pero lo puedes buscar en google no me
importa the ice» → the same sentence again. Four general faults, each with its counter-cases:

1. The tool asked for: the infinitive with clitics and «googlear» head a search (semantic/grammar._SEARCH); a Google
   product is not the engine (_GOOGLE_ENGINE); «búscalo en Google» after a search is that search opened in the browser
   (semantic/dialogue.pronoun_search_place, DialogueState.searched_in_place); a web search continues as its results
   page (same_family).
2. The count asked: semantic/listing.listing_asked (words in data/listing_words.v1.json) → ``limit`` and ``listing``
   on web.search (__main__._with_asked_listing; the provider in C# tests); the writer gets ``askedCount``.
3. The correction: «sí/ok, pero…» is a correction (dialogue.followup); the same plan after it is not done again
   (DialogueState.repeats_the_last_plan, __main__._not_the_same_again).
4. The repetition: the same result after a correction carries ``sameResultAgain`` and its old words are a defect
   (DialogueState.same_result_again/told, llm.compose_visible_defect).
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from baxy_mind import effect_intent
from baxy_mind import compose_payload
from baxy_mind import visible_defect
from baxy_mind import compose_instructions
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.grammar import _explicit_google_search_query
from baxy_mind.semantic.listing import Listing, listing_asked
from baxy_mind import argument_grounding
from baxy_mind import engine_handoff
from baxy_mind import compose_facts
from baxy_mind import turn_followups

AVAILABLE = ("web.search", "browser.navigate", "browser.navigate.named", "web.news.headlines", "task.list")
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "listing": {"type": ["boolean", "null"]},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}
SEED = "Podrias buscarme en google un top 3 peliculas de suspenso del 2026"
TOPIC = "un top 3 de películas de suspenso del 2026"


def _read(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    return intent.operations if intent is not None else None


def _searched_state(topic: str = TOPIC) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(topic, ["web.search"])
    state.record(_search_result(topic))
    return state


def _search_result(topic: str = TOPIC, titles: tuple[str, ...] = ("The Eyes (película de 2026)",)) -> dict:
    return {
        "kind": "operation",
        "operation": "web.search",
        "verified": True,
        "succeeded": True,
        "polarity": "success",
        "observed": {
            "query": topic,
            "count": len(titles),
            "results": [{"title": title, "url": "https://example.org/" + str(i)} for i, title in enumerate(titles)],
            "observedAtUtc": "2026-10-07T19:05:00Z",
        },
    }


# 1. The tool asked for -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        (SEED, "un top 3 peliculas de suspenso del 2026"),
        ("puedes buscarnos en google los horarios del metro", "los horarios del metro"),
        ("googlea el estreno de Dune", "el estreno de Dune"),
        ("googleame quién canta Flowers", "quién canta Flowers"),
    ],
)
def test_the_infinitive_with_clitics_and_googlear_head_a_google_search(text: str, query: str) -> None:
    assert _explicit_google_search_query(text) == query
    assert _read(text) == ("browser.navigate",)


def test_the_seed_opens_the_google_results_page_with_the_persons_words() -> None:
    schema = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False}
    arguments = argument_grounding._ground_explicit_arguments("browser.navigate", SEED, schema)
    url = urlparse(arguments["url"])
    assert url.hostname == "www.google.com" and url.path == "/search"
    assert parse_qs(url.query)["q"] == ["un top 3 peliculas de suspenso del 2026"]


@pytest.mark.parametrize(
    "text",
    [
        "busca en Google Drive mis archivos",  # a Google product is a place of its own
        "busca en google maps la ruta a Ñuñoa",
        "no me lo busques en Google",  # forbidden
        "búscalo en Google",  # no thing to look up of its own
        "googlealo",
    ],
)
def test_counter_cases_are_not_a_google_search_of_their_own(text: str) -> None:
    assert _explicit_google_search_query(text) is None


def test_a_google_search_with_its_own_words_stands_alone_inside_a_conversation() -> None:
    navigate = effect_intent.resolve_explicit_effects(SEED, AVAILABLE, (), ())
    assert engine_handoff._self_contained_mission(SEED, navigate, ())
    # Counter-cases: a plain web search follows the conversation (the decider reads it); nothing read is nothing.
    search = effect_intent.resolve_explicit_effects("busca en internet quién ganó la final", AVAILABLE, (), ())
    assert not engine_handoff._self_contained_mission("busca en internet quién ganó la final", search, ())
    assert not engine_handoff._self_contained_mission("búscalo en Google", None, ())


@pytest.mark.parametrize(
    "text",
    [
        "busca en google eso",
        "búscame en google lo que te dije",
        "busca en google lo mismo",
        "googlea esa canción",
        "search on google for it",
    ],
)
def test_a_google_search_pointing_back_goes_to_the_conversation(text: str) -> None:
    # Revisión 2026-10-07: the words after the engine point back; the decider (or searched_in_place) reads them.
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert not engine_handoff._self_contained_mission(text, intent, ())


def test_the_pronoun_after_the_engine_takes_the_last_search() -> None:
    state = _searched_state()
    assert state.searched_in_place("busca en google eso") == f"busca en google {TOPIC}"
    assert dialogue.DialogueState().searched_in_place("busca en google eso") is None
    # Counter-case: its own words after the engine are its own search.
    assert dialogue.pronoun_search_place("busca en google noticias de hoy") is None
    assert not dialogue.query_points_back("el estreno de Dune")
    assert not dialogue.query_points_back("noticias de hoy")


@pytest.mark.parametrize(
    "text",
    [
        "puedes buscarlo en google por favor",
        "buscarlo en google porfa",
        "googlea por favor",
        "podrías buscarlo en google ahora",
        "busca en google por favor",
    ],
)
def test_courtesy_or_an_object_clitic_is_no_query(text: str) -> None:
    # Revisión 2026-10-07: «por favor» was opened as google.com/search?q=por+favor.
    assert _explicit_google_search_query(text) is None


def test_an_object_clitic_with_the_engine_takes_the_last_search() -> None:
    assert _searched_state().searched_in_place("podrías buscarlo en google ahora") == f"busca en google {TOPIC}"


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("busca en google fotos de gatos", "fotos de gatos"),
        ("busca en google noticias de hoy", "noticias de hoy"),
        ("busca en Google traductor de inglés", "traductor de inglés"),
        ("busca en google noticias", "noticias"),
        ("busca recetas en google", "recetas"),
    ],
)
def test_a_product_name_that_is_a_common_noun_is_the_query(text: str, query: str) -> None:
    # Revisión 2026-10-07: the base opened these searches; the product list must not swallow them.
    assert _explicit_google_search_query(text) == query


@pytest.mark.parametrize(
    "text",
    ["busca en google fotos mis vacaciones", "busca en google calendar mi reunión", "busca en google chrome recetas"],
)
def test_the_product_before_other_words_is_still_the_product(text: str) -> None:
    assert _explicit_google_search_query(text) is None


def test_a_search_without_the_engine_named_stays_a_web_search() -> None:
    assert _read("busca en internet quién ganó la final") == ("web.search",)


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("ok pero lo puedes buscar en google no me importa the ice", "google"),
        ("búscalo en Google", "google"),
        ("no, búscalo en google", "google"),
        ("podrias buscarlo en google porfa", "google"),
        ("search it on Google", "google"),
        ("lo puedes buscar en el navegador?", "browser"),
    ],
)
def test_the_pronoun_with_the_engine_named_is_a_search_in_that_place(text: str, place: str) -> None:
    assert dialogue.pronoun_search_place(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "no me lo busques en Google",
        "nunca lo busques en google",
        "búscalo en google drive",
        "búscalo en Google y ábrelo",  # another order after the place
        "búscalo en google las noticias",  # its own thing to look up
        "sí, dale",
        "otra vez",
    ],
)
def test_counter_cases_of_the_pronoun_search(text: str) -> None:
    assert dialogue.pronoun_search_place(text) is None


def test_the_pronoun_takes_the_query_of_the_last_search_and_reads_as_the_browser() -> None:
    state = _searched_state()
    request = state.searched_in_place("ok pero lo puedes buscar en google no me importa the ice")
    assert request == f"busca en google {TOPIC}"
    assert _read(request) == ("browser.navigate",)
    assert _explicit_google_search_query(request) == TOPIC
    english = _searched_state("the best thriller movies of 2026")
    assert english.searched_in_place("search it on Google") == "search on google for the best thriller movies of 2026"
    assert _read("search on google for the best thriller movies of 2026") == ("browser.navigate",)
    browser = state.searched_in_place("lo puedes buscar en el navegador?")
    assert browser == f"busca {TOPIC} en mi navegador"
    assert _read(browser) == ("browser.navigate",)


def test_the_pronoun_with_nothing_searched_is_not_invented() -> None:
    assert dialogue.DialogueState().searched_in_place("búscalo en Google") is None
    assert _searched_state().searched_in_place("no me lo busques en Google") is None


def test_a_web_search_continues_as_its_results_page_in_the_browser() -> None:
    assert dialogue.same_family(("browser.navigate",), ("web.search",))
    assert dialogue.same_family(("browser.navigate.named",), ("web.search",))
    # Counter-cases: the browser's own controls are not the search, nor is a navigation without a search before.
    assert not dialogue.same_family(("browser.control",), ("web.search",))
    assert not dialogue.same_family(("browser.navigate",), ("weather.current",))
    assert dialogue.same_family(("web.search",), ("web.search",))


# 2. The count asked ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "listing"),
    [
        (SEED, Listing(3, "peliculas")),
        ("las 5 mejores series de 2025", Listing(5, "series")),
        ("a list of the 10 best games", Listing(10, "games")),
        ("best five movies of the year", Listing(5, "movies")),
        ("un top tres de libros de terror", Listing(3, "libros")),
        ("5 canciones más escuchadas de 2024", Listing(5, "canciones")),
        ("los mejores restaurantes de Lima", Listing(None, "restaurantes")),
        ("si pero quiero buscar un top 3", Listing(3, "")),
    ],
)
def test_a_ranked_listing_is_read_with_its_count_and_class(text: str, listing: Listing) -> None:
    assert listing_asked(text) == listing


@pytest.mark.parametrize(
    "text",
    [
        "¿quién ganó el Óscar 2026?",  # one answer
        "dame 3 recetas de pan",  # no ranking said: conversation content
        "top 3 de mi lista de tareas",  # the person's own
        "lee mi lista de tareas",
        "la mejor película de 2025",
        "las 300 mejores frases",  # beyond what a search lists
    ],
)
def test_counter_cases_are_not_a_listing(text: str) -> None:
    assert listing_asked(text) is None


def test_the_search_asks_the_provider_for_the_listing() -> None:
    assert compose_facts._with_asked_listing("web.search", {"query": TOPIC}, SEED, SEARCH_SCHEMA) == {
        "query": TOPIC, "listing": True, "limit": 3,
    }
    assert compose_facts._with_asked_listing(
        "web.search", {"query": "restaurantes Lima"}, "los mejores restaurantes de Lima", SEARCH_SCHEMA,
    ) == {"query": "restaurantes Lima", "listing": True}


def test_counter_cases_of_the_listing_arguments() -> None:
    one = {"query": "ganador Óscar 2026"}
    assert compose_facts._with_asked_listing("web.search", one, "¿quién ganó el Óscar 2026?", SEARCH_SCHEMA) == one
    old_schema = {**SEARCH_SCHEMA, "properties": {k: v for k, v in SEARCH_SCHEMA["properties"].items() if k != "listing"}}
    assert compose_facts._with_asked_listing("web.search", {"query": TOPIC}, SEED, old_schema) == {"query": TOPIC}
    assert compose_facts._with_asked_listing("task.list", {"x": 1}, SEED, SEARCH_SCHEMA) == {"x": 1}


def test_the_writer_gets_the_count_asked_and_is_told_fewer_were_found() -> None:
    state = _searched_state()
    situation = _search_result()
    facts = compose_facts._with_listing_and_repetition_facts({"situation": json.dumps(situation)}, situation, state, SEED, SEED)
    told = facts["situation"]
    assert told["askedCount"] == 3
    payload = compose_payload._compose_situation_payload(told, "es", SEED)
    assert payload["askedCount"] == 3
    assert "askedCount" in compose_instructions._compose_shape_instruction(told, "es", SEED)
    # Counter-case: one answer asked, nothing about a count.
    single = compose_facts._with_listing_and_repetition_facts(
        {"situation": situation}, situation, dialogue.DialogueState(), "¿quién ganó el Óscar 2026?", "¿quién ganó el Óscar 2026?",
    )
    assert "askedCount" not in single["situation"]


def test_a_google_results_page_opened_is_named_as_that_search() -> None:
    situation = {
        "operation": "browser.navigate",
        "observed": {"finalUrl": "https://www.google.com/search?q=un+top+3+peliculas"},
    }
    assert compose_instructions._opened_search_in_navigation(situation) == ("Google", "un top 3 peliculas")
    assert compose_instructions._opened_search_in_navigation(
        {"observed": {"finalUrl": "https://drive.google.com/drive/search?q=x"}}
    ) is None


def test_another_search_read_back_is_never_named_as_the_one_opened() -> None:
    # Uso real v3 t4 (c10): Cercanías asked, the address read was the El Aleph search of another conversation.
    mismatch = {
        "observed": {
            "requestedUrl": "https://www.google.com/search?q=los+horarios+del+cercanias+de+madrid",
            "finalUrl": "https://www.google.com/search?q=si+hay+pel%C3%ADcula+de+El+Aleph",
        },
    }
    assert compose_instructions._opened_search_in_navigation(mismatch) is None
    # Counter-cases: the same search read back (spacing and case aside, parameters the page adds), and a final
    # address that is no search page, still name the search asked for.
    same = {
        "observed": {
            "requestedUrl": "https://www.google.com/search?q=los+horarios+del+cercanias",
            "finalUrl": "https://www.google.com/search?q=Los+horarios++del+cercanias&sca_esv=1",
        },
    }
    assert compose_instructions._opened_search_in_navigation(same) == ("Google", "Los horarios  del cercanias")
    consent = {
        "observed": {
            "requestedUrl": "https://www.google.com/search?q=los+horarios",
            "finalUrl": "https://consent.google.com/ml?continue=x",
        },
    }
    assert compose_instructions._opened_search_in_navigation(consent) == ("Google", "los horarios")


# 3. The correction -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["si pero quiero buscar un top 3", "ok pero lo puedes buscar en google", "ya, pero en inglés", "yes but in English"],
)
def test_an_agreement_with_but_corrects_the_last_result(text: str) -> None:
    assert dialogue.followup(text).corrected
    assert dialogue.corrects_or_insists(text)


@pytest.mark.parametrize("text", ["sí, dale", "otra vez", "repítelo", "¿y ahora cuánto está el dólar?", "y en Rosario"])
def test_counter_cases_are_not_a_correction(text: str) -> None:
    assert not dialogue.corrects_or_insists(text)


def test_the_same_plan_after_a_correction_is_not_done_again() -> None:
    state = _searched_state()
    assert state.repeats_the_last_plan(["web.search"], TOPIC, "si pero quiero buscar un top 3")
    # Counter-cases: what the correction changes is done; «otra vez» repeats; «sí, dale» to an offer goes ahead.
    assert not state.repeats_the_last_plan(["web.search"], "un top 3 de series de 2026", "no, mejor series")
    assert not state.repeats_the_last_plan(["browser.navigate"], TOPIC, "si pero en google")
    assert not state.repeats_the_last_plan(["web.search"], TOPIC, "otra vez")
    assert not state.repeats_the_last_plan(["web.search"], TOPIC, "sí, dale")


class _Writer:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str, dict]] = []

    def compose_user_message(self, user_text: str, intent: str, facts: dict, *, said: str | None = None) -> str:
        self.calls.append((user_text, intent, facts))
        return self.reply


def _decided(objective: str = TOPIC) -> dict:
    return {
        "type": "turn.result", "id": "t2", "kind": "action", "operation": "web.search",
        "intentOperations": ["web.search"], "effectOperations": ["web.search"], "question": "", "reply": "",
        "objective": objective,
    }


def test_the_repeated_plan_becomes_the_offer_told_once() -> None:
    state = _searched_state()
    state.told(_search_result(), "Encontré The Eyes, una obra surcoreana de suspenso.")
    writer = _Writer("Es lo único que encontré. ¿Abro la búsqueda en tu navegador?")
    result = turn_followups._not_the_same_again(_decided(), {"id": "t2", "text": "si pero quiero buscar un top 3"}, state, writer)
    assert result["kind"] == "conversation" and result["effectOperations"] == []
    assert result["reply"] == "Es lo único que encontré. ¿Abro la búsqueda en tu navegador?"
    situation = writer.calls[0][2]["situation"]
    assert situation["sameResultAgain"]["previousReply"] == "Encontré The Eyes, una obra surcoreana de suspenso."


def test_counter_cases_of_the_repeated_plan() -> None:
    state = _searched_state()
    state.told(_search_result(), "Encontré The Eyes, una obra surcoreana de suspenso.")
    same_words = _Writer("Encontré The Eyes, una obra surcoreana de suspenso.")
    decided = _decided()
    # The writer giving the old words back leaves the decided turn (its report still carries sameResultAgain).
    assert turn_followups._not_the_same_again(decided, {"text": "si pero quiero buscar un top 3"}, state, same_words) is decided
    # «otra vez» repeats.
    assert turn_followups._not_the_same_again(decided, {"text": "otra vez"}, state, _Writer("x")) is decided


# 4. The repetition -----------------------------------------------------------------------------------------------


def test_the_same_result_after_a_correction_carries_the_old_words() -> None:
    state = _searched_state()
    old = "Encontré The Eyes, una obra surcoreana de suspenso de 2026."
    state.told(_search_result(), old)
    again = {**_search_result(), "observed": {**_search_result()["observed"], "observedAtUtc": "2026-10-07T19:06:00Z"}}
    assert state.same_result_again(again, "si pero quiero buscar un top 3") == old
    facts = compose_facts._with_listing_and_repetition_facts({"situation": again}, again, state, TOPIC, "si pero quiero buscar un top 3")
    assert facts["situation"]["sameResultAgain"] == {"previousReply": old}
    assert visible_defect.compose_visible_defect(old, "status", TOPIC, facts, said="si pero quiero buscar un top 3") == "repeats_last_answer"
    assert "sameResultAgain" in compose_instructions._compose_shape_instruction(facts["situation"], "es", TOPIC)


def test_counter_cases_of_the_repetition() -> None:
    state = _searched_state()
    state.told(_search_result(), "El dólar está a 950 pesos.")
    # «¿y ahora cuánto está el dólar?» is not a correction: the same figure may be told again.
    assert state.same_result_again(_search_result(), "¿y ahora cuánto está el dólar?") is None
    # Another result is not the same one.
    other = _search_result(titles=("Otra película", "Una más", "Y otra"))
    assert state.same_result_again(other, "si pero quiero buscar un top 3") is None
    # Nothing told yet.
    assert dialogue.DialogueState().same_result_again(_search_result(), "no, otra cosa") is None


# Revisión adversarial 2026-10-07 ----------------------------------------------------------------------------------


def test_an_agreement_with_but_before_an_addition_adds() -> None:
    # «ok pero además una a las 9» set another alarm; it must not cancel the last one (continuing → replaces_last).
    adds = dialogue.followup("ok pero además una a las 9")
    assert not adds.corrected and not adds.replaces_last
    assert not dialogue.followup("sí pero también otra de 20").replaces_last
    # Counter-case: without the addition it replaces.
    assert dialogue.followup("ok pero a las 9").replaces_last


@pytest.mark.parametrize(
    "text", ["no, búscalo de nuevo", "sí pero búscalo otra vez", "ok pero intenta otra vez", "no, try again"],
)
def test_a_retry_asked_anywhere_is_not_a_correction(text: str) -> None:
    assert not dialogue.corrects_or_insists(text)
    assert not _searched_state().repeats_the_last_plan(["web.search"], TOPIC, text)


def test_an_effect_corrected_into_itself_is_done_again() -> None:
    # «no, te dije que abras el bloc de notas» after it opened: the effect is decided, not swapped for a remark.
    state = dialogue.DialogueState()
    state.expect("abre el bloc de notas", ["app.open"])
    state.record({"kind": "operation", "operation": "app.open", "verified": True, "succeeded": True,
                  "observed": {"application": "Bloc de notas"}})
    text = "no, te dije que abras el bloc de notas"
    assert not state.repeats_the_last_plan(["app.open"], "abre el bloc de notas", text)
    decided = {"type": "turn.result", "id": "t", "kind": "action", "operation": "app.open",
               "effectOperations": ["app.open"], "objective": "abre el bloc de notas"}
    assert turn_followups._not_the_same_again(decided, {"text": text}, state, _Writer("x")) is decided


def _created(note_id: str) -> dict:
    return {"kind": "operation", "operation": "note.create", "verified": True, "succeeded": True,
            "observed": {"noteId": note_id, "title": "hola"}}


def test_a_creation_is_never_the_same_result_again() -> None:
    state = dialogue.DialogueState()
    state.told(_created("n1"), "Creé la nota «hola».")
    assert state.same_result_again(_created("n2"), "sí, pero crea otra que diga hola") is None
    assert state.same_result_again(_created("n1"), "no, crea la nota hola") is None


def test_result_fields_are_compared_and_only_clock_fields_are_volatile() -> None:
    state = _searched_state()
    old = "Encontré tres páginas."
    first = {**_search_result(), "observed": {**_search_result()["observed"], "items": ["a"], "lat": 1}}
    state.told(first, old)
    other = {**first, "observed": {**first["observed"], "items": ["b"]}}
    assert state.same_result_again(other, "si pero quiero buscar un top 3") is None
    moved = {**first, "observed": {**first["observed"], "lat": 2}}
    assert state.same_result_again(moved, "si pero quiero buscar un top 3") is None
    later = {**first, "observed": {**first["observed"], "receiptId": "r2", "observedAtUtc": "2026-10-07T20:00:00Z"}}
    assert state.same_result_again(later, "si pero quiero buscar un top 3") == old


def test_the_offer_to_open_the_search_is_only_for_a_search() -> None:
    headlines = {"kind": "operation", "operation": "web.news.headlines", "verified": True, "succeeded": True,
                 "polarity": "success",
                 "observed": {"headlines": [{"title": "Uno"}]}, "sameResultAgain": {"previousReply": "Titular: Uno."}}
    instruction = compose_instructions._compose_shape_instruction(headlines, "es", "no, las noticias")
    assert "sameResultAgain" in instruction and "open the search" not in instruction
    search = {**_search_result(), "sameResultAgain": {"previousReply": "x"}}
    assert "open the search" in compose_instructions._compose_shape_instruction(search, "es", "si pero quiero buscar un top 3")


def test_a_listing_is_never_answered_by_counting_pages() -> None:
    # Three pertinent pages are not «the top 3»: the writer is told results are pages, whatever their count.
    three = {**_search_result(titles=("Las 25 mejores películas de suspenso", "Estrenos 2026", "Top de la crítica")),
             "askedCount": 3}
    instruction = compose_instructions._compose_shape_instruction(three, "es", SEED)
    assert "pages, not the items" in instruction and "fewer" not in instruction
    fewer = {**_search_result(), "askedCount": 3}
    assert "fewer" in compose_instructions._compose_shape_instruction(fewer, "es", SEED)
    # Counter-case: no listing asked, nothing about pages.
    assert "pages, not the items" not in compose_instructions._compose_shape_instruction(_search_result(), "es", "¿quién ganó el Óscar?")
