"""THEN2003 («abrime el bloc de notas» → «Ponele hola mundo»): the final of a verified typing says the
text was typed, quotes it and names the window; the bare echo «Hola mundo» is not a report."""

from __future__ import annotations

from baxy_mind import effect_intent
from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect

OBSERVED = {"version": 1, "ok": True, "effectObserved": True, "action": "text", "textLength": 10,
            "acceptedEvents": 20, "expectedEvents": 20, "foregroundTitleBefore": "Sin título: Bloc de notas"}
SITUATION = {"kind": "operation", "operation": "input.text.type", "polarity": "success", "verified": True,
             "succeeded": True, "observed": OBSERVED}


def test_typed_literal_comes_from_the_request() -> None:
    assert effect_intent.deictic_typed_literal("Ponele hola mundo") == "hola mundo"
    assert effect_intent.deictic_typed_literal("write on it hello please") == "hello"
    assert effect_intent.deictic_typed_literal("qué hora es") is None


def test_typing_payload_carries_the_text_and_the_window() -> None:
    payload = _compose_situation_payload(SITUATION, "es", "Ponele hola mundo")
    assert payload["seen"] == {"typedText": "hola mundo", "typedInto": "Sin título: Bloc de notas"}


def test_bare_echo_and_missing_text_are_rejected() -> None:
    payload = _compose_situation_payload(SITUATION, "es", "Ponele hola mundo")
    assert _payload_fact_defect("Hola mundo", payload, "Ponele hola mundo") == "typed_echo_without_report"
    assert _payload_fact_defect("Listo, ya está.", payload, "Ponele hola mundo") == "missing_typed_text"
    assert _payload_fact_defect("Escribí «hola mundo» en el Bloc de notas.", payload, "Ponele hola mundo") == ""


def test_a_prohibition_with_a_dative_clitic_is_acknowledged() -> None:
    # THEN2003 boundary «No le pongas nada.»: the dative clitic sits before the verb.
    assert effect_intent.explicit_negative_constraint("No le pongas nada.")
    assert effect_intent.explicit_negative_constraint("No les digas nada.")
