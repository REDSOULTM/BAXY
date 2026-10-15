"""Estabilización M3 (2026-10-12): olvidar un recuerdo cuya clave tiene varias palabras.

Evidencia: ``cu-v3/estab/I_identidad_notebook_4.md`` e ``I_evidencia4/conversacion.txt`` (Release 9b7d8d757), 2 de 2:
con «color favorito de prueba: turquesa» guardado, «Olvidá mi color favorito de prueba» → «¿Qué alcance deseas
eliminar de tus memorias locales: todo, exacto, tipo o tema?», y «No, cancelá» → «No pude contarte cómo salió lo que
pediste.». «Olvidá mi color favorito» sí pedía confirmación.
1. El lector de «olvidar X» lee X de cualquier largo con el nombre con que se guardó (el App lo resuelve contra las
   claves guardadas: EstabM3OlvidarTests.cs).
2. Ningún argumento interno de la operación (el alcance) llega a una aclaración (data clarification_fields.v1.json).
3. «No, cancelá» a una pregunta pendiente la cancela por el suelo (data clarificationCancelled).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import compose_payload, operation_floor
from baxy_mind.argument_payload import internal_fields, person_askable_fields
from baxy_mind.llm_clarify import ClarifyMixin
from baxy_mind.semantic.memory import explicit_memory_request, memory_request

ROOT = Path(__file__).resolve().parents[1]
_FIELDS = json.loads((ROOT / "src/baxy_mind/data/clarification_fields.v1.json").read_text(encoding="utf-8"))
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
                                             "description": name, "parameters": schema}}


# ------------------------------------------------------------------ 1. el dato de varias palabras se lee entero

@pytest.mark.parametrize(("said", "selector"), [
    ("Olvidá mi color favorito de prueba", "color_favorito_de_prueba"),
    ("olvidate de mi color favorito de prueba", "color_favorito_de_prueba"),
    ("Borra de tu memoria mi color favorito de prueba", "color_favorito_de_prueba"),
    ("forget my favourite test colour", "favourite_test_colour"),
    # The two-word datum the memory knows by name keeps its stored name.
    ("Olvidá mi color favorito", "favorite_color"),
])
def test_a_datum_of_any_length_is_read_with_the_name_it_was_saved_with(said: str, selector: str) -> None:
    assert memory_request(said) == ("memory.forget", {"version": 1, "scope": "exact", "selector": selector,
                                                      "confirmationRequired": True}), said
    assert explicit_memory_request(said)


def test_the_forget_names_the_datum_as_the_save_named_it() -> None:
    saved = memory_request("Recordá que mi color favorito de prueba es el turquesa")
    forgotten = memory_request("Olvidá mi color favorito de prueba")
    assert saved is not None and forgotten is not None
    assert saved[1]["selector"] == forgotten[1]["selector"] == "color_favorito_de_prueba"


@pytest.mark.parametrize("said", [
    # Contracases: nothing of the person's named, a moment, a thing of the PC, the person's own forgetting.
    "olvida eso",
    "forget it",
    "olvida todo",
    "olvidá mi reunión de mañana",
    "borrá mi color favorito de prueba",
    "olvidé mi color favorito de prueba",
])
def test_contracase_what_names_no_kept_datum_is_not_a_forget(said: str) -> None:
    read = memory_request(said)
    assert read is None or read[0] != "memory.forget", said


# ------------------------------------------------------------------ 2. ningún argumento interno se pregunta

def test_the_scope_of_a_forget_is_never_asked() -> None:
    assert "scope" in internal_fields("memory.forget")
    assert person_askable_fields(("scope", "selector"), _FORGET_SCHEMA, "memory.forget") == ("selector",)
    assert person_askable_fields(("confirmationRequired", "scope", "version"), _FORGET_SCHEMA, "memory.forget") == ()


def test_contracase_a_closed_value_the_person_says_is_still_asked() -> None:
    schema = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
              "required": ["kind"]}
    assert person_askable_fields(("kind",), schema, "notification.schedule") == ("kind",)
    # The same name internal to another operation (memory.save «kind») does not leave this one.
    assert "kind" in internal_fields("memory.save") and "kind" not in internal_fields("notification.schedule")


class _Clarifier(ClarifyMixin):
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload, _what):
        self.payloads.append(payload)
        fields = payload["response_format"]["json_schema"]["schema"]["properties"]["requested_fields"]["items"]["enum"]
        return {"requested_fields": list(fields), "question": "¿Qué dato quieres que olvide?"}


def _closed(values: list[str]) -> dict:
    return {"type": "string", "enum": values}


@pytest.mark.parametrize(
    ("operation", "field"),
    [(operation, field) for operation, fields in sorted(_FIELDS["internal"].items()) for field in fields],
)
def test_no_internal_argument_of_the_catalog_reaches_a_question(operation: str, field: str) -> None:
    # Every closed-value argument the data calls internal (the C# test ties the data to the real catalog), asked alone
    # and beside a value the person says: the question never receives it, nor its values.
    schema = {"type": "object", "properties": {field: _closed(["a", "b"]), "label": {"type": "string"}},
              "required": [field, "label"]}
    alone = _Clarifier()
    question = alone.formulate_missing_argument_question("hacelo", "", _tool(operation, schema), (field,))
    assert question == operation_floor.floor_data()["compositionFailures"]["clarification"]["es"]
    assert alone.payloads == []
    beside = _Clarifier()
    beside.formulate_missing_argument_question("hacelo", "", _tool(operation, schema), (field, "label"))
    context = json.loads(beside.payloads[0]["messages"][-1]["content"])
    assert [missing["field"] for missing in context["missing_arguments"]] == ["label"]
    assert f'"{field}"' not in json.dumps(beside.payloads[0], ensure_ascii=False)


def test_the_live_forget_is_asked_only_what_the_person_can_say() -> None:
    clarifier = _Clarifier()
    question = clarifier.formulate_missing_argument_question(
        "Olvidá mi color favorito de prueba", "", _tool("memory.forget", _FORGET_SCHEMA), ("scope", "selector"),
    )
    sent = json.dumps(clarifier.payloads[0], ensure_ascii=False)
    assert question == "¿Qué dato quieres que olvide?"
    assert '"scope"' not in sent and '"topic"' not in sent and '"exact"' not in sent


@pytest.mark.parametrize(("missing", "said"), [
    ("scope, selector", "selector"),
    # The App leaves out what the contract fixes (MainWindowViewModel.FixedByContract); the scope alone names nothing.
    ("scope", None),
])
def test_the_shell_named_fields_lose_the_internal_ones(missing: str, said: str | None) -> None:
    situation = {"kind": "clarification", "polarity": "pending", "missingValue": missing, "operation": "memory.forget"}
    assert compose_payload._required_compose_input(situation) == said


def test_contracase_without_an_operation_the_shell_named_fields_are_kept() -> None:
    situation = {"kind": "clarification", "polarity": "pending", "missingValue": "scope, selector"}
    assert compose_payload._required_compose_input(situation) == "scope, selector"


# ------------------------------------------------------------------ 3. «No, cancelá» a una pregunta pendiente

@pytest.mark.parametrize(("english", "said"), [
    (False, "Vale, lo dejo: no hice nada."),
    (True, "OK, I'll leave it: I didn't do anything."),
])
def test_a_cancelled_question_is_said_by_the_floor(english: bool, said: str) -> None:
    situation = {"kind": "status", "polarity": "success", "cause": "clarification_cancelled"}
    assert operation_floor.tells_first(situation)
    assert operation_floor.pending_final(situation, english) == said
    assert operation_floor.floor_final(situation, english) == said
    assert "No pude contarte" not in said


def test_contracase_a_cancelled_forget_keeps_its_own_sentence() -> None:
    situation = {"kind": "status", "polarity": "success", "cause": "memory_cancelled",
                 "cancelledAction": {"operation": "memory.forget", "scope": "exact", "selector": "favorite_color"}}
    assert operation_floor.pending_final(situation, False) == "No olvidé tu color favorito: lo cancelaste."
