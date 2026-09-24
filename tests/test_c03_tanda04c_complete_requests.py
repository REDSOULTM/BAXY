"""Tanda 4c (2026-09-24, official window): complete requests answered with a pointless question.

00_IDENTIDAD: «pregunta lo justo» and «actúa solo y luego cuenta». Each request below already says everything the
effect needs, so the question BAXY asked changed nothing:

- t38 «oye compárteme algún chiste para hacerme feliz», t41 «i'd like you to tell me a joke» → «¿Quieres un chiste
  de amor, de trabajo o de general?». A request for a bit of content (a joke, a riddle, a story, a poem…) is the
  free-content shape whatever frame carries it (an address, a courtesy, being able to, wanting it, a voice to
  write it in), with its topic or purpose after it; its contract rejects a menu. Owner: llm._FREE_CONTENT_THING_CUE.
- t30 «a partir de ahora imítame» → «Claro, ya estoy en el mismo estilo… ¿Qué necesitas ahora?». How BAXY talks or
  behaves from now on is a directive on his conduct, acknowledged in one sentence with no question. Owner:
  llm._CONDUCT_DIRECTIVE (constraint_ack).
- t9 «pon cualquier cosa de mi playlist reciente» → «¿Qué quieres que reproduzca de tu playlist reciente?». A free
  choice («cualquier cosa», «lo que sea», «algo», «whatever», «anything», «a song») within the person's own
  collection is complete: what they played last resumes their player (media.control play); any other collection of
  theirs no operation opens, a plain limit. Owners: semantic/media.own_recent_listening_request,
  semantic/patterns.own_collection_free_choice.
- t11 «add flour to my shopping list if it's not already on it» → «Flour isn't on the list. Should I add it?». The
  condition was the person's instruction: the list is read and, in the same plan, the entry is added only when the
  read did not find it; the App skips the add when it did. Owners: semantic/patterns.resolve_explicit_effects,
  planner.guarding_predecessors, Baxy.App PlanObservationProjector.IsGuardedByAFoundEntry.

A value that does change the effect still gets its one question («pon una alarma» without an hour, «pon música»
with nothing named, «pon mi canción favorita»). The phrasings are fresh es/en/spanglish paraphrases; only the
messages marked «tanda 4c» are the run's own.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.effect_intent import effect_request_is_authoritative, known_unsupported_effect_request
from baxy_mind.planner import PlannerCatalog, guarding_predecessors, validate_skeleton
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence, _tool


def _shape(text: str, *, has_history: bool = True) -> str | None:
    return llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=has_history)


# ---------------------------------------------------------------- t38/t41: a bit of content is given, not a menu


@pytest.mark.parametrize(
    "text",
    [
        "oye compárteme algún chiste para hacerme feliz",  # tanda 4c t38
        "i'd like you to tell me a joke",  # tanda 4c t41
        "¿me podrías contar un chiste?",
        "quiero que me cuentes un chiste de programadores",
        "hey, could you share a riddle with me?",
        "can you tell me a funny joke about cats please",
        "échame un chiste porfa",
        "¿sabes algún chiste bueno?",
        "do you know any good jokes",
        "i want a joke about dogs",
        "tell me a joke para reírme un rato",
        "hazme reír",
        "make me laugh, baxy",
        "puedes contarme un cuento corto",
        "cuéntame una historia de dragones",
        "recítame un poema",
        "tírame una adivinanza",
        "got any fun facts?",
        "necesito un chiste para mi presentación",
        "dame un trabalenguas",
        "tell me a short story about the sea",
        "Actúa como Julio Verne y haz un relato basado en el año 2090",
        "habla como un pirata y cuéntame un chiste",
        "chistes",
        "otro chiste",
    ],
)
@pytest.mark.parametrize("has_history", [False, True])
def test_a_request_for_a_bit_of_content_is_free_content_in_any_frame(text: str, has_history: bool) -> None:
    assert _shape(text, has_history=has_history) == "free_content"


@pytest.mark.parametrize(
    "text",
    [
        "¿qué es un chiste?",
        "no me cuentes chistes",
        "why are jokes funny",
        "how do i tell a joke",
        "dime la historia de Roma",
        "tienes chistes guardados en tus notas",
        "me encantan los chistes",
        # A bare topic after other turns may answer a question of BAXY's (tanda-02 contract).
        "chistes de programadores sobre bases de datos antiguas",
    ],
)
def test_talking_about_content_is_not_asking_for_it(text: str) -> None:
    assert _shape(text) != "free_content"


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("oye compárteme algún chiste para hacerme feliz", "¡Claro! ¿Quieres un chiste de amor, de trabajo o de general? 😄"),
        ("i'd like you to tell me a joke", "Sure! Want a love joke, a work joke, or a general one? 😄"),
        ("cuéntame un cuento", "¿Sobre qué tema quieres el cuento?"),
        ("tell me a riddle", "Would you like an easy riddle or a hard one?"),
    ],
)
def test_a_menu_of_kinds_misses_the_free_content_contract(asked: str, reply: str) -> None:
    assert llm._shaped_conversation_answer_violates_contract(reply, asked, "free_content")


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("oye compárteme algún chiste para hacerme feliz",
         "¿Por qué el libro de matemáticas está triste? Porque tiene demasiados problemas. 😄"),
        ("i'd like you to tell me a joke",
         "Why did the scarecrow win an award? Because he was outstanding in his field!"),
        ("recítame un poema", "Luna de plata,\nsobre el mar dormido,\nsueña la ola\ncon su latido."),
        ("tírame una adivinanza", "Blanco por dentro, verde por fuera: ¿qué es? La pera, claro."),
    ],
)
def test_the_content_itself_meets_the_free_content_contract(asked: str, reply: str) -> None:
    assert not llm._shaped_conversation_answer_violates_contract(reply, asked, "free_content")


# ---------------------------------------------------------------- t30: a conduct directive is acknowledged


@pytest.mark.parametrize(
    "text",
    [
        "a partir de ahora imítame",  # tanda 4c t30
        "from now on talk like a pirate",
        "desde ahora háblame de tú",
        "imitate me",
        "copy me from now on",
        "de ahora en adelante sé más breve",
        "from now on please answer in short sentences",
        "baxy, a partir de hoy respóndeme como Yoda",
    ],
)
def test_how_baxy_talks_from_now_on_is_a_constraint_to_acknowledge(text: str) -> None:
    assert _shape(text) == "constraint_ack"


@pytest.mark.parametrize(
    "text",
    ["imita a un gato", "a partir de ahora pon el volumen al 50", "from now on call me Emma", "ríe como si fueras un villano"],
)
def test_an_imitation_to_perform_or_another_order_is_not_a_conduct_directive(text: str) -> None:
    assert _shape(text) != "constraint_ack"


@pytest.mark.parametrize(
    ("reply", "rejected"),
    [
        ("De acuerdo, a partir de ahora te imito.", False),
        ("Entendido, desde ahora imito tu forma de escribir.", False),
        ("Claro, ya estoy en el mismo estilo. ¿Qué necesitas ahora?", True),
        ("Claro, te imito. ¿En qué te ayudo?", True),
    ],
)
def test_the_acknowledgement_ends_without_a_question(reply: str, rejected: bool) -> None:
    assert llm._shaped_conversation_answer_violates_contract(
        reply, "a partir de ahora imítame", "constraint_ack",
    ) is rejected


# ---------------------------------------------------------------- t9: a free choice within the own collection

MEDIA_OPERATIONS = ("media.control", "media.play.query", "media.play.youtube", "notification.schedule", "reminder.create")
MEDIA_CONTROL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["next", "pause", "play", "previous", "stop", "toggle"]},
        "sourceApp": {"type": ["null", "string"], "x-maxUtf8Bytes": 256},
    },
    "required": ["action"], "additionalProperties": False,
}


@pytest.mark.parametrize(
    "text",
    [
        "pon cualquier cosa de mi playlist reciente",  # tanda 4c t9
        "pon mi playlist reciente",
        "play something from my recently played",
        "pon lo último que escuché",
        "play what I was listening to",
        "ponme mis canciones recientes",
        "toca lo que estaba escuchando",
        "put on whatever from my recently played please",
    ],
)
def test_what_the_person_played_last_resumes_their_player(text: str) -> None:
    reading = read(text, available_operations=MEDIA_OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == ("media.control",)
    assert sidecar._ground_explicit_arguments("media.control", text, MEDIA_CONTROL_SCHEMA) == {"action": "play"}
    assert not known_unsupported_effect_request(text, MEDIA_OPERATIONS)


@pytest.mark.parametrize(
    "text",
    [
        "play anything from my liked songs",
        "pon cualquier canción de mis favoritas",
        "pon una canción de mi lista de reproducción",
        "ponme algo de mi biblioteca de spotify",
        "play whatever from my library",
        "pon lo que sea de mi playlist de gym",
    ],
)
def test_a_free_choice_within_another_own_collection_is_a_plain_limit(text: str) -> None:
    assert read(text, available_operations=MEDIA_OPERATIONS).clarification is None
    assert known_unsupported_effect_request(text, MEDIA_OPERATIONS)
    assert effect_request_is_authoritative(text)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # A value that changes the effect is still asked.
        ("pon mi canción favorita", "media.play.query"),
        ("pon música", "media.play.query"),
        ("play my liked songs", "media.play.query"),
        ("pon una alarma", "notification.schedule"),
    ],
)
def test_a_missing_value_still_gets_its_one_question(text: str, operation: str) -> None:
    reading = read(text, available_operations=MEDIA_OPERATIONS)
    assert reading.clarification is not None and reading.clarification.operations == (operation,)
    assert not known_unsupported_effect_request(text, MEDIA_OPERATIONS)


@pytest.mark.parametrize("text", ["pon la canción más reciente de Bad Bunny", "reanuda la música"])
def test_music_named_by_its_artist_or_a_plain_resume_keep_their_reading(text: str) -> None:
    reading = read(text, available_operations=MEDIA_OPERATIONS)
    assert not known_unsupported_effect_request(text, MEDIA_OPERATIONS)
    assert reading.effects is not None
    assert reading.effects.operations == (("media.control",) if text.startswith("reanuda") else ("media.play.youtube",))


# ---------------------------------------------------------------- t11: a conditional add reads, then adds

LIST_OPERATIONS = ("task.search", "task.create", "task.list")
TASK_SCHEMAS = {
    "task.search": {
        "type": "object",
        "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True}},
        "required": ["query"], "additionalProperties": False,
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
}


@pytest.mark.parametrize(
    ("text", "entry", "list_name"),
    [
        ("add flour to my shopping list if it's not already on it", "flour", "shopping list"),  # tanda 4c t11
        ("pon azúcar en mi lista del súper si no la tengo ya", "azúcar", "lista del súper"),
        ("add bread to my grocery list unless it's already there", "bread", "grocery list"),
        ("agrega leche a mi lista de compras, solo si falta", "leche", "lista de compras"),
        ("please add eggs to my shopping list if they aren't on it yet", "eggs", "shopping list"),
        ("¿tengo café en mi lista de la compra? si no, apúntalo", "café", "lista de la compra"),
        ("do i have rice on my grocery list? if not put it on", "rice", "grocery list"),
    ],
)
def test_a_conditional_add_is_a_read_then_the_add_it_guards(text: str, entry: str, list_name: str) -> None:
    effects = read(text, available_operations=LIST_OPERATIONS).effects
    assert effects is not None and effects.operations == ("task.search", "task.create")
    skeleton = sidecar._explicit_plan_skeleton(effects.operations, effects.evidence)
    steps = skeleton["steps"]
    assert [step["operation"] for step in steps] == ["task.search", "task.create"]
    # The add waits on the read and keeps the person's literal arguments.
    assert steps[1]["dependsOn"] == [steps[0]["id"]] and steps[1]["argumentsMode"] == "literal"
    assert guarding_predecessors("task.create", steps[1]["purpose"]) == ("task.search",)
    catalog = PlannerCatalog([_tool("task.search", required=("query",)), _tool("task.create", required=("title",))])
    proposal = validate_skeleton(skeleton, catalog, catalog.tools, text)
    assert [(step.operation, step.depends_on, step.arguments_mode) for step in proposal.steps] == [
        ("task.search", (), "literal"), ("task.create", ("step_1",), "literal"),
    ]
    assert sidecar._ground_explicit_arguments("task.search", steps[0]["purpose"], TASK_SCHEMAS["task.search"]) == {
        "query": entry,
    }
    assert sidecar._ground_explicit_arguments("task.create", steps[1]["purpose"], TASK_SCHEMAS["task.create"]) == {
        "title": entry, "details": list_name,
    }


@pytest.mark.parametrize(
    "text",
    ["add flour to my shopping list", "añade harina a mi lista de la compra", "qué hay en mi lista de la compra"],
)
def test_an_unconditional_add_or_a_plain_read_is_one_operation_with_no_guard(text: str) -> None:
    effects = read(text, available_operations=LIST_OPERATIONS).effects
    assert effects is not None and len(effects.operations) == 1
    assert guarding_predecessors("task.create", text) == ()


class _ConversationLlm:
    @staticmethod
    def decide_turn(*_args, **_kwargs):
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "en",
        }

    @staticmethod
    def public_lookup_requested(_text):
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text):
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text):
        return "en"

    @staticmethod
    def consume_deferred_response_language(_text):
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text):
        return None


def test_the_real_conditional_add_is_planned_without_a_question() -> None:
    tools = {operation: _tool(operation, required=("title",) if operation == "task.create" else ("query",))
             for operation in LIST_OPERATIONS}
    result = _prepare_turn_result(
        {"id": "turn-flour", "text": "add flour to my shopping list if it's not already on it", "history": []},
        llm=_ConversationLlm(),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["task.search", "task.create"]
    assert not result.get("question")


def _step(operation: str, observed: dict) -> str:
    return json.dumps({"kind": "operation", "operation": operation, "polarity": "success", "verified": True,
                       "succeeded": True, "observed": observed})


FLOUR = "add flour to my shopping list if it's not already on it"
HARINA = "añade harina a mi lista de la compra si no está"


def _added(request: str, entry: str, list_name: str) -> dict:
    return {
        "situation": json.dumps({
            "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
            "completedRequest": request,
            "steps": [
                _step("task.search", {"tasks": [], "count": 0, "mode": "search", "limit": 20}),
                _step("task.create", {"taskId": "5c0e3f1e-8a1f-4d0e-9b8e-1c2d3e4f5a6b", "title": entry,
                                      "details": list_name, "completed": False, "deleted": False, "version": 1}),
            ],
        }),
    }


@pytest.mark.parametrize(
    ("asked", "entry", "list_name", "reply", "defect"),
    [
        (FLOUR, "flour", "shopping list", "Flour wasn't on your shopping list, so I added it.", ""),
        (FLOUR, "flour", "shopping list", "I added flour to your shopping list.", ""),
        (HARINA, "harina", "lista de la compra", "Harina no estaba en tu lista de la compra, así que la añadí.", ""),
        # tanda 4c t11: asking after the add ran is the pointless question.
        (FLOUR, "flour", "shopping list", "Flour isn't on the list. Should I add it?", "extra_claim"),
        (HARINA, "harina", "lista de la compra", "Harina no está en tu lista. ¿La añado?", "extra_claim"),
    ],
)
def test_the_final_of_the_add_tells_it_and_asks_nothing(asked, entry, list_name, reply, defect) -> None:
    assert llm.compose_visible_defect(reply, "status", asked, _added(asked, entry, list_name)) == defect


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("Flour is already on your shopping list.", ""),
        ("Flour is already on your shopping list, so I added it again.", "extra_claim"),
        ("I've added flour to your shopping list.", "extra_claim"),
    ],
)
def test_the_read_that_found_the_entry_is_told_without_an_add(reply: str, defect: str) -> None:
    found = {"situation": json.dumps({
        "kind": "status", "polarity": "success", "operation": "task.search", "verified": True, "succeeded": True,
        "observed": {"tasks": [{"title": "flour", "details": "shopping list"}], "count": 1, "mode": "search",
                     "limit": 20},
    })}
    assert llm.compose_visible_defect(reply, "status", FLOUR, found) == defect
