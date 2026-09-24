"""Fase 3.5: forms the real conversations showed and the pattern did not read.

What people think of a public work and a record or dated fact are looked up, not answered from
the model's memory; an order said after talk is still the order; a dictated clipboard literal may
lose its closing quote. Phrases are not the owner's test nor the held-out script.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.effect_intent import EffectIntent
from baxy_mind.semantic.ui import literal_clipboard_write_text
from baxy_mind.semantic.web import public_opinion_query, record_fact_query


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("¿El último disco de Bad Bunny es bueno?", "último disco de Bad Bunny opiniones"),
        ("¿Dune 2 vale la pena?", "Dune 2 opiniones"),
        ("crees que la saga Hunger Games vale la pena", "saga Hunger Games opiniones"),
        ("qué dice la crítica de Barbie", "Barbie opiniones"),
        ("críticas de la serie Severance", "serie Severance opiniones"),
        ("is Baldur's Gate 3 worth it?", "Baldur's Gate 3 reviews"),
    ],
)
def test_the_opinion_of_a_public_work_is_looked_up(text, query):
    assert public_opinion_query(text) == query


@pytest.mark.parametrize(
    "text",
    [
        "el disco es malísimo",  # not a quality word the reader knows, and not asked
        "la peli es buena",  # the person's own opinion, not a question
        "¿el libro es bueno?",  # a bare noun names no work
        "¿mi ensayo es bueno?",  # personal
        "¿esta serie vale la pena?",  # deictic: the topic is in the dialogue, not here
        "¿el café de acá es bueno?",  # not a work
    ],
)
def test_talk_personal_and_deictic_things_are_not_public_opinions(text):
    assert public_opinion_query(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "cuál fue el primer videojuego de la historia",
        "y quién fue la primera mujer en el espacio",
        "cuándo se estrena la nueva de Spider-Man",
        "what was the first Pixar movie",
    ],
)
def test_a_record_or_release_fact_is_looked_up_in_the_persons_words(text):
    assert record_fact_query(text) is not None
    assert record_fact_query(text).lower() in text.lower()


@pytest.mark.parametrize(
    "text",
    ["cuál fue el último archivo que abrí", "cuál fue la primera nota", "cuál fue la última cosa que te dije"],
)
def test_local_and_dialogue_records_are_not_public_facts(text):
    assert record_fact_query(text) is None


def _resolve_orders(tail: str) -> EffectIntent | None:
    folded = tail.lower()
    if folded.startswith(("poné ", "pon ", "abrí ", "abre ", "subí ")):
        return EffectIntent(("stub.effect",), (tail,))
    return None


@pytest.mark.parametrize(
    "text",
    [
        "Qué buena charla, che, hablando de viajes, poné música de Brasil",
        "jaja sí, abrí la calculadora",
        "Uf, qué día. Bueno. Subí el brillo al 70",
    ],
)
def test_the_order_after_talk_is_the_request(text):
    found = mind._order_with_talk(text, _resolve_orders)
    assert found is not None and found.evidence[0].lower().startswith(("poné", "abrí", "subí"))


@pytest.mark.parametrize(
    "text",
    [
        "Si mañana llueve, abrí el clima",  # a condition
        "Mi prima me dijo, poné música de Brasil",  # reported speech
        "cuando termine la descarga, abrí la carpeta",  # a condition
        "abrí Spotify",  # nothing before the order
    ],
)
def test_conditions_and_reported_speech_do_not_become_orders(text):
    assert mind._order_with_talk(text, _resolve_orders) is None


def test_a_dictated_literal_without_its_closing_quote_is_still_the_literal():
    assert literal_clipboard_write_text('copiá al portapapeles "nos vemos a las 8') == "nos vemos a las 8"
    assert literal_clipboard_write_text('copiá "uno" y "dos al portapapeles') is None


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("fijate cuándo se estrena la segunda de Arcane", "record"),
        ("averiguá qué dice la crítica de Wicked", "opinion"),
        ("buscame cuál fue el primer Pokémon", "record"),
    ],
)
def test_a_lookup_verb_before_the_question_asks_the_same_lookup(text, kind):
    assert (record_fact_query(text) if kind == "record" else public_opinion_query(text)) is not None
