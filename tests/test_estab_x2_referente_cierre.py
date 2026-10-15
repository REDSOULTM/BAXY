"""Estabilización X2: «ya ciérrala» after steps in the application the conversation is in closes that application.

Tandas n1/n2 on the notebook (fable/estab-fase3 9b7d8d757), t3-c18: «abre la calculadora» → «ahora ponla en modo
programador» → «esa no es la de programador wey, sigue en la estandar, cambiala» → «ya ciérrala». M96's reader only
looked at the request right before the pronoun, which opened nothing, so the turn was the decider's: in n1 it asked
(«¿Qué quieres que haga exactamente?», raw decision clarify, request «ya ciérrala»), in n2 it restated «Cierra la
Calculadora.». The antecedent is the application the conversation is in (``conversation_application``); it is read,
never left to the model. Without one the decider reads the turn as before, and a pronoun is never the window in front.
The decider is scripted so what is under test is the deterministic step.
"""

from __future__ import annotations

import pytest

from baxy_mind import context_decision, plan_shape
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import closes_the_active_window
from baxy_mind.semantic.decider import ContextDecision

OPERATIONS = (
    "app.open", "app.close", "window.resolve", "window.active", "window.focus", "web.search", "audio.mute",
    "mission.computer.use", "input.visible.click", "input.key.press", "calculator.expression.evaluate",
    "system.settings.set",
)
APPLICATIONS = ("Calculadora", "Calculator", "Bloc de notas", "Notepad", "Visual Studio Code", "Terminal", "Discord")

C18 = ("abre la calculadora", "ahora ponla en modo programador",
       "esa no es la de programador wey, sigue en la estandar, cambiala")
# BAXY's replies as the two tandas published them (tanda_resultado.jsonl, turns 1–3).
N1_REPLIES = ("Listo, abrí la Calculadora.", "Listo, estoy en «Programador».",
              "Ya estás en modo estándar.\n- Programador\n- Estándar")
N2_REPLIES = ("Listo, abrí la Calculadora.", "«Programador» ya estaba elegido en «Calculadora».",
              "La pantalla ya muestra «Programador Calculadora».")


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


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.decided = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        self.decided += 1
        return self.decision

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Cuál querés que cierre?"

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Algo.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def _turn(text: str, said: tuple[str, ...], replies: tuple[str, ...], decider: _Decider) -> dict[str, object]:
    history = [turn for pair in zip(said, replies) for turn in
               ({"role": "user", "content": pair[0]}, {"role": "assistant", "content": pair[1]})]
    return context_decision._context_decided_result(
        {"id": "x2", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
        application_names=APPLICATIONS,
    )


# n1's own decision: clarify, the request unrestated.
_ASKED = ContextDecision("ya ciérrala", "clarify", (), "")


@pytest.mark.parametrize("replies", [N1_REPLIES, N2_REPLIES], ids=["n1", "n2"])
def test_the_pronoun_closes_the_application_the_conversation_is_in(replies: tuple[str, ...]) -> None:
    decider = _Decider(_ASKED)

    result = _turn("ya ciérrala", C18, replies, decider)

    assert decider.decided == 0  # read, never left to the model: both payloads close the same window
    assert (result["kind"], result["operation"], result["objective"]) == ("action", "app.close", "Cierra Calculadora")
    assert not closes_the_active_window(str(result["objective"]))
    first, _ = plan_shape._expand_effect_plan(("app.close",), (str(result["objective"]),))
    assert first[0] == "window.resolve"  # by name, never the window in front


@pytest.mark.parametrize(
    ("said", "replies", "pronoun", "objective"),
    [
        (("abrí el bloc de notas", "escribí hola mundo", "gracias"), ("Listo.", "Listo, escribí «hola mundo».", "De nada."),
         "ya cerralo", "Cierra Bloc de notas"),
        (("open the calculator", "switch it to scientific mode"), ("Done.", "Done, it is in Scientific."),
         "ok close it", "Close Calculator"),
    ],
)
def test_steps_and_thanks_in_between_keep_the_application(
    said: tuple[str, ...], replies: tuple[str, ...], pronoun: str, objective: str,
) -> None:
    decider = _Decider(_ASKED)

    result = _turn(pronoun, said, replies, decider)

    assert decider.decided == 0
    assert (result["kind"], result["operation"], result["objective"]) == ("action", "app.close", objective)


@pytest.mark.parametrize(
    ("said", "replies"),
    [
        ((), ()),  # nothing said before
        (("abre la calculadora", "¿cuál es la capital de Francia?"), ("Listo.", "París.")),  # talk ended it
        (("abre la calculadora", "silencia el audio"), ("Listo.", "Silencié el audio.")),  # a typed order elsewhere
    ],
    ids=["sin-antecedente", "charla-en-medio", "orden-tipada"],
)
@pytest.mark.parametrize(
    "restated", ["Cierra la ventana activa.", "Cierra Visual Studio Code.", "Cierra la Terminal.", "ya ciérrala"],
)
def test_without_the_application_the_pronoun_never_closes_what_nobody_named(
    said: tuple[str, ...], replies: tuple[str, ...], restated: str,
) -> None:
    decider = _Decider(ContextDecision(restated, "action", ("app.close",), ""))

    result = _turn("ya ciérrala", said, replies, decider)

    assert decider.decided == 1  # the decider reads it, as before
    assert result["kind"] == "clarify"  # which one is asked: never the window in front nor one nobody named
    assert result["operation"] is None


# ------------------------------------------------------------------ the first message: nothing before the pointer
# Coordinator, after X4: a first «ya ciérrala» was read by the explicit readers as app.close (``deictic_close_request``
# counted the bare pronoun as the window in front) and planned window.active → app.close. The pointer is no reading of
# the window in front; the decider reads it, and a close it fills with the window in front, with what nobody named or
# with the pointer itself is asked.

_POINTERS = ("ya ciérrala", "cerrala", "ciérralo", "close it", "cierra eso")


@pytest.mark.parametrize("text", _POINTERS)
def test_a_first_pointer_is_no_close_the_readers_prove(text: str) -> None:
    from baxy_mind.semantic.patterns import resolve_explicit_effects

    assert resolve_explicit_effects(text, OPERATIONS, APPLICATIONS) is None
    # The window in front named as such is still that window's close.
    assert resolve_explicit_effects("cierra esta ventana", OPERATIONS, APPLICATIONS).operations == ("app.close",)


@pytest.mark.parametrize("text", _POINTERS)
@pytest.mark.parametrize(
    "decided",
    [
        ("", "clarify", ()),
        ("Cierra la ventana activa.", "action", ("app.close",)),
        ("Cierra Visual Studio Code.", "action", ("app.close",)),
        ("Close the terminal.", "action", ("app.close",)),
        (None, "action", ("app.close",)),  # the pointer kept as said
    ],
)
def test_a_first_pointer_asks_which_and_never_plans_a_close(text: str, decided: tuple) -> None:
    from baxy_mind import turn_decide
    from test_estab_t_orden_sin_pregunta import _Decider as _TurnDecider, _TOOLS

    request, decision, operations = decided
    llm = _TurnDecider(ContextDecision(text if request is None else request, decision, operations, ""))
    result = turn_decide._prepare_turn_result(
        {"id": "x2-first", "text": text, "history": [{"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_TOOLS,
        application_names=APPLICATIONS,
    )

    assert result["kind"] == "clarify"
    assert result.get("operation") is None
    assert "app.close" not in (result.get("effectOperations") or [])
