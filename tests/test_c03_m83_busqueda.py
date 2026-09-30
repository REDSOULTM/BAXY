"""M83 (2026-09-30, independent review of the DEV-D real-app run v3o-devD, HEAD 5761e1ab): the «búsqueda» rows. Each case
is a real turn of that run; the payloads and drafts are the ones the composer judged
(tests/data/c03_m83_v3o_search_turns.json, from window/v3o-devD/compose-audit.jsonl and RUN.jsonl).

1. A dish joined by «and» lost its first half: «…southern-style mac and cheese recipe» → «recipe cheese» (D-s017).
2. A recipe the recipe book did not keep was told from an encyclopedia's definition or as «not found» (D-s017,
   D-w10-t1 «receta sencilla de arepas de queso»): nothing consulted, so it is said from memory with its notice (D35).
3. «No encontré» as the last word (D35 «no se calla»): what pertinent pages do state of the request is said (D-p34-t1
   the time capsules, D-p31-t1 the presidents since 1983); with nothing pertinent read, memory answers with its notice
   (D-p24-t1 a fantasy film with Elijah Wood, D-s111 Barcelona–París, D-p29-t2). Never for what changes with the day
   (D-w08-t1 last night's score, D-s012 a share price) or what is still to come.
4. A work named like the kind asked for is not one of that kind: «Scary Movie» for «scary movies» (D-p29-t2).
5. A day already gone given as the next match (D-w08-t2 «y cuando juega el sigiente» on 30-09 → 27-09).
6. «What's the genre?» after the cast of a film was read alone as a definition and «genre» was looked up (D-p19-t3):
   in a conversation it goes to the contextual decider.
7. «tell me more about the second one» after three headlines looked up the decider's «unemployment headline» and read
   United States figures for a Chilean headline (D-w17-t5): the headline pointed at is the query.
8. «Any good movies for me to watch?» (D-p27-t1): the decider (full3) talked in v3l and v3o and looked it up in v3m with
   the same code; the talk recommended «the latest sci-fi flick about time travel». Works asked for with none named
   are looked up.
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.dialogue import DialogueState, asks_attribute_of_the_last, leans_on_context
from baxy_mind.semantic.knowledge import reference_lookup, works_recommendation
from baxy_mind.semantic.web import asks_upcoming, memory_may_answer

TURNS = json.loads(
    (Path(__file__).parent / "data" / "c03_m83_v3o_search_turns.json").read_text(encoding="utf-8")
)["turns"]
RECORDED_DAY = date(2026, 9, 30)


def _situation(ident: str) -> dict:
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": TURNS[ident]["payload"]["seen"],
    }


def _facts(ident: str) -> dict:
    return {"situation": json.dumps(_situation(ident), ensure_ascii=False)}


def _blocked(draft: str, ident: str, user: str | None = None) -> str:
    """The checks of the compose loop (``blocked``) over the recorded payload of the turn, as a verified search."""

    payload = TURNS[ident]["payload"]
    user = TURNS[ident]["text"] if user is None else user
    return (
        llm.compose_visible_defect(draft, "status", user, _facts(ident))
        or ("invented" if llm._truncated_fact_word(draft, payload) else "")
        or llm._payload_fact_defect(draft, payload, user, said=user)
    )


def _recorded(ident: str, stage: str) -> str:
    return next(item["draft"] for item in TURNS[ident]["drafts"] if item["stage"] == stage)


class _Writer(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


@pytest.fixture
def recorded_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_report_today", lambda: RECORDED_DAY)


# ------------------------------------------------------------------ 1. a dish joined by «and»


def test_d_s017_a_dish_joined_by_and_keeps_both_halves() -> None:
    # v3o: the decider restated «Give me a good southern-style mac and cheese recipe.» and the lookup read «recipe cheese».
    restated = "Give me a good southern-style mac and cheese recipe."
    assert TURNS["D-s017"]["payload"]["seen"]["query"] == "recipe cheese"
    assert reference_lookup(restated).query == "recipe southern style mac and cheese"
    assert reference_lookup("Give me a recipe for mac and cheese").query == "recipe mac and cheese"
    assert reference_lookup("a recipe for rice and beans and tell me how long it takes").query == "recipe rice and beans"
    assert reference_lookup("receta de arroz con leche y me dices cuánto demora").query == "receta arroz con leche"
    # M81's cases stand.
    assert reference_lookup(TURNS["D-s017"]["text"]).query == "recipe southern style mac n cheese"
    assert reference_lookup("my grandma recipe") is None


# ------------------------------------------------------------------ 2. a recipe nothing could be consulted for


HONEST_ES = (
    "No pude comprobarlo; de memoria, puede no ser exacto:\nIngredientes:\n- 2 tazas de harina de maíz precocida\n"
    "- 1 taza de queso rallado\n- Agua tibia y sal\nPreparación:\n1. Mezcla la harina con el agua, la sal y el queso.\n"
    "2. Forma las arepas y ásalas en un sartén."
)


@pytest.mark.parametrize("ident, request_text", [
    ("D-w10-t1", "Dame una receta sencilla de arepas de queso."),
    ("D-s017", "Give me a good southern-style mac and cheese recipe."),
])
def test_d_w10_t1_d_s017_a_recipe_read_from_no_recipe_is_said_from_memory(ident: str, request_text: str) -> None:
    english = ident == "D-s017"
    honest = HONEST_ES if not english else (
        "I couldn't check this; from memory, it may not be exact:\nIngredients:\n- 8 oz elbow macaroni\n"
        "- 2 cups cheddar\n- 2 cups milk\nSteps:\n1. Boil the macaroni.\n2. Stir in the milk and cheese and bake."
    )
    writer = _Writer([honest])
    answer = writer._compose_consulted_answer(
        request_text, {}, _situation(ident), "en" if english else "es", writer._post, None, "t",
    )
    assert answer == honest
    # M87: the form asked for is the recipe's.
    assert writer.requests[0]["messages"][0]["content"] == llm._memory_answer_prompt(request_text, [], english)
    assert ("«Ingredients:»" if english else "«Ingredientes:»") in writer.requests[0]["messages"][0]["content"]
    # What v3o published instead: the encyclopedia's arepa, and «not found»; the read carried no recipe.
    assert TURNS["D-w10-t1"]["reply"].startswith("Las arepas de queso se elaboran")
    assert TURNS["D-s017"]["reply"] == "I did not find a mac and cheese recipe."
    assert llm._read_no_recipe(_situation(ident))


def test_a_search_that_is_not_a_recipe_keeps_the_ordinary_composition() -> None:
    writer = _Writer([])
    assert writer._compose_consulted_answer(
        "¿Qué es una arepa?", {}, _situation("D-w10-t1"), "es", writer._post, None, "t",
    ) is None
    assert writer.requests == []


# ------------------------------------------------------------------ 3. «no encontré» is not the last word


def test_what_memory_may_answer_is_what_an_encyclopedia_keeps() -> None:
    for ident in ("D-p24-t1", "D-s111", "D-p31-t1", "D-p34-t1", "D-p29-t2", "D-s017"):
        assert memory_may_answer(TURNS[ident]["text"]), ident
    for ident in ("D-w08-t1", "D-w08-t2", "D-s012"):
        assert not memory_may_answer(TURNS[ident]["text"]), ident
    for text in ("¿quién es el presidente de Chile?", "what's the weather tomorrow", "farmacias cerca de mí",
                 "¿Vale la pena ver The Last of Us?", "who won the world cup this year", "¿Miguel sigue viviendo en Arkansas?",
                 "precio del dólar hoy", "a cuánto está el yen frente al peso chileno",
                 "can you give me a traffic update for a trip to the grocery store",
                 "Is there valet parking at the Sofitel Marrakech?", "Can you search for movies in Santa ROsa.",
                 "me gustaría saber qué está pasando por el mundo", "tell me more about the second one"):
        assert not memory_may_answer(text), text


def test_d_p34_t1_what_pertinent_pages_state_is_said() -> None:
    reply = TURNS["D-p34-t1"]["reply"]
    assert reply.startswith("No encontré")
    partial = (
        "Entre las cápsulas del tiempo famosas están la Cripta de la Civilización y las de Westinghouse, y un "
        "monumento de 1968 en Amarillo, Texas, con cuatro cápsulas que se abrirán a los 25, 50, 100 y 1000 años."
    )
    writer = _Writer([partial])
    answer = writer._answer_after_not_found(reply, TURNS["D-p34-t1"]["text"], _facts("D-p34-t1"), said=None, deadline=None)
    assert answer == partial
    assert writer.requests[0]["messages"][0]["content"] == llm.PARTIAL_REPORT_PROMPT
    shown = json.loads(writer.requests[0]["messages"][1]["content"])["results"]
    assert any("Cripta de la Civilización" in item["text"] for item in shown)


def test_d_p31_t1_a_partial_draft_the_pages_do_not_support_is_not_said() -> None:
    reply = TURNS["D-p31-t1"]["reply"]
    unsupported = "Los presidentes fueron Alfonsín, Menem, De la Rúa, Duhalde, Kirchner y Macri."
    faithful = (
        "Desde la vuelta a la democracia en 1983, el primer presidente de Argentina fue Raúl Ricardo Alfonsín, "
        "abogado y político."
    )
    writer = _Writer([unsupported, faithful])
    answer = writer._answer_after_not_found(reply, TURNS["D-p31-t1"]["text"], _facts("D-p31-t1"), said=None, deadline=None)
    assert answer == faithful
    assert len(writer.requests) == 2


@pytest.mark.parametrize("ident, honest", [
    ("D-p24-t1", "I couldn't check this; from memory, it may not be exact: The Lord of the Rings: The Fellowship of the "
                 "Ring (2001) is a fantasy film starring Elijah Wood."),
    ("D-s111", "No pude comprobarlo; de memoria, puede no ser exacto: son unos 1.000 km por carretera."),
])
def test_d_p24_t1_d_s111_with_nothing_pertinent_read_memory_answers_with_its_notice(ident: str, honest: str) -> None:
    reply = TURNS[ident]["reply"]
    assert llm._SEARCH_NOT_FOUND.match(llm._reading_fold(reply))
    writer = _Writer([honest])
    answer = writer._answer_after_not_found(reply, TURNS[ident]["text"], _facts(ident), said=None, deadline=None)
    assert answer == honest
    english = ident == "D-p24-t1"
    assert writer.requests[0]["messages"][0]["content"] == llm._memory_answer_prompt(TURNS[ident]["text"], [], english)


def test_an_answer_from_memory_without_its_notice_is_not_said() -> None:
    reply = TURNS["D-s111"]["reply"]
    silent = "La distancia entre Barcelona y París es de unos 1.000 km."
    writer = _Writer([silent, silent])
    assert writer._answer_after_not_found(reply, TURNS["D-s111"]["text"], _facts("D-s111"), said=None, deadline=None) == ""


@pytest.mark.parametrize("ident", ["D-w08-t1", "D-s012"])
def test_d_w08_t1_d_s012_what_changes_with_the_day_stays_not_found(ident: str) -> None:
    writer = _Writer([])
    assert writer._answer_after_not_found(
        TURNS[ident]["reply"], TURNS[ident]["text"], _facts(ident), said=None, deadline=None,
    ) == ""
    assert writer.requests == []


def test_a_report_that_says_something_is_not_a_not_found() -> None:
    writer = _Writer([])
    report = "No encontré la lista completa. La Cripta de la Civilización es de 1936."
    assert writer._answer_after_not_found(
        report, TURNS["D-p34-t1"]["text"], _facts("D-p34-t1"), said=None, deadline=None,
    ) == ""
    assert writer.requests == []


def test_the_answer_after_a_not_found_runs_in_compose_user_message() -> None:
    # The three recorded drafts of D-s111 are rejected as they were in v3o and the last resort says «No encontré…»;
    # then memory answers.
    honest = "No pude comprobarlo; de memoria, puede no ser exacto: son unos 1.000 km por carretera."
    drafts = [item["draft"] for item in TURNS["D-s111"]["drafts"]]
    writer = _Writer([drafts[0], drafts[1], drafts[1], honest])
    reply = writer.compose_user_message(TURNS["D-s111"]["text"], "status", _facts("D-s111"))
    assert reply == honest


# ------------------------------------------------------------------ 4. a namesake is not the kind asked for


def test_d_p29_t2_scary_movie_is_not_a_scary_movie() -> None:
    assert _blocked(_recorded("D-p29-t2", "first"), "D-p29-t2") == "search_report_off_subject"
    assert _blocked("I couldn't find scary movies.", "D-p29-t2") == ""
    text = TURNS["D-p29-t2"]["text"]
    for item in TURNS["D-p29-t2"]["payload"]["seen"]["results"]:
        assert llm._search_result_is_a_namesake(item, text), item["title"]
    # A kind's own article, a work of the kind and a name the person typed in lower case are not namesakes.
    assert not llm._search_result_is_a_namesake({"title": "Horror film"}, text)
    assert not llm._search_result_is_a_namesake({"title": "The Conjuring"}, text)
    assert not llm._search_result_is_a_namesake({"title": "The Beatles"}, "search for the beatles")
    assert not llm._search_result_is_a_namesake({"title": "Scary Movie"}, "Search for Scary Movie.")
    # D-p29-t1 (Gil Bellows' films) is published as it was.
    assert _blocked(_recorded("D-p29-t1", "retry"), "D-p29-t1") == ""


# ------------------------------------------------------------------ 5. a day already gone is not the next one


def test_d_w08_t2_a_past_day_is_not_the_next_match(recorded_day: None) -> None:
    assert asks_upcoming(TURNS["D-w08-t2"]["text"])
    assert not asks_upcoming(TURNS["D-w08-t1"]["text"])
    draft = _recorded("D-w08-t2", "first")
    assert _blocked(draft, "D-w08-t2") == "search_report_past_as_next"
    assert llm._search_report_past_as_next(draft, TURNS["D-w08-t2"]["payload"], TURNS["D-w08-t2"]["text"]) == "2026-09-27"
    for said in ("No encontré cuándo juega el siguiente partido del América.",
                 "No encontré cuándo juega el siguiente partido del América; el del 27 de septiembre ya se jugó."):
        assert _blocked(said, "D-w08-t2") == ""


def test_the_same_day_still_ahead_is_the_next_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_report_today", lambda: date(2026, 9, 26))
    assert _blocked(_recorded("D-w08-t2", "first"), "D-w08-t2") == ""


# ------------------------------------------------------------------ 6. an attribute of what was just named


@pytest.mark.parametrize("text", ["What's the genre?", "¿Cuál es el género?", "who's the director?", "y cuál es la trama"])
def test_d_p19_t3_an_attribute_without_its_owner_leans_on_the_conversation(text: str) -> None:
    assert asks_attribute_of_the_last(text) and leans_on_context(text)


@pytest.mark.parametrize("text", ["What is photosynthesis?", "What's the capital of France?", "what's the time",
                                  "What's the genre of Alien?"])
def test_a_question_that_names_its_subject_stands_alone(text: str) -> None:
    assert not asks_attribute_of_the_last(text)


class _Decider:
    """The contextual decider: it restates the message with the conversation."""

    def __init__(self, decision: decider.ContextDecision) -> None:  # noqa: D107
        self.decision = decision
        self.decided = 0
        self.chats = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decided += 1
        return self.decision

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Photosynthesis is how plants turn light into chemical energy.", []

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


P19 = [
    ("user", TURNS["D-p19-t1"]["text"]), ("assistant", TURNS["D-p19-t1"]["reply"]),
    ("user", TURNS["D-p19-t2"]["text"]), ("assistant", TURNS["D-p19-t2"]["reply"]),
]


def _turn(text: str, model: _Decider, history: list[tuple[str, str]]) -> dict[str, object]:
    tools = {name: _tool(name) for name in ("web.search", "streaming.play.named", "media.control")}
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._prepare_turn_result(
        {"id": "m83", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


def test_d_p19_t3_the_genre_of_the_film_just_read_is_the_deciders() -> None:
    restated = "What's the genre of the movie 'After the Wedding'?"
    model = _Decider(decider.ContextDecision(restated, "action", ("web.search",), ""))
    result = _turn("What's the genre?", model, P19)
    assert model.decided == 1 and model.chats == 0
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert result["objective"] == restated


def test_a_definition_that_names_its_subject_keeps_its_readers() -> None:
    # «What is photosynthesis?» names what it asks about: the readers keep it (as before M83), not the decider.
    model = _Decider(decider.ContextDecision("x", "talk", (), ""))
    _turn("What is photosynthesis?", model, P19)
    assert model.decided == 0


# ------------------------------------------------------------------ 7. the headline pointed at


def _headlines_read() -> DialogueState:
    state = DialogueState()
    state.expect("What are today's news headlines?", ["web.news.headlines"])
    payload = TURNS["D-w17-t4"]["payload"]
    state.record({"kind": "operation", "operation": "web.news.headlines", "verified": True, "succeeded": True,
                  "observed": payload["seen"]})
    return state


def test_d_w17_t5_the_second_headline_is_looked_up_as_it_was_written() -> None:
    state = _headlines_read()
    # The decider's retelling of it, the query v3o searched.
    state.expect("Tell me more about the unemployment headline.", ["web.search"])
    assert TURNS["D-w17-t5"]["payload"]["seen"]["query"] == "more about the unemployment headline"
    second = TURNS["D-w17-t4"]["payload"]["seen"]["headlines"][1]["title"]
    assert second.startswith("El desempleo trepa")
    assert state.pointed_headline(TURNS["D-w17-t5"]["text"]) == second
    assert state.pointed_headline("háblame más de la primera") == TURNS["D-w17-t4"]["payload"]["seen"]["headlines"][0]["title"]
    assert state.pointed_headline("tell me more about it") is None


def test_a_headline_is_pointed_at_only_right_after_the_news() -> None:
    state = _headlines_read()
    state.expect("Set a timer for 5 minutes.", ["notification.schedule"])
    state.expect("Tell me more.", ["web.search"])
    assert state.pointed_headline("tell me more about the second one") is None


# ------------------------------------------------------------------ 8. works asked for with none named


def test_d_p27_t1_works_of_a_kind_with_none_named_are_looked_up() -> None:
    text = TURNS["D-p27-t1"]["text"]
    assert works_recommendation(text)
    model = _Decider(decider.ContextDecision("Recommend some good movies to watch.", "talk", (), ""))
    result = sidecar._context_decided_result(
        {"id": "m83", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool("web.search")]),
    )
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert model.chats == 0


@pytest.mark.parametrize("text", [
    "I am in a mood to watch movie online and I need your help to search for a nice Fantasy Movie like Elijah Wood.",
    "any good movies on Netflix", "recommend a song by Queen", "¿Me recomiendas una serie como Dark?",
    "any good news today", "add good books to my list",
])
def test_a_work_person_or_service_named_is_another_request(text: str) -> None:
    assert not works_recommendation(text)


def test_talk_that_asks_no_works_stays_talk() -> None:
    model = _Decider(decider.ContextDecision("Tell me a joke.", "talk", (), ""))
    result = sidecar._context_decided_result(
        {"id": "m83", "text": "tell me a joke", "history": [{"role": "user", "content": "tell me a joke"}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool("web.search")]),
    )
    assert result["kind"] == "conversation" and model.chats == 1
