"""Uso real 2026-09-23 (tanda 2): conversation replies that claimed effects or invented
facts, and the person's lists answered from the model's memory.

- «do i have cheese on my shopping list if not please add it» → «No, no hay queso en la
  lista de compras. Se añadirá.» with nothing read or added. The list is read (task.search
  for the entry); an absent entry is asked about in the final, and «sí» puts it on the list.
- «decir la lista», «is my todo list free», «tengo algo en mi lista de cosas por hacer»…:
  a list read is task.list (the to-do list) or task.search (a list with another name).
- «cuéntame un artículo random» → an invented discovery: a random article or fact is the
  curiosity lookup, never recited.
- «Te traigo una hamburguesa con queso», «Claro, te la guardo», «Se añadirá.», «I'm mostly
  busy with coding and fixing bugs»: a conversation turn runs nothing, so an effect done,
  being done or promised, the assistant's invented pastime and the person's unread records
  are rejected drafts, retried with a hint that says what was wrong.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.llm import LlmRuntime, conversation_claim_defect
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.notes import list_read_request
from baxy_mind.semantic.patterns import (
    _CURIOSITY_TOPICS_EN,
    _CURIOSITY_TOPICS_ES,
    deferred_clarification_split,
    resolve_explicit_effects,
)
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence, _tool

OPERATIONS = ("task.list", "task.search", "task.create", "reminder.list", "note.list", "web.search")

SCHEMAS = {
    "task.search": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
            "status": {"type": "string", "enum": ["all", "completed", "open"]},
        },
        "required": ["query"], "additionalProperties": False,
    },
    "task.list": {
        "type": "object",
        "properties": {
            "includeDeleted": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "status": {"type": "string", "enum": ["all", "completed", "open"]},
        },
        "required": [], "additionalProperties": False,
    },
    "task.create": {
        "type": "object",
        "properties": {
            "details": {"type": "string", "x-maxUtf8Bytes": 65536},
            "due": {"type": ["null", "string"], "maxLength": 64},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["title"], "additionalProperties": False,
    },
    "web.search": {
        "type": "object",
        "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True}},
        "required": ["query"], "additionalProperties": False,
    },
}

CHEESE = "do i have cheese on my shopping list if not please add it"


# ---------------------------------------------------------------- list reads


@pytest.mark.parametrize(
    "text",
    [
        "tengo algo en mi lista de cosas por hacer",
        "is my todo list free",
        "olly qué es lo siguiente en mi lista",
        "can you please repeat my list back to me",
        "decir la lista",
        "déjame escuchar mi lista",
        "read me my list",
        "what is the next thing on my to-do list",
        "¿mi lista de tareas está vacía?",
        "muéstrame mi lista de pendientes",
    ],
)
def test_the_to_do_list_read_is_every_open_task(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == ("task.list",)
    assert sidecar._ground_explicit_arguments("task.list", reading.effects.evidence[0], SCHEMAS["task.list"]) == {}


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("tengo mi lista de ropa", "lista de ropa"),
        ("¿Qué hay en mi lista de la compra?", "lista de la compra"),
        ("qué hay en la lista de la compra", "lista de la compra"),
        ("what's on my shopping list", "shopping list"),
        ("is there anything on my grocery list", "grocery list"),
        ("léeme mi lista de regalos", "lista de regalos"),
    ],
)
def test_a_list_with_another_name_is_searched_by_that_name(text, query):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("task.search",)
    assert sidecar._ground_explicit_arguments(
        "task.search", reading.effects.evidence[0], SCHEMAS["task.search"],
    ) == {"query": query}


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("¿Está el Queso en mi lista de la compra?", "Queso"),
        ("do i have eggs on my list", "eggs"),
        ("is milk on my grocery list", "milk"),
        ("¿tengo pan en mi lista?", "pan"),
        ("check if I have batteries on my shopping list", "batteries"),
    ],
)
def test_one_entry_asked_about_is_searched_by_itself(text, query):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("task.search",)
    assert sidecar._ground_explicit_arguments(
        "task.search", reading.effects.evidence[0], SCHEMAS["task.search"],
    ) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        # Another store, a playlist, public knowledge, a pointed entry, an addition.
        "check if getting a light bulb is on my list of reminders",
        "qué hay en mi lista de reproducción",
        "dime la lista de los planetas",
        "what is the list of G7 countries",
        "is it on my list",
        "añade leche a mi lista de la compra",
        "hay que poner leche en mi lista",
    ],
)
def test_other_lists_and_other_acts_are_not_a_read_of_the_persons_list(text):
    found = list_read_request(text)
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert found is None
    assert effects is None or not {"task.list", "task.search"} & set(effects.operations)


# ---------------------------------------------------------------- read, then add if absent


@pytest.mark.parametrize(
    ("text", "query", "clause"),
    [
        (CHEESE, "cheese", "if not please add it"),
        ("¿tengo queso en mi lista de la compra? si no, agrégalo", "queso", "si no, agrégalo"),
        ("is milk on my grocery list? if not add it", "milk", "if not add it"),
        ("do i have eggs on my list, otherwise put them on it", "eggs", "otherwise put them on it"),
    ],
)
def test_a_conditional_add_reads_the_list_and_defers_the_add(text, query, clause):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("task.search",)
    deferred = deferred_clarification_split(text, OPERATIONS)
    assert deferred is not None and deferred.kind == "list_entry_if_absent"
    assert deferred.clause == clause
    # The App asks the arguments with the whole message: the read carries them alone.
    assert sidecar._ground_explicit_arguments("task.search", text, SCHEMAS["task.search"]) == {"query": query}


class _InventingLlm:
    """A model that would answer the list from memory and promise the add."""

    @staticmethod
    def decide_turn(*_args, **_kwargs):
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "es",
        }

    @staticmethod
    def chat(*_args, **_kwargs):
        return "No, no hay queso en la lista de compras. Se añadirá.", []

    @staticmethod
    def public_lookup_requested(_text):
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text):
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text):
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text):
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text):
        return None


def _turn(text, history=()):
    tools = {
        "task.search": _tool("task.search", required=("query",)),
        "task.list": _tool("task.list"),
        "task.create": _tool("task.create", required=("title",)),
        "web.search": _tool("web.search", required=("query",)),
    }
    return _prepare_turn_result(
        {"id": "turn-list", "text": text, "history": list(history)},
        llm=_InventingLlm(),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        (CHEESE, "task.search"),
        ("decir la lista", "task.list"),
        ("is my todo list free", "task.list"),
        ("tengo algo en mi lista de cosas por hacer", "task.list"),
        ("qué hay en mi lista de la compra", "task.search"),
    ],
)
def test_the_list_turn_reads_instead_of_answering_from_memory(text, operation):
    result = _turn(text)
    assert result["kind"] == "action"
    assert result["effectOperations"] == [operation]
    assert result["reply"] == ""


def _search_situation(count):
    tasks = [{"title": "cheese", "details": "shopping list"}] * count
    return {
        "kind": "status", "polarity": "success", "operation": "task.search", "verified": True, "succeeded": True,
        "observed": {"tasks": tasks, "count": count, "mode": "search", "limit": 20},
    }


@pytest.mark.parametrize(
    ("count", "reply", "defect"),
    [
        (0, "Cheese is not on your shopping list. Should I add it?", ""),
        (0, "I didn't add it: cheese isn't on your shopping list. Want me to add it?", ""),
        (0, "Cheese is not on your shopping list.", "missing_deferred_question"),
        (0, "Cheese is not on your shopping list, so I added it.", "extra_claim"),
        (0, "Cheese wasn't there; it will be added to your shopping list.", "extra_claim"),
        (1, "Cheese is already on your shopping list.", ""),
        (1, "Cheese is on your shopping list, so I added it again.", "extra_claim"),
    ],
)
def test_the_final_asks_only_about_an_absent_entry_and_never_claims_the_add(count, reply, defect):
    facts = {"situation": json.dumps(_search_situation(count))}
    assert llm.compose_visible_defect(reply, "status", CHEESE, facts) == defect


@pytest.mark.parametrize(
    ("prior", "answer", "arguments"),
    [
        (CHEESE, "sí", {"title": "cheese", "details": "shopping list"}),
        (CHEESE, "yes please", {"title": "cheese", "details": "shopping list"}),
        ("¿tengo queso en mi lista de la compra? si no, agrégalo", "sí, agrégalo",
         {"title": "queso", "details": "lista de la compra"}),
    ],
)
def test_agreeing_after_the_question_puts_the_entry_on_that_list(prior, answer, arguments):
    history = [{"role": "user", "content": prior}, {"role": "assistant", "content": "No está. ¿Lo añado?"}]
    result = _turn(answer, history)
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["task.create"]
    assert sidecar._ground_explicit_arguments(
        "task.create", answer, SCHEMAS["task.create"], history=history,
    ) == arguments


@pytest.mark.parametrize(
    # «ok», «vale», «dale» also acknowledge an entry that was found.
    "answer", ["no", "no, déjalo", "añade también pan", "¿qué más hay?", "ok", "vale, gracias", "dale"],
)
def test_anything_but_a_bare_agreement_adds_nothing(answer):
    history = [{"role": "user", "content": CHEESE}, {"role": "assistant", "content": "No está. ¿Lo añado?"}]
    effects = resolve_explicit_effects(answer, OPERATIONS, previous_user_text=CHEESE)
    assert effects is None or effects.evidence != ("add cheese to my shopping list",)
    assert sidecar._ground_explicit_arguments(
        "task.create", answer, SCHEMAS["task.create"], history=history,
    ) != {"title": "cheese", "details": "shopping list"}


def test_agreeing_after_a_plain_list_read_adds_nothing():
    assert resolve_explicit_effects("sí", OPERATIONS, previous_user_text="qué hay en mi lista de la compra") is None


# ---------------------------------------------------------------- random article → curiosity lookup


@pytest.mark.parametrize(
    ("text", "topics"),
    [
        ("cuéntame un artículo random", _CURIOSITY_TOPICS_ES),
        ("dame un dato curioso", _CURIOSITY_TOPICS_ES),
        ("cuéntame algo interesante", _CURIOSITY_TOPICS_ES),
        ("dame un artículo aleatorio de wikipedia", _CURIOSITY_TOPICS_ES),
        ("léeme un artículo al azar", _CURIOSITY_TOPICS_ES),
        ("sorpréndeme con algo", _CURIOSITY_TOPICS_ES),
        ("tell me a random fact", _CURIOSITY_TOPICS_EN),
        ("give me a random wikipedia article", _CURIOSITY_TOPICS_EN),
        ("surprise me", _CURIOSITY_TOPICS_EN),
    ],
)
def test_a_random_article_or_fact_is_looked_up(text, topics):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("web.search",)
    grounded = sidecar._ground_explicit_arguments("web.search", reading.effects.evidence[0], SCHEMAS["web.search"])
    assert grounded is not None and grounded["query"] in topics


@pytest.mark.parametrize(
    "text",
    ["dame algo", "dame algo de tomar", "dime el artículo 5 de la constitución", "cuéntame un artículo"],
)
def test_other_asks_are_not_a_random_curiosity(text):
    from baxy_mind.semantic.web import curiosity_request

    assert not curiosity_request(text)


# ---------------------------------------------------------------- conversation claims


@pytest.mark.parametrize(
    ("reply", "ask", "defect"),
    [
        # Tanda 2 and earlier runs, verbatim.
        ("No, no hay queso en la lista de compras. Se añadirá.", CHEESE, "effect_claim"),
        ("Claro, te la guardo.", "me gusta mi cancion por favor a guarda esta", "effect_claim"),
        ("Te traigo una hamburguesa con queso.", "me gustaría una hamburguesa con queso", "effect_claim"),
        ("I'm mostly busy with coding and fixing bugs when I'm not working on projects.",
         "what keeps you busy in your free time", "effect_claim"),
        ("estoy preparando un timer para ti", "i would like a timer set", "effect_claim"),
        # The same claims in other words.
        ("Claro, te lo recuerdo mañana.", "", "effect_claim"),
        ("Lo añadiré a tu lista.", "", "effect_claim"),
        ("Voy a guardarla en tus favoritos.", "", "effect_claim"),
        ("I'll add it to your list.", "", "effect_claim"),
        ("Sure, I'm adding it now.", "", "effect_claim"),
        ("It will be added to your list.", "", "effect_claim"),
        ("En mi tiempo libre me gusta leer novelas.", "", "effect_claim"),
        ("In my free time, I enjoy helping people learn.", "", "effect_claim"),
        # The person's records, never read.
        ("No, no hay queso en la lista de compras.", CHEESE, "unread_records"),
        ("Tu lista de la compra tiene leche y pan.", "", "unread_records"),
        ("You have three items on your to-do list.", "", "unread_records"),
        ("Tu agenda está vacía hoy.", "", "unread_records"),
        ("Sí, tienes queso en tu lista.", "", "unread_records"),
    ],
)
def test_a_conversation_reply_may_not_claim_an_effect_or_state_unread_records(reply, ask, defect):
    assert conversation_claim_defect(reply, ask) == defect


@pytest.mark.parametrize(
    ("reply", "ask"),
    [
        ("¿Quieres que lo añada a tu lista?", ""),
        ("¿Lo añado?", ""),
        ("Si quieres, te lo recuerdo mañana a las ocho.", ""),
        ("I can add it if you want.", ""),
        ("Te pongo un ejemplo: el agua hierve a 100 grados.", ""),
        ("Te traigo una curiosidad: los pulpos tienen tres corazones.", ""),
        ("Eso no lo hago.", ""),
        ("No lo guardé: no tengo esa capacidad.", ""),
        ("No sé qué tienes en tu agenda.", "¿qué tengo en mi agenda mañana?"),
        ("No puedo ver tu lista desde aquí.", "what's on my list"),
        ("Una lista de la compra te ayuda a no olvidar nada.", "para qué sirve una lista de la compra"),
        ("La lista de Schindler tiene más de mil nombres.", "qué es la lista de schindler"),
        ("En tu calendario hay una opción para repetir eventos.", ""),
        ("Hi! I'm doing well, thanks for asking.", ""),
        ("Estoy aquí para ayudarte.", ""),
        ("Let me explain: the sky looks blue because of Rayleigh scattering.", ""),
        ("I'll start with the basics.", ""),
        ("El pollo de engorde se cría para producir carne.", ""),
        ("Asegúrate de que el archivo esté en la misma carpeta.", ""),
        ("Haré lo posible por explicarlo mejor.", ""),
        ("Te mando un abrazo.", ""),
    ],
)
def test_questions_offers_denials_speech_and_knowledge_are_not_claims(reply, ask):
    assert conversation_claim_defect(reply, ask) == ""


def test_a_claiming_draft_is_retried_with_a_hint_that_names_the_claim():
    runtime = object.__new__(LlmRuntime)
    payloads = []

    def post(payload):
        payloads.append(payload)
        content = (
            "Te traigo una hamburguesa con queso."
            if len(payloads) == 1
            else '{"answer":"No puedo traerte comida: vivo en este PC."}'
        )
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

    runtime._post = post
    answer, calls = runtime.chat(
        "me gustaría una hamburguesa con queso",
        history=[], temperature=0.0, conversation_kind="knowledge", response_language="es",
    )
    assert answer == "No puedo traerte comida: vivo en este PC."
    assert calls == []
    assert len(payloads) == 2
    hint = payloads[1]["messages"][1]["content"]
    assert "no digas que hiciste, haces o harás algo" in hint
    assert "no afirmes qué hay en sus listas" in hint


def test_a_contextual_answer_stating_unread_records_falls_through_to_generation():
    runtime = object.__new__(LlmRuntime)
    runtime._resolve_contextual_answer = lambda **_kwargs: "No, no hay queso en la lista de compras."
    payloads = []

    def post(payload):
        payloads.append(payload)
        return {"choices": [{"message": {"content": "No sé qué hay en tu lista sin leerla."}, "finish_reason": "stop"}]}

    runtime._post = post
    answer, _ = runtime.chat(
        "¿y queso?",
        history=[
            {"role": "user", "content": "¿qué hay en mi lista de la compra?"},
            {"role": "assistant", "content": "Tienes leche y pan."},
        ],
        temperature=0.0, conversation_kind="followup", response_language="es",
    )
    assert answer == "No sé qué hay en tu lista sin leerla."
    assert len(payloads) == 1
