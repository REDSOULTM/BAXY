"""Pasada v3 r9, v3-57 (vivo 2026-10-08): «abre edge en una pestaña nueva y busca clima en guadalajara» devolvió
«¿Cuál es la URL final del resultado de la búsqueda de «clima en Guadalajara»?». Causa medida: el lector de una
búsqueda en un navegador nombrado exigía que la cláusula de apertura fuera sólo el navegador; «en una pestaña nueva» la
dejaba sin URL y la extracción preguntó por un dato que la persona no tiene que dar. La pestaña nueva donde abre el
navegador no es otro navegador. Contracasos: otro navegador nombrado para la búsqueda, una pestaña que no es el lugar
donde se abre, y una ventana pedida (revisión de r9, hallazgo 8: la navegación nombrada abre una pestaña, nunca honra
«en otra ventana», así que ese pedido no se lee como ella).
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic import arguments as semantic_arguments
from baxy_mind.semantic import patterns

_OPERATIONS = ("browser.navigate.named", "browser.navigate", "web.search", "app.open", "mission.computer.use")


@pytest.mark.parametrize(("said", "browser", "query"), [
    ("abre edge en una pestaña nueva y busca clima en guadalajara", "edge", "clima en guadalajara"),
    ("abre edge en una nueva pestaña y busca clima en guadalajara", "edge", "clima en guadalajara"),
    ("abre chrome en otra pestaña y busca recetas de pan", "chrome", "recetas de pan"),
    ("open chrome in a new tab and search weather in paris", "chrome", "weather in paris"),
])
def test_a_search_in_a_named_browser_opened_in_a_new_tab_is_grounded(said: str, browser: str, query: str) -> None:
    assert patterns._named_browser_search(said) == (browser, query)
    read = patterns.resolve_explicit_effects(said, _OPERATIONS, ("Microsoft Edge",))
    assert read is not None and read.operations == ("browser.navigate.named",)
    grounded = semantic_arguments._explicit_browser_navigation_arguments("browser.navigate.named", said)
    assert grounded is not None and grounded["browser"] == browser and grounded["url"].startswith("https://")


@pytest.mark.parametrize("said", [
    "abre edge en una pestaña nueva y busca clima en guadalajara en opera",
    "abre edge con una pestaña de clima y busca recetas",
    "abre chrome en otra ventana y busca recetas de pan",
    "abre edge en una nueva ventana y busca clima en lima",
    "open edge in the window and search weather",
    "abre edge en la pestaña y busca clima",
])
def test_a_new_tab_never_hides_another_browser_or_another_clause(said: str) -> None:
    assert patterns._named_browser_search(said) is None
