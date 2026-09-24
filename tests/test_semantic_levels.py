"""Output levels said the way people say them (uso real 2026-09-23).

The volume and the brightness were read only as complete requests that named their object. The object left
out («súbele un poco», «bájale», «más bajito»), languages mixed («Volume más alto please», «sube el volume un
10»), a terse level («Brillo 20%») and the bare answer to «¿cuánto?» («un 10», «20», «a 40») reached no reader.
BAXY asked «¿a qué te refieres?», denied a capability it has, or took «a 40» after «bajá el brillo» as «40 less»
(brightness 100 → 60).

Owner rule (H0027): a relative change without an amount asks for the amount; an absolute level acts. The phrases
here are not the literals of the real window. They are other ways of saying the same things.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import levels
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects

AVAILABLE = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "audio.status", "audio.app.volume.adjust",
    "system.settings.adjust", "system.settings.set", "system.settings.status", "media.control",
    "media.play.query", "app.open", "system.time",
)

_SCHEMAS = {
    "audio.volume": {
        "type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
        "required": ["level"], "additionalProperties": False,
    },
    "audio.volume.adjust": {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "minimum": 1, "maximum": 100},
            "direction": {"type": "string", "enum": ["down", "up"]},
        },
        "required": ["amount", "direction"], "additionalProperties": False,
    },
    "system.settings.adjust": {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "minimum": 1, "maximum": 100},
            "direction": {"type": "string", "enum": ["down", "up"]},
            "setting": {"type": "string", "enum": ["brightness"]},
        },
        "required": ["amount", "direction", "setting"], "additionalProperties": False,
    },
    "system.settings.set": {
        "type": "object",
        "properties": {
            "setting": {"type": "string", "enum": ["airplane_mode", "brightness", "do_not_disturb", "night_light"]},
            "value": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["setting", "value"], "additionalProperties": False,
    },
    "audio.mute": {
        "type": "object", "properties": {"state": {"type": "boolean"}},
        "required": ["state"], "additionalProperties": False,
    },
}


def _history(*turns: str) -> list[dict[str, str]]:
    """User turns with BAXY's reply between them; the last turn is the current message."""

    history: list[dict[str, str]] = []
    for index, turn in enumerate(turns):
        if index:
            history.append({"role": "assistant", "content": "¿Cuánto?"})
        history.append({"role": "user", "content": turn})
    return history


def _decided(*turns: str) -> tuple[tuple[str, ...] | None, dict[str, object] | None]:
    """What the reading proves for the last turn, and the arguments the argument stage binds for it."""

    history = _history(*turns)
    text = turns[-1]
    previous = mind._previous_user_request(history, text)
    intent = resolve_explicit_effects(text, AVAILABLE, previous_user_text=previous)
    if intent is None or len(intent.operations) != 1:
        return (intent.operations if intent else None), None
    operation = intent.operations[0]
    arguments = mind._ground_explicit_arguments(operation, text, _SCHEMAS[operation], history=history)
    return intent.operations, arguments


# ------------------------------------------------------------------ a relative change without its amount asks it


@pytest.mark.parametrize(
    "text",
    [
        "súbele un poquito",
        "bájale",
        "bajale un toque porfa",
        "más bajito",
        "un poco más alto",
        "Volume más alto please",
        "más volumen",
        "ponle más volumen",
        "turn it up a bit",
        "turn it down please",
        "habla más bajito por favor",
        "sube el volume",
        "lower el volumen",
        "baja el volumen del altavoz",
        "I don't wanna hear it tan alto",
        "I don’t want to hear it so loud",
        "la música está demasiado fuerte",
        "no se escucha casi nada",
    ],
)
def test_a_volume_change_without_amount_asks_only_the_amount(text):
    assert resolve_explicit_effects(text, AVAILABLE) is None
    asked = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert asked is not None
    assert asked.operations == ("audio.volume.adjust",)
    assert asked.missing_fields == ("amount",)


@pytest.mark.parametrize(
    "text", ["bájale al brillo", "Reduce el brillo of the screen", "lower the screen brightness", "menos brillo"],
)
def test_a_brightness_change_without_amount_asks_only_the_amount(text):
    assert resolve_explicit_effects(text, AVAILABLE) is None
    asked = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert asked is not None
    assert asked.operations == ("system.settings.adjust",)
    assert asked.missing_fields == ("amount",)


def test_a_level_without_object_after_a_brightness_request_asks_the_brightness_amount():
    asked = resolve_explicit_clarification_intent("bájale", AVAILABLE, previous_user_text="¿qué brillo tengo?")
    assert asked is not None and asked.operations == ("system.settings.adjust",)
    asked = resolve_explicit_clarification_intent("bájale", AVAILABLE, previous_user_text="pon música tranquila")
    assert asked is not None and asked.operations == ("audio.volume.adjust",)


# ------------------------------------------------------------------ an amount or a target said with the request acts


@pytest.mark.parametrize(
    ("text", "operation", "arguments"),
    [
        ("baja unos veinte por ciento", "audio.volume.adjust", {"amount": 20, "direction": "down"}),
        ("súbele 15", "audio.volume.adjust", {"amount": 15, "direction": "up"}),
        ("sube el volume un 10", "audio.volume.adjust", {"amount": 10, "direction": "up"}),
        ("decrease thirty percent", "audio.volume.adjust", {"amount": 30, "direction": "down"}),
        ("bájale 5 al volumen", "audio.volume.adjust", {"amount": 5, "direction": "down"}),
        ("turn up el volumen by 25", "audio.volume.adjust", {"amount": 25, "direction": "up"}),
        ("volumen 35", "audio.volume", {"level": 35}),
        ("Volume al 60%", "audio.volume", {"level": 60}),
        ("súbele al máximo", "audio.volume", {"level": 100}),
        ("Brillo 30%", "system.settings.set", {"setting": "brightness", "value": 30}),
        ("brightness al 70", "system.settings.set", {"setting": "brightness", "value": 70}),
        ("lower el brillo by 15", "system.settings.adjust", {"amount": 15, "direction": "down", "setting": "brightness"}),
    ],
)
def test_an_elliptical_or_mixed_level_with_its_quantity_acts(text, operation, arguments):
    assert _decided(text) == ((operation,), arguments)


# ------------------------------------------------------------------ the answer to «¿cuánto?» completes the request


@pytest.mark.parametrize(
    ("turns", "operation", "arguments"),
    [
        (("súbele un poquito", "un 15"), "audio.volume.adjust", {"amount": 15, "direction": "up"}),
        (("más bajito", "10"), "audio.volume.adjust", {"amount": 10, "direction": "down"}),
        (("bájale", "treinta"), "audio.volume.adjust", {"amount": 30, "direction": "down"}),
        (("sube el volumen", "en 5%"), "audio.volume.adjust", {"amount": 5, "direction": "up"}),
        (("sube el volumen", "a 30"), "audio.volume", {"level": 30}),
        (("Volume más alto please", "al máximo"), "audio.volume", {"level": 100}),
        (("baja el brillo", "25"), "system.settings.adjust", {"amount": 25, "direction": "down", "setting": "brightness"}),
        (("¿qué brillo tengo?", "bájale", "un 10"), "system.settings.adjust",
         {"amount": 10, "direction": "down", "setting": "brightness"}),
    ],
)
def test_the_answer_to_how_much_completes_the_pending_request(turns, operation, arguments):
    assert _decided(*turns) == ((operation,), arguments)


@pytest.mark.parametrize("answer", ["a 40", "al 40", "hasta el 40", "to 40%"])
def test_a_level_answered_after_a_relative_brightness_request_is_where_it_ends_not_how_much_it_moves(answer):
    # uso real 2026-09-23: «bájale el brillo a la pantalla» → «a 40» took the brightness from 100 to 60.
    assert _decided("bájale el brillo al monitor", answer) == (
        ("system.settings.set",), {"setting": "brightness", "value": 40},
    )


def test_a_bare_number_answered_after_a_relative_request_is_how_much_it_moves():
    assert _decided("bájale el brillo al monitor", "40%") == (
        ("system.settings.adjust",), {"amount": 40, "direction": "down", "setting": "brightness"},
    )


def test_a_pronoun_level_takes_the_object_of_the_request_before_the_answer():
    # «súbelo a 80» after «bajá el brillo» → «a 40» is the brightness, not a question about what to raise.
    assert _decided("baja el brillo de la pantalla", "a 40", "súbelo a 80") == (
        ("system.settings.set",), {"setting": "brightness", "value": 80},
    )
    assert _decided("pon música de los ochenta", "súbelo a 70") == (("audio.volume",), {"level": 70})


def test_a_setting_pronoun_needs_a_level_request_before_it():
    # «ponlo al 50» says neither what nor which way: it is the level of the request before it, or nothing.
    assert _decided("sube el volumen", "ponlo al 50") == (("audio.volume",), {"level": 50})
    assert _decided("¿cuánto brillo tengo?", "déjalo al 50") == (
        ("system.settings.set",), {"setting": "brightness", "value": 50},
    )
    assert resolve_explicit_effects(
        "ponlo al 50", AVAILABLE, previous_user_text="abre la calculadora",
    ) is None


@pytest.mark.parametrize(
    "turns",
    [
        ("abre spotify", "20"),
        ("pon el brillo a 40", "20"),
        ("baja el brillo", "a 40", "30"),
        ("baja el brillo", "20 notas"),
        ("baja el brillo", "no, mejor nada"),
    ],
)
def test_a_number_completes_only_the_relative_request_right_before_it(turns):
    history = _history(*turns)
    previous = mind._previous_user_request(history, turns[-1])
    intent = resolve_explicit_effects(turns[-1], AVAILABLE, previous_user_text=previous)
    assert intent is None or not {"system.settings.adjust", "system.settings.set", "audio.volume.adjust"} & set(
        intent.operations,
    )


# ------------------------------------------------------------------ what is not an output level


@pytest.mark.parametrize(
    "text",
    [
        "baja",
        "súbelo",
        "súbelo a drive",
        "sube a la azotea",
        "baja las luces",
        "pon música",
        "quiero escucharla muy fuerte",
        "el edificio es muy alto",
        "¿por qué suena tan alto?",
        "no está muy alto",
        "no bajes el volumen",
        "baja el volumen de spotify",
        "súbele el volumen a la tele",
        "ponlo a las 5",
        "baja el volumen 200",
    ],
)
def test_other_requests_are_not_read_as_an_output_level(text):
    assert levels.read(text) is None
    assert levels.answer(text) is None


# ------------------------------------------------------------------ the mute said as a switch, the sound asked back


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("vuelve el sonido", False),
        ("regresa el audio", False),
        ("Turn off silenciar", False),
        ("switch off the mute", False),
        ("desactiva el modo silencio", False),
        ("apagá el mute porfa", False),
        ("activa el silencio", True),
        ("turn on mute", True),
        ("¡para ese ruido horrible!", True),
        ("stop that noise", True),
        ("silencio por favor", True),
    ],
)
def test_the_mute_switched_and_a_noise_stopped_are_the_global_mute(text, state):
    assert _decided(text) == (("audio.mute",), {"state": state})


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("vuelve a abrir spotify", "app.open"),
        ("para la música", "media.control"),
        ("apaga la música", "media.control"),
    ],
)
def test_other_orders_with_the_same_verbs_keep_their_own_operation(text, operation):
    intent = resolve_explicit_effects(text, AVAILABLE)
    assert intent is not None and intent.operations == (operation,)


# ------------------------------------------------------------------ the whole turn


class _NoEvidence:
    @staticmethod
    def candidate_families(*_args: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": _SCHEMAS.get(operation, {"type": "object", "properties": {}, "required": []}),
        },
    }


class _Runtime:
    """A model that must not be asked: the readers already know the turn."""

    def __init__(self) -> None:
        self.questions: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        pytest.fail("the output level is already proved; the model must not decide it")

    def rewrite_in_context(self, *_args: object, **_kwargs: object) -> str:
        pytest.fail("the output level is completed by the readers, not rewritten by the model")

    def formulate_explicit_clarification_question(
        self, objective: str, operations: tuple[str, ...], missing_fields: tuple[str, ...],
    ) -> str:
        self.questions.append((objective, operations, missing_fields))
        return "¿Cuánto?"


def _turn(*turns: str, pending: str | None = None) -> tuple[dict[str, object], _Runtime]:
    names = ("audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.adjust", "system.settings.set")
    tools = [_tool(name) for name in names]
    runtime = _Runtime()
    message: dict[str, object] = {"id": "levels", "text": turns[-1], "history": _history(*turns)}
    if pending is not None:
        message["pendingObjective"] = pending
    result = mind._prepare_turn_result(
        message, llm=runtime, planner_catalog=PlannerCatalog(tools), turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (), tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )
    return result, runtime


def test_the_answer_after_a_brightness_question_sets_the_level_in_the_whole_turn():
    result, _ = _turn("bájale el brillo a la pantalla", "a 40", pending="bájale el brillo a la pantalla")
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["system.settings.set"]


def test_the_answer_after_an_elliptical_volume_question_adjusts_the_volume_in_the_whole_turn():
    result, _ = _turn("ponme algo tranquilo", "súbele un poco", "un 10", pending="súbele un poco")
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["audio.volume.adjust"]


def test_a_pronoun_level_after_a_brightness_exchange_sets_the_brightness_in_the_whole_turn():
    result, _ = _turn("bájale el brillo a la pantalla", "a 40", "súbelo a 80")
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["system.settings.set"]


def test_an_elliptical_volume_request_asks_the_amount_in_the_whole_turn():
    result, runtime = _turn("ponme algo tranquilo", "bájale")
    assert result["kind"] == "clarify"
    assert runtime.questions == [("bájale", ("audio.volume.adjust",), ("amount",))]
