"""tanda-03 (2026-09-24, official window): output levels said as a target, a step or a comparative.

Three turns of the official window, none read by the level readers: a brightness put «en un N%» after
«pon» was asked which way to move it; a brightness lowered «un nivel» was asked «¿cuánto y en qué
dirección?», though the direction had been said; the screen asked to be made brighter ended in «No pude
entender bien la solicitud».

- «pon/deja/set/put» + «en un N», «a un N», «al N», «en N», «on N» put the level there (absolute).
- A step («un nivel», «a notch», «dos niveles») or «un poco» gives the direction and no amount: only the
  amount is asked (owner rule H0027), never the direction, and a step is never read as an amount of 1 or 2.
- Making the screen brighter or darker, or the sound louder or softer («haz la pantalla más clara», «make
  it louder») is the direction without an amount: the amount is asked.
- The model's own argument question, when it still has to ask, asks only for what was not said: the
  direction a level change states and a field with one allowed value are never asked again.

None of these phrases is a literal of the real window.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baxy_mind import __main__ as mind  # noqa: E402
from baxy_mind.llm import DirectArgumentExtraction, LlmRuntime  # noqa: E402
from baxy_mind.semantic import levels  # noqa: E402
from baxy_mind.semantic.patterns import (  # noqa: E402
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)

from test_semantic_levels import _SCHEMAS, AVAILABLE, _decided, _tool, _turn  # noqa: E402

_BRIGHTNESS = "system.settings.adjust"
_VOLUME = "audio.volume.adjust"

# ------------------------------------------------------------------ an absolute level acts


@pytest.mark.parametrize(
    ("text", "operation", "arguments"),
    [
        ("Pon el brillo del monitor en un 45%", "system.settings.set", {"setting": "brightness", "value": 45}),
        ("pon el brillo en un 60%", "system.settings.set", {"setting": "brightness", "value": 60}),
        ("deja el brillo en un 40 por ciento", "system.settings.set", {"setting": "brightness", "value": 40}),
        ("ponle el brillo a un 45 por ciento", "system.settings.set", {"setting": "brightness", "value": 45}),
        ("dejá el brillo en un 50", "system.settings.set", {"setting": "brightness", "value": 50}),
        ("coloca el brillo en 40", "system.settings.set", {"setting": "brightness", "value": 40}),
        ("ajusta el brillo a un 65%", "system.settings.set", {"setting": "brightness", "value": 65}),
        ("deja el brillo del monitor a 90", "system.settings.set", {"setting": "brightness", "value": 90}),
        ("set the brightness at 70%", "system.settings.set", {"setting": "brightness", "value": 70}),
        ("set the screen brightness to 35 percent", "system.settings.set", {"setting": "brightness", "value": 35}),
        ("put the display brightness on 20%", "system.settings.set", {"setting": "brightness", "value": 20}),
        ("deja la pantalla al 50%", "system.settings.set", {"setting": "brightness", "value": 50}),
        ("pon la pantalla en un 30%", "system.settings.set", {"setting": "brightness", "value": 30}),
        ("ajusta la pantalla al 75%", "system.settings.set", {"setting": "brightness", "value": 75}),
        ("ponme la pantalla al máximo", "system.settings.set", {"setting": "brightness", "value": 100}),
        ("deja el brillo al mínimo", "system.settings.set", {"setting": "brightness", "value": 0}),
        ("pon el volume en un 15%", "audio.volume", {"level": 15}),
        ("ponme el volumen en un 25", "audio.volume", {"level": 25}),
        ("deja el volumen a un 30%", "audio.volume", {"level": 30}),
        ("pon el sonido en un 10%", "audio.volume", {"level": 10}),
        ("pon el volumen del pc en 70", "audio.volume", {"level": 70}),
        ("set el volumen en 35", "audio.volume", {"level": 35}),
        ("put my volume at 15%", "audio.volume", {"level": 15}),
        ("put the volume at 45 percent", "audio.volume", {"level": 45}),
    ],
)
def test_a_level_put_somewhere_is_absolute_and_acts(text, operation, arguments):
    assert _decided(text) == ((operation,), arguments)


# ------------------------------------------------------------------ a direction without an amount asks the amount


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # a step of unsaid size
        ("bájale el brillo un nivel", _BRIGHTNESS),
        ("por favor bájale un nivel al brillo del monitor", _BRIGHTNESS),
        ("baja un nivel el brillo por favor", _BRIGHTNESS),
        ("lower the brightness one level", _BRIGHTNESS),
        ("baja el brillo dos niveles", _BRIGHTNESS),
        ("baja el brillo en tres pasos", _BRIGHTNESS),
        ("turn the brightness down two notches", _BRIGHTNESS),
        ("turn up the brightness a notch", _BRIGHTNESS),
        ("súbele el volumen un nivel", _VOLUME),
        ("sube un nivel el volumen", _VOLUME),
        ("sube el volumen en dos niveles", _VOLUME),
        ("sube el volumen en 2 niveles", _VOLUME),
        ("súbele un par de niveles al volumen", _VOLUME),
        ("bájale una rayita al volumen", _VOLUME),
        ("turn the volume down a notch", _VOLUME),
        ("bring the volume down a notch", _VOLUME),
        ("knock the volume down a notch", _VOLUME),
        ("raise the volume a step", _VOLUME),
        ("turn the volume up by two notches", _VOLUME),
        # a small amount, the object after the particle
        ("dial the brightness up a little", _BRIGHTNESS),
        ("turn my screen brightness down a bit", _BRIGHTNESS),
        # the screen made brighter or darker
        ("ponme la pantalla más clara", _BRIGHTNESS),
        ("haz la pantalla más oscura", _BRIGHTNESS),
        ("pon la pantalla más brillante", _BRIGHTNESS),
        ("deja la pantalla un poco más oscura", _BRIGHTNESS),
        ("hazme la pantalla más brillante porfa", _BRIGHTNESS),
        ("quiero la pantalla más brillante", _BRIGHTNESS),
        ("la pantalla un poquito más oscura porfa", _BRIGHTNESS),
        ("la pantalla más tenue", _BRIGHTNESS),
        ("pantalla mas brillante please", _BRIGHTNESS),
        ("make the screen brighter", _BRIGHTNESS),
        ("make the display darker please", _BRIGHTNESS),
        ("make my screen a little brighter", _BRIGHTNESS),
        ("I want the screen brighter", _BRIGHTNESS),
        ("screen darker please", _BRIGHTNESS),
        ("make it brighter", _BRIGHTNESS),
        ("brighter please", _BRIGHTNESS),
        ("un poco más brillante", _BRIGHTNESS),
        ("más oscuro", _BRIGHTNESS),
        ("pon el brillo más alto", _BRIGHTNESS),
        ("haz el brillo más bajo", _BRIGHTNESS),
        ("darken the screen a bit", _BRIGHTNESS),
        ("aclara la pantalla", _BRIGHTNESS),
        ("oscurece la pantalla", _BRIGHTNESS),
        # the sound made louder or softer
        ("make the volume louder", _VOLUME),
        ("make the music louder please", _VOLUME),
        ("make the sound quieter", _VOLUME),
        ("make it louder", _VOLUME),
        ("hazlo más bajito", _VOLUME),
        ("ponlo más fuerte", _VOLUME),
        ("déjalo más bajo", _VOLUME),
        ("pon el volumen más alto", _VOLUME),
        ("quiero el volumen más bajito", _VOLUME),
        ("haz que suene más fuerte", _VOLUME),
    ],
)
def test_a_direction_without_an_amount_asks_only_the_amount(text, operation):
    assert resolve_explicit_effects(text, AVAILABLE) is None, text
    asked = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert asked is not None, text
    assert asked.operations == (operation,), text
    assert asked.missing_fields == ("amount",), text


@pytest.mark.parametrize(
    ("text", "setting", "direction"),
    [
        ("make it brighter", levels.BRIGHTNESS, "up"),
        ("oscurece la pantalla", levels.BRIGHTNESS, "down"),
        ("aclara la pantalla", levels.BRIGHTNESS, "up"),
        ("haz que suene más fuerte", levels.VOLUME, "up"),
        ("bájale el brillo un nivel", levels.BRIGHTNESS, "down"),
    ],
)
def test_the_level_read_keeps_the_object_and_the_direction_said(text, setting, direction):
    level = levels.read(text)
    assert level is not None and (level.setting, level.direction, level.amount, level.target) == (
        setting, direction, None, None,
    )
    assert levels.direction_of(text) == direction


@pytest.mark.parametrize(
    "text",
    [
        "baja la pantalla",
        "pon la pantalla",
        "baja la pantalla un poco",
        "pon la pantalla 2",
        "pon la pantalla completa",
        "cambia a la pantalla 2",
        "sube a la pantalla de inicio",
        "haz la letra más grande",
        "make the font bigger",
        "habla más claro",
        "pon algo más fuerte",
        "pon algo más alegre",
        "quiero la pantalla limpia",
        "el brillo más alto al 50",
        "make it brighter to 80",
        "pon el volumen más brillante",
        "make the screen louder",
    ],
)
def test_other_requests_with_the_same_words_are_not_an_output_level(text):
    assert levels.read(text) is None, text


# ------------------------------------------------------------------ the whole turn


def test_an_absolute_brightness_after_pon_acts_in_the_whole_turn():
    result, runtime = _turn("Pon el brillo del monitor en un 45%")
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["system.settings.set"]
    assert runtime.questions == []


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("por favor bájale un nivel al brillo del monitor", _BRIGHTNESS),
        ("hazme la pantalla más brillante porfa", _BRIGHTNESS),
        ("make it louder", _VOLUME),
    ],
)
def test_a_direction_without_amount_asks_only_the_amount_in_the_whole_turn(text, operation):
    result, runtime = _turn(text)
    assert result["kind"] == "clarify"
    assert runtime.questions == [(text, (operation,), ("amount",))]


# ------------------------------------------------------------------ the model's question asks only what is missing


@pytest.mark.parametrize(
    ("operation", "text", "stated"),
    [
        (_BRIGHTNESS, "bájale al brillo lo que te parezca", ("direction", "setting")),
        (_BRIGHTNESS, "cambia el brillo como veas", ("setting",)),
        (_VOLUME, "súbele un montón al volumen", ("direction",)),
        (_VOLUME, "ajusta el volumen", ()),
    ],
)
def test_the_fields_a_request_already_settles_are_never_asked(operation, text, stated):
    assert mind._stated_argument_fields(operation, text, _SCHEMAS[operation]) == stated


class _AbstainingExtraction:
    def __init__(self) -> None:
        self.stated: list[tuple[str, ...]] = []

    def extract_direct_arguments(self, _objective: str, _tool: dict, *, stated_fields=()) -> DirectArgumentExtraction:
        self.stated.append(tuple(stated_fields))
        return DirectArgumentExtraction(None, (), "¿Cuánto?")


def test_the_grounding_gate_tells_the_extraction_what_was_already_said():
    llm = _AbstainingExtraction()
    decision = {
        "mode": "action", "operation": _BRIGHTNESS, "question": "", "conversation_kind": "",
        "effect_count": "one", "effect_operations": [_BRIGHTNESS], "effect_verification": "grounding_required",
    }
    clarified = mind.apply_turn_action_grounding_gate(
        decision, "bájale al brillo lo que te parezca", {_BRIGHTNESS: _tool(_BRIGHTNESS)}, llm,
    )
    assert clarified["mode"] == "clarify"
    assert llm.stated == [("direction", "setting")]


def _extraction_runtime() -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"grounded": False, "arguments": None, "fallback_question": "¿Cuánto lo bajo?"},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
    )
    return runtime


def test_the_extraction_asks_only_for_the_fields_not_said():
    runtime = _extraction_runtime()
    extraction = runtime.extract_direct_arguments(
        "bájale al brillo lo que te parezca", _tool(_BRIGHTNESS), stated_fields=("direction", "setting"),
    )
    assert extraction.arguments is None
    assert extraction.fallback_question == "¿Cuánto lo bajo?"
    prompt = runtime._post.call_args.args[0]["messages"][0]["content"]
    asked = prompt.split("obtener estos campos: ", 1)[1]
    assert '["amount"]' in asked
    assert "direction" not in asked and "setting" not in asked
    # The arguments themselves are still the whole schema.
    schema = runtime._post.call_args.args[0]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["arguments"]["anyOf"][0]["required"] == ["amount", "direction", "setting"]


def test_without_stated_fields_the_extraction_still_asks_for_every_required_field():
    runtime = _extraction_runtime()
    runtime.extract_direct_arguments("cambia el brillo", _tool(_BRIGHTNESS))
    prompt = runtime._post.call_args.args[0]["messages"][0]["content"]
    assert '["amount","direction","setting"]' in prompt.split("obtener estos campos: ", 1)[1]
