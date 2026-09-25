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
- «¿puedes activar este modo que tienes que repites todo el rato lo mismo que yo digo?» → «No pude entender…»: the
  parrot mode (a known limit) was read only with an imperative right before «lo que digo»; the repeating verb in
  any person or form, a few words before what is said next, is the same mode, and a negated one is not asked.
- «consígueme un billete de tren a madrid para el próximo jueves…» → a web search and ⚠: getting a ticket, a seat or
  a flight is buying it, the same known limit as a product paid with a card; it is never looked up.
- 6c «i would like to know the timezone for britain» → a web search: the zone of a place is named with «for/of/de»
  after the zone's noun; it is the clock of that place, and the zone asked is given as its offset.
- «¿podemos estar un rato en silencio?» → «…¿Quieres que hablemos de algo específico…?»: an unshaped conversational
  reply that offers something more is rejected, as the prompt's «sin ofertas» already asks.
- 6c «Quiero el sound de nuevo please» (sound on at volume 0): the drafts said it was silenced or «desactivado»; the
  sound said disabled over an unmuted read is a reversed mute, «cero» is the level 0, and the hint says it is on.

The phrasings below are not the tandas': they are paraphrases (es/en/spanglish) the fixes do not name, with negative
controls.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic import reading, web
from baxy_mind.semantic.patterns import echo_mode_request, known_unsupported_effect_request
from baxy_mind.semantic.grammar import _fold
from baxy_mind.semantic.temporal import clock_elsewhere, countdown_target

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


# ------------------------------------------------------------------ the parrot mode, said with the verb in any form


@pytest.mark.parametrize(
    "text",
    [
        "pon el modo donde imitas todo lo que digo",
        "quiero que estés repitiendo siempre lo que yo te diga",
        "¿te acuerdas del modo ese en que repetías cada cosa que yo escribo?",
        "can you turn on the mode where you keep repeating everything I say",
        "activate that thing where you mimic whatever I type",
        "oye porfa ponte a repetir to el rato lo mismo que digo",
    ],
)
def test_the_parrot_mode_with_the_verb_in_any_form_is_the_known_limit(text: str) -> None:
    assert echo_mode_request(text)
    assert known_unsupported_effect_request(text, ("web.search", "app.open"))


@pytest.mark.parametrize(
    "text",
    [
        "no repitas lo que digo",
        "don't repeat everything I say",
        "repite lo que dije",
        "¿puedes repetir lo mismo que te he dicho?",
        "repeat what I said",
        "copia lo que escribo en el portapapeles",
        "repite conmigo: hola",
    ],
)
def test_a_negated_repetition_or_a_recall_is_not_the_parrot_mode(text: str) -> None:
    assert not echo_mode_request(text)


# ------------------------------------------------------------------ getting a ticket is buying it: a limit


@pytest.mark.parametrize(
    "text",
    [
        "cómprame dos entradas pal concierto de la Rosalía",
        "book me a flight to London next friday",
        "oye sácame un pasaje a Santiago pa mañana",
        "get me a ticket for the 8pm show",
        "resérvame un asiento en el bus a Córdoba",
        "alexa buy me tickets for the Lakers game",
        "porfa consígueme boletos pal cine el sábado",
        "Get me vanilla, wait, cinnamon using my American Express card.",
    ],
)
def test_getting_a_ticket_or_a_paid_product_is_a_known_limit_not_a_lookup(text: str) -> None:
    assert known_unsupported_effect_request(text, ("web.search", "app.open"))
    # With a purchase operation served, it is that operation's, never a limit.
    assert not known_unsupported_effect_request(text, ("commerce.product.purchase",))


@pytest.mark.parametrize(
    "text",
    [
        "busca billetes de tren a madrid",
        "cuánto cuesta un billete a madrid",
        "a qué hora sale el tren a madrid",
        "consígueme el horario del tren a madrid",
        "how much is a flight to London",
        "saca una foto",
        "get me the new zelda game with my visa",
    ],
)
def test_asking_about_tickets_or_times_is_not_a_purchase(text: str) -> None:
    assert not known_unsupported_effect_request(text, ("web.search", "app.open"))


# ------------------------------------------------------------------ the zone of a place is read on the clock


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("cuál es la zona horaria de Japón", "japon"),
        ("what is the time zone of Australia", "australia"),
        ("dime el huso horario de chile porfa", "chile"),
        ("which timezone for new zealand", "new zealand"),
        ("zona horaria del peru?", "peru"),
    ],
)
def test_the_zone_of_a_place_is_the_clock_elsewhere(text: str, place: str) -> None:
    asked = clock_elsewhere(_fold(text))
    assert asked is not None and asked.place == place and asked.zone
    got = reading.read(text, available_operations=("system.time", "web.search"))
    assert got.effects is not None and got.effects.operations == ("system.time",)


@pytest.mark.parametrize(
    "text", ["cuál es mi zona horaria", "change the time zone for this pc", "zona horaria de mi pc", "qué es un huso horario"],
)
def test_this_pcs_zone_or_the_word_itself_is_no_other_place(text: str) -> None:
    assert clock_elsewhere(_fold(text)) is None


def test_the_zone_asked_is_given_as_its_offset_and_the_time_alone_is_not() -> None:
    observed = {
        "version": 1, "utc": "2026-09-25T03:35:00Z", "localUtcOffsetMinutes": -180,
        "place": {"name": "Tokio", "country": "Japón", "timeZone": "Asia/Tokyo", "utcOffsetMinutes": 540,
                  "authority": "named_place_geocoded"},
    }
    zone = llm._place_clock_facts(observed, "what's the time zone of tokyo", "en")
    assert zone is not None and zone["zone"] == "UTC+09:00 (Asia/Tokyo)" and zone["clock"] == "12:35"
    clock = llm._place_clock_facts(observed, "qué hora es en tokio", "es")
    assert clock is not None and "zone" not in clock


# ------------------------------------------------------------------ a conversational reply offers nothing more


@pytest.mark.parametrize(
    "reply",
    [
        "Claro, me quedo callado. ¿Quieres que te ponga algo de música mientras tanto?",
        "Sure, I'll be quiet. Want me to play something relaxing?",
        "La capital de Australia es Canberra. ¿Te gustaría saber más sobre ella?",
        "Vale, tranqui. ¿Te apetece que ponga algo suave?",
        "Okay. Do you want some white noise?",
    ],
)
def test_a_conversational_reply_offering_more_is_rejected(reply: str) -> None:
    assert _violates(reply, "¿nos quedamos un rato calladitos?", None)


@pytest.mark.parametrize(
    "reply",
    [
        "Claro, me quedo en silencio.",
        "Sure, quiet it is.",
        "La capital de Australia es Canberra.",
        "¡Hola! ¿Qué tal tu día?",
        # A greeting's own question is no offer of something more.
        "¡Hola! ¿En qué puedo ayudarte?",
    ],
)
def test_a_conversational_reply_without_an_offer_passes(reply: str) -> None:
    assert not _violates(reply, "¿nos quedamos un rato calladitos?", None)


# ------------------------------------------------------------------ the sound already on is said as read


def _sound_on_at_zero() -> dict:
    return {
        "kind": "operation", "operation": "audio.mute", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {
            "operation": "audio.mute", "targetId": "default_output", "endpointIdHash": "0" * 64,
            "baseline": {"volumePercent": 0, "muted": False}, "final": {"volumePercent": 0, "muted": False},
            "applied": False, "reconciled": False,
        },
    }


def _sound_defect(reply: str, asked: str) -> str:
    situation = _sound_on_at_zero()
    payload = llm._compose_situation_payload(situation, "es", asked)
    return llm.compose_visible_defect(reply, "status", asked, {"situation": json.dumps(situation)}) or (
        llm._payload_fact_defect(reply, payload, asked)
    )


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("devuélveme el sonido porfa", "El sonido ya está activo y el volumen está en cero."),
        ("sound back on pls", "The sound is already on; the volume is at zero."),
    ],
)
def test_the_sound_on_with_its_level_said_as_a_word_passes(asked: str, reply: str) -> None:
    assert _sound_defect(reply, asked) == ""


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("devuélveme el sonido porfa", "El sonido está desactivado y el volumen es cero."),
        ("sound back on pls", "The sound is disabled and the volume is at zero."),
    ],
)
def test_the_sound_said_disabled_over_an_unmuted_read_is_a_reversed_mute(asked: str, reply: str) -> None:
    assert _sound_defect(reply, asked) == "reversed_mute"
