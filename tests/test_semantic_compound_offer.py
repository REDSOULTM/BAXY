"""Fase 3.5: a mission with a part BAXY can do and a part it cannot is not a flat «no puedo».

The proved clauses are offered in the person's own words and an assent resumes only them; the
rest is not declared impossible (it may be its own request), only not done in this one. A title
with a conjunction is one name, not two clauses. The phrases are not the owner's test nor the
held-out script.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.effect_intent import CompoundEffectContract


def _resolve_opens(clause: str):
    folded = clause.lower()
    return ("app.open",) if folded.startswith(("abre ", "abrí ", "open ")) else None


@pytest.mark.parametrize(
    ("text", "proved", "pending"),
    [
        ("Abre Paint y dibujá un perro", ["Abre Paint"], ["dibujá un perro"]),
        ("abrí Excel, armame una planilla de sueldos", ["abrí Excel"], ["armame una planilla de sueldos"]),
        ("open Photoshop and remove the background", ["open Photoshop"], ["remove the background"]),
        ("abre Teams y después llamame a Pedro", ["abre Teams"], ["llamame a Pedro"]),
    ],
)
def test_the_leading_clauses_the_pattern_proves_are_the_offered_part(text, proved, pending):
    assert mind._leading_proved_clauses(text, None, _resolve_opens) == (proved, pending)


@pytest.mark.parametrize(
    "text",
    ["abre Ratchet y Clank", "abre Dungeons and Dragons", "abre Hollow y Knight", "abre la app de Pérez y Asociados"],
)
def test_a_title_with_a_conjunction_is_one_name(text):
    assert mind._leading_proved_clauses(text, None, _resolve_opens) is None


def test_nothing_to_offer_when_no_clause_is_proved_or_all_are():
    assert mind._leading_proved_clauses("dibujá un perro y pintalo de azul", None, _resolve_opens) is None
    assert mind._leading_proved_clauses("abre Paint y abre Word", None, _resolve_opens) is None


def test_the_compound_contract_reading_wins_and_keeps_the_original_words():
    contract = CompoundEffectContract(
        minimum_effects=2,
        required_clause_sequences=(("app.open",),),
        clause_requirements=(("abri la calculadora", ("app.open",)), ("sacame la raiz de 81", ())),
    )
    text = "Abrí la Calculadora y sacame la raíz de 81."
    assert mind._leading_proved_clauses(text, contract, lambda clause: None) == (
        ["Abrí la Calculadora"],
        ["sacame la raíz de 81"],
    )


def test_the_offer_quotes_both_parts_asks_and_resumes_only_the_proved_part():
    question, objective = mind._compound_partial_offer(
        "abrí Excel y armame una planilla", (["abrí Excel"], ["armame una planilla"]), "es"
    )
    assert "«abrí Excel»" in question and "«armame una planilla»" in question
    assert question.endswith("?")
    assert objective == "abrí Excel"
    # It never says the rest is impossible, only that it is not done in this request.
    assert "no puedo" not in question.lower()


def test_the_offer_speaks_the_request_language():
    question, objective = mind._compound_partial_offer(
        "open Photoshop and remove the background",
        (["open Photoshop"], ["remove the background"]),
        "en",
    )
    assert question.startswith("I can do “open Photoshop”") and question.endswith("?")
    assert objective == "open Photoshop"
