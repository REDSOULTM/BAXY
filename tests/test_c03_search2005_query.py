"""SEARCH2005 (H0098 «buscá recetas de pizza», H0380 «Busca Transformers»): the voseo clitic and a
trailing courtesy are the person's way of asking, not part of the query."""

from __future__ import annotations

import pytest

from baxy_mind.effect_intent import _direct_public_search_query


@pytest.mark.parametrize(
    "text,query",
    [
        ("buscá recetas de pizza", "recetas de pizza"),
        ("dale, buscame recetas de pizza", "recetas de pizza"),
        ("buscame recetas de pizza, porfa", "recetas de pizza"),
        ("Buscá Transformers, porfa", "Transformers"),
        ("search Transformers please", "Transformers"),
        ("search for pizza recipes", "pizza recipes"),
    ],
)
def test_search_query_drops_the_clitic_and_the_courtesy(text: str, query: str) -> None:
    assert _direct_public_search_query(text) == query


def test_a_search_answer_neither_lists_pages_nor_names_sites() -> None:
    # SEARCH2005 case 2 asked for the site of each page. Owner rule 2026-09-24 reverses that intent: the lookup
    # is invisible, so a list of pages with their sites is the search shown; the answer itself is what is said.
    from baxy_mind.llm import _payload_fact_defect
    payload = {"operation": "web.search", "seen": {"results": [
        {"title": "47 Homemade Pizza Recipes That Are Faster Than Delivery", "url": "https://www.tasteofhome.com/collection/homemade-pizza-recipes/", "snippet": "skip the delivery"},
        {"title": "15 Homemade Pizza Recipes That Taste Better Than Delivery", "url": "https://www.allrecipes.com/pizza/", "snippet": "Detroit-style"},
    ]}}
    with_site = "I found «47 Homemade Pizza Recipes That Are Faster Than Delivery» on tasteofhome.com and «15 Homemade Pizza Recipes» on allrecipes.com."
    assert _payload_fact_defect(with_site, payload, "search for pizza recipes") == "search_report_shows_the_search"
    answer = "There are homemade pizza recipes that are faster than delivery, including a Detroit-style one."
    assert _payload_fact_defect(answer, payload, "search for pizza recipes") == ""


def test_the_grounded_query_argument_drops_the_courtesy_too() -> None:
    # SEARCH2011: the argument grounder has its own search regex.
    from baxy_mind.__main__ import _explicit_arguments_from_evidence
    assert _explicit_arguments_from_evidence("web.search", "Buscá Transformers, porfa") == {"query": "Transformers"}
    assert _explicit_arguments_from_evidence("web.search", "buscame recetas de pizza, por favor") == {"query": "recetas de pizza"}


def test_the_reports_own_narration_words_are_not_unsourced_claims() -> None:
    # SEARCH2015 H0098: counting the results and saying what a page offers is the report's voice.
    from baxy_mind.llm import _search_report_unsourced_claim
    payload = {"operation": "web.search", "seen": {"results": [
        {"title": "31 recetas de pizza casera: una pizza para cada día del mes", "url": "https://www.directoalpaladar.com/recetario/31-recetas", "snippet": "Cómo hacer pizza casera de forma fácil: las mejores recetas tradicionales y originales."},
        {"title": "Cómo hacer PIZZA CASERA - Receta de masa FÁCIL - RecetasGratis", "url": "https://recetas.elperiodico.com/receta-de-pizza-casera-31391.html", "snippet": "Receta de masa perfecta explicada paso a paso."},
    ]}}
    report = ("Se encontraron cinco resultados sobre recetas de pizza. Una página titulada «31 recetas de pizza casera» de "
              "directoalpaladar.com menciona cómo hacer pizza casera de forma fácil. Finalmente, «Cómo hacer PIZZA CASERA» "
              "de recetas.elperiodico.com ofrece una receta de masa perfecta explicada paso a paso.")
    assert _search_report_unsourced_claim(report, payload, "buscá recetas de pizza") is False
    invented = "La página de directoalpaladar.com menciona que la pizza se inventó en Nápoles en 1889."
    assert _search_report_unsourced_claim(invented, payload, "buscá recetas de pizza") is True


def test_the_unsourced_hint_names_the_words_no_result_uses() -> None:
    # SEARCH2019: the hint names the paraphrased words so the model keeps the report and drops them.
    from baxy_mind.llm import _search_report_unsourced_words
    payload = {"operation": "web.search", "seen": {"results": [
        {"title": "Cómo hacer PIZZA CASERA - Receta de masa FÁCIL", "url": "https://recetas.elperiodico.com/receta-de-pizza-casera-31391.html", "snippet": "Receta de masa perfecta explicada paso a paso."},
    ]}}
    report = "«Cómo hacer PIZZA CASERA» de recetas.elperiodico.com ofrece instrucciones para una masa perfecta."
    assert _search_report_unsourced_words(report, payload, "buscá recetas de pizza") == ["instrucciones"]
