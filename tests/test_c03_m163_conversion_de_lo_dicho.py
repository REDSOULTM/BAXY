"""M163 (2026-10-04, product mind run mind/v4y-w — written history with BAXY's greeting before it — against the
isolated decider full3 with the same history; owner rules D35, D52, D58 and D61): a figure BAXY has just said, asked in
another unit, is converted in the talk, never looked up.

The largest class of decision ballast left in the sealed set was «action (web.search) where the gold is talk», mostly
follow-ups. Two of them are conversions. G-w16-t3 «uy y eso cuánto sería en fahrenheit, es que yo no entiendo bien
celsius» after «En Cali hay 29°C y soleado.»: the decider talked, and M104 read the person's words as a figure of the
world and searched them. G-w08-t3 «brilliant, so if the recipe wants 300 g of that, how many cups is it» after «Around
200 g per cup of caster sugar.»: the decider talked, and M88 read its restatement «How many cups is 300 g of caster
sugar?» as a kitchen quantity and searched it.

Now (``semantic.knowledge.converted_from_what_was_said``, through M162's ``worked_out_from_what_was_said``): a figure of
BAXY's last answer asked in another unit of one kind with a fixed factor or formula (°C↔°F, kg↔lb, km↔miles; the units
of ``semantic.quantities``), or the person's own figure converted by the equivalence BAXY's last answer said («200 g per
cup»), stays the decider's talk (D35: calculations are worked out with units). The message points back at what was said
or names nothing the conversation did not. Decision D35/D52/D61 is kept for the rest: how many cups a weight of a named
ingredient is, with no equivalence said, is a density — a figure of the world — and is still looked up (M88), and so is
a figure nobody said and an amount in another currency (M154). Decisions the decider took (an action) are not touched
(D58).

Rows are quoted with their real text and their written history (the greeting before it, as the App has it) or the
history the App lived (window v4y); every other phrasing is our own.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.knowledge import converted_from_what_was_said, reference_lookup, worked_out_from_what_was_said
from test_c03_m154_cifra_se_consulta import _turn
from test_c03_m157_regresiones_v4v import I_W41

GREETING = "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"


def _talk(request: str) -> ContextDecision:
    return ContextDecision(request, "talk", (), "")


def _worked(said: list[str], greeting: bool = False) -> bool:
    """``said``: the conversation, user first and alternating, ending in the person's message; ``greeting`` puts BAXY's
    greeting before it, as the App's history has it."""

    earlier = said[:-1]
    return worked_out_from_what_was_said(said[-1], [*([GREETING] if greeting else []), *earlier[1::2]], earlier[0::2])


def _talked(result: dict) -> bool:
    return result["kind"] == "conversation" and result["operation"] is None


def _searched(result: dict) -> bool:
    return (result["kind"], result["operation"]) == ("action", "web.search")


# ------------------------------------------------------------------ 1. the rows

G_W16 = [
    "parce, antes de salir pa la oficina necesito que me digas si en medellín va a llover o hace sol",
    "Ahorita en Medellín están a 24°C, con el cielo medio nublado.",
    "¿y en cali?",
    "En Cali hay 29°C y soleado.",
    "uy y eso cuánto sería en fahrenheit, es que yo no entiendo bien celsius",
]
G_W08 = [
    "roughly how many grams is a cup of plain flour",
    "About 125 g for a cup of plain flour, spooned in and levelled.",
    "and caster sugar?",
    "Around 200 g per cup of caster sugar.",
    "brilliant, so if the recipe wants 300 g of that, how many cups is it",
]
# What BAXY said in the App run (window v4y-devG) before the same messages.
G_W16_LIVED = [
    *G_W16[:3],
    "En Santiago de Cali hoy nublado con máximo de 28.8 °C y mañana llovizna con probabilidad de lluvia del 80 %.",
    G_W16[-1],
]
G_W08_LIVED = [*G_W08[:3], "One cup of caster sugar weighs about 225 grams.", G_W08[-1]]


@pytest.mark.parametrize(
    ("said", "restated", "kind"),
    [
        (G_W16, "uy y eso cuánto sería en fahrenheit, es que yo no entiendo bien celsius", "figure"),
        (G_W08, "How many cups is 300 g of caster sugar?", "quantity"),
        (G_W16_LIVED, "uy y eso cuánto sería en fahrenheit, es que yo no entiendo bien celsius", "figure"),
        (G_W08_LIVED, "How many cups is 300 grams of caster sugar?", "quantity"),
    ],
    ids=["G-w16-t3", "G-w08-t3", "G-w16-t3-lived", "G-w08-t3-lived"],
)
def test_a_conversion_of_what_baxy_said_stays_the_deciders_talk(said: list[str], restated: str, kind: str) -> None:
    # The decider's restatement alone is a lookup (that is what went wrong); the conversion of what was said is not.
    found = reference_lookup(restated)
    assert found is not None and found.kind == kind
    assert _worked(said) and _worked(said, greeting=True)
    assert _talked(_turn(said, _talk(restated)))


def test_i_w41_t2_ounces_of_the_grams_said_are_a_conversion() -> None:
    # DEV-I written history: the grams were said, so ounces are a fixed factor away.
    said = [I_W41[0], "3 tazas de harina de trigo son unos 375 g (125 g por taza).", "¿y en onzas?"]
    assert _worked(said, greeting=True)
    assert _talked(_turn(said, _talk("¿Cuántas onzas son 375 gramos?")))


# ------------------------------------------------------------------ 2. our own variants, es and en


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # A figure BAXY said, in another unit of a fixed factor or formula.
        (["cuánto se puede llevar en la maleta de bodega", "En la maleta de bodega puedes llevar hasta 23 kg.",
          "¿y eso cuánto es en libras?"], "¿Cuánto pesa la maleta de bodega en libras?"),
        (["how far is Paris from London", "Paris is about 344 km from London.", "how far is that in miles?"],
         "How far is Paris from London in miles?"),
        (["what's the weather in London", "It's 18 °C and cloudy in London right now.",
          "and how much is that in fahrenheit?"], "and how much is that in fahrenheit?"),
        (["¿qué tan alto es el Aconcagua?", "El Aconcagua mide 6.961 metros.", "pásamelo a pies"],
         "¿Qué tan alto es el Aconcagua en pies?"),
        # The person's own figure, by the equivalence BAXY said.
        (["¿cuánto pesa una taza de azúcar?", "Una taza de azúcar son unos 200 g.",
          "y si la receta pide 450 g de eso, ¿cuántas tazas son?"], "¿Cuántas tazas son 450 g de azúcar?"),
        (["how much does a cup of plain flour weigh", "About 125 g per cup of plain flour.",
          "so 2 cups of it would be how many grams?"], "How many grams are 2 cups of plain flour?"),
    ],
    ids=["es-libras", "en-miles", "en-fahrenheit", "es-pies", "es-tazas-por-lo-dicho", "en-grams-by-what-was-said"],
)
def test_conversions_of_what_was_said_in_other_words(said: list[str], restated: str) -> None:
    assert reference_lookup(restated) is not None
    assert _worked(said)
    assert _talked(_turn(said, _talk(restated)))


# ------------------------------------------------------------------ 3. what must not change


def test_another_currency_is_still_looked_up() -> None:
    # M154: an amount in another currency needs a rate nobody said; «libras» after euros are pounds sterling.
    said = ["cuánto cuesta el PlayStation 5 en Estados Unidos", "El PlayStation 5 cuesta 499 dólares allá.",
            "¿y eso en euros?"]
    assert not _worked(said)
    assert _searched(_turn(said, _talk("¿Cuántos euros son 499 dólares?")))
    assert not _worked(["cuánto cuesta el abono", "El abono cuesta 500 euros.", "¿y en libras?"])


def test_a_figure_nobody_said_is_not_made_up() -> None:
    # No conversation: the elephant's weight is a figure of the world.
    alone = ["¿cuánto pesa un elefante en libras?"]
    assert not _worked(alone) and not _worked(alone, greeting=True)
    assert _searched(_turn(alone, _talk("¿Cuánto pesa un elefante en libras?")))
    # A figure in kilos said of something else is no elephant.
    said = ["cuánto pesa un rinoceronte", "El rinoceronte blanco pesa unos 2.300 kg.", "¿cuánto pesa un elefante en libras?"]
    assert not _worked(said)
    assert _searched(_turn(said, _talk("¿Cuánto pesa un elefante en libras?")))


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # The rows' words with no conversation before them (the App's greeting alone).
        ([G_W16[-1]], G_W16[-1]),
        ([G_W08[-1]], "How many cups is 300 g of caster sugar?"),
    ],
    ids=["G-w16-t3-alone", "G-w08-t3-alone"],
)
def test_the_same_words_with_no_conversation_do_not_change(said: list[str], restated: str) -> None:
    assert not _worked(said) and not _worked(said, greeting=True)
    assert _searched(_turn(said, _talk(restated)))


def test_grams_to_cups_with_no_equivalence_said_is_still_the_kitchen_quantity() -> None:
    # D35/D52/D61 and M88: a recipe's amounts side by side say no density; how many cups 500 g of flour is, is looked
    # up (DEV-G G-w25-t2, written history; its gold accepts the lookup).
    said = [
        "oye como se hacen las sopaipillas pasadas",
        "Mezcla 500 g de harina, 250 g de zapallo cocido molido, 60 g de manteca derretida, 1 cdta de polvos de hornear "
        "y sal; estira, corta y fríe. Luego hiérvelas unos minutos en almíbar de chancaca con canela y cáscara de naranja.",
        "y los 500 gramos de harina cuantas tazas son",
    ]
    assert not _worked(said, greeting=True)
    assert _searched(_turn(said, _talk("¿Cuántas tazas son 500 gramos de harina?")))
    # The equivalence said is about another ingredient than the one asked now.
    other = [*G_W08[:4], "brilliant, so if the recipe wants 300 g of flour, how many cups is it"]
    assert not _worked(other)
    assert _searched(_turn(other, _talk("How many cups is 300 g of flour?")))
    # Ounces of cups nobody turned into grams (DEV-I I-w41 in the App run): a density again.
    assert not converted_from_what_was_said(I_W41[2], [I_W41[1]], [I_W41[0]])


def test_translations_are_as_m157_left_them() -> None:
    # M157 (I-w41-t3): «tradúceme eso al inglés» names no unit; it is no conversion.
    assert not converted_from_what_was_said(I_W41[-1], [I_W41[1], I_W41[3]], [I_W41[0], I_W41[2]])
    assert _talked(_turn(I_W41, _talk("Traduce al inglés «¿Cuántas onzas son 3 tazas de harina de trigo?».")))


@pytest.mark.parametrize(
    "said",
    [
        # Another reading in the unit asked is a new read, not the figure said converted.
        [*G_W16[:4], "¿y mañana en fahrenheit?"],
        # A unit of another kind than the figure said.
        [*G_W16[:4], "¿y en millas?"],
        # The unit the figure was already said in.
        ["how far is Paris from London", "Paris is about 344 km from London.", "and how many kilometers to Brussels?"],
    ],
    ids=["new-read", "other-kind", "same-unit-new-place"],
)
def test_neighbours_that_are_no_conversion_of_what_was_said(said: list[str]) -> None:
    assert not converted_from_what_was_said(said[-1], said[1::2], said[0:-1:2])


def test_an_action_the_decider_chose_is_not_touched() -> None:
    # D58: the guard only keeps the decider's talk; its own search stays a search.
    searched = ContextDecision("¿Cuántos grados Fahrenheit son 29 °C?", "action", ("web.search",), "")
    assert _searched(_turn(G_W16, searched))
