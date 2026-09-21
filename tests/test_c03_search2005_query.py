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


def test_a_search_report_names_a_site_not_only_titles() -> None:
    # SEARCH2005 case 2: five titles with snippets and no site name no page a person can open.
    from baxy_mind.llm import _search_report_without_source
    payload = {"operation": "web.search", "seen": {"results": [
        {"title": "47 Homemade Pizza Recipes That Are Faster Than Delivery", "url": "https://www.tasteofhome.com/collection/homemade-pizza-recipes/", "snippet": "skip the delivery"},
        {"title": "15 Homemade Pizza Recipes That Taste Better Than Delivery", "url": "https://www.allrecipes.com/pizza/", "snippet": "Detroit-style"},
    ]}}
    titles_only = "47 Homemade Pizza Recipes That Are Faster Than Delivery - skip the delivery. 15 Homemade Pizza Recipes That Taste Better Than Delivery - Detroit-style."
    assert _search_report_without_source(titles_only, payload, "search for pizza recipes") is True
    with_site = "I found «47 Homemade Pizza Recipes That Are Faster Than Delivery» on tasteofhome.com and «15 Homemade Pizza Recipes» on allrecipes.com."
    assert _search_report_without_source(with_site, payload, "search for pizza recipes") is False


def test_the_grounded_query_argument_drops_the_courtesy_too() -> None:
    # SEARCH2011: the argument grounder has its own search regex.
    from baxy_mind.__main__ import _explicit_arguments_from_evidence
    assert _explicit_arguments_from_evidence("web.search", "Buscá Transformers, porfa") == {"query": "Transformers"}
    assert _explicit_arguments_from_evidence("web.search", "buscame recetas de pizza, por favor") == {"query": "recetas de pizza"}
