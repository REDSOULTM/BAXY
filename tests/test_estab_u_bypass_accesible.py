"""Estabilización U (identity live check, 2026-10-11): BAXY's own settings asked by chat.

«Activa el modo bypass» and «Activa el modo accesible para personas no videntes» went to computer use on BAXY's own
window, which is protected, and the second final said «la ventana protegida era un editor de código»: the cause datum
listed «un editor de código, una consola o BAXY» and the writer picked one. Now both are BAXY's own settings on
``system.settings.set`` (the accessible mode switched both ways; bypass only switched off from the chat, its switching
on refused by the handler with its cause), and a protected window is said by the name it showed.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent, operation_floor
from baxy_mind import cu_projection
from baxy_mind import cu_finals
from baxy_mind import deterministic_finals
from baxy_mind import compose_situation
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments as semantic_arguments
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind import turn_decide

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
SET = "system.settings.set"


@pytest.mark.parametrize(
    ("text", "switched"),
    [
        ("Activa el modo accesible para personas no videntes", ("accessible_mode", 1)),
        ("activá el modo accesible", ("accessible_mode", 1)),
        ("desactiva el modo de accesibilidad", ("accessible_mode", 0)),
        ("turn on accessible mode please", ("accessible_mode", 1)),
        ("switch off accessibility mode", ("accessible_mode", 0)),
        ("ponme el modo no vidente", ("accessible_mode", 1)),
        ("Activa el modo bypass", ("confirmation_bypass", 1)),
        ("apagá el bypass", ("confirmation_bypass", 0)),
        ("turn off bypass mode", ("confirmation_bypass", 0)),
        # Counter-cases: a question about the state, Windows' own accessibility settings, a mode of another app.
        ("¿está activado el modo accesible?", None),
        ("abre la configuración de accesibilidad de Windows", None),
        ("activa el modo oscuro", None),
    ],
)
def test_baxys_own_settings_are_switched_like_the_others(text: str, switched: tuple[str, int] | None) -> None:
    assert effect_intent.setting_switch_request(text) == switched


@pytest.mark.parametrize(
    ("text", "arguments"),
    [
        ("Activa el modo accesible para personas no videntes", {"setting": "accessible_mode", "value": 1}),
        ("Activa el modo bypass", {"setting": "confirmation_bypass", "value": 1}),
        ("desactiva el modo bypass", {"setting": "confirmation_bypass", "value": 0}),
    ],
)
def test_the_live_orders_are_the_setting_never_computer_use(text: str, arguments: dict) -> None:
    read = effect_intent.resolve_explicit_effects(text, OPERATIONS)
    assert read is not None and read.operations == (SET,), read
    assert semantic_arguments._explicit_arguments_from_evidence(SET, read.evidence[0]) == arguments


@pytest.mark.parametrize(
    ("window", "app"),
    [
        ({"title": "BAXY", "process": "Baxy", "protected": True}, "«Baxy»"),
        # Revisión U, H3: the title of a protected console or editor carries the person's commands and paths; the
        # cause names the application by its process, never the title.
        ({"title": "Administrador: Símbolo del sistema - mysql -u root -pHunter2", "process": "cmd.exe",
          "protected": True}, "«cmd»"),
        ({"title": "ssh usuario@192.168.1.20", "process": "WindowsTerminal", "protected": True}, "«WindowsTerminal»"),
    ],
)
def test_a_protected_window_is_said_by_its_application_never_its_title(window: dict, app: str) -> None:
    observed = {"goal": "activar el modo accesible", "reached": False, "steps": [],
                "stoppedBy": "computer_use_window_protected", "window": window}
    for language in ("es", "en"):
        cause = str(cu_projection.project_seen(observed, language)["stoppedBecause"])
        assert app in cause
        assert window["title"] not in cause and "Hunter2" not in cause and "192.168" not in cause
        assert "editor" not in cause and "consola" not in cause and "console" not in cause


def test_the_generic_protected_cause_names_no_category_to_pick_from() -> None:
    # Counter-case: with no window name seen, the generic cause still says nothing was touched, and names no kind of
    # window the writer could turn into a false cause.
    cause = cu_projection._STOP_CAUSES["computer_use_window_protected"]
    assert "no pulsé ni escribí nada" in cause["es"] and "pressed and typed nothing" in cause["en"]
    for word in ("editor", "consola", "console", "BAXY"):
        assert word not in cause["es"] and word not in cause["en"]


def _setting(observed: dict | None = None, ok: bool = True, **extra: object) -> dict:
    situation: dict = {"kind": "operation", "operation": SET, "polarity": "success" if ok else "failure",
                       "verified": ok, "succeeded": ok}
    if observed is not None:
        situation["observed"] = {"version": 1, **observed}
    situation.update(extra)
    return situation


@pytest.mark.parametrize(
    ("observed", "spanish", "english"),
    [
        # Encargo I2: switched now, the floor says which way («activé», never «cambié» nor «ya está»).
        ({"setting": "accessible_mode", "value": 1, "changed": True}, "Listo, activé el modo accesible.",
         "I turned the accessible mode on."),
        ({"setting": "accessible_mode", "value": 0, "changed": True}, "Listo, desactivé el modo accesible.",
         "I turned the accessible mode off."),
        ({"setting": "accessible_mode", "value": 0, "changed": False}, "El modo accesible ya estaba así.",
         "The accessible mode was already that way."),
        ({"setting": "confirmation_bypass", "value": 0, "changed": True}, "Apagué el modo bypass.",
         "I switched bypass mode off."),
    ],
)
def test_baxys_own_setting_is_told_from_its_facts(observed: dict, spanish: str, english: str) -> None:
    assert operation_floor.floor_final(_setting(observed), False) == spanish
    assert operation_floor.floor_final(_setting(observed), True) == english


def test_bypass_asked_from_the_chat_says_where_it_is_switched_on() -> None:
    refused = _setting(ok=False, error="confirmation_bypass_interface_only")
    spanish = deterministic_finals._deterministic_final(refused, {}, "Activa el modo bypass", "es")
    assert "no lo enciendo desde el chat" in spanish and "«confirmaciones»" in spanish
    assert "protegida" not in spanish and "editor" not in spanish
    assert "«confirmaciones»" in deterministic_finals._deterministic_final(refused, {}, "turn on bypass mode", "en")


class _ComputerUseDecider:
    """A decider that would take every order to computer use (what the live turns did): the readers decide first."""

    _native_tool_policy_enabled = False

    def __init__(self) -> None:
        self.asked = 0

    def decide_in_context(self, request, *_a, **_k):
        self.asked += 1
        return ContextDecision(request, "action", ("mission.computer.use",), "", ())

    def prepare_decision(self, *_a, **_k):
        return None

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def public_lookup_requested(self, _text):
        return False

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(operation: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


@pytest.mark.parametrize(
    "text",
    ["Activa el modo bypass", "Activa el modo accesible para personas no videntes", "apagá el modo accesible"],
)
def test_the_live_turns_are_the_setting_without_asking_the_decider(text: str) -> None:
    tools = {name: _tool(name) for name in OPERATIONS}
    model = _ComputerUseDecider()
    result = turn_decide._prepare_turn_result(
        {"id": "estab-u", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, application_names=("Steam", "Spotify"), dialogue_state=DialogueState(),
    )
    assert (result["kind"], result["effectOperations"]) == ("action", [SET]), result
    assert model.asked == 0


@pytest.mark.parametrize(
    "text",
    [
        # Revisión U, H4: a bypass or an accessible mode of something else is never BAXY's setting.
        "apagá el bypass del router",
        "desactivá el bypass del proxy",
        "set up a bypass on the router",
        "activa el bypass del proxy en Windows",
        "turn on the bypass valve in the game",
        "activa el modo de accesibilidad de Windows",
        "turn on accessible mode in Word",
        "activa el modo accesible de la página",
        "set accessibility mode on in the settings app",
    ],
)
def test_a_setting_of_something_else_is_not_baxys(text: str) -> None:
    assert effect_intent.setting_switch_request(text) is None


@pytest.mark.parametrize(
    ("text", "switched"),
    [
        # Contracases: BAXY named, who the mode is for, a courtesy or «on/off» after it keep it BAXY's.
        ("activa el modo accesible de BAXY", ("accessible_mode", 1)),
        ("turn accessible mode on", ("accessible_mode", 1)),
        ("activá el modo accesible ahora, porfa", ("accessible_mode", 1)),
        ("apaga tu bypass", ("confirmation_bypass", 0)),
        ("desactiva el modo bypass de baxy", ("confirmation_bypass", 0)),
    ],
)
def test_baxys_own_setting_keeps_its_reading(text: str, switched: tuple[str, int]) -> None:
    assert effect_intent.setting_switch_request(text) == switched


def test_the_bypass_cause_fact_is_data() -> None:
    fact = operation_floor.floor_data()["causeFacts"]["facts"]["confirmation_bypass_interface_only"]
    assert compose_situation._CAUSE_FACT["confirmation_bypass_interface_only"] == fact


def test_a_protected_windows_title_never_names_the_place() -> None:
    # Revisión U, H3: the head of the final («No pude hacerlo en …») used the window's title too.
    observed = {"goal": "escribir hola", "reached": False, "steps": [], "stoppedBy": "computer_use_window_protected",
                "window": {"title": "mysql -u root -pHunter2", "process": "cmd.exe", "protected": True}}
    seen = cu_projection.project_seen(observed, "es")
    assert seen["windowTitle"] is None
    assert "Hunter2" not in cu_finals.floor_sentence(observed, False, False)
