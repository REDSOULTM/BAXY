"""Encargo TZ-OSC2 (tandas z5-z8 del notebook, fable/estab-fase3 e61a9ed41, t4-c04 t3 «vale y ahora en configuracion pon
el modo oscuro»). El tema ya estaba en Oscuro antes de la misión. La misión abrió Configuración, escribió «oscuro» en su
búsqueda y pulsó el resultado «Activar el modo oscuro para aplicaciones», que trajo la página con «Oscuro» ya elegido; la
comprobación se cumplió ahí. Ningún paso pulsó «Oscuro», y las cuatro corridas dijeron «Llegué a la Configuración y elegí
el modo Oscuro.».

Causa: el suelo (cu_finals.already_chosen_sentence → _held_before_acting) devolvía "" porque contaba el texto de la
búsqueda y el clic del resultado (su etiqueta contiene la palabra) como actos que pudieron elegirlo; el redactor lo
redactó y el libro de actos lo dejó pasar porque el objeto es el del objetivo. Ahora el suelo lo dice como estaba.
Las situaciones son las reales (tests/data/tz_osc2_ya_estaba.json); el contracaso con el clic sobre «Oscuro» usa el recibo
real del paso 4 de z3 (tests/data/tz_osc_modo_oscuro.json).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use_finals, cu_finals  # noqa: E402

FROZEN = json.loads((ROOT / "tests" / "data" / "tz_osc2_ya_estaba.json").read_text(encoding="utf-8"))
CLICKED = json.loads((ROOT / "tests" / "data" / "tz_osc_modo_oscuro.json").read_text(encoding="utf-8"))["steps"][3]
RUNS = tuple(FROZEN["runs"])
TOLD = {
    "es": "Abrí «Configuración» y «Oscuro» ya estaba elegido.",
    "en": "I opened «Configuración» and «Oscuro» was already chosen.",
}


def _situation(run: str) -> dict:
    return copy.deepcopy(FROZEN["runs"][run]["situation"])


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("language", ["es", "en"])
def test_an_option_a_search_only_brought_into_view_is_told_as_it_was(run: str, language: str) -> None:
    situation = _situation(run)
    said = computer_use_finals._computer_use_floor_first(situation, language)
    assert said == TOLD[language]
    assert cu_finals.floor_sentence(situation["observed"], language == "en", True) == TOLD[language]
    assert said != FROZEN["runs"][run]["published"]


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_click_on_the_option_chose_it(run: str) -> None:
    """Theme in Claro: the mission then presses «Oscuro» (the real receipt of z3's step 4) and the final tells the mode
    reached by that act, never «ya estaba»."""

    situation = _situation(run)
    observed = situation["observed"]
    observed["steps"].append(copy.deepcopy(CLICKED))
    observed["stepCount"] = len(observed["steps"])
    assert cu_finals._held_before_acting(observed) == ""
    said = computer_use_finals._computer_use_floor_first(situation, "es")
    assert said == "Listo, estoy en «Oscuro»."
    assert "ya estaba" not in said
    assert computer_use_finals._computer_use_floor_first(situation, "en") == "Done, I'm in «Oscuro»."


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_click_named_as_the_option_chose_it_even_bringing_a_new_view(run: str) -> None:
    observed = _situation(run)["observed"]
    observed["steps"][2].update(label="Oscuro", name="Oscuro")
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_click_holding_the_name_that_brought_no_new_view_may_have_chosen_it(run: str) -> None:
    observed = _situation(run)["observed"]
    observed["steps"][2]["broughtNew"] = False
    assert cu_finals._held_before_acting(observed) == ""
    observed = _situation(run)["observed"]
    observed["steps"][2]["appeared"] = ["atras", "colores"]
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_click_holding_the_name_that_is_no_search_result_may_have_chosen_it(run: str) -> None:
    """Only the result of a search is known to take the window to the option's page: a menu entry or a button whose
    label holds the name may have chosen it while its new view shows it."""

    observed = _situation(run)["observed"]
    del observed["steps"][1]
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_search_typed_after_the_option_came_into_view_may_have_chosen_it(run: str) -> None:
    """A list filtered as it is typed may select its entry: the option counts only when a click after the last search
    brought it into view."""

    observed = _situation(run)["observed"]
    observed["steps"].append({**copy.deepcopy(observed["steps"][1]), "step": 4})
    assert cu_finals._held_before_acting(observed) == ""
    observed = _situation(run)["observed"]
    del observed["steps"][2]
    assert cu_finals._held_before_acting(observed) == ""


@pytest.mark.parametrize("run", RUNS)
def test_contracase_a_text_typed_into_a_field_that_is_no_search_may_have_chosen_it(run: str) -> None:
    observed = _situation(run)["observed"]
    observed["steps"][1].pop("intoSearch")
    assert cu_finals._held_before_acting(observed) == ""
