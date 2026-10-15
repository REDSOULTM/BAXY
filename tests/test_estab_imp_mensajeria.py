"""Estabilización, imprescindibles de mensajería (dueño 2026-10-10, decisión 4; destinos de prueba 2026-10-11).

Ninguna operación tipada leía un chat ni salía de una llamada: «qué me escribió Ron92 en Discord» era el límite
«no leo chats» y «en Discord salí del canal de voz» no tenía ruta (sondeo del 2026-10-11 sobre 40534dee6). Ahora las dos
son una misión sobre la aplicación nombrada: ir al chat y responder desde la conversación que muestra la vista (el
suelo cita el último mensaje cuyo autor es la persona preguntada, como lo nombra el árbol de Discord: «autor , texto ,
hora», medido en redpc), y pulsar el control que deja la llamada (salir no sale al mundo: no se confirma). Las palabras
son datos (data/conversation_acts.v1.json). Cada regla con su contracaso.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from baxy_mind import cu_finals, cu_projection
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic import account_acts, chats, missions
from baxy_mind.semantic.conversation import stable_no_effect_preempts
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.patterns import known_unsupported_effect_request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cu_v3_cobertura import APPS, OPERATIONS, _tool  # noqa: E402
from test_cu_v3_r21_palabras_de_la_persona import _WholeTurn  # noqa: E402

from baxy_mind import turn_decide  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402

PLACES = (*APPS, "WhatsApp")
DATA = json.loads(
    (Path(chats.__file__).resolve().parent.parent / "data" / "conversation_acts.v1.json").read_text(encoding="utf-8")
)
# The last messages of the DM «Mensajes en Ron92» as Discord's accessible tree names them (redpc, 2026-10-11), with
# one of Ron92's put among them.
DM = [
    "RED Etiqueta del servidor: DEMO , prueba BAXY G1 , 12:39 p. m.",
    "Ron92 , ¿jugamos a las 9? , 12:40 p. m.",
    "RED Etiqueta del servidor: DEMO , prueba BAXY G1 , 12:41 p. m.",
    "Ron92 Etiqueta del servidor: XYZ , dale, nos vemos , 12:50 p. m.",
    "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 01:12 p. m.",
]


def _whole_turn(text: str) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return turn_decide._decide_turn_result(
        {"id": "imp", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_WholeTurn(ContextDecision("", "talk", (), "")), planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _text: (), tool_by_name=tools, application_names=PLACES, in_conversation=False,
    )


# ------------------------------------------------------------------------------------------------ the data's examples

@pytest.mark.parametrize("example", DATA["lastWritten"]["examples"])
def test_every_last_written_example_reads_its_chat_and_author(example: dict) -> None:
    read = chats.last_written(example["said"])
    assert read is not None, example
    assert read.author == example.get("author")
    assert read.chat == example.get("chat", example.get("author"))


@pytest.mark.parametrize("said", DATA["lastWritten"]["notExamples"])
def test_no_last_written_counter_example_is_read(said: str) -> None:
    assert chats.last_written(said) is None


@pytest.mark.parametrize("said", DATA["leaveCall"]["examples"])
def test_every_leave_call_example_leaves(said: str) -> None:
    assert chats.leaves_the_call(said)


@pytest.mark.parametrize("said", DATA["leaveCall"]["notExamples"])
def test_no_leave_call_counter_example_leaves(said: str) -> None:
    assert not chats.leaves_the_call(said)


# ------------------------------------------------------------------------------------------ reading the last written

@pytest.mark.parametrize(
    ("said", "application", "chat"),
    [
        ("en Discord leé lo último que me escribió Ron92", "Discord", "ron92"),
        ("qué me escribió Ron92 en Discord", "Discord", "ron92"),
        ("¿qué fue lo último que me escribió Ron92 en Discord?", "Discord", "ron92"),
        ("what did Ron92 write me on Discord", "Discord", "ron92"),
        ("en WhatsApp leé lo último que me escribieron en Música", "WhatsApp", "musica"),
    ],
)
def test_a_chat_read_in_an_application_goes_to_the_chat_and_asks(said: str, application: str, chat: str) -> None:
    mission = missions.mission_request(said, PLACES)
    assert mission is not None and mission.application == application
    goal, _, question = mission.goal.partition(missions.QUESTION_MARK)
    assert goal == f"ir a {chat}" and question
    # Arrived is the chat reached, by the same check as going there («en Discord abrí el chat con Ron92»).
    assert mission.success_check == missions.read_clause(f"ir a {chat}")[1]
    found = resolve_explicit_effects(said, OPERATIONS, PLACES)
    assert found is not None and found.operations == ("mission.computer.use",)
    assert _whole_turn(said)["effectOperations"] == ["mission.computer.use"]


def test_a_chat_read_with_no_application_is_still_the_plain_limit() -> None:
    said = "qué me escribió mamá"
    assert missions.mission_request(said, PLACES) is None
    assert known_unsupported_effect_request(said, OPERATIONS)
    assert stable_no_effect_preempts(said)
    # Said in an application, the limit no longer closes it (the mission reads it).
    assert not known_unsupported_effect_request("qué me escribió Ron92 en Discord", OPERATIONS)
    assert not stable_no_effect_preempts("qué me escribió Ron92 en Discord")
    # Without the engine there is still nothing that reads it.
    assert known_unsupported_effect_request("qué me escribió Ron92 en Discord", ("web.search",))


def test_going_to_a_chat_and_sending_are_read_as_before() -> None:
    assert missions.mission_request("en Discord abrí el chat con Ron92", PLACES).goal == "ir a ron92"
    assert missions.mission_request("en Discord entrá al canal Cotele", PLACES).goal == "ir a cotele"
    assert _whole_turn('en Discord mandale a Ron92 "prueba BAXY 14"')["effectOperations"] == [
        "message.recipient.resolve", "message.send",
    ]
    # Encargo IMP2: WhatsApp's send is the mission that sends in Discord (data conversation_acts «sendInPlace»; its
    # typed route failed live in imp1); tests/test_estab_imp2.py reads the chain.
    assert _whole_turn('en WhatsApp mandale a Música "prueba BAXY imp"')["effectOperations"] == ["mission.computer.use"]


# ------------------------------------------------------------------------------------------------- the floor's answer

def _seen(question: str, messages: list[str] | None, reached: bool = True) -> dict:
    observed = {"goal": f"ir a ron92{missions.QUESTION_MARK}{question}", "reached": reached, "steps": [],
                "window": {"title": "@Ron92 - Discord"}, "screen": {"title": "@Ron92 - Discord"}}
    if messages is not None:
        observed["screen"]["groups"] = messages
    return cu_projection.project_seen(observed, "es")


def test_the_last_message_of_the_person_asked_is_said_with_its_time() -> None:
    answer = cu_finals.question_answer(_seen("qué me escribió Ron92", DM), english=False)
    assert answer == "Lo último que te escribió Ron92 fue «dale, nos vemos» (12:50 p. m.)."
    english = cu_finals.question_answer(_seen("what did Ron92 write me", DM), english=True)
    assert english == "The last thing Ron92 wrote you was «dale, nos vemos» (12:50 p. m.)."


def test_a_conversation_with_none_of_theirs_says_so_and_names_no_other_message() -> None:
    mine = [entry for entry in DM if not entry.startswith("Ron92")]
    answer = cu_finals.question_answer(_seen("qué me escribió Ron92", mine), english=False)
    assert answer == "En lo que muestra el chat no hay mensajes de Ron92."


@pytest.mark.parametrize(
    ("question", "messages"),
    [
        # No author said: the chat of a group, whoever wrote; the model answers from the lines.
        ("leé lo último que me escribieron en Música", DM),
        # No conversation read (WhatsApp draws no tree): nothing to say from the floor.
        ("qué me escribió Ron92", None),
        ("qué me escribió Ron92", ["Mensajes directos", "Amigos"]),
        # Another question about the window never reads the conversation.
        ("decime si el modo es claro u oscuro", DM),
    ],
)
def test_the_floor_is_silent_without_an_author_or_a_conversation(question: str, messages: list[str] | None) -> None:
    assert cu_finals.question_answer(_seen(question, messages), english=False) == ""


def test_the_conversation_reaches_only_a_last_written_question() -> None:
    assert _seen("qué me escribió Ron92", DM)["messages"] == DM
    other = _seen("decime si el modo es claro u oscuro", DM)
    assert "messages" not in other and "groups" not in other["screen"]
    assert cu_finals.question_answer(_seen("qué me escribió Ron92", DM, reached=False), english=False) == ""


# ------------------------------------------------------------------------------------------------- leaving the call

@pytest.mark.parametrize(
    "said",
    ["en Discord salí del canal de voz", "salí del canal de voz en Discord", "en Discord desconectate de la llamada",
     "leave the voice channel in Discord", "en Discord colgá"],
)
def test_leaving_the_call_presses_the_control_that_leaves_it(said: str) -> None:
    mission = missions.mission_request(said, PLACES)
    assert mission is not None and mission.application == "Discord"
    assert mission.goal == "hacer clic en desconectar"
    assert mission.success_check.split("|") == [
        f"stepDone:input.visible.click:{missions.fold(label)}" for label in chats.leave_call_labels()
    ]
    assert _whole_turn(said)["effectOperations"] == ["mission.computer.use"]


def test_leaving_does_not_go_out_to_the_world_and_joining_does() -> None:
    # Decision 8: what goes out to the world is confirmed; leaving ends one's own presence and is undone by joining.
    for label in chats.leave_call_labels():
        assert account_acts.world_act(label) is None, label
    assert account_acts.world_act("Cotele!!!😎, Canal de voz, Choche") == "call"
    # Counter-cases: an order that only says «salí» or leaves another place is no call left.
    assert missions.mission_request("en Discord salí", PLACES) is None or (
        missions.mission_request("en Discord salí", PLACES).goal != "hacer clic en desconectar"
    )
    assert not chats.leaves_the_call("salí de configuración")
