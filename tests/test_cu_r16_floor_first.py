"""Voice audit 2026-10-07 (cu-r16): a third of the published computer-use finals the model wrote had a defect («Ya te
llevé a la sección de sonido», «Abrazé a la sección de Bluetooth», «ahora selecciono Títulos», «mis playlists»). A
mission without a question is now told from its facts first (computer_use.floor_first, data «computerUse.parts»):
places, picks, typed and searched text, a calculation whose value the window shows. The model words only questions
about the window and parts the facts cannot tell. Every situation here is our own shape of those runs; the twins of
the App are tests/data/cu_floor_twins.json («cu-parts-*»)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use, llm  # noqa: E402

TWINS = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))["cases"]}


def _first(case_id: str, language: str) -> str:
    return llm._computer_use_floor_first(TWINS[case_id]["situation"], language)


@pytest.mark.parametrize("case_id", [
    "cu-parts-select", "cu-parts-type", "cu-parts-type-chain", "cu-parts-search", "cu-parts-calculate",
    "cu-parts-calculate-grouped", "cu-parts-calculate-decimal", "cu-parts-places", "cu-parts-select-then-place",
    "cu-parts-place-then-search", "cu-reached-place", "cu-reached-tab",
    # A chain whose first place the window did not spell is told by where it is.
    "cu-reached-chain",
])
@pytest.mark.parametrize("language", ["es", "en"])
def test_a_mission_without_a_question_is_told_from_its_facts_first(case_id: str, language: str) -> None:
    assert _first(case_id, language) == TWINS[case_id][language]


@pytest.mark.parametrize("case_id", [
    # The value is not on the screen, only the expression's own operand, or the text typed is not the part's.
    "cu-parts-calculate-not-shown", "cu-parts-calculate-operand-only", "cu-parts-typed-other-text",
    # A switch turned on.
    "cu-reached-act",
])
@pytest.mark.parametrize("language", ["es", "en"])
def test_what_the_facts_cannot_tell_is_left_to_the_model(case_id: str, language: str) -> None:
    assert _first(case_id, language) == ""


def test_the_facts_never_tell_a_colour_shade_the_model_would_misname() -> None:
    situation = json.loads(json.dumps(TWINS["cu-parts-select"]["situation"]))
    observed = situation["observed"]
    observed["goal"] = "seleccionar texto; luego seleccionar azul"
    observed["subgoals"] = [{"goal": "seleccionar texto", "application": "Paint", "reached": True},
                            {"goal": "seleccionar azul", "application": "Paint", "reached": True}]
    observed["steps"][1:] = [
        {"step": 2, "operation": "input.visible.click", "label": "Texto", "name": "Texto", "ok": True},
        {"step": 3, "operation": "input.visible.click", "label": "Añil", "name": "Añil", "ok": True},
    ]
    assert llm._computer_use_floor_first(situation, "es") == "Listo, elegí «Texto» y Añil, el azul de la paleta."
    assert llm._computer_use_floor_first(situation, "en") == "Done, I picked «Texto» and Añil, the blue of the palette."


def test_a_question_about_the_window_is_the_model_s() -> None:
    situation = json.loads(json.dumps(TWINS["cu-reached-tab"]["situation"]))
    situation["observed"]["goal"] = "ir a la pestaña de alarma; y responder: a qué hora suena"
    assert llm._computer_use_floor_first(situation, "es") == ""


def test_a_place_the_window_did_not_spell_is_the_model_s() -> None:
    # «ir a world clock» on a Spanish window: the floor would say «world clock», the window says «Reloj mundial».
    situation = json.loads(json.dumps(TWINS["cu-reached-place"]["situation"]))
    situation["observed"]["goal"] = "ir a world clock"
    assert llm._computer_use_floor_first(situation, "en") == ""
    assert llm._deterministic_final(situation, {}, "", "en") == "Done, I'm in «world clock»."


def test_keys_pressed_in_another_application_are_the_model_s() -> None:
    # «calculá 12*12, copialo y pegalo en el Bloc de notas»: the paste is in a window no part is told in.
    situation = json.loads(json.dumps(TWINS["cu-parts-calculate"]["situation"]))
    observed = situation["observed"]
    observed["goal"] = "calcular 37*12; luego apretar ctrl c; luego apretar ctrl v"
    observed["subgoals"] = [{"goal": "calcular 37*12", "application": "Calculadora", "reached": True},
                            {"goal": "apretar ctrl c", "application": "Calculadora", "reached": True},
                            {"goal": "apretar ctrl v", "application": "Bloc de notas", "reached": True}]
    assert llm._computer_use_floor_first(situation, "es") == ""
    assert llm._deterministic_final(situation, {}, "", "es") == "Listo, calculé 37 × 12 = 444."


def test_a_failure_with_its_typed_cause_is_told_from_its_facts_first() -> None:
    for case_id in ("cu-failed-covered", "cu-failed-direct"):
        for language in ("es", "en"):
            assert _first(case_id, language) == TWINS[case_id][language], case_id
    # A chain that failed after some of its parts were done: the model tells what was done and what was not.
    assert _first("cu-failed-cause", "es") == "" and _first("cu-failed-place-not-found", "en") == ""
    # An untyped stop code says no cause: the model words it.
    assert _first("cu-failed-untyped", "es") == ""


def test_a_progress_notice_is_never_a_final() -> None:
    situation = dict(TWINS["cu-reached-tab"]["situation"], kind="progress")
    assert llm._computer_use_floor_first(situation, "es") == ""


def test_the_value_must_be_the_window_s_and_not_an_operand() -> None:
    texts = ["La expresión es 144 ÷ 12="]
    assert computer_use._calculation_shown("144 ÷ 12", texts) is None
    assert computer_use._calculation_shown("144 ÷ 12", [*texts, "Se muestra 12"]) == ("144 ÷ 12", "12")
    assert computer_use._calculation_shown("10 / 3", ["Se muestra 3,333333333333333"]) is None
    assert computer_use._calculation_shown("2 * (3 + 4)", ["Display is 14"]) == ("2 × (3 + 4)", "14")
    assert computer_use._calculation_shown("5 / 0", ["Se muestra 0"]) is None


# Live 2026-10-07 (cu-r17): a chain across two applications lost its first one («Listo, estoy en «TIENDA».»), the
# Chilean «1.500» was read as 1,5, and a calculation took its value from another window's status bar.
@pytest.mark.parametrize("case_id", [
    "cu-parts-places-across-apps", "cu-parts-calculate-thousands", "cu-parts-place-in-capitals",
])
@pytest.mark.parametrize("language", ["es", "en"])
def test_chains_across_apps_thousands_and_capitals_are_told_from_their_facts(case_id: str, language: str) -> None:
    assert _first(case_id, language) == TWINS[case_id][language]


@pytest.mark.parametrize("language", ["es", "en"])
def test_a_calculation_is_never_told_from_another_window_s_numbers(language: str) -> None:
    assert _first("cu-parts-calculate-other-window", language) == ""
    told = llm._deterministic_final(TWINS["cu-parts-calculate-other-window"]["situation"], {}, "", language)
    assert "13" not in told


@pytest.mark.parametrize(("name", "told"), [("TIENDA", "Tienda"), ("MÚSICA", "Música"), ("VPN", "VPN"),
                                            ("HDMI", "HDMI"), ("Tienda", "Tienda")])
def test_a_name_in_capitals_is_told_with_its_first_letter_only_unless_an_acronym(name: str, told: str) -> None:
    assert computer_use._calm_caps(name) == told


@pytest.mark.parametrize(("expression", "value"), [("1.500 + 500", 2000), ("2.000 × 3", 6000), ("1.500,5 + 1", "1501.5"),
                                                   ("3.5 + 1", "4.5"), ("1.250.000 ÷ 2", 625000)])
def test_a_point_before_three_digits_groups_thousands(expression: str, value: object) -> None:
    from fractions import Fraction
    tokens = [computer_use._PARTS["operators"].get(token, token) for token in computer_use._CALC_TOKEN.findall(expression)]
    assert computer_use._calculated(tokens) == Fraction(str(value))
