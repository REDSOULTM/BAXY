"""Goal computer use v3, regresiones medidas en vivo (regr6, 2026-10-08), each with its counter-cases.

- Tanda 3 c06 «busca en google como hacer un pivot table en excel pls» answered from memory: a how-to that is the query
  of a Google search was read as a how-to asked of BAXY (grammar._is_explicit_meta_or_tool_denial) or as a research
  question for web.search (web._research_question_query); it is Google's results page in the person's browser.
- Tanda 3 c03 «dame 5 juegos cooperativos … que no pidan mucha compu» listed the Steam library: games of a kind are
  not the library unless they are the person's or this PC's (games.games_of_this_pc).
- Tanda 3 c18 «ahora ponla en modo programador», restated «En la Calculadora, haz clic en «Programador»»: a mode clicked
  or selected by name behind a closed navigation opens the navigation (cu_rules.deterministic_step).
- Tanda 3 c16 «che y cómo se llamaba el que cantaba» (Soda Stereo) → «los hermanos Astudillo»: who holds a role in a
  named work or group is looked up (knowledge reference kind ``person``).
"""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind import cu_rules
from baxy_mind.semantic import knowledge
from baxy_mind import argument_grounding

AVAILABLE = (
    "web.search", "browser.navigate", "browser.navigate.named", "web.news.headlines", "task.list",
    "game.catalog.list", "game.entitlement.named", "app.installed", "app.open", "mission.computer.use",
)
NAVIGATE_SCHEMA = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"],
                   "additionalProperties": False}


def _read(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    return intent.operations if intent is not None else None


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("busca en google como hacer un pivot table en excel pls", "como+hacer+un+pivot+table+en+excel+pls"),
        ("busca en google por qué falla whatsapp", None),
        ("googlea como se hace un nudo de corbata", None),
    ],
)
def test_a_how_to_searched_on_google_opens_googles_results_page(text: str, query: str | None) -> None:
    assert _read(text) == ("browser.navigate",)
    url = argument_grounding._ground_explicit_arguments("browser.navigate", text, NAVIGATE_SCHEMA)["url"]
    assert url.startswith("https://www.google.com/search?q=")
    if query is not None:
        assert url.endswith(query)


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        ("investiga en internet por qué falla WhatsApp", ("web.search",)),  # no engine named: the public search
        ("busca como hacer un pivot table en excel", ("web.search",)),
        ("explicame como hacer pan", None),  # a how-to asked of BAXY stays talk
        ("como hacer un pivot table en excel", None),
        ("no uses herramientas, busca en google gatos", None),  # a no-tool constraint still holds
    ],
)
def test_counter_cases_of_the_google_how_to(text: str, operations: tuple[str, ...] | None) -> None:
    assert _read(text) == operations


@pytest.mark.parametrize(
    "text",
    [
        "dame 5 juegos cooperativos pa jugar con mis primos en la pc que no pidan mucha compu",
        "dame 5 juegos cooperativos",
    ],
)
def test_games_of_a_kind_are_not_the_library(text: str) -> None:
    assert _read(text) != ("game.catalog.list",)


@pytest.mark.parametrize(
    "text",
    [
        "qué juegos tengo instalados",
        "Lista mis juegos de Steam",
        "Que juegos estan instalados en Steam?",
        "Show installed Steam games",
        "what games do I have",
        "Lista mi biblioteca de juegos de Steam",
    ],
)
def test_the_persons_games_are_the_library(text: str) -> None:
    assert _read(text) == ("game.catalog.list",)


_NAVIGATION_CLOSED = {
    "window": {"title": "Calculadora", "process": "CalculatorApp", "requested": True,
               "rect": {"x": 0, "y": 0, "w": 700, "h": 800}, "focused": {"kind": "Button", "name": "Multiplicar por"}},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Cerrar Calculadora", "zone": "TR"},
        {"i": 1, "kind": "Button", "name": "Abrir navegación", "zone": "TL"},
        {"i": 2, "kind": "Button", "name": "Más", "zone": "B"},
        {"i": 3, "kind": "Button", "name": "Siete", "zone": "L"},
    ],
    "text": {"TL": ["Calculadora", "Estándar"]},
}
_NAVIGATION_OPEN = {
    **_NAVIGATION_CLOSED,
    "controls": [
        {"i": 0, "kind": "Button", "name": "Cerrar navegación", "zone": "TL"},
        {"i": 1, "kind": "ListItem", "name": "Estándar Calculadora", "state": "selected", "zone": "L"},
        {"i": 2, "kind": "ListItem", "name": "Programador Calculadora", "zone": "L"},
    ],
    "newText": ["Estándar", "Programador"],
}


@pytest.mark.parametrize("goal", ["hacer clic en Programador", "hacer clic en «Programador»", "seleccionar modo programador",
                                  "seleccionar programador"])
def test_a_mode_clicked_or_selected_by_name_opens_the_navigation_first(goal: str) -> None:
    history = [{"step": 1, "operation": "app.open", "ok": True, "appId": "Calculadora"}]
    first = cu_rules.deterministic_step(goal=goal, view=_NAVIGATION_CLOSED, history=history, application="Calculadora")
    assert first == {"operation": "input.visible.click", "arguments": {"label": "Abrir navegación", "index": 1},
                     "reason": "el destino no está en pantalla: abro la navegación"}
    opened = [*history, {"step": 2, "operation": "input.visible.click", "label": "Abrir navegación", "index": 1, "ok": True}]
    picked = cu_rules.deterministic_step(goal=goal, view=_NAVIGATION_OPEN, history=opened, application="Calculadora")
    assert picked["arguments"] == {"label": "Programador Calculadora", "index": 2}


def test_a_click_on_a_name_that_is_no_mode_is_looked_up_as_before_not_in_the_navigation() -> None:
    # A name that is no mode goes on as it did (its own lookup, here the window's search), never to the navigation.
    step = cu_rules.deterministic_step(goal="hacer clic en Guardar", view=_NAVIGATION_CLOSED, history=[])
    assert step is None or step["arguments"].get("label") != "Abrir navegación"


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("¿Cómo se llamaba el que cantaba en el video de Soda Stereo?", "cantante de Soda Stereo"),
        ("quién era el cantante de Soda Stereo", "cantante de Soda Stereo"),
        ("como se llama el que escribió Cien años de soledad", "autor de Cien años de soledad"),
        ("who was the lead singer of Queen", "lead singer of Queen"),
        ("who directed Inception", "director of Inception"),
    ],
)
def test_who_holds_a_role_in_a_named_work_is_looked_up(text: str, query: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is not None and lookup.kind == "person" and lookup.query == query


@pytest.mark.parametrize(
    "text",
    [
        "che y cómo se llamaba el que cantaba",  # nothing named: the conversation's restatement names it
        "quién canta en la ducha",
        "quién es el dueño de mi casa",  # the person's own life
        "quien es el que canta eso",
        "quién ganó el mundial 2022",
    ],
)
def test_no_named_work_no_role_lookup(text: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is None or lookup.kind != "person"
