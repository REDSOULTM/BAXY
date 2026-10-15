"""Estabilización X4 (tandas n1, n2 en el notebook y fin1, fin2 en redpc, todas sobre fable/estab-fase3).

1. t4-c03 t4 «ya cierra discord», t2-c03 t2 «ya cierra configuracion que me esta laggeando el valorant»: in every run
   the turn audit shows the decider's call and then the last barrier's, which wrote «¿Quieres que te avise cuando
   Discord se cierre?». X4 deduced a question of the decider's in the other language; X5 read the decider's real reply
   offline (an app.close with the application among its values) and fixed the guard that asked: these tests hold the
   real reply now.
2. t3-c18 t3 (n1) «esa no es la de programador wey, sigue en la estandar, cambiala» → «Ya estás en modo estándar.» with
   Programador read on the screen. X4 vetoed such a draft; encargo TZ-CAL says the held state from its own sentence,
   never drafted, so the claimed state is never said to hold.

Contracasos: an aviso asked for («cuando se cierre discord avisame») is never a close; a pointer with no antecedent is
asked; a question of the decider's own in the person's language is still asked.
"""

from __future__ import annotations

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import turn_decide, turn_followups

from test_estab_t_orden_sin_pregunta import _Decider, _TOOLS
from test_cu_v3_correccion_contra_lo_hecho import _calculator_mission, _state

_APPLICATIONS = ("Discord", "Spotify", "Configuración", "Calculadora")
# t4-c03 before turn 4, as the notebook runs (n1, n2) and redpc's (fin1, fin2) answered it.
_T4_C03 = {
    "notebook": [
        {"role": "user", "content": "abre discord porfa"},
        {"role": "assistant", "content": "La aplicación «Discord» ya estaba abierta."},
        {"role": "user", "content": "mandale a Ron92 que si se conecta a las 9 pa jugar"},
        {"role": "assistant", "content": "Envié el mensaje a «Ron92» en Discord: dice «si se conecta a las 9 pa jugar»."},
        {"role": "user", "content": "y ponme una alarma a las 8:50 pa acordarme"},
        {"role": "assistant",
         "content": "He programado la alarma para las 08:50 mañana con el título \"Acordarme para jugar\"."},
    ],
    "redpc": [
        {"role": "user", "content": "abre discord porfa"},
        {"role": "assistant", "content": "La aplicación «Discord» ya estaba abierta."},
        {"role": "user", "content": "mandale a Ron92 que si se conecta a las 9 pa jugar"},
        {"role": "assistant", "content": "Envié el mensaje a «Ron92» en Discord: dice «¿Te conectas a las 9 para jugar?»."},
        {"role": "user", "content": "y ponme una alarma a las 8:50 pa acordarme"},
        {"role": "assistant", "content": "He programado la alarma para las 08:50 con el título \"Acordarme para jugar\"."},
    ],
}
# t2-c03 before turn 2 (the four runs answered it alike).
_T2_C03 = [
    {"role": "user", "content": "abre configuracion que quiero ver lo de la pantalla"},
    {"role": "assistant", "content": "Listo, estoy en «pantalla»."},
]


def _route(text: str, history: list[dict], question: str) -> tuple[dict, _Decider]:
    llm = _Decider(ContextDecision(text, "clarify", (), question))
    result = turn_decide._prepare_turn_result(
        {"id": "turn-estab-x4", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_TOOLS,
        application_names=_APPLICATIONS,
    )
    return result, llm


# Estabilización X5: the decider never asked these turns. Replayed offline with the real model and the whole
# conversation it chose app.close with the application among its values ({"appId": "discord"}, {"app": "Configuración"});
# the questions came from the undeclared-argument guard (test_estab_x5_ordenes.py). The two tests that fixed «a question
# in the other language is read as none» are the decider's real reply now.
def _acted(text: str, history: list[dict], restated: str, arguments: tuple) -> dict:
    llm = _Decider(ContextDecision(restated, "action", ("app.close",), "", arguments))
    result = turn_decide._prepare_turn_result(
        {"id": "turn-estab-x4", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_TOOLS,
        application_names=_APPLICATIONS,
    )
    assert llm.recoveries == 0
    return result


@pytest.mark.parametrize("run", sorted(_T4_C03))
def test_t4_c03_close_the_decider_chose_is_done(run: str) -> None:
    result = _acted("ya cierra discord", _T4_C03[run], "Cierra Discord.", (("appId", "discord"),))

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"


def test_t2_c03_close_with_its_reason_the_decider_chose_is_done() -> None:
    result = _acted(
        "ya cierra configuracion que me esta laggeando el valorant", _T2_C03, "Cierra Configuración.",
        (("app", "Configuración"),),
    )

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"


@pytest.mark.parametrize(
    ("text", "history"),
    [
        # An aviso asked for is no close.
        ("cuando se cierre discord avisame", _T4_C03["notebook"]),
        ("avisame cuando se cierre discord", []),
        # A pointer with nothing it can point to before it is asked (M19/M118).
        ("ya ciérrala", [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "Hola, ¿qué necesitas?"}]),
        # Taken back.
        ("ya cierra discord, bueno no, mejor no", _T4_C03["notebook"]),
    ],
)
def test_no_complete_close_keeps_asking_whatever_language_the_question_was(text: str, history: list[dict]) -> None:
    result, _ = _route(text, history, "Do you want me to close Discord?")

    assert result.get("operation") != "app.close"
    assert "app.close" not in (result.get("effectOperations") or [])


def test_the_deciders_own_question_in_the_persons_language_is_asked() -> None:
    question = "¿Cuál de las dos ventanas de Discord cierro?"
    result, llm = _route("ya cierra discord", _T4_C03["notebook"], question)

    assert result["kind"] == "clarify"
    assert result["question"] == question
    assert llm.recoveries == 0


T3_C18 = "esa no es la de programador wey, sigue en la estandar, cambiala"


class _Writer:
    """A writer that would draft the n1 final; a held state is never drafted (encargo TZ-CAL)."""

    def __init__(self) -> None:
        self.calls = 0

    def compose_user_message(self, *_args: object, **_kwargs: object) -> str:
        self.calls += 1
        return "Ya estás en modo estándar. Programador, Estándar."


def test_t3_c18_the_held_state_is_said_from_what_was_read_never_drafted() -> None:
    # Encargo TZ-CAL rewrote X4's check: X4 vetoed the n1 draft that said Estándar held (held_final_defect, through
    # ``refused``); the held state is now said with its own sentence (data «heldFact.state»), so no draft can say it.
    shown = _calculator_mission(values=[{"name": "Programador", "value": "Programador"}])
    state = _state("ahora ponla en modo programador", "mission.computer.use", shown, "Listo, estoy en «Programador».")
    writer = _Writer()
    result = turn_followups._correction_already_held({"id": "x4", "text": T3_C18, "history": []}, state, writer)

    assert result is not None and writer.calls == 0
    assert result["reply"] == "Ya está en «Programador»: es lo que muestra la pantalla."
    assert "estándar" not in result["reply"].lower()
