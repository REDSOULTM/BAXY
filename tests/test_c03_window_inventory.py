"""Global inventory requests and page facts cross the existing product seams."""

import copy

import pytest

from baxy_mind.__main__ import _ground_explicit_arguments
from baxy_mind.effect_intent import (
    operation_domain_is_grounded, resolve_explicit_effects, window_inventory_arguments,
)
from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect


SCHEMA = {
    "type": "object", "required": ["process"], "additionalProperties": False,
    "properties": {
        "process": {"type": "string"}, "byTitle": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "offset": {"type": "integer", "minimum": 0},
    },
}
REQUESTS = [
    "Enumera las ventanas.", "Muéstrame las ventanas.", "Lista mis ventanas.",
    "Dime cuántas ventanas hay abiertas.", "¿Cuáles son las ventanas abiertas?",
    "Las ventanas abiertas, muéstramelas.", "Quiero ver todas las ventanas del escritorio.",
    "Enséñame las ventanas que tengo abiertas.", "¿Qué ventanas están visibles ahora?",
    "Cuenta las ventanas de mi PC.", "Necesito los títulos de las ventanas abiertas.",
    "Dime qué ventanas tengo en este escritorio.", "List my windows.",
    "Show all open windows.", "Which windows are open?",
    "How many windows are visible right now?", "What are the titles of my open windows?",
    "Show windows on this desktop.", "Lista mis windows.", "Muéstrame las open windows.",
    "Which ventanas tengo abiertas?", "Dime los titles de las ventanas abiertas.",
    "Show las ventanas del escritorio.", "Cuenta mis ventanas, please.",
    "Tell me how many windows are open.", "The open windows, list them.",
    "Dame el inventario de las ventanas.", "Show the inventory of my windows.",
    "Comprueba las ventanas visibles.", "List the windows on my computer.",
]


@pytest.mark.parametrize("text", REQUESTS)
@pytest.mark.parametrize("envelope", ["{text}", "Baxy, por favor: {text}"])
def test_global_request_selects_inventory_and_preserves_its_selector(text, envelope):
    text = envelope.format(text=text)
    expected = {"process": "*", "byTitle": False}
    assert window_inventory_arguments(text) == expected
    assert operation_domain_is_grounded(text, "window.resolve") is True
    result = resolve_explicit_effects(text, {"window.active", "window.resolve"})
    assert result is not None and result.operations == ("window.resolve",)
    assert _ground_explicit_arguments("window.resolve", text, SCHEMA) == expected
    assert _ground_explicit_arguments("window.resolve", result.evidence[0], SCHEMA) == expected


@pytest.mark.parametrize("value", [1, 2, 7, 20, 50])
@pytest.mark.parametrize("pattern", ["Muestra las primeras {value} ventanas.", "Show the first {value} open windows."])
def test_explicit_page_size_uses_the_catalog_bound(value, pattern):
    assert _ground_explicit_arguments("window.resolve", pattern.format(value=value), SCHEMA) == {
        "process": "*", "byTitle": False, "limit": value,
    }


@pytest.mark.parametrize("text", [
    "Muestra las primeras cinco ventanas.", "Show the first five windows.",
])
def test_spoken_cardinal_supplies_the_same_page_size(text):
    assert _ground_explicit_arguments("window.resolve", text, SCHEMA)["limit"] == 5


@pytest.mark.parametrize("text", [
    "Muestra las primeras 0 ventanas.", "Show the first 51 windows.",
    "Muestra las ventanas de Opera.", "List the windows of Nimbus 47.",
    "Show my browser windows.", "Muestra las ventanas minimizadas.",
    "No muestres las ventanas.", "Don't show all windows.",
    "Muéstrame las ventanas que tenía ayer.", "Show the windows I had yesterday.",
    "Muestra las ventanas en mi teléfono.", "List the windows on another computer.",
    "Muestra las ventanas y cierra Notepad.", "List the windows and delete report.txt.",
    "Translate 'Show all open windows'.", "«Lista todas las ventanas».",
    "Escribe una nota que diga: muestra las ventanas.",
    "Dime cuántas ventanas hay abiertas sin usar herramientas.",
    "Explica cómo sellar las ventanas de la cocina.", "Quiero pintar las ventanas de mi casa.",
    "Enumera los tipos de ventanas de aluminio.", "Why does glass fog up on house windows?",
    "List the windows shown on this house floor plan.", "What is a window of opportunity?",
    "Explain the Windows operating system.", "Show me window insulation techniques for my house.",
])
def test_a_global_selector_cannot_replace_a_different_request(text):
    assert window_inventory_arguments(text) is None
    assert _ground_explicit_arguments("window.resolve", text, SCHEMA) is None


def test_missing_inventory_operation_does_not_become_foreground():
    assert resolve_explicit_effects("Show all open windows.", {"window.active"}) is None


def test_global_selection_cannot_drop_a_schema_field():
    schema = copy.deepcopy(SCHEMA)
    del schema["properties"]["byTitle"]
    assert _ground_explicit_arguments("window.resolve", "Lista las ventanas.", schema) is None


@pytest.mark.parametrize("text", [
    "Lista las ventanas y luego dime la hora.", "List the windows and then tell me the time.",
])
def test_composition_keeps_inventory_and_clock_as_separate_reads(text):
    result = resolve_explicit_effects(text, {"window.resolve", "system.time"})
    assert result is not None and result.operations == ("window.resolve", "system.time")


def situation(count=2, observed=7, complete=True, offset=0, names=("Atlas", "Vega")):
    return {
        "kind": "operation", "operation": "window.resolve", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {
            "windows": [{"title": names[i % len(names)], "processName": "Example", "foreground": False}
                        for i in range(count)],
            "count": count, "observedCount": observed,
            "complete": complete, "totalCount": observed if complete else None,
            "limit": 2, "offset": offset, "hasMore": offset + count < observed,
            "nextOffset": offset + count if offset + count < observed else None,
            "observationScope": "visible_top_level_windows",
            "pageConsistency": "fresh_enumeration_per_request",
        },
    }


@pytest.mark.parametrize("complete", [True, False])
@pytest.mark.parametrize("observed", [3, 7, 25])
@pytest.mark.parametrize("language", ["es", "en"])
def test_page_count_and_observed_count_remain_distinct(complete, observed, language):
    source = situation(observed=observed, complete=complete)
    original = copy.deepcopy(source)
    text = (
        f"Esta página muestra 2 ventanas: Atlas, Vega; se han observado {observed} ventanas."
        if language == "es" else
        f"This page shows 2 windows: Atlas, Vega; {observed} windows were observed."
    )
    payload = _compose_situation_payload(source, language)
    assert not _payload_fact_defect(text, payload, "List the windows.")
    assert source == original
    assert payload["seen"]["count"] == 2
    assert payload["seen"]["totalCount"] == (observed if complete else None)


@pytest.mark.parametrize("reply,complete,valid", [
    ("Hay siete ventanas en total; en esta página muestro dos ventanas: Atlas, Vega.", True, True),
    ("There are seven windows in total; this page shows two windows: Atlas, Vega.", True, True),
    ("Hay dos ventanas abiertas en total: Atlas y Vega.", True, False),
    ("There are two open windows in total: Atlas and Vega.", True, False),
    ("Hay siete ventanas en total; la lista es parcial.", False, False),
    ("There are seven windows in total; this is a partial list.", False, False),
    ("He observado al menos siete ventanas; esta página incluye Atlas y Vega.", False, True),
    ("At least seven windows were observed; this page includes Atlas and Vega.", False, True),
    ("Esta página contiene tres ventanas: Atlas y Vega.", True, False),
    ("This page contains three windows: Atlas and Vega.", False, False),
    ("Estas son todas las ventanas: Atlas y Vega.", True, False),
    ("These are all the windows: Atlas and Vega.", False, False),
    ("Atlas y Vega.", False, False),
    ("Atlas and Vega.", True, False),
    ("No hay ventanas visibles.", False, False),
    ("There are no visible windows.", True, False),
    ("This page shows two windows; Example is running in the background.", True, False),
    ("Esta página muestra dos ventanas: Atlas y Vega; no comprobé los procesos en segundo plano.", False, True),
])
def test_inventory_claims_preserve_page_total_and_uncertainty(reply, complete, valid):
    payload = _compose_situation_payload(situation(complete=complete), "en")
    assert (not _payload_fact_defect(reply, payload, "List the windows.")) is valid


@pytest.mark.parametrize("complete", [True, False])
def test_an_empty_page_does_not_prove_an_empty_desktop(complete):
    payload = _compose_situation_payload(situation(0, 7, complete, 7), "en")
    assert not _payload_fact_defect("There are no windows in this page.", payload)
    assert _payload_fact_defect("There are no windows.", payload)


def test_complete_empty_inventory_can_report_no_windows():
    payload = _compose_situation_payload(situation(0, 0), "es")
    assert not _payload_fact_defect("No hay ventanas visibles.", payload)


def test_count_only_question_can_answer_the_verified_total_without_listing_a_page():
    payload = _compose_situation_payload(situation(), "es")
    assert not _payload_fact_defect("Hay siete ventanas abiertas.", payload, "¿Cuántas ventanas hay?")


def test_quoted_window_names_cannot_invent_cardinality_claims():
    payload = _compose_situation_payload(situation(names=("99 windows", "No other windows")), "en")
    assert not _payload_fact_defect('This page shows "99 windows" and "No other windows".', payload)


@pytest.mark.parametrize("reply", [
    "Muestro dos de las siete ventanas: Atlas y Vega.",
    "Estas son 2 de un total de 7 ventanas: Atlas, Vega.",
    "Showing two of the seven windows: Atlas and Vega.",
    "Here are 2 windows out of 7: Atlas, Vega.",
])
def test_a_subset_can_express_page_and_total_without_a_prescribed_format(reply):
    payload = _compose_situation_payload(situation(), "en")
    assert not _payload_fact_defect(reply, payload, "List the windows.")
    payload["seen"]["totalCount"] = None
    payload["seen"]["complete"] = False
    assert _payload_fact_defect(reply, payload, "List the windows.") == "extra_claim"


class Recorder(LlmRuntime):
    def __init__(self, model):
        self._gguf = model
        self.requests = []
        self.replies = iter([
            "There are two open windows in total: Atlas and Vega.",
            "There are seven windows in total; this page shows two windows: Atlas and Vega.",
        ])

    def _post(self, payload):
        self.requests.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("model", ["Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "K2-Horizon-3.7B-Q4_K_M.gguf"])
def test_actual_compositor_repairs_page_as_total_for_each_model(model):
    client = Recorder(model)
    reply = client.compose_user_message("List the windows.", "status", {"situation": situation()})
    assert reply == "There are seven windows in total; this page shows two windows: Atlas and Vega."
    assert len(client.requests) == 2
