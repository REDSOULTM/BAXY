"""Estabilización M2 (2026-10-11): cinco defectos vistos en vivo al comprobar la identidad en el notebook.

Evidencia: ``cu-v3/estab/I_identidad_notebook_2.md`` y ``I_evidencia2/conversation.v1.jsonl`` (perfil identidad-prueba-2,
Release 4d9c38ac1). Frases reales de la conversación, con sus contracasos:
1. «Activa el modo bypass» → «No pude contarte cómo salió lo que pediste.» (el App rechazó la frase del suelo).
2. «Olvidá mi color favorito», «Borra de tu memoria mi color favorito» → «¿Qué confirmación, alcance y versión
   necesitas…?»: el paso de argumentos preguntó campos que el contrato fija.
3. «No, cancelá» a «¿confirmar o cancelar?» volvió a preguntar (sólo «cancelar» cancelaba).
4. «Estoy acordado de que tu color favorito es el verde.», «Te acordaré que…», «Te olvidé el color favorito…».
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import context_decision, deterministic_finals, direct_arguments, operation_floor
from baxy_mind.argument_payload import person_askable_fields
from baxy_mind.argument_grounding import prepare_direct_argument_result
from baxy_mind.planner import PlannerCatalog, fixed_arguments
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.memory import explicit_memory_request, memory_request

ROOT = Path(__file__).resolve().parents[1]

# memory.forget as ProductCatalog publishes it (ProductOperationSchema writes «const» for a constant boolean and the
# payload version is Integer("version", 1, 1)); MemoryForgetSchemaIsTheOneTheMindFixes (C#) ties it to the catalog.
_FORGET_SCHEMA = {
    "type": "object",
    "properties": {
        "confirmationRequired": {"type": "boolean", "const": True},
        "scope": {"type": "string", "enum": ["all", "exact", "kind", "topic"]},
        "selector": {"type": ["string", "null"]},
        "version": {"type": "integer", "minimum": 1, "maximum": 1},
    },
    "required": ["confirmationRequired", "scope", "selector", "version"],
    "additionalProperties": False,
}


def _tool(name: str, schema: dict) -> dict:
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "work_loss", "parameters": schema}}


# ------------------------------------------------------------------ 2. olvidar un dato dicho entero

@pytest.mark.parametrize(("said", "selector"), [
    ("Olvidá mi color favorito", "favorite_color"),
    ("Borra de tu memoria mi color favorito", "favorite_color"),
    ("borrá mi color favorito de tu memoria", "favorite_color"),
    ("olvidate de mi cumpleaños", "birthday"),
    ("olvidá lo del color favorito", "favorite_color"),
    ("forget my favorite color", "favorite_color"),
    ("delete my favorite drink from your memory", "favorite_drink"),
    ("olvidá que mi color favorito es el verde", "favorite_color"),
])
def test_a_forget_of_one_datum_is_read_whole(said: str, selector: str) -> None:
    read = memory_request(said)
    assert read == ("memory.forget", {"version": 1, "scope": "exact", "selector": selector,
                                      "confirmationRequired": True}), said
    assert explicit_memory_request(said)


@pytest.mark.parametrize("said", ["Olvidá todo lo que sabés de mí", "forget everything about me",
                                  "borra todos tus recuerdos de mí"])
def test_a_forget_of_everything_about_the_person_is_read_whole(said: str) -> None:
    assert memory_request(said) == ("memory.forget", {"version": 1, "scope": "all", "selector": None,
                                                      "confirmationRequired": True}), said


@pytest.mark.parametrize("said", [
    # Contracases: no datum the memory keeps by name, a thing of the PC erased, the person's own forgetting, a forget
    # of nothing named («olvida todo», «olvida eso»: the App asks which), a file.
    "olvidá mi reunión de mañana",
    "borrá mi cumpleaños",
    "borra la carpeta Descargas",
    "olvidé mi color favorito",
    "me olvidé de mi cumpleaños",
    "olvida todo",
    "olvida eso",
    "forget it",
])
def test_what_is_no_forget_of_a_kept_datum_is_not_read(said: str) -> None:
    read = memory_request(said)
    assert read is None or read[0] != "memory.forget", said


class _Talks:
    _native_tool_policy_enabled = False

    def __init__(self) -> None:
        self.decisions = 0

    def decide_in_context(self, text, *_a, **_k):
        self.decisions += 1
        return ContextDecision(text, "action", ("audio.volume",), "")

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


@pytest.mark.parametrize("said", ["Olvidá mi color favorito", "Borra de tu memoria mi color favorito"])
def test_the_live_forgets_decide_the_turn_with_their_arguments_and_ask_nothing(said: str) -> None:
    model = _Talks()
    volume = _tool("audio.volume", {"type": "object", "properties": {}, "required": []})
    catalog = PlannerCatalog([_tool("memory.forget", _FORGET_SCHEMA), volume])
    result = context_decision._context_decided_result(
        {"id": "M2", "text": said, "history": [{"role": "user", "content": said}]}, llm=model, planner_catalog=catalog,
    )
    assert result["kind"] == "action" and result["operation"] == "memory.forget" and model.decisions == 0
    arguments, question = direct_arguments._direct_arguments_result(
        {"type": "arguments", "operation": "memory.forget", "text": said, "history": []},
        llm=model, tool=_tool("memory.forget", _FORGET_SCHEMA), dialogue_state=DialogueState(),
    )
    assert question == "" and arguments == memory_request(said)[1]


# ------------------------------------------------------------------ 2b. lo que el contrato fija nunca se pregunta

def test_what_the_contract_fixes_is_filled_and_never_asked() -> None:
    assert fixed_arguments(_FORGET_SCHEMA) == {"confirmationRequired": True, "version": 1}
    assert person_askable_fields(("confirmationRequired", "scope", "version"), _FORGET_SCHEMA) == ("scope",)

    class _NeverAsks:
        def formulate_missing_argument_question(self, *_a, **_k):
            raise AssertionError("nothing is missing")

    # The model gave what the person said; the contract's own values are filled, nothing is asked.
    arguments, question = prepare_direct_argument_result(
        _NeverAsks(), "Olvidá mi color favorito", _tool("memory.forget", _FORGET_SCHEMA),
        {"scope": "exact", "selector": "favorite_color"},
        trusted_source="Olvidá mi color favorito favorite_color exact",
    )
    assert question == "" and arguments == {"scope": "exact", "selector": "favorite_color",
                                            "confirmationRequired": True, "version": 1}


def test_contracase_what_the_person_must_say_is_still_asked_and_only_that() -> None:
    asked: list[tuple[str, ...]] = []

    class _Asks:
        def formulate_missing_argument_question(self, _objective, _purpose, _tool, fields, **_k):
            asked.append(person_askable_fields(fields, _FORGET_SCHEMA))
            return "¿Qué quieres que olvide?"

    arguments, question = prepare_direct_argument_result(
        _Asks(), "olvidá eso", _tool("memory.forget", _FORGET_SCHEMA), {}, trusted_source="olvidá eso",
    )
    assert arguments is None and question == "¿Qué quieres que olvide?"
    assert asked and "version" not in asked[0] and "confirmationRequired" not in asked[0]
    # A field the person may say (a free value) keeps being askable: nothing but the contract's is left out.
    assert person_askable_fields(("scope", "selector"), _FORGET_SCHEMA) == ("scope", "selector")


# ------------------------------------------------------------------ 3. un no a una confirmación cancela

@pytest.mark.parametrize("said", ["No, cancelá", "no, dejalo", "cancelalo", "nah", "no thanks", "No, cancel",
                                  "no, cancelá eso", "cancelar"])
def test_a_no_in_any_form_is_a_refusal(said: str) -> None:
    assert dialogue.is_refusal(said), said


@pytest.mark.parametrize("said", ["no, mandalo igual", "no, cancelá la reunión del lunes y avisale a Ana",
                                  "no, en YouTube", "sí, dale"])
def test_contracase_a_no_that_says_something_else_is_no_bare_refusal(said: str) -> None:
    assert not dialogue.is_refusal(said), said


def test_every_word_of_the_one_no_list_is_a_refusal_and_never_a_yes() -> None:
    # The App's side is MemoryOperationProtectionTests.EveryDeclineWordCancelsAndAnOrderDoesNot.
    data = json.loads((ROOT / "src/baxy_mind/data/assent_words.v1.json").read_text(encoding="utf-8"))
    assert not set(data["declineWords"]) & set(data["words"])
    for word in data["declineWords"]:
        assert dialogue.is_refusal(word) and dialogue.is_refusal(f"no, {word}."), word
        assert not dialogue.is_assent(word), word


# ------------------------------------------------------------------ 4. el resultado de la memoria, dicho del suelo

def _status(operation: str, cause: str, observed: dict) -> dict:
    return {"kind": "status", "polarity": "success", "cause": cause, "operation": operation, "verified": True,
            "succeeded": True, "observed": observed}


@pytest.mark.parametrize(("operation", "observed", "spanish", "english"), [
    ("memory.save", {"saved": True, "remembered": "verde", "selector": "favorite_color"},
     "Listo, me acuerdo: tu color favorito es el verde.", "Done, I'll remember: your favorite color is verde."),
    ("memory.save", {"saved": True, "remembered": "3 de mayo", "selector": "birthday"},
     "Listo, me acuerdo: tu cumpleaños es el 3 de mayo.", "Done, I'll remember: your birthday is 3 de mayo."),
    ("memory.save", {"saved": True, "remembered": "mate", "selector": "favorite_drink"},
     "Listo, me acuerdo: tu bebida favorita es mate.", "Done, I'll remember: your favorite drink is mate."),
    ("memory.correct", {"saved": True, "corrected": True, "remembered": "azul", "selector": "favorite_color"},
     "Listo, me acuerdo: tu color favorito es el azul.", "Done, I'll remember: your favorite color is azul."),
    # A datum the floor has no words for, a fact kept whole: said short, never with its stored name.
    ("memory.save", {"saved": True, "remembered": "soy alérgico al maní", "selector": "historical_fact_0a1b2c3d4e5f6a7b"},
     "Listo, me acuerdo.", "Done, I'll remember that."),
    ("memory.forget", {"deletedCount": 1}, "Listo, lo olvidé.", "Done, I forgot it."),
    ("memory.forget", {"deletedCount": 3, "scope": "all"}, "Listo, olvidé todo lo que recordaba de ti.",
     "Done, I forgot everything I remembered about you."),
])
def test_a_memory_result_is_said_from_the_floor_never_drafted(
    operation: str, observed: dict, spanish: str, english: str,
) -> None:
    situation = _status(operation, "memory_deleted" if operation == "memory.forget" else "memory_updated", observed)
    assert operation_floor.tells_first(situation)
    assert operation_floor.floor_final(situation, False) == spanish
    assert operation_floor.floor_final(situation, True) == english


def test_contracase_a_memory_read_and_a_status_still_are_the_writer_s() -> None:
    listed = _status("memory.list", "memory_records", {"shown": 1, "total": 1, "records": []})
    assert not operation_floor.tells_first(listed)
    assert not operation_floor.tells_first({"kind": "status", "cause": "acting"})


def test_the_floor_s_memory_words_are_the_subjects_the_memory_knows() -> None:
    floor = operation_floor.floor_data()["operations"]
    subjects = json.loads((ROOT / "src/baxy_mind/data/memory_subjects.v1.json").read_text(encoding="utf-8"))
    for operation in ("memory.save", "memory.correct"):
        said = set(floor[operation]["told"]["values"]) - {""}
        assert said == set(subjects["selectors"]), operation
        assert said <= set(subjects["labels"]), operation


# ------------------------------------------------------------------ 1. «Activa el modo bypass» por chat

def test_bypass_asked_from_the_chat_is_told_first_and_short() -> None:
    refused = {"kind": "operation", "operation": "system.settings.set", "polarity": "failure", "status": "failed",
               "error": "confirmation_bypass_interface_only"}
    assert operation_floor.tells_first(refused)
    said = deterministic_finals._deterministic_final(refused, {}, "Activa el modo bypass", "es")
    assert said == "El modo bypass no lo enciendo desde el chat: se enciende en mi ventana, en el ajuste «confirmaciones»."


# ------------------------------------------------------------------ recomprobación 2026-10-12 (I_identidad_notebook_3)
# «Borra de tu memoria mi bebida favorita» → «¿Quieres confirmar que borro de mi memoria…?» → «nah» → «He borrado de tu
# memoria tu bebida favorita.» with nothing erased: the question and the cancellation are the floor's, never drafted.

def _asked(action: dict) -> dict:
    return {"kind": "confirmation", "polarity": "pending", "cause": "memory_forget_irreversible",
            "choices": ["confirmar", "confirm", "cancelar", "cancel"], "pendingAction": action}


def _cancelled(action: dict) -> dict:
    return {"kind": "status", "polarity": "success", "cause": "memory_cancelled", "cancelledAction": action}


@pytest.mark.parametrize(("action", "asked", "cancelled"), [
    ({"operation": "memory.forget", "scope": "exact", "selector": "favorite_drink"},
     "¿Quieres confirmar que olvide tu bebida favorita o cancelar?", "No olvidé tu bebida favorita: lo cancelaste."),
    ({"operation": "memory.forget", "scope": "exact", "selector": "birthday"},
     "¿Quieres confirmar que olvide tu cumpleaños o cancelar?", "No olvidé tu cumpleaños: lo cancelaste."),
    ({"operation": "memory.forget", "scope": "all"},
     "¿Quieres confirmar que olvide todo lo que sé de ti o cancelar?", "No olvidé nada: lo cancelaste."),
    ({"operation": "memory.forget", "scope": "exact", "selector": "perro"},
     "¿Quieres confirmar que olvide ese dato o cancelar?", "No olvidé ese dato: lo cancelaste."),
])
def test_a_forget_is_asked_and_its_cancellation_told_from_the_floor(action: dict, asked: str, cancelled: str) -> None:
    for situation, said in ((_asked(action), asked), (_cancelled(action), cancelled)):
        assert operation_floor.tells_first(situation)
        assert operation_floor.floor_final(situation, False) == said
        assert deterministic_finals._floor_first_final(situation, {}, "nah", "es") == said
    assert operation_floor.floor_final(_cancelled(action), True).startswith("I didn't forget")


def test_contracase_another_confirmation_or_cancellation_stays_as_it_was() -> None:
    enable = {"operation": "memory.enable", "target": "private local memory"}
    assert operation_floor.pending_final(_asked(enable), False) == ""
    assert operation_floor.pending_final(_cancelled(enable), False) == ""
    assert operation_floor.pending_final({"kind": "status", "cause": "acting"}, False) == ""
