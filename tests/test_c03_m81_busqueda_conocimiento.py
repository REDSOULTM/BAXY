"""M81 (2026-09-30, independent review of the DEV-D real-app run v3m-devD, HEAD d946de8b): the not-ok rows of «búsqueda»
and «conocimiento o código» whose cause is in the code. Each case is a real turn of that run; the payloads and drafts
are the ones the composer judged (tests/data/c03_m81_v3m_search_turns.json, from window/v3m-devD/compose-audit.jsonl).

1. The person's own data went to the web: «It's going to rain en la casa de mamá?» (D-s020), «¿Miguel sigue viviendo
   en Arkansas?» (D-s053). Asked, never looked up.
2. A faithful report died on the question's form: «Who's» after «Yes, that's right.» and «Wedding'» with its quote read
   as names no page carries (D-p19-t2, the cast read and «I couldn't find» said); the headline's own «nuestra vida»
   read as the page speaking (D-s021); «No encontré en los resultados…» (D-p31-t1, D-p34-t1); the site named when the
   person asked where to find a list (D-p34-t3).
3. A report that listed the name asked three times as film titles was published (D-p27-t3).
4. The last resort: the news read is said as its headlines instead of «No lo encontré» (D-s021); the typo is not said
   back (D-w08-t1 «cuánto qedo»).
5. Content and code the model writes: a letter «crear» (D-s030), more of a dialogue being written (D-p36-t2/t3), the
   same content as a list or a table (D-p32-t2), a script described and asked for with «write it» (D-w20-t1/t2), a
   named dish before «recipe» looked up (D-s017).
The provider side (Baxy.Providers.Windows) is tested in ExternalAdaptersTests: «near me» carries this PC's country
(D-p12-t2) and what a share is worth is not an encyclopedia's (D-s012).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.conversation import asks_for_code
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.knowledge import reference_lookup
from baxy_mind.semantic.patterns import conversation_only_content_request
from baxy_mind.semantic.web import (
    asks_where_to_find,
    names_own_data,
    not_a_public_lookup,
    question_names,
    searched_clause,
)

TURNS = json.loads(
    (Path(__file__).parent / "data" / "c03_m81_v3m_search_turns.json").read_text(encoding="utf-8")
)["turns"]


def _blocked(draft: str, ident: str, user: str | None = None) -> str:
    """The checks of the compose loop (``blocked``) over the recorded payload of the turn, as a verified search."""

    turn = TURNS[ident]
    payload = turn["payload"]
    user = turn["text"] if user is None else user
    facts = {"situation": json.dumps({
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": payload["seen"],
    }, ensure_ascii=False)}
    return (
        llm.compose_visible_defect(draft, "status", user, facts)
        or ("invented" if llm._truncated_fact_word(draft, payload) else "")
        or llm._payload_fact_defect(draft, payload, user, said=user)
    )


def _recorded(ident: str, stage: str) -> str:
    return next(item["draft"] for item in TURNS[ident]["drafts"] if item["stage"] == stage)


# ------------------------------------------------------------------ 1. the person's own data stays on the PC


@pytest.mark.parametrize("text", ["It's going to rain en la casa de mamá?", "¿Miguel sigue viviendo en Arkansas?",
                                  "llamé a papá ayer", "¿Laura anda por Madrid?"])
def test_d_s020_d_s053_the_persons_mother_and_a_bare_name_are_their_own_data(text: str) -> None:
    assert names_own_data(text)
    assert not_a_public_lookup(text)


@pytest.mark.parametrize("text", ["síntomas del cáncer de mama", "¿qué dijo el papa Francisco hoy?",
                                  "¿cuántos años tiene la mamá de Messi?", "receta de papa rellena",
                                  "¿Messi sigue jugando en Miami?"])
def test_public_words_that_fold_like_a_parent_are_still_looked_up(text: str) -> None:
    assert not names_own_data(text)


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Dónde vive tu mamá?"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


@pytest.mark.parametrize("text", ["It's going to rain en la casa de mamá?", "¿Miguel sigue viviendo en Arkansas?"])
def test_the_decider_s_search_of_own_data_is_asked_instead(text: str) -> None:
    # v3m: the decider answered web.search with the whole sentence as the query (turn-audit, RUN.jsonl).
    decider = _Decider(ContextDecision(text, "action", ("web.search",), ""))
    result = sidecar._context_decided_result(
        {"id": "m81", "text": text, "history": [{"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool("web.search"), _tool("weather.current")]),
    )
    assert result["kind"] == "clarify"
    assert result["question"]


def test_a_public_search_of_the_decider_still_runs() -> None:
    text = "¿Cuál es la capital de Australia?"
    decider = _Decider(ContextDecision(text, "action", ("web.search",), ""))
    result = sidecar._context_decided_result(
        {"id": "m81", "text": text, "history": [{"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool("web.search")]),
    )
    assert result["kind"] == "action" and result["operation"] == "web.search"


# ------------------------------------------------------------------ 2. faithful reports that died on the question's form


def test_d_p19_t2_the_head_of_a_second_sentence_and_a_quoted_title_are_not_names() -> None:
    assert question_names("Yes, that's right. Who's in it?") == set()
    assert question_names("Who's in the movie 'After the Wedding'?") == {"after", "wedding"}
    for stage in ("first", "retry"):
        assert _blocked(_recorded("D-p19-t2", stage), "D-p19-t2", "Yes, that's right. Who's in it?") == ""
    assert _recorded("D-p19-t2", "first").startswith("The 2006 film stars Mads Mikkelsen")


def test_d_p19_t2_the_not_found_clause_keeps_the_copula_with_its_subject() -> None:
    assert searched_clause("Who's in the movie 'After the Wedding'?", "en") == (
        "who is in the movie 'After the Wedding'", True,
    )
    assert searched_clause("What's the genre?", "en") == ("what the genre is", True)


def test_d_s021_the_headlines_own_first_person_is_the_headline() -> None:
    draft = _recorded("D-s021", "first")
    assert "nuestra vida" in draft
    assert not llm._search_report_speaks_as_a_page(draft, TURNS["D-s021"]["payload"], TURNS["D-s021"]["text"])
    # The page speaking to its reader is still its voice.
    assert llm._search_report_speaks_as_a_page(
        "Nuestra selección de noticias trae lo mejor del día.", TURNS["D-s021"]["payload"], TURNS["D-s021"]["text"]
    )


@pytest.mark.parametrize("ident, stage", [("D-p31-t1", "first"), ("D-p34-t1", "first"), ("D-p34-t1", "third")])
def test_d_p31_t1_d_p34_t1_the_results_named_after_the_not_found_verb_are_clipped(ident: str, stage: str) -> None:
    draft = _recorded(ident, stage)
    assert _blocked(draft, ident) == "search_report_shows_the_search"
    clipped = llm._SEARCH_RESULTS_TAIL.sub("", llm._SEARCH_RESULTS_AFTER_NOT_FOUND.sub(r"\1 ", draft)).rstrip(" ,;")
    assert clipped.startswith("No encontré ") and "resultados" not in clipped
    assert _blocked(clipped, ident) == ""


def test_d_p34_t3_where_to_find_a_list_is_answered_by_where_it_is() -> None:
    assert asks_where_to_find(TURNS["D-p34-t3"]["text"])
    assert not asks_where_to_find("¿Qué cápsulas del tiempo son famosas?")
    assert _blocked(_recorded("D-p34-t3", "retry"), "D-p34-t3") == ""
    # How BAXY searched stays invisible even then.
    assert _blocked("Busqué en internet y hay un anexo de Wikipedia con ellas.", "D-p34-t3") != ""


# ------------------------------------------------------------------ 3. a report that lists the name asked as titles


def test_d_p27_t3_the_same_quote_listed_three_times_lists_nothing_read() -> None:
    draft = _recorded("D-p27-t3", "first")
    assert _blocked(draft, "D-p27-t3") == "search_report_repeats_a_quote"
    assert _blocked(
        'Eugene Dynarski was in two Steven Spielberg films: "El diablo sobre ruedas" and "Encuentros en la '
        'tercera fase".', "D-p27-t3",
    ) == ""


# ------------------------------------------------------------------ 4. the last resort


def test_d_s021_the_news_read_is_said_as_its_headlines() -> None:
    payload = TURNS["D-s021"]["payload"]
    final = llm._asked_news_headlines_final(payload, TURNS["D-s021"]["text"], "es")
    titles = [item["title"] for item in payload["seen"]["results"][:3]]
    assert final == "Estas son las noticias: " + "; ".join(f"«{title}»" for title in titles) + "."
    assert _blocked(final, "D-s021") == ""
    # Only for what-is-happening questions: a parking search that read headlines is not the news asked.
    assert llm._asked_news_headlines_final(payload, "Necesito aparcamiento para mañana.", "es") == ""


def test_d_w08_t1_the_typo_is_not_said_back() -> None:
    payload = TURNS["D-w08-t1"]["payload"]
    clause, _ = searched_clause("cuanto qedo el america anoche", "es")
    assert llm._spelled_as_read(clause, payload) == "cuánto quedó el america anoche"
    # An inflection is not a typo: a different or an added last letter stays as the person said it.
    fake = {"seen": {"query": "x", "results": [{"title": "Llueva o no, casas", "snippet": ""}]},
            "operation": "web.search"}
    assert llm._spelled_as_read("si llueve en las casa", fake) == "si llueve en las casa"


# ------------------------------------------------------------------ 5. content and code the model writes


@pytest.mark.parametrize("text", [
    "Me puedes ayudar a crear una carta de finalización de contrato laboral para un empleado que incumple con sus "
    "tareas constantemente?",
    "agrega a la conversación un fragmento donde se dan cuenta que el xenomorfo logro evadir la expulsion",
    "agrega a la conversación características físicas del xenomorfo",
    "Dame las claves que mencionas en esa respuesta en forma de lista o tabla.",
])
def test_d_s030_d_p36_d_p32_content_asked_is_written(text: str) -> None:
    assert conversation_only_content_request(text)
    assert llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=True) == (
        "content_draft"
    )


@pytest.mark.parametrize("text", [
    "crea una lista de compras", "crea un recordatorio para la carta", "agrega a la conversación a Juan",
    "agrega leche a la lista del super", "crea una carta nueva en Word y guárdala", "crea una carpeta llamada fotos",
    "ponlo en la lista de tareas", "agrega a la historia de Instagram esta foto",
])
def test_lists_reminders_chats_and_files_stay_effects(text: str) -> None:
    assert not conversation_only_content_request(text)


def test_d_w20_t1_t2_a_script_described_and_asked_with_write_it_is_code() -> None:
    first = ("Hey Baxy, estoy haciendo un script en Python y necesito leer un CSV y sacar el promedio de la columna "
             "price, can you write it?")
    assert asks_for_code(first)
    assert asks_for_code("nice, ahora que se salte las filas donde price esté vacío", (first,))
    assert asks_for_code("tengo un script en python, ¿lo puedes escribir?")
    assert not asks_for_code("Write it down in my notes")


def test_d_s017_a_dish_named_before_recipe_is_looked_up() -> None:
    found = reference_lookup("a good southern style mac n cheese recipe")
    assert found is not None and found.kind == "recipe" and found.query == "recipe southern style mac n cheese"
    assert reference_lookup("I need a banana bread recipe").query == "recipe banana bread"
    assert reference_lookup("the best pancake recipe please").query == "recipe pancake"
    for text in ("give me a recipe", "a vegetarian recipe", "save this recipe", "my grandma recipe",
                 "what is your favorite recipe", "quick dinner recipe"):
        assert reference_lookup(text) is None, text
