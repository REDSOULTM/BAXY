"""r30, latencia (bancos Br28 y Bb3tb, 2026-10-10): 21 of the 70 mission finals were worded by the model (p50 1,1 s
against 0,1 s from the facts). In 16 of them the facts already held what to say: the App had read, in the look that
proved the term, how the window writes the place («Cronómetro» for «ir a stopwatch», «Tu biblioteca» after the click on
«Abre Tu biblioteca») or which control the verified click pressed («Borrador» for «seleccionar eraser»); the final kept
the person's word, was not the window's spelling and went to the model, which added «it shows 96 hours», «I see two
devices paired». A part is now told by what its term read (observed arrivedAs, a chain's parts already carried theirs),
under the rule of ronda 24b: only after an act of the part, found already there or on a strong term. A search a focused
field proved opened never names the place asked, so its sentence is the facts' too. Twins: tests/data/cu_floor_twins.json
(«cu-r30-*»), said the same by the App's OperationFloor (ComputerUseFloorTests)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_finals
from baxy_mind import computer_use_finals
from baxy_mind import deterministic_finals

FIXTURE = json.loads((ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))
# «floorOnly» (revisión de r30): what the two floors say of a mission whose final is the model's.
TWINS = {case["id"]: case for key in ("cases", "floorOnly") for case in FIXTURE[key]}


def _situation(case_id: str) -> dict:
    return json.loads(json.dumps(TWINS[case_id]["situation"]))


@pytest.mark.parametrize("case_id", [
    "cu-r30-place-as-the-window-wrote-it", "cu-r30-place-by-its-page-after-a-click",
    "cu-r30-pick-as-its-verified-click-named-it", "cu-r30-chain-places-as-the-window-wrote-them",
    # «Ya estabas» only with proof: no act, a window already open and a strong term the plan's check lists.
    "cu-r30-contracase-already-there-only-on-a-strong-term",
    # A search a focused field proved opened: the sentence names the field, never the place asked.
    "cu-r24b-search-opened-field", "cu-r24b-search-opened-no-field", "cu-r24b-one-part-search-opened",
])
@pytest.mark.parametrize("language", ["es", "en"])
def test_a_part_is_told_from_the_facts_by_what_its_term_read(case_id: str, language: str) -> None:
    situation = _situation(case_id)
    assert computer_use_finals._computer_use_floor_first(situation, language) == TWINS[case_id][language]
    assert deterministic_finals._deterministic_final(situation, {}, "", language) == TWINS[case_id][language]


@pytest.mark.parametrize("language", ["es", "en"])
def test_contracase_a_weak_arrival_with_no_act_is_still_the_model_s(language: str) -> None:
    # The page's header read «Cronómetro» with no act of the mission: nothing says the window got there now.
    case_id = "cu-r30-contracase-weak-arrival-with-no-act-keeps-the-word-asked"
    situation = _situation(case_id)
    assert computer_use_finals._computer_use_floor_first(situation, language) == ""
    assert "«stopwatch»" in TWINS[case_id][language] and "Cronómetro" not in TWINS[case_id][language]
    assert deterministic_finals._deterministic_final(situation, {}, "", language) == TWINS[case_id][language]


@pytest.mark.parametrize("case_id", [
    "cu-r30-place-as-the-window-wrote-it", "cu-r30-pick-as-its-verified-click-named-it",
])
def test_contracase_without_what_the_term_read_the_word_asked_is_the_model_s(case_id: str) -> None:
    situation = _situation(case_id)
    del situation["observed"]["arrivedAs"]
    asked = situation["observed"]["goal"].split()[-1]
    assert computer_use_finals._computer_use_floor_first(situation, "es") == ""
    assert f"«{asked}»" in deterministic_finals._deterministic_final(situation, {}, "", "es")


def test_contracase_a_chain_part_reached_with_no_act_on_a_weak_term_keeps_the_window_s_names() -> None:
    situation = _situation("cu-r30-chain-places-as-the-window-wrote-them")
    observed = situation["observed"]
    observed["steps"] = [step for step in observed["steps"] if step.get("name") != "Temas"]
    observed["screen"]["lines"] = ["Fondo"]
    observed["subgoals"][1]["acted"] = False
    assert computer_use_finals._computer_use_floor_first(situation, "es") == ""
    assert "«themes»" in deterministic_finals._deterministic_final(situation, {}, "", "es")


def test_contracase_a_failure_is_told_with_its_cause_whatever_a_term_read() -> None:
    # Nothing is said reached without its receipt: a mission that did not reach keeps its failure and its typed cause.
    for case_id in ("cu-failed-covered", "cu-failed-direct", "cu-failed-place-not-found"):
        for language in ("es", "en"):
            situation = _situation(case_id)
            before = computer_use_finals._computer_use_floor_first(situation, language)
            situation.get("reason", situation)["observed"]["arrivedAs"] = "Cronómetro"
            assert computer_use_finals._computer_use_floor_first(situation, language) == before, case_id
            assert deterministic_finals._deterministic_final(situation, {}, "", language) == TWINS[case_id][language], case_id
            assert "Cronómetro" not in TWINS[case_id][language]


@pytest.mark.parametrize("case_id", [
    "cu-r24b2-blank-item-created-by-the-opening", "cu-r24b3-blank-offer-clicked-is-chosen-not-created",
    "cu-r24b3-click-that-recorded-the-document-created-it",
])
@pytest.mark.parametrize("language", ["es", "en"])
def test_contracase_a_blank_document_is_told_by_what_was_made(case_id: str, language: str) -> None:
    # Office in the cold (banco u5, n6): the offer's verified click now gives the mission its arrivedAs («Documento en
    # blanco»); a creation is still told by the document the mission made (its window's title), or as chosen.
    situation = _situation(case_id)
    situation["observed"]["satisfiedBy"] = "stepDone:input.visible.click:=documento en blanco"
    situation["observed"]["arrivedAs"] = "Documento en blanco"
    assert deterministic_finals._deterministic_final(situation, {}, "", language) == TWINS[case_id][language]


def test_contracase_keys_in_an_application_no_part_is_told_in_are_still_the_model_s() -> None:
    # The facts' sentence would leave the paste out: «preferred» stays false whatever the names (r16).
    situation = _situation("cu-parts-calculate")
    observed = situation["observed"]
    observed["goal"] = "calcular 37*12; luego apretar ctrl c; luego apretar ctrl v"
    observed["subgoals"] = [{"goal": "calcular 37*12", "application": "Calculadora", "reached": True},
                            {"goal": "apretar ctrl c", "application": "Calculadora", "reached": True},
                            {"goal": "apretar ctrl v", "application": "Bloc de notas", "reached": True}]
    assert computer_use_finals._computer_use_floor_first(situation, "es") == ""


def test_the_name_in_capitals_a_term_read_is_told_calmly() -> None:
    situation = _situation("cu-r30-place-as-the-window-wrote-it")
    situation["observed"]["arrivedAs"] = "CRONÓMETRO"
    assert cu_finals.floor_first(situation["observed"], False, True) == "Listo, estoy en «Cronómetro»."


# ---------------------------------------------------------------- revisión de r30 (H1, H2, H4)
# The equality the branch retired (the name read equals the name asked) also kept two finals with the model. Both go
# back to it; what the twins hold is the respaldo's own sentence, which is prior to this branch.


@pytest.mark.parametrize("language", ["es", "en"])
def test_h1_an_arrival_by_resemblance_gives_no_name_and_stays_the_model_s(language: str) -> None:
    # «ir a language», a verified click on «Hora e idioma», closed on control:hora e idioma:current&similar:…: the
    # window is there, nothing proves it is what was asked. Before the fix: «Listo, estoy en «Hora e idioma».»
    case_id = "cu-r30-contracase-resemblance-gives-no-name"
    situation = _situation(case_id)
    assert computer_use_finals._computer_use_floor_first(situation, language) == ""
    assert "Hora e idioma" not in TWINS[case_id][language]
    assert deterministic_finals._deterministic_final(situation, {}, "", language) == TWINS[case_id][language]
    # Contracase: the same click closed on the term alone (no atom of a resemblance) is told as the window writes it.
    situation["observed"]["satisfiedBy"] = "control:hora e idioma:current"
    assert "«Hora e idioma»" in computer_use_finals._computer_use_floor_first(situation, language)


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("opened", [True, False])
def test_h2_a_pick_found_chosen_with_no_act_gives_no_name_and_stays_the_model_s(language: str, opened: bool) -> None:
    # «seleccionar pencil», Paint with «Lápiz» already chosen, control:=lapiz:selected, no act of the mission (only the
    # opening, or a window already open). Before the fix: «Listo, elegí «Lápiz».» Encargo H1 (tandas fin1/fin2 t4-c04 t3,
    # t3-c18 t2): this was left to the model, which said «Lo hice» / «elegí»; the floor now tells it as it already was
    # (cu_finals._held_before_acting), with the name the window wrote and never a pick (row in «appAndMindDiffer»).
    case_id = "cu-r30-contracase-pick-found-chosen-with-no-act-gives-no-name"
    row = next(row for row in FIXTURE["appAndMindDiffer"] if row["id"] == case_id)
    situation = json.loads(json.dumps(row["situation"]))
    if not opened:
        situation["observed"]["steps"] = []
    said = computer_use_finals._computer_use_floor_first(situation, language)
    if opened:
        assert said == row["mind"][language]
    else:
        assert said == ("«Lápiz» ya estaba elegido en «Paint»." if language == "es" else
                        "«Lápiz» was already chosen in «Paint».")
    assert deterministic_finals._deterministic_final(situation, {}, "", language) == said
    assert "elegí" not in said and "picked" not in said
    # Contracase: after the mission's own verified click the pick is told, as the window names it.
    situation["observed"]["steps"].append(
        {"step": 2, "operation": "input.visible.click", "label": "Lápiz", "name": "Herramienta Lápiz", "ok": True})
    told = computer_use_finals._computer_use_floor_first(situation, language)
    assert "«Lápiz»" in told and "ya estaba" not in told and "already" not in told


def test_h2_contracase_a_place_found_on_a_strong_term_is_still_told_with_no_act() -> None:
    # The rule of the pick is the pick's alone: a place read on a strong term with no act keeps «Ya estás en».
    situation = _situation("cu-r30-contracase-already-there-only-on-a-strong-term")
    assert computer_use_finals._computer_use_floor_first(situation, "es") == "Ya estás en «Cronómetro»."


def test_h4_where_the_mind_tells_more_than_the_app_is_written_down() -> None:
    # One situation, two sentences on purpose (the App carries no colour shades): ComputerUseFloorTests reads the same
    # rows for the App's side.
    rows = FIXTURE["appAndMindDiffer"]
    assert rows
    for row in rows:
        for language in ("es", "en"):
            assert deterministic_finals._deterministic_final(row["situation"], {}, "", language) == row["mind"][language], row["id"]
            assert row["app"][language] != row["mind"][language], row["id"]
