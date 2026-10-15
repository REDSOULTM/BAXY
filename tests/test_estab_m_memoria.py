"""Estabilización M (2026-10-11): la memoria se guarda, se corrige y se cuenta como pasó.

Evidencia: comprobación en vivo de identidad en el notebook (``cu-v3/estab/I_identidad_notebook.md`` §3):
(c) «Recordá que mi color favorito de prueba es el turquesa» se preguntó de vuelta y no guardó nada;
(d) «Corrige ese recuerdo: …ahora es el verde» no corrió ninguna operación y, tras «Sí, estoy seguro», el final dijo
«Tu color favorito ahora es el verde.» (éxito inventado); (e) un «olvida todo» verificado terminó «No pude contarte cómo
salió lo que pediste.». Frases propias; ninguna es del banco.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind import operation_floor
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.memory import explicit_memory_request, memory_request
from baxy_mind import context_decision
from baxy_mind import direct_arguments

ROOT = Path(__file__).resolve().parents[1]


def _catalog_block(name: str) -> str:
    source = (ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs").read_text(encoding="utf-8")
    if name == "memory.save":
        start = source.index("private static OperationArgumentsSchema MemorySaveSchema(")
        return source[start:source.index("]);", start) + 3]
    start = source.index(f'"{name}"')
    return source[start:source.index("OperationRisks", start)]


def _declared(name: str) -> tuple[set[str], set[str]]:
    block = _catalog_block(name)
    declared = set(re.findall(r'(?:String|ScalarProperty|Boolean|Integer)\(\s*"([A-Za-z]+)"', block))
    declared |= {"tags"} if "\"tags\"" in block else set()
    declared |= {"version"} if "Version()" in block else set()
    required = set(re.findall(r'"([A-Za-z]+)"', block[block.rindex("["):]))
    return declared, required


# ------------------------------------------------------------------ 1. guardar: voseo, «-me», inglés, spanglish

@pytest.mark.parametrize(("said", "selector", "value"), [
    ("Recordá que mi color favorito de prueba es el turquesa", "color_favorito_de_prueba", "turquesa"),
    ("recordame que mi bebida favorita es el mate", "favorite_drink", "mate"),
    ("Acordate que mi color favorito es el azul", "favorite_color", "azul"),
    ("remember that my favorite color is teal", "favorite_color", "teal"),
    ("please remember that my name is Ana", "name", "Ana"),
    ("recordá que my favorite color es el verde", "favorite_color", "verde"),
    ("save in your memory that my birthday is May 5", "birthday", "May 5"),
])
def test_a_save_said_whole_is_the_save_with_its_datum(said: str, selector: str, value: str) -> None:
    read = memory_request(said)
    assert read is not None and read[0] == "memory.save", said
    arguments = read[1]
    assert (arguments["selector"], arguments["value"]) == (selector, value)
    assert arguments["retention"] == "persistent" and arguments["sensitivity"] == "normal"
    declared, required = _declared("memory.save")
    assert required <= set(arguments) <= declared
    assert explicit_memory_request(said)


def test_a_fact_with_no_named_datum_is_kept_whole() -> None:
    read = memory_request("recordá que prefiero el café sin azúcar")
    assert read is not None and read[0] == "memory.save"
    assert read[1]["value"] == "prefiero el café sin azúcar" and read[1]["kind"] == "preference"
    assert str(read[1]["selector"]).startswith("historical_fact_")
    # The same fact said twice is the same record (a save is idempotent by its selector).
    assert memory_request("Recordá que prefiero el café sin azúcar.") == read


@pytest.mark.parametrize("said", [
    # A reminder, a moment, a task, a save of «this» or of a file are not a datum to keep (revisión M H3/H4: clocks of
    # two digits, «18:30», spans said in words, «tengo que…»). A secret is judged by the App's filters (H2), see
    # MindShellEndToEndTests.AMindChosenSecretOrGrantIsNeverKept.
    "recordame que llame a mi mamá",
    "recordame que mañana tengo dentista",
    "recordá que mi turno es el martes a las 10",
    "recordá que mi turno es a las 10",
    "remember that my meeting is at 10",
    "recorda que mi clase es a las 18:30",
    "recuérdame que mi clase de inglés es los lunes a las 18",
    "acordate que mi reunión es en dos horas",
    "remember that my flight is in three hours",
    "acordate de que tengo que comprar pan",
    "acordate de que tengo que apagar la luz",
    "remember that I have to call the bank",
    "remember this",
    "save that file as informe.txt",
    "guardá el documento",
    "mi color favorito es azul",
    "abre la calculadora",
])
def test_what_is_not_a_save_said_whole_is_not_read(said: str) -> None:
    read = memory_request(said)
    assert read is None or read[0] != "memory.save", said


@pytest.mark.parametrize("said", [
    "recordá que mi turno es a las 10", "remember that my flight is in three hours",
    "acordate de que tengo que comprar pan", "recuérdame que mi clase de inglés es los lunes a las 18",
])
def test_a_moment_or_a_task_is_no_memory_even_for_the_decider(said: str) -> None:
    # The reminder readers take it, or it is asked: the decider's memory.save on it does not pass the gate.
    assert not explicit_memory_request(said)


# ------------------------------------------------------------------ 2. corregir

@pytest.mark.parametrize(("said", "selector", "value"), [
    ("cambiá mi color favorito a verde", "favorite_color", "verde"),
    ("Corrige ese recuerdo: mi color favorito ya no es el turquesa, ahora es el verde", "favorite_color", "verde"),
    ("Cambia en tu memoria mi color favorito a verde", "favorite_color", "verde"),
    ("actualizá lo que recordás de mi nombre: ahora es Ana", "name", "Ana"),
    ("update my favorite color to green", "favorite_color", "green"),
    ("change my name to Ana in your memory", "name", "Ana"),
    ("update mi color favorito to green", "favorite_color", "green"),
    ("cambiá en tu memoria mi color favorito de prueba a verde", "color_favorito_de_prueba", "verde"),
    ("cambiá en tu memoria mi nombre a Ana", "name", "Ana"),
    ("change my birthday to May 6", "birthday", "May 6"),
])
def test_a_correction_said_whole_corrects_the_selector_the_save_wrote(said: str, selector: str, value: str) -> None:
    read = memory_request(said)
    assert read is not None and read[0] == "memory.correct", said
    assert (read[1]["selector"], read[1]["value"]) == (selector, value)
    declared, required = _declared("memory.correct")
    assert required <= set(read[1]) <= declared
    assert explicit_memory_request(said), said


@pytest.mark.parametrize("said", [
    # Contracasos: a change of the PC or of something memory does not keep is never a memory correction.
    "cambia el volumen a 30",
    "cambia mi fondo de pantalla a azul",
    "actualiza Windows",
    "corrige el texto de la nota",
    "change my wallpaper to blue",
    # Revisión M H1: an order about a thing is no memory unless the memory is named; a second order never joins a value.
    "actualizá mi proyecto a la versión 2",
    "update my project to the latest version",
    "fix my project to build",
    "cambia mi proyecto a Python 3.12",
    "cambia mi proyecto a la carpeta Documentos",
    "cambia mi nombre a Ana, que es más corto",
    "cambiá mi color favorito a verde y borrá la carpeta Descargas",
    "change my favorite color to green and open Spotify",
    "recordá que mi color favorito es verde y abrí Spotify",
])
def test_a_change_of_anything_else_is_no_memory_correction(said: str) -> None:
    assert memory_request(said) is None, said
    if "memoria" not in said:
        assert not explicit_memory_request(said), said


# ------------------------------------------------------------------ 3. the turn: read before the decider, arguments

_TYPES = {"version": {"type": "integer", "minimum": 1, "maximum": 1}, "tags": {"type": "array", "items": {"type": "string"}},
          "value": {"type": ["string", "number", "boolean"]}, "expectedValue": {"type": ["string", "number", "boolean"]}}


def _schema(name: str) -> dict:
    declared, required = _declared(name)
    properties = {field: _TYPES.get(field, {"type": "string"}) for field in declared}
    return {"type": "object", "properties": properties, "required": sorted(required), "additionalProperties": False}


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "low", "parameters": _schema(name)}}


class _Talks:
    """The decider of a whole turn that reads the volume: the reader, not the model, decides a save or a correction."""

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


def _turn(text: str) -> tuple[dict, _Talks]:
    model = _Talks()
    volume = {"type": "function", "function": {"name": "audio_volume", "canonical_name": "audio.volume",
                                               "description": "audio.volume", "risk": "read_only",
                                               "parameters": {"type": "object", "properties": {}, "required": []}}}
    catalog = PlannerCatalog([_tool("memory.save"), _tool("memory.correct"), volume])
    result = context_decision._context_decided_result(
        {"id": "M", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=catalog,
    )
    return result, model


@pytest.mark.parametrize(("said", "operation"), [
    ("Recordá que mi color favorito de prueba es el turquesa", "memory.save"),
    ("cambiá mi color favorito a verde", "memory.correct"),
])
def test_the_reading_decides_the_turn_and_grounds_its_arguments(said: str, operation: str) -> None:
    result, model = _turn(said)
    assert result["kind"] == "action" and result["operation"] == operation
    assert model.decisions == 0
    arguments, question = direct_arguments._direct_arguments_result(
        {"type": "arguments", "operation": operation, "text": said, "history": []},
        llm=model, tool=_tool(operation), dialogue_state=DialogueState(),
    )
    assert question == "" and arguments == memory_request(said)[1]


@pytest.mark.parametrize("said", ["mi color favorito es el verde, ¿y el tuyo?", "cambia el volumen a 30"])
def test_what_the_reading_does_not_read_is_still_the_decider_s(said: str) -> None:
    result, model = _turn(said)
    assert model.decisions == 1 and not str(result.get("operation") or "").startswith("memory.")


# ------------------------------------------------------------------ 4. «sí, estoy seguro» is a yes

@pytest.mark.parametrize("said", ["Sí, estoy seguro", "sí, segura", "yes, I'm sure", "seguro"])
def test_being_sure_said_to_a_question_is_a_yes(said: str) -> None:
    assert dialogue.is_assent(said)
    assert dialogue.talk_act(said) is None
    assert dialogue.joined_answer("Corrige mi color favorito a verde", said) == "Corrige mi color favorito a verde"


@pytest.mark.parametrize("said", [
    "estoy seguro de que mañana llueve", "estoy cansado", "no estoy seguro",
    # Revisión M H6: a doubt is no yes.
    "¿Seguro?", "¿Estoy seguro?", "seguro?", "¿sí?",
])
def test_a_statement_about_oneself_or_a_doubt_is_no_yes(said: str) -> None:
    assert not dialogue.is_assent(said)


def test_every_word_of_the_one_yes_list_is_a_yes() -> None:
    # Revisión M H5: the same list confirms the kernel's challenges in the App (ConfirmationReplyParser), tested there
    # by MemoryOperationProtectionTests.EveryAssentWordConfirmsAndAQuestionDoesNot.
    words = json.loads((ROOT / "src/baxy_mind/data/assent_words.v1.json").read_text(encoding="utf-8"))["words"]
    for word in words:
        assert dialogue.is_assent(word) and dialogue.is_assent(f"sí, {word}."), word


# ------------------------------------------------------------------ 5. what the floor says of a memory result

def _status(operation: str, cause: str, observed: dict) -> dict:
    return {"kind": "status", "polarity": "success", "cause": cause, "operation": operation, "verified": True,
            "succeeded": True, "observed": observed}


@pytest.mark.parametrize("case_id", ["mem-forget-all", "mem-forget-one", "mem-correct"])
def test_the_mind_s_floor_says_what_the_twins_hold(case_id: str) -> None:
    # Revisión M H5: the same rows are the App's (ComputerUseFloorTests.TheAppsFloorSaysWhatTheFixtureHoldsForIt).
    twins = json.loads((ROOT / "tests/data/cu_floor_twins.json").read_text(encoding="utf-8"))
    row = next(case for case in twins["floorOnly"] if case["id"] == case_id)
    assert operation_floor.floor_final(row["situation"], False) == row["es"]
    assert operation_floor.floor_final(row["situation"], True) == row["en"]


def test_a_verified_forget_of_everything_is_said_never_the_composition_failure() -> None:
    # Rewritten by Estabilización M2 (live identity check 2026-10-11 §4: «Te olvidé el color favorito como pediste.»
    # after «Olvida todo…»): a memory result is said whole from data, short.
    situation = _status("memory.forget", "memory_deleted", {"deletedCount": 2, "scope": "all"})
    assert operation_floor.floor_final(situation, False) == "Listo, olvidé todo lo que recordaba de ti."
    assert operation_floor.floor_final(situation, True) == "Done, I forgot everything I remembered about you."
    one = _status("memory.forget", "memory_deleted", {"deletedCount": 1})
    assert operation_floor.floor_final(one, False) == "Listo, lo olvidé."
    corrected = _status("memory.correct", "memory_updated", {"saved": True, "corrected": True})
    assert operation_floor.floor_final(corrected, False) == "Listo, lo corregí."


def test_a_status_that_names_no_verified_operation_still_has_no_floor() -> None:
    assert operation_floor.floor_final({"kind": "status", "cause": "acting"}, False) == ""
    unverified = {**_status("memory.forget", "memory_deleted", {}), "verified": False}
    assert operation_floor.floor_final(unverified, False) == ""


@pytest.mark.parametrize(("code", "spanish"), [
    ("memory_none", "No tengo nada guardado sobre eso."),
    ("memory_forget_empty", "No tenía nada guardado que borrar."),
    ("memory_not_found", "No pude cambiarlo: no tengo ese dato guardado."),
])
def test_an_empty_memory_and_a_missing_datum_are_said_as_such(code: str, spanish: str) -> None:
    assert operation_floor.failure_sentences()[code][0] == spanish
