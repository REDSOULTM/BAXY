"""Uso real 2026-09-23: BAXY asked a question where nothing that changes the effect was missing.

The identity says «pregunta lo justo» and «actúa solo y luego cuenta». Each test
here names the real message that got a pointless question and the stage that
produced it; a value that does change the effect still gets its one question.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as mind_main
from baxy_mind.__main__ import (
    LIMIT_WORDING_FAILURE,
    _explicit_arguments_from_evidence,
    _prepare_turn_result,
    _recover_failed_turn,
    _turn_failure_kind,
)
from baxy_mind.llm import (
    ConversationReplyContractError,
    LlmRuntime,
    _compose_situation_payload,
    _conversation_presentation_shape,
    _payload_fact_defect,
    _shaped_conversation_answer_violates_contract,
    compose_visible_defect,
    validate_missing_argument_clarification,
)
from baxy_mind.planner import PlannerCatalog
from baxy_mind.request_reading import read_request, speaking_directive
from baxy_mind.semantic import patterns
from baxy_mind.semantic.reading import read


def _tool(operation: str, *, required: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {name: {"type": "string", "minLength": 1} for name in required},
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


class _NoEvidence:
    @staticmethod
    def candidate_families(_text: str, _encoder: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


# --- «Cuéntame un poco sobre el modelo de aprendizaje transformer» ----------
# The native selector started answering in prose, ran out of tokens and the
# truncation failed both attempts; the recovery then asked «¿Te refieres a…?».


def _native_runtime(message: dict[str, object], finish_reason: str) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._post = lambda _payload: {  # type: ignore[method-assign]
        "choices": [{"finish_reason": finish_reason, "message": message}],
    }
    return runtime


def test_truncated_prose_without_a_call_is_a_zero_authority_conversation() -> None:
    runtime = _native_runtime(
        {"content": "El modelo Transformer es una arquitectura de redes neuronales que"},
        "length",
    )
    result = runtime._post_native_tool_selection(
        "Cuéntame un poco sobre el modelo de aprendizaje transformer",
        ["web.search"],
        {"web.search": {"description": "Search the web."}},
        [],
    )
    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "knowledge"
    assert result["effect_operations"] == []


@pytest.mark.parametrize(
    "message",
    [
        {"content": '<tool_call>{"name": "baxy_web__search", "argu'},
        {"content": '{"name": "baxy_web__search"'},
        {"content": "Voy a usar baxy_web__search para"},
        {"content": ""},
        {"content": None},
    ],
)
def test_a_truncated_reply_that_may_have_begun_a_call_still_fails(
    message: dict[str, object],
) -> None:
    runtime = _native_runtime(message, "length")
    with pytest.raises(ValueError, match="respuesta nativa de operaciones inválida"):
        runtime._post_native_tool_selection(
            "busca el clima", ["web.search"], {"web.search": {"description": "Search."}}, [],
        )


# --- «¿en qué día de la semana estamos?» -------------------------------------
# No reader took it, the model answered knowledge, the effect guard made it a
# limit and the recovery asked «¿Te refieres al día de la semana actual…?».


_TIME_OPERATIONS = ("system.time", "web.search", "calendar.event.list")


@pytest.mark.parametrize(
    "text",
    [
        "¿en qué día de la semana estamos?",
        "qué día de la semana es hoy",
        "en qué día estamos",
        "en qué fecha estamos",
        "what day of the week is it",
        "What day of the week is today?",
    ],
)
def test_the_weekday_of_this_pc_is_read_from_its_clock(text: str) -> None:
    reading = read(text, available_operations=_TIME_OPERATIONS)
    assert reading.effects is not None
    assert reading.effects.operations == ("system.time",)
    assert patterns.operation_domain_is_grounded(text, "system.time", ())


@pytest.mark.parametrize(
    "text",
    ["qué día de la semana es el 4 de julio", "en qué día de la semana cae navidad"],
)
def test_the_weekday_of_another_date_is_not_this_pc_clock(text: str) -> None:
    reading = read(text, available_operations=_TIME_OPERATIONS)
    assert reading.effects is None or reading.effects.operations != ("system.time",)


_WEDNESDAY = {
    "kind": "operation", "operation": "system.time", "polarity": "success",
    "verified": True, "succeeded": True,
    # 2026-09-24 01:04 UTC is Wednesday 2026-09-23 22:04 at UTC-3.
    "observed": {"utc": "2026-09-24T01:04:11.4543673+00:00", "localUtcOffsetMinutes": -180},
}


@pytest.mark.parametrize(
    ("language", "user_text", "weekday"),
    [
        ("es", "¿en qué día de la semana estamos?", "miércoles"),
        ("en", "what day of the week is it", "Wednesday"),
    ],
)
def test_the_weekday_travels_as_a_fact_of_the_observed_date(
    language: str, user_text: str, weekday: str,
) -> None:
    payload = _compose_situation_payload(_WEDNESDAY, language, user_text)
    assert payload["date"] == "2026-09-23"
    assert payload["weekday"] == weekday


def test_a_plain_date_request_gets_no_weekday_fact() -> None:
    payload = _compose_situation_payload(_WEDNESDAY, "es", "qué día es hoy")
    assert payload["date"] == "2026-09-23"
    assert "weekday" not in payload


@pytest.mark.parametrize(
    ("answer", "valid"),
    [
        ("Hoy es miércoles 23 de septiembre de 2026.", True),
        ("Hoy es miercoles, 23 de septiembre.", True),
        ("Hoy es jueves 23 de septiembre de 2026.", False),
        ("Hoy es 23 de septiembre de 2026.", False),
        ("Hoy es miércoles o jueves, 23 de septiembre.", False),
        ("Hoy es miércoles.", False),
    ],
)
def test_the_weekday_answer_names_the_observed_weekday_and_date(answer: str, valid: bool) -> None:
    user_text = "¿en qué día de la semana estamos?"
    facts = {"situation": json.dumps(_WEDNESDAY)}
    payload = _compose_situation_payload(_WEDNESDAY, "es", user_text)
    assert (compose_visible_defect(answer, "status", user_text, facts) == "") is valid
    assert (_payload_fact_defect(answer, payload) == "") is valid


# --- «qué hora es en tokio», «qué eventos se celebran en la ciudad de nueva york»
# The model answered knowledge; the catalogue probe then named this PC's clock
# (or the person's calendar) and the turn asked «¿Quieres que te diga…?». What
# the guard reads as public information is looked up first.


class _PublicKnowledgeLlm:
    def __init__(self, *, public: bool) -> None:
        self.public = public
        self.identity_calls: list[str] = []
        self.strict_calls: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": "es",
        }

    def public_lookup_requested(self, _text: str) -> bool:
        return self.public

    def operation_is_the_requested_effect(
        self, _text: str, operation: str, _contract: dict[str, object],
    ) -> bool:
        self.identity_calls.append(operation)
        return operation == "system.time"

    def operation_satisfies_the_request(
        self, _text: str, operation: str, _contract: dict[str, object],
    ) -> bool:
        # A kitchen clock, or Tokyo's, is not this PC's clock.
        self.strict_calls.append(operation)
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "En Tokio son las once.", []


def _public_turn(llm: _PublicKnowledgeLlm, text: str) -> dict[str, object]:
    tools = {
        "system.time": _tool("system.time"),
        "web.search": _tool("web.search", required=("query",)),
    }
    return _prepare_turn_result(
        {"id": "turn-public", "text": text},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize("text", ["qué hora es en tokio", "qué hora es en londres ahora mismo"])
def test_public_information_is_looked_up_before_the_catalogue_is_offered(text: str) -> None:
    llm = _PublicKnowledgeLlm(public=True)
    result = _public_turn(llm, text)

    assert result["kind"] == "action"
    # Tanda 4: the time of another place is this clock read with that place's
    # zone (system.time with «place»), read before the model, never searched.
    assert result["operation"] == "system.time"
    assert result["question"] == ""
    # The catalogue probe is never reached.
    assert llm.identity_calls == llm.strict_calls == []


def test_the_catalogue_probe_still_speaks_when_the_guard_reads_no_public_lookup() -> None:
    llm = _PublicKnowledgeLlm(public=False)
    # «qué hora es en tokio» is now read before the model (clock_elsewhere); a
    # question no reader takes keeps the probe.
    result = _public_turn(llm, "dime la hora que marca el reloj de la cocina")

    # When the guard does not read public information the probe is still asked;
    # what it names is strictly verified, and refused it is neither dispatched
    # nor offered back as «¿Quieres que…?» (tanda 4, D3).
    assert llm.identity_calls
    assert llm.strict_calls == ["system.time"]
    assert result["effectOperations"] == []
    assert result["kind"] == "conversation"
    assert result["question"] == ""


def test_this_pc_clock_is_described_as_never_another_place() -> None:
    # Tanda 4: another place's time is this clock read with that place, never
    # this clock recited as theirs.
    described = mind_main._native_selection_description("system.time", "Lee la fecha y hora actuales.")
    assert "only with that place in «place»" in described
    assert "never this clock as theirs" in described


# --- «play reggae music», «alexa play song over the rainbow», «play song aces high»
# The clarification reader asked «What song would you like to play?» although
# the request named it. A bare music noun, a possessive or a purpose still asks.


_MEDIA_OPERATIONS = ("media.play.query", "media.play.youtube", "web.search")


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("play reggae music", "reggae music"),
        ("alexa play song over the rainbow", "over the rainbow"),
        ("play song aces high", "aces high"),
        ("Play the song Bohemian Rhapsody", "Bohemian Rhapsody"),
        ("pon la canción despacito", "despacito"),
        ("pon música clásica", "música clásica"),
        ("play some jazz music", "jazz music"),
    ],
)
def test_named_music_is_played_not_asked_for(text: str, query: str) -> None:
    assert patterns.resolve_explicit_clarification_intent(text, _MEDIA_OPERATIONS) is None
    effect = patterns.resolve_explicit_effects(text, _MEDIA_OPERATIONS)
    assert effect is not None
    assert effect.operations == ("media.play.youtube",)
    assert _explicit_arguments_from_evidence(effect.operations[0], effect.evidence[0]) == {
        "query": query,
    }


@pytest.mark.parametrize(
    "text",
    [
        "play music",
        "play some music",
        "pon música",
        "ponme una canción",
        "play a song",
        "play song",
        "pon mi música favorita ahora",
        "play my favorite music",
        "pon una canción para dormir",
        "pon la canción que me gusta",
        "play a new song",
    ],
)
def test_music_with_nothing_named_still_asks_what_to_play(text: str) -> None:
    clarification = patterns.resolve_explicit_clarification_intent(text, _MEDIA_OPERATIONS)
    assert clarification is not None
    assert clarification.operations == ("media.play.query",)
    assert clarification.missing_fields == ("query",)


# --- «do i have appointments today» -------------------------------------------
# Asked «What time are you looking for appointments today?»: the day is the
# whole range, and the calendar grounding already reads it.


@pytest.mark.parametrize(
    "text",
    ["do i have appointments today", "Do I have any meetings tomorrow?", "¿tengo alguna cita hoy?"],
)
def test_own_appointments_in_a_named_window_are_read(text: str) -> None:
    effect = patterns.resolve_explicit_effects(text, ("calendar.event.list", "reminder.create"))
    assert effect is not None
    assert effect.operations == ("calendar.event.list",)
    arguments = _explicit_arguments_from_evidence("calendar.event.list", effect.evidence[0])
    assert arguments is not None and set(arguments) == {"startUtc", "endUtc"}


@pytest.mark.parametrize(
    "text",
    ["tengo una cita mañana recuérdame", "do i have time today"],
)
def test_a_statement_or_another_question_is_not_read_as_the_calendar(text: str) -> None:
    effect = patterns.resolve_explicit_effects(text, ("calendar.event.list",))
    assert effect is None or effect.operations != ("calendar.event.list",)


# --- «súbele un poco», «bájale» ----------------------------------------------
# The domain gate withdrew the volume change (no volume named), the confirmation
# «¿Quieres que suba un poco el volumen?» was vetoed and the fallback asked
# «¿A qué exactly quieres que le suba?». Owner rule: a relative change with no
# amount asks the amount.


@pytest.mark.parametrize(
    "text", ["súbele un poco", "bájale", "súbele", "bájale un poquito por favor", "Súbele más."],
)
def test_a_bare_clitic_volume_order_asks_the_amount(text: str) -> None:
    clarification = patterns.resolve_explicit_clarification_intent(
        text, ("audio.volume.adjust", "audio.volume", "system.settings.adjust"),
    )
    assert clarification is not None
    assert clarification.operations == ("audio.volume.adjust",)
    assert clarification.missing_fields == ("amount",)


@pytest.mark.parametrize("text", ["súbele 20", "bájale un 10%"])
def test_a_bare_clitic_volume_order_with_an_amount_is_the_volume(text: str) -> None:
    assert patterns.operation_domain_is_grounded(text, "audio.volume.adjust", ())
    assert patterns.resolve_explicit_clarification_intent(text, ("audio.volume.adjust",)) is None


@pytest.mark.parametrize("text", ["súbele a la tele", "súbele el brillo"])
def test_a_clitic_with_another_object_is_not_the_bare_volume(text: str) -> None:
    clarification = patterns.resolve_explicit_clarification_intent(text, ("audio.volume.adjust",))
    assert clarification is None or clarification.operations != ("audio.volume.adjust",)
    assert not patterns.operation_domain_is_grounded(text, "audio.volume.adjust", ())


# --- «prepárame una taza de café» ---------------------------------------------
# The turn decided a limit; its wording failed the limit contract twice and the
# recovery asked «¿Te refieres a que quieras que el café esté más suave…?».


@pytest.mark.parametrize(
    "reason",
    ["unsupported_malformed_modal", "unsupported_missing_inability", "unsupported_shape"],
)
def test_a_failed_limit_wording_is_its_own_failure_class(reason: str) -> None:
    assert _turn_failure_kind(ConversationReplyContractError(reason)) == LIMIT_WORDING_FAILURE


@pytest.mark.parametrize(
    "error",
    [
        ConversationReplyContractError("unsupported_language"),
        ConversationReplyContractError("echo"),
        ValueError("respuesta nativa de operaciones inválida"),
    ],
)
def test_other_attempt_failures_stay_runtime(error: BaseException) -> None:
    assert _turn_failure_kind(error) == "runtime"


class _RecoveryLlm:
    def __init__(self) -> None:
        self.questions = 0
        self.situations: list[dict[str, object]] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        self.questions += 1
        return "¿Te refieres a que quieras que el café esté más suave?"

    def compose_user_message(self, _text: str, _intent: str, facts: dict[str, str]) -> str:
        self.situations.append(json.loads(facts["situation"]))
        return "No puedo preparar café: eso no lo hago."


def test_a_decided_limit_is_recovered_as_the_limit_not_a_question() -> None:
    llm = _RecoveryLlm()
    result = _recover_failed_turn(
        {"id": "turn-cafe", "text": "prepárame una taza de café", "history": []},
        llm,
        failure_kinds=(LIMIT_WORDING_FAILURE, LIMIT_WORDING_FAILURE),
    )

    assert llm.questions == 0
    assert llm.situations == [
        {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"},
    ]
    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert result["reply"] == "No puedo preparar café: eso no lo hago."
    assert result["question"] == ""
    assert result["effectOperations"] == [] and result["intentOperations"] == []


def test_a_runtime_failure_still_gets_the_recovery_question() -> None:
    llm = _RecoveryLlm()
    result = _recover_failed_turn(
        {"id": "turn-x", "text": "prepárame una taza de café", "history": []},
        llm,
        failure_kinds=(LIMIT_WORDING_FAILURE, "runtime"),
    )
    assert llm.questions == 1
    assert result["kind"] == "clarify"


# --- «cuándo y qué es la cita que quieres recordar?» ---------------------------
# Argument questions reached the screen in lower case and without «¿».


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "cuándo y qué es la cita que quieres recordar?",
            "¿Cuándo y qué es la cita que quieres recordar?",
        ),
        ("¿cuál es el título de la nota?", "¿Cuál es el título de la nota?"),
        ("what is the latest disney podcast?", "What is the latest disney podcast?"),
        ("¿Cuánto quieres subir el volumen?", "¿Cuánto quieres subir el volumen?"),
        ("Para Spotify, ¿qué canción pongo?", "Para Spotify, ¿qué canción pongo?"),
    ],
)
def test_argument_questions_open_as_a_sentence(question: str, expected: str) -> None:
    assert validate_missing_argument_clarification(
        {"question": question, "requested_fields": ["when"]}, ("when",),
    ) == expected


# --- «vuelve a hablar en español» ----------------------------------------------
# The social reply ended with «¿En qué puedo ayudarte hoy?». How BAXY speaks is a
# directive on his conduct: one acknowledging sentence in that language, no
# question and no offer after it.


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("vuelve a hablar en español", "es"),
        ("háblame en inglés por favor", "en"),
        ("keep talking in spanish", "es"),
        ("Please speak in English.", "en"),
    ],
)
def test_a_speaking_directive_is_acknowledged_in_the_requested_language(
    text: str, language: str,
) -> None:
    assert speaking_directive(text)
    assert read_request(text).language == language
    assert _conversation_presentation_shape(
        text, conversation_kind="social", has_history=True,
    ) == "constraint_ack"


@pytest.mark.parametrize(
    "text",
    [
        "habla en español sobre la historia de Roma",
        "quiero hablar en público",
        "responde en inglés: qué es un átomo",
    ],
)
def test_speaking_about_something_is_not_a_bare_directive(text: str) -> None:
    assert not speaking_directive(text)


@pytest.mark.parametrize(
    ("answer", "rejected"),
    [
        ("Claro, sigo hablando en español.", False),
        ("Entendido. Te hablo en español.", False),
        ("Claro, estoy aquí para ayudarte en español 😎 ¿En qué puedo ayudarte hoy?", True),
    ],
)
def test_the_acknowledgement_is_the_whole_reply(answer: str, rejected: bool) -> None:
    assert _shaped_conversation_answer_violates_contract(
        answer, "vuelve a hablar en español", "constraint_ack",
    ) is rejected

