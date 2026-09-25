"""Tandas 6c and 7 (2026-09-25, official window): single-message misses.

- «¿quién te desarrolló?» → «No tengo información sobre quién me desarrolló.»: the identity answer told nothing about
  him; it now carries one of his facts (his name or the PC he lives on) beside the detail he does not have.
- «¿cuánto rato queda para las seis?» → a web search and «No se indica…»: the countdown reading knew only «cuánto
  (tiempo) falta/queda/resta»; any measure of time and any verb of remaining asks the same countdown.
- «No se menciona ningún famoso…», «…los resultados de búsqueda son irrelevantes»: the lookup is invisible; an
  absence told as what the pages do not say, or a failed search told as a search, is rejected, and the fact of a
  lookup that answered nothing is that it was not found.
- «¿hoy qué día tengo que marcar en el calendario?» → «El fallo ocurre porque este PC no tiene un perfil clásico de
  Outlook…»: the fact named the profile as a technicality; it now says Outlook is not set up and cannot be reached.
- «alto precio de las acciones» → «Los expertos de TU han preparado para ti una lista…», «sería genial cenar en este
  nuevo restaurante…» → «Se pueden consultar menús, reseñas…»: the page addressing its reader («para ti») or offering
  what can be done on it is its voice. «Bob Dean afirma que … nunca lo hemos estado» is reported speech, not the page.
- «alexa dime todo lo que sabes sobre bob dean»: what he knows about a name, after an address, asks who or what it
  is; the bare name is looked up and answered from its pages.

The phrasings below are not the tandas': they are paraphrases (es/en/spanglish) the fixes do not name, with negative
controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.semantic import reading, web
from baxy_mind.semantic.temporal import countdown_target

_violates = llm._shaped_conversation_answer_violates_contract

# ------------------------------------------------------------------ identity: one of his facts, never a bare «no info»


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("¿quién te programó?", "No tengo información sobre quién me programó."),
        ("who built you?", "I don't have information about who built you."),
        ("quién te hizo, bro", "No sé quién me hizo."),
        ("who's your creator", "I don't know who my creator is."),
    ],
)
def test_a_bare_no_information_identity_answer_is_rejected(request_text: str, reply: str) -> None:
    assert _violates(reply, request_text, "identity")


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("¿quién te programó?", "Soy BAXY y vivo en este PC; quién me programó no lo sé."),
        ("who built you?", "I'm BAXY, a program that lives on this PC; I don't have who built me."),
        ("quién te hizo, bro", "No tengo ese dato: soy un programa que vive en este PC."),
        ("dime quién te creó", "Soy BAXY; no tengo el dato de quién me creó."),
    ],
)
def test_an_identity_answer_with_one_of_his_facts_passes(request_text: str, reply: str) -> None:
    assert not _violates(reply, request_text, "identity")


def test_the_identity_instructions_ask_for_one_of_his_facts_beside_the_missing_detail() -> None:
    prompt = llm.IDENTITY_PRESENTATION_PROMPT
    assert "say plainly you do not have that" in prompt
    assert "say who you are from these facts" in prompt


# ------------------------------------------------------------------ the time left to a clock time is a countdown


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("cuántas horas faltan para las 8 de la noche", "20:00"),
        ("cuantos minutos quedan pa las 3", "03:00"),
        ("qué tanto falta para que sean las once", "11:00"),
        ("cuánto rato falta hasta las 10 y media", "10:30"),
        ("how many minutes until 5 pm", "17:00"),
        ("how much time is left till noon", "12:00"),
        ("how long do we have until six o'clock", "06:00"),
        ("how many hours to go until midnight", "00:00"),
        ("oye, cuánto tiempo queda para las siete de la tarde?", "19:00"),
    ],
)
def test_the_time_left_to_a_clock_time_is_a_countdown(text: str, target: str) -> None:
    assert countdown_target(text) == target


@pytest.mark.parametrize(
    "text",
    [
        "cuánto falta para mi cumpleaños",
        "cuánto queda de batería",
        "how long until christmas",
        "cuánto rato queda de película",
        "cuántos minutos quedan en el temporizador",
        "how many minutes are left in the game",
    ],
)
def test_time_left_of_something_else_is_not_a_clock_countdown(text: str) -> None:
    assert countdown_target(text) is None


@pytest.mark.parametrize(
    "text", ["¿cuánto rato queda para las nueve?", "how many minutes until 4 pm", "cuántas horas faltan pa las 11"],
)
def test_a_countdown_is_read_on_the_clock_not_searched(text: str) -> None:
    got = reading.read(text, available_operations=("system.time", "web.search"))
    assert got.effects is not None and got.effects.operations == ("system.time",)


# ------------------------------------------------------------------ a lookup that did not answer is «not found»

_SEARCHED = {
    "operation": "web.search",
    "seen": {
        "query": "músicos famosos que tocaron en orquestas juveniles",
        "count": 1,
        "results": [{
            "title": "Los cantantes más famosos del momento",
            "url": "https://musica.example.com/famosos",
            "snippet": "Una lista de los diez artistas que dominan hoy la escena musical global.",
        }],
    },
}
_SEARCH_FAILED = {
    "outcome": "failed",
    "reason": {"outcome": "failed", "cause": "it was not found; say only that, briefly", "operation": "web.search"},
}


@pytest.mark.parametrize(
    ("draft", "payload"),
    [
        ("No se menciona ningún músico famoso que tocara en una orquesta juvenil.", _SEARCHED),
        ("No se indica qué músicos famosos tocaron en orquestas juveniles.", _SEARCHED),
        ("No se especifican nombres de músicos de orquestas juveniles.", _SEARCHED),
        ("Famous musicians from youth orchestras are not mentioned.", _SEARCHED),
        ("There is no mention of famous musicians from youth orchestras.", _SEARCHED),
        ("No se sabe quién ganó porque los resultados de búsqueda son irrelevantes.", _SEARCH_FAILED),
        ("The web search results were irrelevant to the time zone of Britain.", _SEARCH_FAILED),
        ("Según las páginas que encontré, no hay datos del partido.", _SEARCH_FAILED),
    ],
)
def test_an_absence_told_as_what_the_pages_do_not_say_shows_the_search(draft: str, payload: dict) -> None:
    assert llm._payload_fact_defect(draft, payload, "¿qué famosos tocaron en orquestas juveniles?") == (
        "search_report_shows_the_search"
    )


@pytest.mark.parametrize(
    ("draft", "payload"),
    [
        ("No lo encontré.", _SEARCHED),
        ("No encontré ningún músico famoso que tocara en una orquesta juvenil.", _SEARCHED),
        ("I couldn't find a famous musician who played in a youth orchestra.", _SEARCHED),
        ("No encontré quién ganó el partido de anoche.", _SEARCH_FAILED),
        ("I couldn't find it.", _SEARCH_FAILED),
    ],
)
def test_not_found_said_briefly_is_the_answer(draft: str, payload: dict) -> None:
    assert llm._payload_fact_defect(draft, payload, "¿qué famosos tocaron en orquestas juveniles?") != (
        "search_report_shows_the_search"
    )


def test_a_positive_statement_with_a_participle_is_not_an_absence() -> None:
    assert llm._payload_fact_defect(
        "Los diez artistas que dominan hoy la escena musical fueron nombrados en una lista global.",
        _SEARCHED,
        "¿qué artistas dominan la escena musical?",
    ) != "search_report_shows_the_search"
    assert not llm._SEARCH_NARRATED_ABSENCE.search("he was named best player and was given the award")


@pytest.mark.parametrize(
    ("code", "forbidden"),
    [
        ("web_search_results_irrelevant", ("search", "result", "irrelevant", "page")),
        ("outlook_profile_not_configured", ("profile", "classic")),
    ],
)
def test_the_fact_of_a_failure_says_what_the_person_hears_not_the_mechanism(
    code: str, forbidden: tuple[str, ...],
) -> None:
    fact = llm._cause_in_prose(code, "es")
    assert fact != code.replace("_", " ")
    assert not any(word in fact.casefold() for word in forbidden)


@pytest.mark.parametrize(
    "draft",
    [
        "No puedo ver tu calendario de Outlook: Outlook no está configurado en este PC.",
        "I can't reach your Outlook calendar, Outlook isn't set up on this PC.",
        "No pude abrir tu agenda de Outlook porque no está configurado aquí.",
    ],
)
def test_the_unreachable_outlook_said_plainly_is_the_failure_told(draft: str) -> None:
    assert llm._asserts_failure(draft)


# ------------------------------------------------------------------ the page's voice: its offer to the reader


_PAGES = {
    "operation": "web.search",
    "seen": {
        "query": "q",
        "count": 1,
        "results": [{
            "title": "Restaurantes nuevos en el centro",
            "url": "https://comer.example.com/nuevos",
            "snippet": "Descubre los restaurantes abiertos cerca de ti. Consulta menús, reseñas y fotos.",
        }],
    },
}


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        ("Se pueden consultar menús, reseñas y fotos de los restaurantes nuevos del centro.",
         "me encantaría probar el restaurante nuevo del centro"),
        ("Puedes reservar mesa y comparar precios en los restaurantes del centro.", "algún sitio nuevo pa cenar?"),
        ("You can browse menus and book a table at the new places downtown.", "any new restaurant downtown?"),
        ("Los analistas han seleccionado para ti las acciones más caras del momento.", "acciones caras"),
        ("Here are the priciest stocks, handpicked for you by our team.", "most expensive stocks rn"),
        ("Hoy podrás descubrir los mejores sitios para cenar.", "dónde ceno hoy"),
    ],
)
def test_a_page_offering_itself_to_its_reader_is_its_voice(draft: str, asked: str) -> None:
    assert llm._search_report_speaks_as_a_page(draft, _PAGES, asked)


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        ("Se puede ver la aurora boreal en Tromsø entre septiembre y marzo.", "dónde se ve la aurora boreal"),
        ("You can visit the Louvre for free on the first Friday of the month.", "is the louvre free"),
        ("Bob Dean afirma que nunca hemos estado solos en el universo.", "qué sabes de bob dean"),
        ("He claimed that we are not alone and that our planet is watched.", "who is bob dean"),
        ("El restaurante nuevo del centro abre de 13 a 23 h.", "a qué hora abre el restaurante nuevo del centro"),
    ],
)
def test_an_answer_reported_or_asked_for_themselves_is_not_the_page_speaking(draft: str, asked: str) -> None:
    assert not llm._search_report_speaks_as_a_page(draft, _PAGES, asked)


def test_the_page_speaking_for_itself_is_still_its_voice() -> None:
    assert llm._search_report_speaks_as_a_page("Nuestro conversor te dice el cambio al instante.", _PAGES, "dólar hoy")
    assert llm._search_report_speaks_as_a_page("Hemos preparado una guía de los mejores sitios.", _PAGES, "sitios")


# ------------------------------------------------------------------ what he knows about a name is who or what it is


@pytest.mark.parametrize(
    ("text", "entity"),
    [
        ("siri, what do you know about Nikola Tesla", "Nikola Tesla"),
        ("qué sabes de Messi", "Messi"),
        ("tell me everything you know about Daft Punk", "Daft Punk"),
        ("oye cuéntame lo que sabes de Rosalía", "Rosalía"),
        ("what can you tell me about Pompeii", "Pompeii"),
        ("qué me puedes contar de Frida Kahlo", "Frida Kahlo"),
        ("que conocés de Neruda", "Neruda"),
        ("alexa quién es Shakira", "Shakira"),
    ],
)
def test_what_he_knows_about_a_name_looks_up_the_name(text: str, entity: str) -> None:
    assert web._entity_lookup_query(text) == entity


@pytest.mark.parametrize(
    "text",
    [
        "qué sabes sobre ti",
        "what do you know about yourself",
        "que sabes de mi",
        "qué sabes hacer",
        "what do you know about my files",
        "dime todo lo que sabes sobre los perezosos",
    ],
)
def test_what_he_knows_about_himself_the_person_or_a_common_noun_is_no_name_lookup(text: str) -> None:
    assert web._entity_lookup_query(text) is None
