from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import traceback

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as sidecar


# Exact wire schemas of ProductCatalog.cs audio.volume/audio.volume.adjust.
SCHEMAS = {
    "audio.volume": {
        "type": "object",
        "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
        "required": ["level"],
        "additionalProperties": False,
    },
    "audio.volume.adjust": {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "minimum": 1, "maximum": 100},
            "direction": {"type": "string", "enum": ["down", "up"]},
        },
        "required": ["amount", "direction"],
        "additionalProperties": False,
    },
}

EXPLICIT = [
    pytest.param("audio.volume.adjust", "Baja nueve puntos el volumen que tenga ahora el equipo, sin ponerlo en silencio.", {"amount": 9, "direction": "down"}, id="858-T3"),
    pytest.param("audio.volume", "Deja la salida del equipo a veintisiete por ciento para escuchar esta explicación.", {"level": 27}, id="858-T5"),
    pytest.param("audio.volume", "Quiero el volumen del sistema justo a la mitad de su escala.", {"level": 50}, id="858-T7"),
    pytest.param("audio.volume", "Set the volume of the computer to eleven percent.", {"level": 11}, id="english-eleven"),
    pytest.param("audio.volume", "Subí el volumen al máximo.", {"level": 100}, id="maximum"),
    pytest.param("audio.volume.adjust", "Increase the volume by twelve points.", {"amount": 12, "direction": "up"}, id="english-relative"),
    pytest.param("audio.volume", "Pon el volumen al 27 por ciento.", {"level": 27}, id="numeric-absolute"),
    pytest.param("audio.volume.adjust", "Subí el volumen en 13 puntos.", {"amount": 13, "direction": "up"}, id="numeric-relative"),
]


@pytest.mark.parametrize("operation,text,expected", EXPLICIT)
def test_explicit_audio_survives_the_public_grounding_boundary(operation, text, expected):
    assert sidecar._ground_explicit_arguments(operation, text, SCHEMAS[operation]) == expected


@pytest.mark.parametrize("operation,text,expected", EXPLICIT)
def test_arguments_dispatch_returns_canonical_audio_without_model_extraction(
    monkeypatch, operation, text, expected,
):
    class FailIfCalledLlm:
        def start_warmup(self):
            pass

        def wait_warmup(self, _timeout):
            return True

        def begin_request(self, *_args, **_kwargs):
            pass

        def end_request(self):
            pass

        def extract_direct_arguments(self, *_args, **_kwargs):
            pytest.fail("closed explicit audio must not reach model extraction")

        def formulate_missing_argument_question(self, *_args, **_kwargs):
            pytest.fail("a grounded explicit audio quantity is not missing")

    # Only resource startup is inert. Catalog validation, request dispatch,
    # literal extraction, schema validation and the reply all run unchanged.
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "never-loaded.gguf")
    monkeypatch.setattr(sidecar, "LlmRuntime", FailIfCalledLlm)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", lambda: object())
    monkeypatch.setattr(sidecar, "TurnEvidenceService", lambda: SimpleNamespace(state="ready", start=lambda *_: None))
    # This two-operation catalog has no unrelated product skills to resolve.
    monkeypatch.setattr(
        sidecar.SkillRegistry, "load_default",
        lambda operations, encoder=None: sidecar.SkillRegistry([], operations, encoder),
    )
    def fail_dispatch_error(*_args):
        pytest.fail(traceback.format_exc())
    monkeypatch.setattr(sidecar, "technical_failure_message", fail_dispatch_error)
    lifecycle = SimpleNamespace(
        own_llm=lambda value: value,
        own_router=lambda value: value,
        own_turn_evidence=lambda value: value,
        own_planner_promotion=lambda _thread, stop: stop.set(),
    )
    pending = iter([
        {
            "type": "catalog.configure", "id": "catalog",
            "capabilities": [{
                "name": name, "argumentsSchema": schema,
                "risk": "low_reversible", "description": "Fixture audio operation",
            } for name, schema in SCHEMAS.items()],
        },
        {"type": "arguments", "id": "audio-request", "operation": operation, "text": text},
        None,
    ])
    replies = []
    assert sidecar._run_sidecar(
        lifecycle, read_message=lambda: next(pending), write_message=replies.append,
    ) == 0
    assert replies[1] == {"type": "catalog.ready", "id": "catalog", "count": 2}
    assert replies[2] == {
        "type": "arguments.result", "id": "audio-request", "operation": operation,
        "arguments": expected, "ok": True, "question": "",
    }


@pytest.mark.parametrize("operation,text", [
    ("audio.volume", "No pongas el volumen a la mitad."),
    ("audio.volume.adjust", "No subas el volumen en nueve puntos."),
    ("audio.volume", "Pon el volumen de Spotify al máximo."),
    ("audio.volume.adjust", "Sube el volumen de Spotify en nueve puntos."),
    ("audio.volume", "Set the volume of the app to eleven percent."),
    ("audio.volume", "Set the computer volume there."),
    ("audio.volume.adjust", "Subí un poco el volumen."),
    ("audio.volume.adjust", "Baja el volumen."),
    ("audio.volume", "Pon el volumen al 137 por ciento."),
    ("audio.volume.adjust", "Sube el volumen en 137 puntos."),
    ("audio.volume", "Pon el volumen a once o doce por ciento."),
    ("audio.volume.adjust", "Sube el volumen en nueve puntos y bájalo en cuatro."),
    ("audio.volume", "Pon el volumen al veintisiete por ciento para la llamada de las 5."),
    ("audio.volume.adjust", "Sube el volumen en nueve puntos para la llamada de las 5."),
    ("audio.volume", "Set the volume to twenty seven percent for the call at 5."),
    ("audio.volume.adjust", "Lower the volume by nine points for the call at 5."),
])
def test_public_explicit_grounding_keeps_denial_scope_and_quantity_guards(operation, text):
    assert sidecar._ground_explicit_arguments(operation, text, SCHEMAS[operation]) is None


@pytest.mark.parametrize("operation,text,expected", EXPLICIT[:3])
def test_canonical_audio_still_requires_the_received_catalog_schema(operation, text, expected):
    schema = deepcopy(SCHEMAS[operation])
    quantity = "level" if operation == "audio.volume" else "amount"
    schema["properties"][quantity]["maximum"] = expected[quantity] - 1
    assert sidecar._ground_explicit_arguments(operation, text, schema) is None


def test_audio_direction_still_requires_the_catalog_enum():
    schema = deepcopy(SCHEMAS["audio.volume.adjust"])
    schema["properties"]["direction"]["enum"] = ["up"]
    assert sidecar._ground_explicit_arguments(
        "audio.volume.adjust", "Baja nueve puntos el volumen.", schema,
    ) is None


def test_model_arguments_do_not_acquire_the_closed_parser_authority():
    schema = SCHEMAS["audio.volume"]
    assert sidecar.normalize_objective_arguments({"level": 27}, schema, "Set the volume.")[0] is None
    assert sidecar.normalize_objective_arguments({"level": 5}, schema, "Set the volume to eleven percent.")[0] is None


def test_explicit_audio_cannot_ignore_a_required_catalog_field():
    schema = deepcopy(SCHEMAS["audio.volume"])
    schema["properties"]["deviceId"] = {"type": "string"}
    schema["required"].append("deviceId")
    assert sidecar._ground_explicit_arguments("audio.volume", "Pon el volumen a la mitad.", schema) is None
