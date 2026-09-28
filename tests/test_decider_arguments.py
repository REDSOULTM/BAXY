"""Fase 3.5b M42 (D33): the decider returns the values the person gave, and the arguments step uses them."""

import json

from baxy_mind import __main__ as mind
from baxy_mind.semantic import decider


_FOLDER_SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string", "enum": ["documents", "downloads", "desktop"]},
        "query": {"type": "string", "minLength": 1, "maxLength": 200},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["folder", "query"],
    "additionalProperties": False,
}


def test_signature_names_fields_without_identifiers() -> None:
    schema = {
        "type": "object",
        "properties": {"windowId": {"type": "string"}, "appId": {"type": "string"}, "side": {"type": "string"}},
        "required": ["windowId", "side"],
    }
    assert decider.argument_signature(schema) == ("appId?", "side")


def test_prompt_with_signatures_asks_for_arguments() -> None:
    tools = [("audio.volume", "Pone el volumen.")]
    plain = decider.catalog_prompt(tools)
    signed = decider.catalog_prompt(tools, {"audio.volume": ("level",)})
    assert "\"arguments\"" not in plain
    assert "- audio.volume(level):" in signed and "\"arguments\"" in signed
    schema = decider.response_schema(["audio.volume"], with_arguments=True)
    assert list(schema["properties"]) == ["request", "decision", "operations", "arguments", "question"]
    assert schema["required"] == list(schema["properties"])
    assert "arguments" not in decider.response_schema(["audio.volume"])["properties"]


def test_parse_reads_flat_and_per_operation_arguments() -> None:
    flat = decider.parse(
        json.dumps({"request": "Pon el volumen al 8", "decision": "action", "operations": ["audio.volume"],
                    "arguments": {"level": 8, "extra": {"nested": 1}}, "question": ""}),
        ["audio.volume"],
    )
    assert flat.arguments == (("level", 8),)
    keyed = decider.parse(
        json.dumps({"request": "Clima en Oviedo", "decision": "action", "operations": ["weather.current"],
                    "arguments": {"weather.current": {"location": "Oviedo"}}, "question": ""}),
        ["weather.current"],
    )
    assert keyed.arguments == (("location", "Oviedo"),)
    talk = decider.parse(
        json.dumps({"request": "Hola", "decision": "talk", "operations": [], "arguments": {"x": 1}, "question": ""}),
        ["weather.current"],
    )
    assert talk.arguments == ()


def test_decided_values_fill_only_what_is_grounded() -> None:
    request = "Busca en documentos el pdf del contrato del piso"
    mind._remember_decided_arguments(
        request, ("filesystem.known.search",),
        (("folder", "Documents"), ("query", "contrato del piso"), ("limit", "7"), ("resourceId", "r-1")),
    )
    merged = mind._with_decided_arguments("filesystem.known.search", request, {}, _FOLDER_SCHEMA, request)
    assert merged is not None
    assert merged.get("query") == "contrato del piso"
    assert "resourceId" not in merged
    # «7» was never said: an invented optional value does not enter.
    assert "limit" not in merged
    # Another operation, or a request the decider did not restate, gets nothing.
    assert mind._with_decided_arguments("file.open", request, {}, _FOLDER_SCHEMA, request) is None
    assert mind._with_decided_arguments("filesystem.known.search", "otra cosa", {}, _FOLDER_SCHEMA, "otra cosa") is None


def test_decided_value_types() -> None:
    assert mind._decided_value("8", {"type": "integer"}) == 8
    assert mind._decided_value("ocho", {"type": "integer"}) is None
    assert mind._decided_value("UP", {"type": "string", "enum": ["up", "down"]}) == "up"
    assert mind._decided_value("  Horno   24 ", {"type": "string"}) == "Horno 24"


def test_grounding_source_is_what_was_said_in_the_conversation() -> None:
    history = [
        {"role": "user", "content": "busca el pdf del contrato en documentos"},
        {"role": "assistant", "content": "El dólar blue está a 1.215 pesos."},
        {"role": "user", "content": "anótalo"},
    ]
    source = mind._conversation_grounding_source("Anota el valor del dólar blue", history)
    assert "documentos" in source and "1.215" in source and source.startswith("Anota")
    assert mind._conversation_grounding_source("Abre el Calendario", None) == "Abre el Calendario"


def test_decided_arguments_alone_skip_extraction_only_when_complete() -> None:
    tool = {"function": {"canonical_name": "filesystem.known.search", "parameters": _FOLDER_SCHEMA}}
    request = "Busca el contrato del piso en la carpeta downloads"
    mind._remember_decided_arguments(
        request, ("filesystem.known.search",), (("folder", "downloads"), ("query", "contrato del piso")),
    )
    assert mind._decided_arguments_alone("filesystem.known.search", request, tool, request) == {
        "folder": "downloads", "query": "contrato del piso",
    }
    partial = "Busca el contrato"
    mind._remember_decided_arguments(partial, ("filesystem.known.search",), (("query", "contrato"),))
    assert mind._decided_arguments_alone("filesystem.known.search", partial, tool, partial) is None
