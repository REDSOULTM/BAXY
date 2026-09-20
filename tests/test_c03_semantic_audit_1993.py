"""REOPEN1993 (auditoría semántica, D24): readings that act when the context is
deterministic or the candidate unique, and keep asking under real ambiguity.

Owner rule (2026-09-20): act when the context is deterministic or the
candidate is unique and say what was done; ask only with real ambiguity;
choose for the person only where it is deterministic.
"""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind.__main__ import (
    _explicit_arguments_from_evidence,
    _unresolved_input_kind,
    _verified_dependency_identity_arguments,
    _with_session_alarm_selector,
)

APPLICATIONS = ("Steam", "Microsoft Teams", "Google Chrome", "Discord", "Calculadora", "Bloc de notas")
GAMES = effect_intent.build_game_catalog_index(
    [("steam", "2767030", "Marvel Rivals"), ("steam", "108600", "Project Zomboid")]
)
OPERATIONS = (
    "app.open", "game.launch", "app.installed", "web.search", "browser.navigate", "window.focus",
    "window.resolve", "game.entitlement.named", "capture.screenshot", "ocr.read", "input.text.type",
    "notification.cancel.latest", "notification.cancel.at", "notification.list", "notification.schedule",
)


# --- B. nombre aproximado con candidato único («lo mal dicho lo arregla BAXY») -------------
@pytest.mark.parametrize("text", ["abre Steel.", "Sí. Abre Steel.", "Abre stea,", "Sí, abre Ste."])
def test_single_near_application_opens_without_asking(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and intent.operations == ("app.open",)
    assert effect_intent.near_single_open_candidate(text, APPLICATIONS, GAMES) == ("app.open", "Steam")
    assert _explicit_arguments_from_evidence("app.open", text, APPLICATIONS, GAMES) == {"appId": "Steam"}


def test_single_near_game_launches_without_asking() -> None:
    text = "Ve a Mad de Rivals."
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and intent.operations == ("game.launch",)
    assert _explicit_arguments_from_evidence("game.launch", text, APPLICATIONS, GAMES) == {"appId": "2767030"}


def test_two_near_candidates_keep_asking() -> None:
    # H0521 «abres team»: Steam and Microsoft Teams are both installed; the question stands.
    assert effect_intent.near_single_open_candidate("abres team", APPLICATIONS, GAMES) is None
    assert effect_intent.resolve_explicit_effects("abres team", OPERATIONS, APPLICATIONS, GAMES) is None


def test_exact_names_and_unknown_names_are_untouched() -> None:
    exact = effect_intent.resolve_explicit_effects("abre steam", OPERATIONS, APPLICATIONS, GAMES)
    assert exact is not None and exact.operations == ("app.open",)
    unknown = effect_intent.resolve_explicit_effects("Y quema, abre Saint Rose.", OPERATIONS, APPLICATIONS, GAMES)
    assert unknown is not None and unknown.operations == ("app.installed",)


# --- A. contexto determinista ------------------------------------------------------------
SESSION_ALARM = [
    {"role": "user", "content": "pon una alarma en 2 minutos"},
    {"role": "assistant", "content": "Listo, la alarma quedó programada."},
]


def test_cancel_the_alarm_after_setting_one_in_this_session_cancels_the_latest() -> None:
    history = [*SESSION_ALARM, {"role": "user", "content": "cancelá la alarma"}]
    rewritten = _with_session_alarm_selector("cancelá la alarma", history)
    assert rewritten == "cancelá la ultima alarma"
    intent = effect_intent.resolve_explicit_effects(rewritten, OPERATIONS)
    assert intent is not None and intent.operations == ("notification.cancel.latest",)
    assert effect_intent.resolve_explicit_clarification_intent(rewritten, OPERATIONS) is None
    assert _explicit_arguments_from_evidence("notification.cancel.latest", rewritten) == {"kind": "alarm"}


def test_cancel_the_alarm_in_english_after_one_alarm() -> None:
    history = [{"role": "user", "content": "set an alarm for 8 am"}]
    assert _with_session_alarm_selector("cancel the alarm", history) == "cancel the last alarm"


@pytest.mark.parametrize(
    "history",
    [
        [],
        [*SESSION_ALARM, {"role": "user", "content": "pon otra alarma a las 9"}],
        [*SESSION_ALARM, {"role": "user", "content": "cancelá la alarma"}, {"role": "user", "content": "cancelá la alarma"}],
        [{"role": "user", "content": "qué hora es"}],
    ],
)
def test_cancel_the_alarm_without_a_single_session_alarm_keeps_asking(history: list) -> None:
    # AGENDA1337 stands: no alarm, two alarms or a cancellation since → which alarm.
    assert _with_session_alarm_selector("cancelá la alarma", history) == "cancelá la alarma"
    asked = effect_intent.resolve_explicit_clarification_intent("cancelá la alarma", OPERATIONS)
    assert asked is not None and asked.missing_fields == ("which_alarm",)


def test_named_alarm_cancellations_are_not_rewritten() -> None:
    history = [*SESSION_ALARM]
    assert _with_session_alarm_selector("cancelá la alarma de las 7", history) == "cancelá la alarma de las 7"
    assert _with_session_alarm_selector("cancelá las alarmas", history) == "cancelá las alarmas"


@pytest.mark.parametrize("text", ["cambiá a la otra ventana", "switch to the other window", "volvé a la otra ventana", "pasá a la ventana anterior"])
def test_the_other_window_switches_to_the_window_behind_the_foreground(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES)
    assert intent is not None and intent.operations == ("window.resolve", "window.focus")
    assert _unresolved_input_kind(text, APPLICATIONS) is None
    assert _explicit_arguments_from_evidence("window.resolve", text) == {"process": "*", "byTitle": False, "limit": 50}
    observations = [{
        "stepId": "step_1", "operation": "window.resolve", "verified": True, "status": "completed",
        "result": {"windows": [
            {"windowId": "front", "foreground": True, "state": "normal"},
            {"windowId": "hidden", "foreground": False, "state": "minimized"},
            {"windowId": "behind", "foreground": False, "state": "normal"},
        ]},
    }]
    tool = {"function": {"canonical_name": "window.focus", "parameters": {
        "type": "object", "properties": {"windowId": {"type": "string"}}, "required": ["windowId"], "additionalProperties": False}}}
    assert _verified_dependency_identity_arguments("window.focus", text, observations, tool) == {"windowId": "behind"}


@pytest.mark.parametrize("text", ["enfocá la mejor", "cambiá a la otra pestaña"])
def test_the_best_window_and_the_other_tab_keep_asking(text: str) -> None:
    # WINDOWS1537 stands for «la mejor»; a tab is not a window.
    assert effect_intent.resolve_explicit_effects(text, OPERATIONS, APPLICATIONS, GAMES) is None
    assert _unresolved_input_kind(text, APPLICATIONS) == "indeterminate_window"


@pytest.mark.parametrize("text", ["Quiero que lo veas y de que se trata?", "Miralo y decime de qué se trata", "look at it and tell me what it is"])
def test_look_at_it_with_nothing_said_before_reads_the_screen(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, OPERATIONS, previous_user_text=None)
    assert intent is not None and intent.operations == ("capture.screenshot", "ocr.read")
    # With an antecedent the reader steps aside and the question «qué debo mirar» stands (DIALOGUE1487).
    assert effect_intent.resolve_explicit_effects(text, OPERATIONS, previous_user_text="abrí el informe.pdf") is None
    assert _unresolved_input_kind(text, APPLICATIONS) == "deictic_look"


# --- C/D. dentro de la aplicación: «ponle hola» tras abrir una aplicación --------------------
def test_put_text_after_opening_an_application_types_it_there() -> None:
    intent = effect_intent.resolve_explicit_effects(
        "ponle hola", OPERATIONS, APPLICATIONS, GAMES, previous_user_text="abrí el bloc de notas",
    )
    assert intent is not None and intent.operations == ("input.text.type",)
    assert effect_intent.deictic_text_to_type("ponle hola", "abrí el bloc de notas", APPLICATIONS) == "hola"
    assert effect_intent.deictic_text_to_type("Ponle Hola mundo", "traé chrome al frente", APPLICATIONS) == "Hola mundo"
    assert _explicit_arguments_from_evidence("input.text.type", "ponle hola") == {"text": "hola"}


@pytest.mark.parametrize("previous", [None, "qué hora es", "subí el volumen al 40"])
def test_put_text_without_an_opened_application_keeps_asking_where(previous: str | None) -> None:
    # UI1643 stands: nothing opened before → «¿dónde querés que ponga «hola»?».
    assert effect_intent.deictic_text_to_type("ponle hola", previous, APPLICATIONS) is None
    assert effect_intent.resolve_explicit_effects("ponle hola", OPERATIONS, APPLICATIONS, GAMES, previous_user_text=previous) is None
    assert _unresolved_input_kind("ponle hola", APPLICATIONS) == "deictic_text"


def test_put_text_naming_a_place_is_not_the_deictic_reading() -> None:
    assert effect_intent.deictic_text_to_type("ponle hola en el chat", "abrí el bloc de notas", APPLICATIONS) is None
