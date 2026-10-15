"""Encargo FF: dos finales falsos de la tanda n10 del notebook (y de n8, los mismos turnos), con los payloads reales.

- t2-c01 t1 «pone los bunkers en spotify pa estudiar»: ``media.play.query`` quedó incierto con
  ``spotify_exact_result_not_found`` y el redactor dijo «…porque la búsqueda no mostró nada que pudiera reproducirse.»,
  algo que nadie vio (BAXY buscó y no eligió nada; no leyó si había resultados ni qué suena). Ahora lo dice el suelo
  con los datos (operation_floor «openedUnconfirmed.spotify_exact_result_not_found»), sin pedir borrador.
- t2-c02 t3 «dale, la segunda como se hace? pasame los pasos cortitos»: la búsqueda leyó la receta, el borrador de la
  receta consultada se cortó por su presupuesto (``finish_reason: length``), el reintento no cupo, el borrador corto
  murió como ``reversed_result`` y la reserva dijo «No encontré los pasos cortos…». Ahora la receta cortada guarda sus
  líneas enteras y dice que sigue (consulted_answers._whole_part_of_cut_recipe, dato «consultedCut»).

Contracasos: la búsqueda que de verdad no trae la receta (n5) sigue diciendo «No encontré…»; Spotify que reproduce
(n5) sigue diciendo lo que suena; con tiempo, el reintento entero gana a la parte cortada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import llm, operation_floor  # noqa: E402
from baxy_mind.consulted_answers import _whole_part_of_cut_recipe  # noqa: E402

CASES = json.loads((ROOT / "tests" / "data" / "estab_ff_finales.json").read_text(encoding="utf-8"))["cases"]
SPOTIFY = operation_floor.floor_data()["openedUnconfirmed"]["spotify_exact_result_not_found"]
CUT = operation_floor.floor_data()["consultedCut"]


class _Writer(llm.LlmRuntime):
    """Answers the given (draft, finish_reason) in order; None or no draft left is a writer out of time."""

    def __init__(self, drafts: list[tuple[str, str] | None]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.asked = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.asked += 1
        item = self.drafts.pop(0) if self.drafts else None
        if item is None:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": item[0]}, "finish_reason": item[1]}]}


def _final(case: dict, drafts: list[tuple[str, str] | None], said: str | None = None) -> tuple[str, int]:
    writer = _Writer(drafts)
    facts = {
        "situation": json.dumps(case["situation"], ensure_ascii=False),
        "priorRequests": case.get("prior", []),
        "mustNotAskFollowUp": True,
    }
    said = said or case["said"]
    return writer.compose_user_message(case.get("user_text", said), case["intent"], facts, said=said), writer.asked


# ------------------------------------------------------------------ Spotify: searched, nothing picked


@pytest.mark.parametrize("name", ["spotify_uncertain_n8", "spotify_uncertain_n10"])
def test_a_spotify_search_that_picked_nothing_is_said_from_the_facts(name: str) -> None:
    case = CASES[name]
    final, asked = _final(case, [(draft, "stop") for draft in case["drafts"]])
    assert asked == 0
    assert final == "Busqué «los bunkers» en Spotify, pero no pude elegir qué poner; no sé si quedó sonando algo."
    assert final == SPOTIFY["es"].format(target="«los bunkers»")
    assert "no mostró" not in final and "resultado" not in final


def test_the_same_search_in_english_is_said_in_english() -> None:
    case = CASES["spotify_uncertain_n10"]
    final, asked = _final(case, [("The search returned no results.", "stop")], said="play some music by los bunkers on spotify so I can study")
    assert asked == 0
    assert final == SPOTIFY["en"].format(target="«los bunkers»")


def test_spotify_that_plays_still_says_what_plays() -> None:
    case = CASES["spotify_playing_n5"]
    final, _ = _final(case, [(draft, "stop") for draft in case["drafts"]])
    assert final == case["measured_final"] == "Está sonando «Los Bunkers - Llueve Sobre La Ciudad» en Spotify."


# ------------------------------------------------------------------ a recipe read, its telling cut by the budget


@pytest.mark.parametrize("name", ["recipe_found_n8", "recipe_found_n10"])
def test_a_recipe_found_and_cut_by_its_budget_is_told_never_as_not_found(name: str) -> None:
    case = CASES[name]
    # As measured: the consulted draft cut, no retry in time, the short draft refused, then out of time.
    final, _ = _final(case, [(case["consulted_draft"], "length"), None, (case["drafts"][0], "stop"), None])
    if name.endswith("n10"):
        assert "\n6. Vierte el caldo de pollo sobre el arroz, mezcla todo bien y deja que hierva.\n" in final
    assert final != case["measured_final"]
    assert "No encontré" not in final
    assert final.endswith("\n" + CUT["es"])
    kept = final.removesuffix("\n" + CUT["es"])
    assert kept in case["consulted_draft"] and "\nPreparación:\n1. " in kept
    # Only whole lines: the one the budget was writing goes.
    assert kept.endswith(".") and case["consulted_draft"][len(kept):].startswith("\n")
    assert final.startswith("Arroz con pollo y frijoles:\n- 2 pechugas de pollo")


def test_with_time_the_whole_retry_wins_over_the_cut_part() -> None:
    case = CASES["recipe_found_n10"]
    whole = (
        "Ingredientes:\n- 2 pechugas de pollo\n- 1 taza de arroz\n- 1 taza de frijoles\n"
        "Preparación:\n1. Dora el pollo y resérvalo.\n2. Sofríe la cebolla, el ajo y el pimiento.\n"
        "3. Cocina el arroz en el caldo a fuego bajo 15-20 minutos.\n4. Mezcla con los frijoles y el pollo."
    )
    final, asked = _final(case, [(case["consulted_draft"], "length"), (whole, "stop")])
    assert (final, asked) == (whole, 2)


def test_a_recipe_cut_before_any_step_keeps_nothing() -> None:
    draft = CASES["recipe_found_n10"]["consulted_draft"]
    assert _whole_part_of_cut_recipe(draft.split("Preparación:")[0] + "Preparación:\n1. Calien", False) == ""
    assert _whole_part_of_cut_recipe("Ingredientes:\n- 2 pechugas de pollo\n- 1 taza de ar", False) == ""
    assert _whole_part_of_cut_recipe(draft, True).endswith("\n" + CUT["en"])


def test_a_search_that_did_not_bring_the_recipe_still_says_not_found() -> None:
    case = CASES["recipe_not_found_n5"]
    final, _ = _final(case, [(draft, "stop") for draft in case["drafts"]])
    assert final.startswith("No encontré")
    assert CUT["es"] not in final
