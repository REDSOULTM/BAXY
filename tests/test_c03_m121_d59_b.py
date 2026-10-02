"""M121 (2026-10-02): the owner's decisions D59 items 4, 5 and 8, with phrasings of our own (es/en).

4. Music, songs or a playlist asked for a purpose («pon mi playlist de gym», «put on party songs», «música para
   estudiar») is music for that purpose, searched and played (``semantic.media.purpose_music_query``); a playlist the
   person named by its own name («mi playlist «Viaje 2024»») is still theirs and still asked.
5. A new list with nothing on it («crea una lista de la compra», «make a packing list») is made empty with its name
   (``semantic.notes.new_list_title``) and the final, written by the model, offers to add things; what the person names
   next goes on it. An entry that names nothing is still asked; a list named as content to write stays with the decider.
8. The analysis of a real, named organization (FODA/DAFO/SWOT, a market analysis, its pros and cons said of «la
   empresa …») is looked up first (``web.search`` on its name + «empresa»/«company») and written from what was read,
   figures only if read (D52); an analysis of a topic that is no named organization stays talk.
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import knowledge
from baxy_mind.semantic.media import purpose_music_query
from baxy_mind.semantic.notes import new_list_title
from baxy_mind.semantic.patterns import known_unsupported_effect_request, resolve_explicit_effects
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "media.control", "media.play.query", "media.play.youtube", "task.create", "task.list", "task.search",
    "web.search", "system.time", "notification.schedule",
)
YOUTUBE = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"],
           "additionalProperties": False}
SPOTIFY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                            "query": {"type": "string"}},
           "required": ["provider", "query"], "additionalProperties": False}
TASK = {"type": "object", "properties": {"title": {"type": "string"}, "details": {"type": "string"},
                                         "due": {"type": ["null", "string"]}},
        "required": ["title"], "additionalProperties": False}


# ------------------------------------------------------------------ 4. music for a purpose


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("ponme mi playlist del gimnasio", "música para entrenar"),
        ("reproduce mi lista de reproducción de yoga", "música para yoga"),
        ("quiero música para concentrarme", "música para estudiar"),
        ("pon canciones para la cena", "música para la cena"),
        ("pon una canción para dormir", "música para dormir"),
        ("pon cualquier cosa de mi playlist de correr", "música para correr"),
        ("play my running playlist", "running music"),
        ("put on some party songs", "party songs"),
        ("play some music for cooking please", "cooking music"),
        ("turn on my road trip playlist", "road trip music"),
    ],
)
def test_music_for_a_purpose_is_searched_and_played(text: str, query: str) -> None:
    assert purpose_music_query(text) == query, text
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None, text
    assert reading.effects is not None and reading.effects.operations == ("media.play.youtube",), text
    assert sidecar._ground_explicit_arguments("media.play.youtube", text, YOUTUBE) == {"query": query}
    assert not known_unsupported_effect_request(text, OPERATIONS), text


def test_music_for_a_purpose_on_spotify_is_searched_there() -> None:
    text = "pon mi playlist de pesas en spotify"
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("media.play.query",)
    assert sidecar._ground_explicit_arguments("media.play.query", text, SPOTIFY) == {
        "provider": "spotify", "query": "música para entrenar",
    }


@pytest.mark.parametrize(
    "text",
    [
        "pon mi playlist «Verano 2023»",  # named by its own name
        'play my "Chill Sunday" playlist',
        "pon mi playlist favorita",  # a taste, no purpose
        "pon mi playlist de los tíos",  # a word that is no purpose names the list
    ],
)
def test_a_playlist_named_by_its_own_name_is_still_asked(text: str) -> None:
    assert purpose_music_query(text) is None, text
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None or "media.play.youtube" not in reading.effects.operations, text


@pytest.mark.parametrize(
    "text",
    [
        "pon algo para dormir",  # no music said (tanda 4: asked)
        "no pongas música para dormir",
        "pon una alarma para el gym",
        "pon la versión de estudio de esa canción",
        "la música para estudiar me aburre",
    ],
)
def test_no_purpose_music_is_read_where_none_is_asked(text: str) -> None:
    assert purpose_music_query(text) is None, text


# ------------------------------------------------------------------ 5. a new list made empty


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("crea una lista para el súper", "Lista para el súper"),
        ("haz una lista de la compra porfa", "Lista de la compra"),
        ("empieza una lista nueva", "Lista nueva"),
        ("make a packing list", "Packing list"),
        ("start a new grocery list", "Grocery list"),
        ("create a new list for my holiday gifts", "List for my holiday gifts"),
    ],
)
def test_a_new_list_is_made_empty_with_its_name(text: str, title: str) -> None:
    assert new_list_title(text) == title, text
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None, text
    assert reading.effects is not None and reading.effects.operations == ("task.create",), text
    assert sidecar._ground_explicit_arguments("task.create", text, TASK) == {"title": title}


@pytest.mark.parametrize(
    "text",
    ["haz una lista de países de Sudamérica", "make a list of the best beaches in Chile", "crea una lista de canciones"],
)
def test_a_list_named_as_content_or_music_is_no_new_list(text: str) -> None:
    assert new_list_title(text) is None, text
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None or "task.create" not in reading.effects.operations, text


def test_an_entry_that_names_nothing_is_still_asked() -> None:
    reading = read("agrega una cosa a mi lista de la compra", available_operations=OPERATIONS)
    assert reading.clarification is not None and reading.clarification.missing_fields == ("list_entries",)


def test_what_the_person_names_after_the_offer_goes_on_the_new_list() -> None:
    effects = resolve_explicit_effects("sí, tomates y arroz", OPERATIONS, previous_user_text="crea una lista para el súper")
    assert effects is not None and effects.operations == ("task.create", "task.create")
    assert [sidecar._ground_explicit_arguments("task.create", said, TASK) for said in effects.evidence] == [
        {"title": "tomates", "details": "lista para el súper"}, {"title": "arroz", "details": "lista para el súper"},
    ]
    for said in ("gracias", "sí", "ok, perfecto", "qué hora es"):
        found = resolve_explicit_effects(said, OPERATIONS, previous_user_text="crea una lista para el súper")
        assert found is None or "task.create" not in found.operations, said


class _Drafts(LlmRuntime):
    """The recorded drafts stand in for the model, in order; every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _created(title: str) -> dict:
    return {
        "kind": "operation", "operation": "task.create", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"taskId": "0b5e7c1e-0000-4000-8000-000000000001", "title": title, "details": "",
                     "completed": False, "deleted": False, "version": 1},
    }


def test_the_final_of_a_new_list_offers_to_add_things() -> None:
    situation = _created("Lista para el súper")
    assert llm._new_empty_list("crea una lista para el súper", situation) == "Lista para el súper"
    assert llm._new_empty_list("añade tomates a la lista para el súper", situation) is None
    offer = "Creé la lista «Lista para el súper», vacía. ¿Quieres que le añada algo?"
    claimed = "Añadí leche a la lista «Lista para el súper». ¿Algo más?"
    assert llm.compose_visible_defect(claimed, "status", "crea una lista para el súper", {"situation": situation})
    writer = _Drafts([offer, offer, offer])
    assert writer.compose_user_message("crea una lista para el súper", "status", {"situation": situation}) == offer
    prompt = json.dumps(writer.requests[0]["messages"], ensure_ascii=False)
    assert "ofrezca añadirle cosas" in prompt
    # The floor, when no draft could be written, says the list was created, not that something was added.
    floor = llm._told_result_final(situation, {"seen": situation["observed"]}, "crea una lista para el súper", "es")
    assert floor == "Creé la lista «Lista para el súper»."


# ------------------------------------------------------------------ 8. analyses of named organizations


@pytest.mark.parametrize(
    ("text", "subject", "query"),
    [
        ("hazme un FODA de Falabella con un tono cercano", "Falabella", "Falabella empresa"),
        ("¿me puedes hacer un análisis DAFO de la empresa Iberia?", "Iberia", "Iberia empresa"),
        ("dame los pros y contras de la marca Patagonia", "Patagonia", "Patagonia empresa"),
        ("análisis de mercado de Mercado Libre", "Mercado Libre", "Mercado Libre empresa"),
        ("write a SWOT analysis of Spotify", "Spotify", "Spotify company"),
        ("what are the strengths and weaknesses of the company Lego", "Lego", "Lego company"),
    ],
)
def test_the_analysis_of_a_named_organization_is_looked_up_first(text: str, subject: str, query: str) -> None:
    found = knowledge.reference_lookup(text)
    assert found is not None and (found.kind, found.subject, found.query) == ("analysis", subject, query), text


@pytest.mark.parametrize(
    "text",
    [
        "hazme un FODA de mi pyme de repostería",
        "pros y contras del trabajo remoto",
        "write a SWOT for a small bakery",
        "pros and cons of Python",  # a named thing that is no organization said as one
        "haz un análisis de Hamlet",
        "¿cómo hiciste el FODA de Falabella?",
        "análisis FODA de la empresa donde trabajo",
    ],
)
def test_an_analysis_of_no_named_organization_stays_talk(text: str) -> None:
    found = knowledge.reference_lookup(text)
    assert found is None or found.kind != "analysis", text


def _searched(results: list[dict]) -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "Falabella empresa", "count": len(results), "results": results},
    }


FALABELLA_READ = [
    {"title": "Falabella - Wikipedia", "url": "https://es.wikipedia.org/wiki/Falabella",
     "snippet": "Falabella es una empresa chilena de retail fundada en 1889 con tiendas por departamento, "
                "mejoramiento del hogar, supermercados y banco en varios países de Sudamérica."},
    {"title": "Falabella cierra tiendas", "url": "https://example.org/falabella",
     "snippet": "La compañía enfrenta la competencia del comercio electrónico y cerró tiendas en Argentina."},
]
SWOT = (
    "Fortalezas:\n- Presencia en varios países de Sudamérica.\n- Negocios variados: tiendas, hogar, supermercados y "
    "banco.\nDebilidades:\n- Cierre de tiendas en Argentina.\nOportunidades:\n- Crecer en el comercio electrónico.\n"
    "Amenazas:\n- La competencia del comercio electrónico."
)


def test_the_analysis_is_written_from_what_was_read_with_its_figures_only() -> None:
    invented = SWOT.replace("- Presencia en varios", "- 120 años y 500 tiendas; presencia en varios")
    writer = _Drafts([invented, SWOT])
    reply = writer.compose_user_message(
        "hazme un FODA de Falabella con un tono cercano", "status", {"situation": _searched(FALABELLA_READ)},
    )
    assert reply == SWOT
    system = writer.requests[0]["messages"][0]["content"]
    assert "Fortalezas:" in system and "Amenazas:" in system
    evidence = json.loads(writer.requests[0]["messages"][1]["content"])["evidence"]
    assert evidence["title"] == "Falabella" and "fundada en 1889" in evidence["text"]
    # 120 and 500 were never read: the second draft is asked without them.
    assert "120" in writer.requests[1]["messages"][-1]["content"]


def test_an_ordinary_search_is_not_written_as_an_analysis() -> None:
    writer = _Drafts([])
    assert writer._compose_consulted_answer(
        "busca noticias de Falabella", {}, _searched(FALABELLA_READ), "es", writer._post, None, "t",
    ) is None
    assert writer.requests == []
