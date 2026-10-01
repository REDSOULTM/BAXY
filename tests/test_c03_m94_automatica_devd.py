"""M94 (2026-09-30, the automatic score of the official-window DEV-D run v3u, HEAD 30861483): the stable failures with
a code cause.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3u-devD/ (and v3o, v3r for stability): RUN.jsonl,
turn-audit.jsonl (decision_path, raw_decision, stages), compose-audit.jsonl (payload and situation of every reply). The
DEV-D texts are quoted as evidence; every other phrasing is this file's own.

1. A failed or unverified step said only its cause (D-s102 «abre google keep» → ``app_not_found``; D-s087 the weather
   of «Abingdon Virginia»; D-p22-t2/D-p24-t4 a Netflix title behind a sign-in; D-w07-t2 «1850 entre 7»; D-w09-t3 the
   newest file of Descargas; D-p37-t3 «chips»): the App now names what was tried (C#: ``MindPlanBoundary.WithStepFacts``,
   tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs); here, the composer keeps that target in the facts.
2. Limits a reader closed wrong or not at all: the person's mails taken together (D-s007, a list to write), an entry
   taken off the calendar (D-s016, the calendar listed), a ride called off «¿sería posible…?» (D-s064, advice as
   knowledge), a camera photo asked as a capability or a wish (D-p02-t2, D-p07-t2, talk about the camera app).
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.grammar import _is_past_or_hypothetical_state
from baxy_mind.semantic.notes import agenda_read_request, takes_off_the_agenda
from baxy_mind.semantic.patterns import (
    _fold,
    camera_photo_request,
    conversation_only_content_request,
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    person_mail_collection_request,
    resolve_explicit_clarification_intent,
    unserved_personal_request,
)
from baxy_mind.semantic.system import physical_world_request

TOOLS = (
    "calendar.event.list", "calendar.event.create", "email.latest.read", "task.create", "note.create",
    "capture.screenshot", "web.search", "notification.schedule", "reminder.create", "app.open",
)
WELCOME = [("assistant", "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?")]


# ------------------------------------------------------------------ 1. the failed step names what was tried


@pytest.mark.parametrize(
    ("reason", "target"),
    [
        # D-s102: compose-audit t102, the situation the App sent (now with the grounded appId as target).
        ({"kind": "operation", "operation": "app.open", "polarity": "failure", "verified": False,
          "succeeded": False, "error": "app_not_found"}, "Notion"),
        # D-p24-t4: an unverified Netflix playback.
        ({"kind": "operation", "operation": "streaming.play.named", "polarity": "failure", "verified": False,
          "succeeded": False, "error": "netflix_authentication_required", "cause": "external_effect_ambiguous",
          "effectUncertain": True}, "Paddington 2"),
        # D-w07-t2: the calculator was not in front.
        ({"kind": "operation", "operation": "calculator.expression.evaluate", "polarity": "failure",
          "verified": False, "succeeded": False, "error": "calculator_not_foreground"}, "960/12"),
    ],
)
def test_the_failure_facts_keep_what_was_tried(reason: dict[str, object], target: str) -> None:
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
                 "reason": {**reason, "target": target}}
    payload = llm._compose_situation_payload(situation, "es")
    assert payload["reason"]["target"] == target
    assert target.casefold() in json.dumps(payload, ensure_ascii=False).casefold()


# ------------------------------------------------------------------ 2a. the person's mails taken together


@pytest.mark.parametrize(
    "text",
    [
        "hazme una lista de los destinatarios y remitentes de los emails de la ultima semana",  # D-s007
        "dame un resumen de mis correos de hoy",
        "list the senders of all my emails from yesterday",
        "how many emails did I get this week?",
        "¿cuántos correos tengo sin leer?",
    ],
)
def test_the_mails_taken_together_are_a_limit_and_no_text_to_write(text: str) -> None:
    assert person_mail_collection_request(text)
    assert unserved_personal_request(text)
    assert not conversation_only_content_request(text)
    assert resolve_explicit_clarification_intent(text, TOOLS) is None


@pytest.mark.parametrize(
    "text",
    ["léeme el último correo", "read my latest email", "lee mis correos",
     "redáctame un correo para mi jefe pidiendo vacaciones", "hazme una lista de ideas para emails de bienvenida"],
)
def test_one_mail_or_a_mail_to_write_is_not_the_collection(text: str) -> None:
    assert not person_mail_collection_request(text)


def test_writing_about_mails_is_still_content() -> None:
    assert conversation_only_content_request("hazme una lista de ideas para emails de bienvenida")
    assert conversation_only_content_request("redáctame un correo para mi jefe pidiendo vacaciones")


# ------------------------------------------------------------------ 2b. an entry taken off the calendar


@pytest.mark.parametrize(
    "text",
    [
        "please take off my calendar on saturday the 6th birthday party for john",  # D-s016
        "quita de mi agenda la cena del viernes",
        "take Ana's birthday off my calendar",
        "remove the dentist from my calendar",
        "borra del calendario el partido del domingo",
    ],
)
def test_what_is_taken_off_the_calendar_is_the_removal_limit(text: str) -> None:
    assert takes_off_the_agenda(_fold(text))
    assert not agenda_read_request(text)
    assert known_unsupported_effect_request(text, TOOLS)


@pytest.mark.parametrize(
    "text", ["take a look at my calendar", "take the dates from my calendar", "quita el recordatorio de mi agenda"],
)
def test_looking_at_the_calendar_or_a_reminder_is_no_event_removed(text: str) -> None:
    assert not known_unsupported_effect_request(text, TOOLS)
    assert agenda_read_request("qué tengo en mi calendario el sábado")


# ------------------------------------------------------------------ 2c. «¿sería posible …?» and a ride


@pytest.mark.parametrize(
    "text",
    [
        "¿Sería posible suprimir mi orden de recogida en Lyft de las 16:00 h para el transporte al Wizink Center.",  # D-s064
        "¿Sería posible cancelar mi Uber de las ocho?",
        "would it be possible to cancel my Uber pickup?",
        "¿Sería posible abrir Spotify?",
    ],
)
def test_asking_whether_it_would_be_possible_asks_for_it(text: str) -> None:
    assert effect_request_is_authoritative(text)


@pytest.mark.parametrize(
    "text", ["¿Sería posible que el sol se apague?", "¿sería posible viajar a Marte?"],
)
def test_a_possibility_of_the_world_is_no_request(text: str) -> None:
    assert not effect_request_is_authoritative(text)


def test_a_conditional_state_is_still_a_hypothesis() -> None:
    assert _is_past_or_hypothetical_state(_fold("¿cuánta RAM sería necesaria para jugar?"))
    assert not _is_past_or_hypothetical_state(_fold("¿sería posible cancelarlo?"))


@pytest.mark.parametrize(
    "text",
    ["¿Sería posible suprimir mi orden de recogida en Lyft?", "pídeme un taxi al aeropuerto",
     "cancel my Lyft ride at 4 pm", "would it be possible to book a cab for tomorrow?"],
)
def test_a_ride_is_an_errand_outside_this_pc(text: str) -> None:
    assert physical_world_request(_fold(text))


@pytest.mark.parametrize("text", ["cancela la alarma de las 7", "el taxi llegó tarde ayer"])
def test_no_ride_asked_is_no_errand(text: str) -> None:
    assert not physical_world_request(_fold(text))


# ------------------------------------------------------------------ 2d. a camera photo asked as a capability or a wish


@pytest.mark.parametrize(
    "text",
    ["¿Serías capaz de hacer foto ahora?", "Quiero hacer fotos en modo ráfaga",  # D-p02-t2, D-p07-t2
     "are you able to take a selfie?", "I'd like to take a photo"],
)
def test_being_able_to_or_wanting_a_photo_asks_for_it(text: str) -> None:
    assert camera_photo_request(text)


@pytest.mark.parametrize(
    "text",
    ["quiero hacer una foto de la pantalla", "¿eres capaz de sacar una captura de pantalla?",
     "quiero hacer fotos del atardecer"],
)
def test_the_screen_or_a_named_subject_is_left_to_the_readers(text: str) -> None:
    assert not camera_photo_request(text)


# ------------------------------------------------------------------ the turns


class _Decider:
    """The contextual decider, recorded talk: it is never asked when a reader proves the limit."""

    def __init__(self) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request="x", decision="talk", operations=(), question="")
        self.decisions = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decisions += 1
        return self.decided

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Vale.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que haga?"

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Qué pongo en la lista?"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
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


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _turn(text: str, history: list[tuple[str, str]], model: _Decider) -> dict[str, object]:
    tools = {name: _tool(name) for name in TOOLS}
    turns = [{"role": role, "content": content} for role, content in WELCOME + history]
    return sidecar._prepare_turn_result(
        {"id": "m94", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "history"),
    [
        # turn-audit request 42: explicit_conversation, knowledge (the list to write).
        ("hazme una lista de los destinatarios y remitentes de los emails de la ultima semana", []),
        # request 96: explicit_effects calendar.event.list over an unsupported raw decision.
        ("please take off my calendar on saturday the 6th birthday party for john", []),
        # request 376: unsupported, then conversation_presentation made it knowledge.
        ("¿Sería posible suprimir mi orden de recogida en Lyft de las 16:00 h para el transporte al Wizink Center.", []),
        # D-p02-t2, D-p07-t2: the contextual decider talked about the camera.
        ("¿Serías capaz de hacer foto ahora?", [("user", "Saca foto ahora"), ("assistant", "No saco fotos con la cámara.")]),
        ("Quiero hacer fotos en modo ráfaga",
         [("user", "Saca una foto en modo ráfaga"), ("assistant", "No hago fotos en modo ráfaga.")]),
        ("can you remove the dentist from my calendar?", []),
        ("would it be possible to cancel my Uber pickup?", []),
    ],
)
def test_the_turn_is_the_limit(text: str, history: list[tuple[str, str]]) -> None:
    model = _Decider()
    result = _turn(text, history, model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported", text
    assert result["effectOperations"] == [] and model.decisions == 0
