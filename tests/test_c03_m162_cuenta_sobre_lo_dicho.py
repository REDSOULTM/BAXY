"""M162 (2026-10-04, product mind run mind/v4w against the isolated decider full3 with the same written history; owner
rules D35, D52 and D58): a sum on numbers BAXY has just said is worked out with those numbers, never looked up.

In a follow-up the decider talked — it scaled the recipe it had just given, or compared the two figures it had just
said — and the product ended in web.search. The lookup came from M53/M104 reading the decider's restatement, never the
person's words: «¿Cuánto le hago a la receta de chipá para tres personas?» (I-w08-t2) and «¿Cómo queda la receta de
sopaipillas pasadas para el doble de gente?» (H-w31-t3) as a recipe, «¿Cuánta harina necesito para hacer 20
sopaipillas?» (I-w18-t2) as a kitchen quantity (M88), «¿Cuánto es la brecha en porcentaje entre el dólar blue y el
oficial del Banco Nación?» (H-w24-t3) and «¿Cuánta diferencia horaria hay entre Buenos Aires y Lima?» (H-w08-t3) as
figures of the world (M104). M118 had already kept a rate of what BAXY said («¿y eso cuánto sale por metro?»).

Now (``semantic.knowledge.worked_out_from_what_was_said``): a recipe scaled by a factor or to a count, a difference, a
gap, a percentage or a proportion of what BAXY said stays the decider's talk when every number it needs was said (the
amounts; for a count also the yield they make; two figures for a comparison) and the message names nothing the
conversation did not. What needs a fact nobody said — a currency's rate (M154), another recipe, the calories nobody
gave, a figure of the world — is still looked up. The hours apart from here right after BAXY told one place's clock
(H-w08-t3 «cuánta diferencia hay con aquí») are that place's clock read, as «allá» is in M84
(``semantic.temporal.hours_apart_from_the_clock_told``); the difference is computed on the reading
(``llm._place_clock_facts``), whose instant the test fixes (M108).

Rows are quoted with their real text and their written history; every other phrasing is our own.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.knowledge import reference_lookup, worked_out_from_what_was_said
from baxy_mind.semantic.temporal import hours_apart_from_the_clock_told
from test_c03_m154_cifra_se_consulta import _turn
from test_c03_m157_regresiones_v4v import I_W41


def _talk(request: str) -> ContextDecision:
    return ContextDecision(request, "talk", (), "")


def _worked(said: list[str]) -> bool:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    earlier = said[:-1]
    return worked_out_from_what_was_said(said[-1], earlier[1::2], earlier[0::2])


def _talked(result: dict) -> bool:
    return result["kind"] == "conversation" and result["operation"] is None


def _searched(result: dict) -> bool:
    return (result["kind"], result["operation"]) == ("action", "web.search")


# ------------------------------------------------------------------ 1. the rows, with the decider's v4w restatement

I_W08 = [
    "che, pasame una receta de chipá que me salga bien",
    "Rinde para seis personas, unos 30 chipacitos: en un bol juntá 500 g de almidón de mandioca con 250 g de queso "
    "rallado (mitad pategrás, mitad sardo queda bárbaro) y sal; sumá 100 g de manteca blanda, 2 huevos y de a poco 150 "
    "ml de leche hasta que la masa no se pegue. Bolitas tamaño nuez, 20 minutos a 200 °C.",
    "y para la mitad de gente?",
]
I_W18 = [
    "¿me podrías dar una receta de sopaipillas pasadas?",
    "Para unas 12: masa con 500 g de harina, 250 g de zapallo cocido, 60 g de manteca derretida y sal; se fríen y luego "
    "se pasan 5 minutos por un almíbar de 1 chancaca, 1 taza de agua, canela y cáscara de naranja.",
    "y pa hacer 20, ¿cuánta harina sería?",
]
H_W24 = [
    "che, a cuánto está hoy el blue",
    "El dólar blue cerró hoy a $1.385 la compra y $1.405 la venta.",
    "ok y el del banco nación cuánto está?",
    "El oficial del Banco Nación está a $1.240 la venta.",
    "pasame la brecha en porcentaje",
]
H_W31 = [
    "oye, ¿me puedes encargar por Rappi un completo italiano con harta palta del local de la esquina? ando con un "
    "hambre terrible",
    "Pedir delivery por Rappi no está a mi alcance desde el PC; eso lo tendrías que hacer tú en la app.",
    "ya filo, búscame una receta de sopaipillas pasadas entonces",
    "Sopaipillas pasadas: 2 tazas de harina, 1 taza de zapallo cocido, 2 cdas de manteca derretida, 1 cdta de polvos de "
    "hornear y sal; amasas, estiras, cortas, fríes y después las pasas por chancaca derretida con canela y cáscara de "
    "naranja.",
    "y eso pa'l doble de gente cómo queda?",
]
H_W08 = [
    "hora en buenos aires",
    "En Buenos Aires son las 14:10.",
    "y lima, que ahí vive mi primo",
    "En Lima son las 12:10.",
    "cuánta diferencia hay con aquí",
]


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (I_W08, "¿Cuánto le hago a la receta de chipá para tres personas?"),
        (I_W18, "¿Cuánta harina necesito para hacer 20 sopaipillas?"),
        (H_W24, "¿Cuánto es la brecha en porcentaje entre el dólar blue y el oficial del Banco Nación?"),
        (H_W31, "¿Cómo queda la receta de sopaipillas pasadas para el doble de gente?"),
    ],
    ids=["I-w08-t2", "I-w18-t2", "H-w24-t3", "H-w31-t3"],
)
def test_the_sum_on_what_baxy_said_stays_the_deciders_talk(said: list[str], restated: str) -> None:
    # The restatement alone is a lookup (that is what went wrong); the sum on what was said is not.
    assert reference_lookup(restated) is not None
    assert _worked(said)
    assert _talked(_turn(said, _talk(restated)))


def test_h_w08_t3_the_hours_apart_from_here_are_the_clock_read_of_the_place_just_told() -> None:
    result = _turn(H_W08, _talk("¿Cuánta diferencia horaria hay entre Buenos Aires y Lima?"))
    assert (result["kind"], result["operation"]) == ("action", "system.time")
    assert result["objective"] == "¿cuánta diferencia horaria hay entre Lima y aquí?"
    # The difference is computed on the reading (Lima −300, this PC −180, at a fixed instant), never by the writer.
    observed = {
        "version": 1, "utc": "2026-10-04T15:10:00+00:00", "localUtcOffsetMinutes": -180,
        "place": {"name": "Lima", "country": "Perú", "timeZone": "America/Lima", "utcOffsetMinutes": -300,
                  "authority": "named_place_geocoded"},
    }
    facts = llm._place_clock_facts(observed, result["objective"], "es")
    assert (facts["clock"], facts["clockAt"], facts["difference"]) == ("10:10", "Lima", "2 h menos que aquí")


# ------------------------------------------------------------------ 2. our own variants, es and en


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (
            ["give me a pancake recipe", "Serves 4: 200 g flour, 2 eggs, 300 ml milk, 1 tbsp sugar and a pinch of salt.",
             "and for 8 people?"],
            "Give me the pancake recipe for 8 people.",
        ),
        (
            ["what's a good banana bread recipe", "Makes 1 loaf: 3 ripe bananas, 250 g flour, 100 g butter, 150 g "
             "sugar, 2 eggs and 1 tsp baking soda; bake 60 minutes at 175 °C.", "can you halve that?"],
            "Halve the banana bread recipe.",
        ),
        (
            ["dame una receta de panqueques", "Para 4 personas: 2 tazas de harina, 3 huevos y 2 tazas de leche.",
             "¿y cómo sería el triple?"],
            "¿Cómo sería la receta de panqueques para el triple?",
        ),
        (
            ["how much is the Pixel 9 now", "The Pixel 9 is at 799 dollars.", "and the Galaxy S24?",
             "The Galaxy S24 is at 859 dollars.", "what's the difference in percent?"],
            "What is the price difference in percent between the Pixel 9 and the Galaxy S24?",
        ),
        (
            ["cuánto cuesta el arriendo en Ñuñoa", "Un departamento de dos dormitorios en Ñuñoa ronda los 650.000 "
             "pesos.", "¿y en Providencia?", "En Providencia ronda los 720.000 pesos.", "¿cuánta diferencia hay?"],
            "¿Cuánta diferencia hay entre el arriendo en Ñuñoa y en Providencia?",
        ),
    ],
    ids=["en-for-8", "en-halve", "es-triple", "en-percent", "es-diferencia"],
)
def test_sums_on_what_was_said_in_other_words(said: list[str], restated: str) -> None:
    assert _worked(said)
    assert _talked(_turn(said, _talk(restated)))


@pytest.mark.parametrize(
    ("text", "reply", "expected"),
    [
        ("how many hours ahead of here is that?", "It's 12:10 in Lima right now.",
         "what's the time difference between Lima and here?"),
        ("¿y cuántas horas de diferencia hay con acá?", "Ahora son las 01:09 en Tokio, Japón, el día siguiente.",
         "¿cuánta diferencia horaria hay entre Tokio y aquí?"),
    ],
)
def test_hours_apart_from_here_in_other_words(text: str, reply: str, expected: str) -> None:
    assert hours_apart_from_the_clock_told(text, reply) == expected


# ------------------------------------------------------------------ 3. what must not change


def test_another_currency_is_still_looked_up() -> None:
    # M154: the amount in euros needs a rate nobody said.
    said = ["cuánto cuesta el PlayStation 5 en Estados Unidos", "El PlayStation 5 cuesta 499 dólares allá.",
            "y en euros?"]
    assert not _worked(said)
    assert _searched(_turn(said, _talk("¿Cuántos euros son 499 dólares?")))


def test_another_recipe_and_the_calories_nobody_said_are_still_looked_up() -> None:
    other = [*I_W08[:2], "dame otra receta"]
    assert not _worked(other)
    assert _searched(_turn(other, _talk("Dame otra receta de chipá.")))
    calories = [*I_W18[:2], "¿cuántas calorías tiene?"]
    assert not _worked(calories)
    assert _searched(_turn(calories, _talk("¿Cuántas calorías tiene la receta de sopaipillas pasadas?")))


def test_translations_are_as_m157_left_them() -> None:
    # M157 (I-w41-t3): the words said, asked in English, are talk; «tradúcelo» is no sum.
    assert not _worked(I_W41)
    assert _talked(_turn(I_W41, _talk("Traduce al inglés «¿Cuántas onzas son 3 tazas de harina de trigo?».")))
    # A recipe asked to be translated, restated as the recipe, is still the recipe looked up (M157 left it so).
    said = [*I_W18[:2], "tradúcelo al inglés"]
    assert not _worked(said)
    assert _searched(_turn(said, _talk("Traduce la receta de sopaipillas pasadas al inglés.")))


def test_a_sum_with_no_numbers_said_is_not_made_up() -> None:
    said = ["che, pasame una receta de chipá", "Claro, el chipá lleva almidón de mandioca, queso, manteca, huevo y "
            "leche.", "y para la mitad de gente?"]
    assert not _worked(said)
    assert _searched(_turn(said, _talk("¿Cuánto le hago a la receta de chipá para tres personas?")))
    # To a count, the yield must have been said too: a recipe with amounts and no yield is scaled by nobody.
    assert not _worked(["receta de sopaipillas", "2 tazas de harina y 1 taza de zapallo cocido.",
                        "y pa hacer 20, ¿cuánta harina sería?"])
    # One figure is no comparison (window v4w H-w24: the blue was not found).
    assert not _worked(["a cuánto está el blue", "No encontré un valor específico para el dólar blue hoy.",
                        "y el del banco nación?", "El dólar cerró a $1.545 en el Banco Nación.",
                        "pasame la brecha en porcentaje"])


@pytest.mark.parametrize(
    "said",
    [
        # The same words with no conversation before them.
        ["receta de chipá para la mitad de gente"],
        ["what's the difference in percent?"],
        # A figure nobody said, brought by the person (a new number, a new name).
        ["how much is the iPhone 16", "The iPhone 16 is at 799 dollars.", "and the difference with the iPhone 15?"],
        ["cuánto mide el Everest", "El Everest mide 8.849 metros.", "¿y cuánta diferencia hay con el Aconcagua?"],
        # The same word, another sense: no figures compared.
        ["El blue cerró a 1.405 y el oficial a 1.240.", "Sí.", "¿cuál es la diferencia entre un virus y una bacteria?"],
        # Another dish to a count.
        [*I_W08[:2], "y pa hacer 20 empanadas de pino?"],
    ],
    ids=["no-history-es", "no-history-en", "new-number", "new-name", "other-sense", "other-dish"],
)
def test_neighbours_that_are_not_a_sum_on_what_was_said(said: list[str]) -> None:
    assert not _worked(said)


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("qué hora es aquí", "En Lima son las 12:10."),
        ("cuánta diferencia hay con Tokio", "En Lima son las 12:10."),
        ("cuánta diferencia hay con aquí", "El blue cerró a 1.405 y el oficial a 1.240."),
        ("cuánta diferencia de precio hay con aquí", "En Lima son las 12:10."),
        ("cuánta diferencia hay con aquí", "En Lima son las 12:10 y en Bogotá son las 12:10."),
        ("how many hours ahead of here is that?", "The meeting is at 12:10."),
    ],
)
def test_hours_apart_that_must_not_change(text: str, reply: str) -> None:
    assert hours_apart_from_the_clock_told(text, reply) is None
