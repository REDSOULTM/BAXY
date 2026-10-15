"""Estabilización X5 (tandas n5 y n6 en el notebook sobre fable/estab-fase3 5862303c4, que ya incluía X4).

t4-c03 t4 «ya cierra discord» and t2-c03 t2 «ya cierra configuracion que me esta laggeando el valorant» were still asked
(«¿Quieres que te avise cuando Discord se cierre?», «¿Te gustaría que cierre la configuración ahora mismo?»). Replayed
offline with the real model, the decider LoRA and the whole conversation (the mind sidecar on redpc, the same questions
came back), the decider never asked: it chose app.close with {"appId": "discord"} and {"app": "Configuración"}. App.close
declares only the identifier ``windowId``, so ``_fills_an_undeclared_argument`` read the application as a part of the
request the operation cannot honour and turned the order into a question with none; the last barrier wrote it. The
target of app.close is named through its catalog prerequisite (window.resolve, ``applicationName``), which takes the
decider's values in the plan (M141): those fields are declared too.

Contracasos: a part no operation nor prerequisite holds (a tab) is still not a close of the whole application; an aviso
asked for is never a close; the order of the 20b guard (a folder the count cannot take) keeps asking.
"""

from __future__ import annotations

import pytest

from baxy_mind.decided_arguments import _schema_field_of
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import turn_decide

from test_estab_t_orden_sin_pregunta import _Decider, _tool

# The schemas are the real catalog's (src/Baxy.Kernel/Operations/ProductCatalog.cs).
_TOOLS = {
    "app.close": _tool("app.close", "work_loss", {"windowId": {"type": "string"}}, ["windowId"]),
    "window.resolve": _tool(
        "window.resolve", "read_only",
        {"applicationName": {"type": "string"}, "byTitle": {"type": "boolean"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 50}, "offset": {"type": "integer", "minimum": 0},
         "process": {"type": "string"}},
    ),
    "window.active": _tool("window.active", "read_only"),
    "app.open": _tool("app.open", "low_reversible", {"appId": {"type": "string"}}, ["appId"]),
    "notification.schedule": _tool("notification.schedule", "low_reversible", {"title": {"type": "string"}}),
    "filesystem.explorer.count": _tool(
        "filesystem.explorer.count", "read_only", {"extension": {"type": "string"}}, ["extension"],
    ),
}
_APPLICATIONS = ("Discord", "Spotify", "Configuración", "Microsoft Edge")
# The conversations before the turn, as n6 answered them (n5 alike).
_T4_C03 = [
    {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"},
    {"role": "user", "content": "abre discord porfa"},
    {"role": "assistant", "content": "La aplicación «Discord» ya estaba abierta."},
    {"role": "user", "content": "mandale a Ron92 que si se conecta a las 9 pa jugar"},
    {"role": "assistant", "content": "Envié el mensaje a «Ron92» en Discord: dice «si se conecta a las 9 pa jugar»."},
    {"role": "user", "content": "y ponme una alarma a las 8:50 pa acordarme"},
    {"role": "assistant",
     "content": "He programado la alarma para las 08:50 mañana con el título \"Acordarme para jugar\"."},
]
_T2_C03 = [
    {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"},
    {"role": "user", "content": "abre configuracion que quiero ver lo de la pantalla"},
    {"role": "assistant", "content": "Listo, estoy en «pantalla»."},
]


class _Talker(_Decider):
    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Eso no lo hago.", []


def _route(text: str, history: list[dict], decision: ContextDecision) -> tuple[dict, _Decider]:
    llm = _Talker(decision)
    result = turn_decide._prepare_turn_result(
        {"id": "turn-estab-x5", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_TOOLS,
        application_names=_APPLICATIONS,
    )
    return result, llm


@pytest.mark.parametrize(
    ("text", "history", "decision"),
    [
        # The decider's replies read offline (redpc, real model + decider-full3, twice each, identical).
        ("ya cierra discord", _T4_C03,
         ContextDecision("Cierra Discord.", "action", ("app.close",), "", (("appId", "discord"),))),
        ("ya cierra configuracion que me esta laggeando el valorant", _T2_C03,
         ContextDecision("Cierra Configuración.", "action", ("app.close",), "", (("app", "Configuración"),))),
    ],
)
def test_the_close_the_decider_chose_is_done_with_no_question(
    text: str, history: list[dict], decision: ContextDecision,
) -> None:
    result, llm = _route(text, history, decision)

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"
    assert not result.get("question")
    assert llm.recoveries == 0


def test_an_identifier_is_named_by_what_it_identifies() -> None:
    resolve = _TOOLS["window.resolve"]["function"]["parameters"]["properties"]
    assert _schema_field_of("appId", "window.resolve", resolve, []) == "applicationName"
    assert _schema_field_of("app", "window.resolve", resolve, []) == "applicationName"
    # Contracaso: a field named as itself stays itself, and a bare «Id» names nothing.
    assert _schema_field_of("appId", "app.open", {"appId": {}}, ["appId"]) == "appId"
    assert _schema_field_of("Id", "window.resolve", resolve, []) is None


def test_a_part_neither_the_close_nor_its_prerequisite_holds_is_no_close() -> None:
    # Contracaso: a tab is not the application; closing the whole browser would not be what was asked.
    decision = ContextDecision(
        "Cierra la pestaña de YouTube en Edge.", "action", ("app.close",), "",
        (("app", "Microsoft Edge"), ("tab", "YouTube")),
    )
    result, _ = _route("cierra la pestaña de youtube en edge", _T2_C03, decision)

    assert result.get("operation") != "app.close"
    assert "app.close" not in (result.get("effectOperations") or [])


def test_an_aviso_asked_for_is_never_a_close() -> None:
    # Contracaso: the real decider read «cuando se cierre discord avisame» as a limit (replay); it is never app.close.
    decision = ContextDecision("Avisame cuando se cierre Discord.", "limit", (), "")
    result, _ = _route("cuando se cierre discord avisame", _T4_C03, decision)

    assert result.get("operation") != "app.close"
    assert "app.close" not in (result.get("effectOperations") or [])


def test_a_count_with_a_folder_it_cannot_take_still_asks() -> None:
    # Contracaso (ronda 20b-3): the prerequisites widen only the operations that have them.
    decision = ContextDecision(
        "Cuenta los zip de baxy-prueba-v3.", "action", ("filesystem.explorer.count",), "",
        (("extension", "zip"), ("folder", "baxy-prueba-v3")),
    )
    result, _ = _route("¿cuántos zip hay en baxy-prueba-v3?", [], decision)

    assert result["kind"] == "clarify"
