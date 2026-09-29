"""M65: the regressions of the owner script and the held-out between conv-m35 (b73137f4) and conv-v3g (0ef2d86b).

Each case is the real turn of conv-v3g, with the decision its contextual decider took (turn-audit) and the history
the App sent; the decider is scripted so the deterministic steps after it are what is under test.

- owner script t37 «Perfecto muy bien» after BAXY asked «¿Quieres que te ayude a abrir Steam y veas tu biblioteca?»:
  the decider restated «Abre Steam y entra a la biblioteca.» and Steam opened. Praise asks for nothing.
- owner script t30 «Di la palabra"algo"»: restated «Escribe la palabra «algo».» and «Algo» was typed into the window
  in front. Saying is not typing.
- held-out t11 «cerralo» after «abrí el bloc de notas»: restated «Cierra el Bloc de notas.»; the M19 check read
  «cierra» as a word nobody said and asked «¿Quieres que cierre el Bloc de notas?» instead of the confirmation, so
  t12 «sí, dale» only reached the confirmation. The person's verb in another form is the person's.
- owner script t37 final «He abierto Steam y he entrado en la biblioteca.» over app.open with alreadyRunning=true.
"""

from __future__ import annotations

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue as dialogue_slot
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.ui import asks_to_type

OPERATIONS = ("app.open", "app.close", "input.text.type", "input.visible.click", "web.search", "window.resolve")


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
        self.chats = 0

    def decide_in_context(self, text: str, history: object, tools: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Algo.", []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que cierre?"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _turn(text: str, llm_: _Decider, history: list[tuple[str, str]]) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._context_decided_result(
        {"id": "m65", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=llm_,
        planner_catalog=PlannerCatalog(list(tools.values())),
    )


# conv-v3g owner script t35–t36, as the App sent them.
STEAM_HISTORY = [
    ("user", "Entonces cual fue el 1er libro de zombies"),
    ("assistant", "No pude buscar esa información ahora mismo, pero puedo abrirlo en tu navegador."),
    ("user", "abre steam y ve a la biblioteca"),
    ("assistant", "¿Quieres que te ayude a abrir Steam y veas tu biblioteca?"),
]


def test_praise_after_a_composed_question_opens_nothing() -> None:
    decider = _Decider(ContextDecision("Abre Steam y entra a la biblioteca.", "action", ("app.open",), ""))

    result = _turn("Perfecto muy bien", decider, STEAM_HISTORY)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == [] and result["intentOperations"] == []
    assert decider.chats == 1


def test_a_yes_to_the_same_question_still_answers_it() -> None:
    decider = _Decider(ContextDecision("Abre Steam y entra a la biblioteca.", "action", ("app.open",), ""))

    result = _turn("sí, dale", decider, STEAM_HISTORY)

    assert result["kind"] == "action"
    assert result["operation"] == "app.open"


def test_praise_and_thanks_are_social_and_a_yes_is_not() -> None:
    for said in ("Perfecto muy bien", "Muy bien baxy", "gracias", "vale, perfecto", "excelente", "good job"):
        assert dialogue_slot.is_social(said), said
    for said in ("sí, dale", "perfecto, dale", "bien", "ok", "abre steam"):
        assert not dialogue_slot.is_social(said), said


# conv-v3g owner script t28–t29.
SAY_HISTORY = [
    ("user", "Obvio que no lo entendiste, porque tus detectores semanticos no funcionan de forma general"),
    ("assistant", "Entiendo tu frustración y me disculpo si mi respuesta anterior no fue la que esperabas."),
    ("user", "Dime algo"),
    ("assistant", "Puedo ayudarte con cualquier tema que te interese."),
]


def test_saying_a_word_types_nothing() -> None:
    decider = _Decider(ContextDecision("Escribe la palabra «algo».", "action", ("input.text.type",), ""))

    result = _turn('Di la palabra"algo"', decider, SAY_HISTORY)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []


def test_typing_asked_or_answered_is_still_typed() -> None:
    typed = ContextDecision("Escribe hola en el Bloc de notas.", "action", ("input.text.type",), "")
    assert _turn("escribí hola en el bloc de notas", _Decider(typed), SAY_HISTORY)["operation"] == "input.text.type"
    answered = [("user", "abrí el bloc de notas"), ("assistant", "¿Qué quieres que escriba en el Bloc de notas?")]
    assert _turn("hola mundo", _Decider(typed), answered)["operation"] == "input.text.type"
    deictic = [("user", "abrí el bloc de notas"), ("assistant", "Abrí el Bloc de notas.")]
    assert _turn("ponele hola", _Decider(typed), deictic)["operation"] == "input.text.type"
    assert not asks_to_type('Di la palabra"algo"', "Puedo ayudarte con cualquier tema que te interese.", "Dime algo")


# conv-v3g held-out t10.
NOTEPAD_HISTORY = [
    ("user", "abrí el bloc de notas"),
    ("assistant", "Abrí el Bloc de notas que ya estaba abierto."),
]


def test_the_pronoun_closes_what_was_just_opened_in_the_persons_verb_in_another_form() -> None:
    decider = _Decider(ContextDecision("Cierra el Bloc de notas.", "action", ("app.close",), ""))

    result = _turn("cerralo", decider, NOTEPAD_HISTORY)

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"
    assert result["objective"] == "Cierra el Bloc de notas."


def test_a_pointer_filled_with_an_object_nobody_said_is_still_asked() -> None:
    # Fase 3.5b M19 (cien-104): «ábreme eso porfa» after the time → «Abre el navegador».
    assert not dialogue_slot.restatement_was_said("Abre el navegador", ["ábreme eso porfa", "Son las 17:05."])
    assert not dialogue_slot.restatement_was_said("Cierra Discord", ["cerralo", *(c for _, c in NOTEPAD_HISTORY)])
    assert dialogue_slot.restatement_was_said("Cierra el Bloc de notas.", ["cerralo", *(c for _, c in NOTEPAD_HISTORY)])
    assert dialogue_slot.restatement_was_said("Vuelve a abrir el Bloc de notas", ["volvé a abrirlo", "abrí el bloc de notas"])


STEAM_OPENED = {
    "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"appId": "Steam", "displayName": "Steam", "alreadyRunning": True, "windowHandle": 3344132},
}


def test_an_open_that_reused_steam_is_not_told_as_opened_and_entered() -> None:
    user = "Perfecto muy bien"
    final = "He abierto Steam y he entrado en la biblioteca."
    assert llm.compose_visible_defect(final, "status", user, {"situation": STEAM_OPENED}) == "unstated_already_running"
    launched = {**STEAM_OPENED, "observed": {**STEAM_OPENED["observed"], "alreadyRunning": False}}
    assert llm.compose_visible_defect(final, "status", user, {"situation": launched}) == "extra_claim"
    assert llm.compose_visible_defect("Abrí Steam.", "status", user, {"situation": launched}) == ""
    assert llm.compose_visible_defect("Steam ya estaba abierto.", "status", user, {"situation": STEAM_OPENED}) == ""
