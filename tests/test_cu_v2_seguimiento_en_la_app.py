"""Live 2026-10-07 (v2-s13): «y ahora andá a configuración» after a mission in a chat application.

The contextual decider took the application from the conversation and restated «En <app>, haz clic en
Configuración.», but chose a lone ``input.visible.click``: the click went to whatever window was in front and the
person read «No se confirmó si la acción … funcionó, por lo que debes verificar…». A restatement the mission reader
reads as a step inside an application is that mission (the screen decides it, its final says «no pude» with the cause
or the verified result); one of the mission's own primitives chosen alone is a piece of it. A restatement that names
no application keeps the decider's own choice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import missions
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import context_decision
from baxy_mind import argument_grounding
from baxy_mind import engine_handoff

ROOT = Path(__file__).resolve().parents[1]
APPS = ("Discord", "Steam", "Bloc de notas")
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
HISTORY = [
    {"role": "user", "content": "en Discord andá al canal general"},
    {"role": "assistant", "content": "No pude ir al canal general porque no lo encontré en la pantalla."},
    {"role": "user", "content": "no"},
    {"role": "assistant", "content": "Lo dejas ahí."},
]


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The decider answers what it is given; every other model call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def detect_response_language(self, _text):
        return "es"

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _decided(text: str, decision: ContextDecision) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    return context_decision._context_decided_result(
        {"id": "s13", "text": text, "history": [*HISTORY, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=APPS,
    )


@pytest.mark.parametrize(
    ("restated", "chosen"),
    [
        # the live turn
        ("En Discord, haz clic en Configuración.", "input.visible.click"),
        ("En Discord, ve a configuración.", "input.visible.click"),
        ("En Discord, ve a configuración.", "app.open"),
        # the application said after the place: the last «en» frames it
        ("Haz clic en Configuración en Discord.", "input.visible.click"),
    ],
)
def test_a_follow_up_restated_inside_the_application_is_the_mission(restated: str, chosen: str) -> None:
    result = _decided("y ahora andá a configuración", ContextDecision(restated, "action", (chosen,), ""))

    assert result["kind"] == "action"
    assert result["operation"] == "mission.computer.use"
    assert result["effectOperations"] == ["mission.computer.use"]
    if chosen == "input.visible.click":
        # Ronda 21 (pasada r18 v3-23, v3-65): a click the person never said is the decider's paraphrase; the engine
        # takes the person's words in the conversation's application, with the check of a place, not a click's receipt.
        assert result["objective"] == "en Discord, andá a configuración"
        mission = missions.mission_request(result["objective"], APPS)
        assert mission is not None and (mission.success_check or "").startswith("control:configuracion:current")
    else:
        assert result["objective"] == restated
    # The engine's arguments come from the conversation's application and its goal.
    mission = missions.mission_request(result["objective"], APPS)
    assert mission is not None and mission.application == "Discord"


def test_a_restatement_that_names_no_application_keeps_the_decider_choice() -> None:
    restated = "Haz clic en Aceptar."
    assert resolve_explicit_effects(restated, OPERATIONS, APPS) is None or (
        resolve_explicit_effects(restated, OPERATIONS, APPS).operations != ("mission.computer.use",)
    )
    result = _decided("aceptá", ContextDecision(restated, "action", ("input.visible.click",), ""))

    assert result["operation"] == "input.visible.click"


def test_a_typed_operation_the_decider_chose_is_never_replaced_by_the_engine() -> None:
    # Only the mission's own primitives are pieces of it; a catalog operation keeps its typed route (D21).
    restated = "En Discord, ve a configuración."
    result = _decided("y ahora andá a configuración", ContextDecision(restated, "action", ("web.search",), ""))

    assert result["operation"] == "web.search"


@pytest.mark.parametrize(
    ("text", "application", "goal"),
    [
        ("hacé clic en Ajustes en Steam", "Steam", "hacer clic en ajustes"),
        ("andá a la biblioteca en Steam", "Steam", "ir a biblioteca"),
    ],
)
def test_the_application_said_after_the_last_place_frames_the_mission(text: str, application: str, goal: str) -> None:
    mission = missions.mission_request(text, APPS)

    assert mission is not None
    assert (mission.application, missions.fold(mission.goal)) == (application, goal)


# Live v2-x12: «abrí la calculadora» → «ahora ponela en modo científica»; the decider closed it as a limit («Pon la
# Calculadora en modo científico.») and the engine ran the bare words in no application: «no vi ningún control».
X12_APPS = ("Calculadora", "Discord", "Paint", "Bloc de notas")


def _followed(conversation: list[str], text: str, decision: ContextDecision) -> dict[str, Any]:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    history: list[dict[str, str]] = []
    for said in conversation:
        history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]
    return context_decision._context_decided_result(
        {"id": "x12", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=_Decider(decision), planner_catalog=catalog, application_names=X12_APPS,
    )


_LIMIT = ContextDecision("Pon la Calculadora en modo científico.", "limit", (), "")


@pytest.mark.parametrize(
    ("conversation", "text", "application", "goal"),
    [
        # the live turn
        (["abrí la calculadora"], "ahora ponela en modo científica", "Calculadora", "activar modo cientifica"),
        (["open the calculator"], "and switch it to dark mode", "Calculadora", "activar dark mode"),
        (["abrí Discord"], "y ahora andá a configuración", "Discord", "ir a configuracion"),
        # after a mission, and after a step that inherited it
        (["en Discord andá al canal general"], "y ahora andá a configuración", "Discord", "ir a configuracion"),
        (["abrí la calculadora", "ahora ponela en modo científica"], "y ahora hacé clic en Historial", "Calculadora",
         "hacer clic en historial"),
    ],
)
def test_a_follow_up_without_application_is_the_mission_in_the_conversation_application(
    conversation: list[str], text: str, application: str, goal: str,
) -> None:
    result = _followed(conversation, text, _LIMIT)

    assert result["kind"] == "action"
    assert result["operation"] == "mission.computer.use"
    mission = missions.mission_request(result["objective"], X12_APPS)
    assert mission is not None and mission.application == application
    assert missions.fold(mission.goal) == goal
    # The arguments the engine gets: the application, the reader's goal and its check, as for the one-turn order.
    grounded = argument_grounding._ground_explicit_arguments("mission.computer.use", result["objective"], _MISSION_SCHEMA, X12_APPS)
    assert grounded is not None
    assert (grounded["application"], missions.fold(grounded["goal"])) == (application, goal)
    assert grounded["successCheck"] == mission.success_check


_MISSION_SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": ["string", "null"]},
        "budgetSteps": {"type": ["integer", "null"]},
        "goal": {"type": "string"},
        "successCheck": {"type": ["string", "null"]},
    },
    "required": ["goal"],
    "additionalProperties": False,
}


def test_the_x12_follow_up_checks_the_mode_as_the_one_turn_order() -> None:
    inherited = missions.follow_up_in_application(
        "ahora ponela en modo científica", ["abrí la calculadora"], OPERATIONS, X12_APPS,
    )
    one_turn = missions.mission_request("abrí la calculadora y ponela en modo científica", X12_APPS)

    assert inherited is not None and one_turn is not None
    mission = missions.mission_request(inherited, X12_APPS)
    assert mission is not None
    assert (mission.application, mission.goal, mission.success_check) == (
        one_turn.application, one_turn.goal, one_turn.success_check,
    )


def test_a_typed_operation_the_decider_chose_for_the_step_keeps_its_route() -> None:
    result = _followed(["abrí Discord"], "y ahora andá a configuración",
                       ContextDecision("Abre la configuración de Windows.", "action", ("system.settings.status",), ""))

    assert result["operation"] != "mission.computer.use"


@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        ([], "ahora ponela en modo científica"),  # no application in the conversation
        (["qué hora es"], "ahora ponela en modo científica"),
        (["abrí la calculadora", "poné música de Queen"], "ponela en modo científica"),  # something else came after
        (["abrí la calculadora y el bloc de notas"], "ponela en modo científica"),  # which one is the decider's
        (["abrí la calculadora"], "subí el volumen"),  # no step inside a window
        (["abrí la calculadora"], "activá el modo avión"),  # a typed operation of its own
        (["abrí la calculadora"], "andá a youtube.com"),  # a site
    ],
)
def test_a_follow_up_with_no_application_to_inherit_stays_the_decider_s(conversation: list[str], text: str) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, X12_APPS) is None


def test_a_follow_up_naming_another_application_uses_that_application() -> None:
    text = "ponela en modo científica en Paint"
    assert missions.follow_up_in_application(text, ["abrí la calculadora"], OPERATIONS, X12_APPS) is None
    mission = missions.mission_request(text, X12_APPS)
    assert mission is not None and mission.application == "Paint"


# Review r10: the application is inherited from the request right before the follow-up only. A message in between
# that does nothing on the screen («cuál es la capital de Francia», «gracias») ends the conversation's application;
# a bare yes/no answer to BAXY's own question, or a step that itself inherited it, does not.
@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        (["abrí la calculadora", "cuál es la capital de Francia"], "y ahora andá a historial"),
        (["abrí la calculadora", "gracias"], "y ahora andá a historial"),
        (["abrí la calculadora", "contame un chiste", "sí"], "y ahora andá a historial"),
    ],
)
def test_a_message_in_between_ends_the_inherited_application(conversation: list[str], text: str) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, X12_APPS) is None


@pytest.mark.parametrize("answer", ["sí", "no", "dale"])
def test_a_bare_answer_to_baxy_s_question_keeps_the_application(answer: str) -> None:
    inherited = missions.follow_up_in_application(
        "y ahora andá a historial", ["abrí la calculadora", answer], OPERATIONS, X12_APPS,
    )

    assert inherited is not None and inherited.startswith("en Calculadora, ")


R10_APPS = (*X12_APPS, "Outlook")


class _AnsweringDecider(_Decider):
    """A decider whose talk, question or limit is then worded by the model."""

    def chat(self, *_a, **_k):
        return "¿Qué querés enviar?", []


@pytest.mark.parametrize(
    "decision",
    [
        ContextDecision("¿Qué querés enviar en Outlook?", "clarify", (), "¿Qué querés enviar?"),
        ContextDecision("Hacé clic en enviar.", "talk", (), ""),
        ContextDecision("No puedo enviar correos.", "limit", (), "¿Querés que abra Outlook?"),
    ],
)
def test_the_inherited_step_never_replaces_a_decider_question_or_talk(decision: ContextDecision) -> None:
    catalog = PlannerCatalog([_tool(name) for name in OPERATIONS])
    text = "ahora hacé clic en enviar"
    assert missions.follow_up_in_application(text, ["abrí Outlook"], OPERATIONS, R10_APPS) is not None
    result = context_decision._context_decided_result(
        {"id": "r10", "text": text, "history": [
            {"role": "user", "content": "abrí Outlook"}, {"role": "assistant", "content": "Listo."},
            {"role": "user", "content": text},
        ]},
        llm=_AnsweringDecider(decision), planner_catalog=catalog, application_names=R10_APPS,
    )

    assert result.get("operation") != "mission.computer.use"
    assert "mission.computer.use" not in (result.get("effectOperations") or [])


# r29 (pasada r27 v3-69): «abre el monitor de recursos» → «ahora anda a la pestaña red». Read alone, a tab said with no
# browser was the person's default browser's (``BROWSER_CATEGORY``): the mission clicked seven times in the owner's
# Opera, which nobody named. In a conversation that is in an application, the tab is that application's.
R29_APPS = ("Monitor de recursos", "Calculadora", "Google Chrome", "Bloc de notas")


@pytest.mark.parametrize(
    ("conversation", "text", "request_read", "application"),
    [
        (["abre el monitor de recursos"], "ahora anda a la pestaña red",
         "en Monitor de recursos, anda a la pestaña red", "Monitor de recursos"),
        (["abre el monitor de recursos"], "andá a la pestaña de Memoria",
         "en Monitor de recursos, andá a la pestaña de Memoria", "Monitor de recursos"),
        (["abre el monitor de recursos"], "now go to the network tab",
         "en Monitor de recursos, go to the network tab", "Monitor de recursos"),
        # the conversation's own browser, never «the person's default one» in its place
        (["abrí chrome"], "y ahora andá a la pestaña de YouTube",
         "en Google Chrome, andá a la pestaña de YouTube", "Google Chrome"),
    ],
)
def test_a_tab_said_with_no_browser_is_the_conversation_s_application_s(
    conversation: list[str], text: str, request_read: str, application: str,
) -> None:
    inherited = missions.follow_up_in_application(text, conversation, OPERATIONS, R29_APPS)

    assert inherited == request_read
    mission = missions.mission_request(inherited, R29_APPS)
    assert mission is not None and mission.application == application and mission.success_check


@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        ([], "andá a la pestaña de YouTube"),  # no conversation: the tab read alone, as before
        (["qué hora es"], "andá a la pestaña de YouTube"),  # the conversation is in no application
        (["abre el monitor de recursos"], "andá a la pestaña de YouTube en el navegador"),  # the browser, said
        (["abre el monitor de recursos"], "en el navegador andá a la pestaña de YouTube"),
    ],
)
def test_a_tab_stays_the_browser_s_when_said_so_or_with_no_application_to_inherit(
    conversation: list[str], text: str,
) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, R29_APPS) is None
    own = missions.mission_request(text, R29_APPS)
    assert own is not None and own.application == missions.BROWSER_CATEGORY


R29_MORE_APPS = (*R29_APPS, "Word")


# Review of r29 (B2): the conversation stays in its application over a tab follow-up, so the third turn is framed too
# (it was read alone again: «navegador»). B1: a spoken link («now …») does not hide the tab from the reader.
@pytest.mark.parametrize(
    ("conversation", "text", "request_read"),
    [
        (["abre el monitor de recursos", "ahora anda a la pestaña red"], "ahora andá a la pestaña memoria",
         "en Monitor de recursos, andá a la pestaña memoria"),
        (["abre el monitor de recursos", "andá a la pestaña de Memoria"], "go to the network tab",
         "en Monitor de recursos, go to the network tab"),
        (["abre el monitor de recursos", "now go to the network tab"], "and now go to the memory tab",
         "en Monitor de recursos, go to the memory tab"),
        (["abrí chrome", "y ahora andá a la pestaña de YouTube"], "andá a la pestaña de Gmail",
         "en Google Chrome, andá a la pestaña de Gmail"),
        (["abre word", "andá a la pestaña de inicio"], "ahora andá a la pestaña insertar",
         "en Word, andá a la pestaña insertar"),
        (["en Word andá a la pestaña Insertar", "ahora andá a la pestaña diseño"], "ahora andá a la pestaña inicio",
         "en Word, andá a la pestaña inicio"),
    ],
)
def test_the_conversation_stays_in_its_application_over_a_tab_follow_up(
    conversation: list[str], text: str, request_read: str,
) -> None:
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, R29_MORE_APPS) == request_read
    application = request_read[len("en "):request_read.index(",")]
    assert missions.conversation_application([*conversation, text], R29_MORE_APPS, OPERATIONS)[0] == application
    mission = missions.mission_request(request_read, R29_MORE_APPS)
    assert mission is not None and mission.application == application and mission.success_check


# Review of r29 (B3): the chain a tab was said in rode whole to the person's browser («escribir hola» typed there).
@pytest.mark.parametrize(
    ("conversation", "text", "application"),
    [
        (["abre word"], "escribí hola y andá a la pestaña insertar", "Word"),
        (["abre el monitor de recursos"], "maximizalo y andá a la pestaña red", "Monitor de recursos"),
        (["abre word", "andá a la pestaña de inicio"], "ahora escribí hola y andá a la pestaña insertar", "Word"),
    ],
)
def test_the_chain_a_tab_is_said_in_happens_in_the_conversation_s_application(
    conversation: list[str], text: str, application: str,
) -> None:
    inherited = missions.follow_up_in_application(text, conversation, OPERATIONS, R29_MORE_APPS)

    assert inherited is not None and inherited.startswith(f"en {application}, ")
    mission = missions.mission_request(inherited, R29_MORE_APPS)
    assert mission is not None and len(mission.steps) == 2
    assert {step.application for step in mission.steps} == {application}


@pytest.mark.parametrize(
    ("conversation", "text"),
    [
        (["andá a la pestaña de YouTube"], "ahora andá a la pestaña de Gmail"),  # the browser's from the first message
        (["abre word", "andá a la pestaña de YouTube en el navegador"], "ahora andá a la pestaña de Gmail"),
        (["abre word", "qué hora es"], "andá a la pestaña insertar"),  # the conversation left the application
    ],
)
def test_a_tab_after_the_browser_s_or_after_talk_inherits_no_application(conversation: list[str], text: str) -> None:
    assert missions.conversation_application(conversation, R29_MORE_APPS, OPERATIONS) is None
    assert missions.follow_up_in_application(text, conversation, OPERATIONS, R29_MORE_APPS) is None


@pytest.mark.parametrize(
    ("text", "alone"),
    [
        ("ahora anda a la pestaña red", True),
        ("now go to the network tab", True),
        ("escribí hola y andá a la pestaña insertar", True),
        ("andá a la pestaña de YouTube en el navegador", False),
        ("en Word andá a la pestaña Insertar", False),
        ("ahora ponela en modo científica", False),
        ("abrí una pestaña nueva", False),
    ],
)
def test_one_reader_says_whether_a_tab_names_no_application(text: str, alone: bool) -> None:
    assert missions.tab_names_no_application(text, R29_MORE_APPS) is alone


# Review 2 of r29: as a FIRST message, the chain a tab is said in was read whole in the person's browser («escribir
# hola» typed there, an Enter pressed there). The browser a tab takes when nobody says where is lent to no other
# clause: the chain has no application and is not read (the decider takes it); the engine, if chosen, gets no
# application (ComputerUseLoopTests.AChainWithATabAndNoApplicationTypesNothingInThePersonsBrowser).
@pytest.mark.parametrize(
    "text",
    [
        "escribí hola y andá a la pestaña insertar",
        "andá a la pestaña insertar y escribí hola",
        "write hello and go to the insert tab",
        "go to the insert tab and write hello",
        "apretá enter y andá a la pestaña red",
        "escribí mi contraseña 1234 y andá a la pestaña de Gmail",
        "andá a la pestaña de YouTube y dale play",
    ],
)
def test_a_first_message_chain_with_a_tab_and_no_application_is_no_mission_in_the_browser(text: str) -> None:
    assert missions.mission_request(text, R29_MORE_APPS) is None
    assert missions.follow_up_in_application(text, [], OPERATIONS, R29_MORE_APPS) is None
    handed = missions.free_form_arguments(text, R29_MORE_APPS, ())
    assert handed is not None and "application" not in handed and "frontWindow" not in handed
    # In a conversation that is in an application the same chain happens there, every clause of it.
    inherited = missions.follow_up_in_application(text, ["abre word"], OPERATIONS, R29_MORE_APPS)
    assert inherited is not None and inherited.startswith("en Word, ")
    mission = missions.mission_request(inherited, R29_MORE_APPS)
    assert mission is not None and {step.application for step in mission.steps} == {"Word"}


def test_a_chain_with_a_tab_said_in_the_browser_is_the_browser_s() -> None:
    mission = missions.mission_request("escribí hola y andá a la pestaña insertar en el navegador", R29_MORE_APPS)

    assert mission is not None and {step.application for step in mission.steps} == {missions.BROWSER_CATEGORY}
    assert missions.tab_names_no_application("escribí hola y andá a la pestaña insertar en el navegador", R29_MORE_APPS) is False
    # The residue that stays: one clause, going to a tab and nothing else, is the person's browser's.
    alone = missions.mission_request("andá a la pestaña de YouTube", R29_MORE_APPS)
    assert alone is not None and alone.application == missions.BROWSER_CATEGORY and not alone.steps


def test_the_v3_69_mission_is_the_one_the_loop_test_runs() -> None:
    # ComputerUseLoopTests.TheFollowUpOfV369StopsOnTheRaisedApplicationAndNeverLooksAtThePersonsBrowser runs these
    # very arguments through the engine.
    mission = missions.mission_request("en Monitor de recursos, anda a la pestaña red", R29_APPS)

    assert mission is not None
    assert (mission.application, mission.goal, mission.success_check) == (
        "Monitor de recursos", "ir a la pestaña red", "control:red:selected|title:red",
    )


def test_the_v3_69_follow_up_is_decided_in_the_application_the_conversation_opened() -> None:
    history = [
        {"role": "user", "content": "abre el monitor de recursos"},
        {"role": "assistant", "content": "Listo, abrí Monitor de recursos."},
    ]
    text = "ahora anda a la pestaña red"

    assert engine_handoff._the_place_gone_to_again(
        text, [*history, {"role": "user", "content": text}], OPERATIONS, R29_APPS,
    ) == "en Monitor de recursos, anda a la pestaña red"
