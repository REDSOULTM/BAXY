from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.corrector import FuzzyCorrector, catalog_correction_terms


def _tool_with_closed_entities() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "media.control",
                "description": "Un texto que nunca debe entrar al corrector.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "enum": ["orbelion", "prime_video"],
                        },
                        "action": {
                            "type": "string",
                            "enum": ["pause", "resume"],
                        },
                    },
                    "additionalProperties": False,
                },
            },
        }
    ]


def test_inventory_is_derived_only_from_closed_entity_contracts() -> None:
    terms = catalog_correction_terms(_tool_with_closed_entities())

    assert terms == ("orbelion", "prime video")
    assert "pause" not in terms
    assert "media control" not in terms
    assert all("nunca" not in term for term in terms)


def test_unseen_verbs_and_long_phrases_do_not_gate_entity_correction() -> None:
    corrector = FuzzyCorrector(("orbelion",))

    assert corrector.correct("zarpifica orbelyon") == "zarpifica orbelion"
    assert corrector.correct(
        "frumple por favor ahora mismo con mucha calma el canal orbelyon"
    ) == "frumple por favor ahora mismo con mucha calma el canal orbelion"


def test_exact_entities_and_unrelated_language_are_preserved() -> None:
    corrector = FuzzyCorrector(("orbelion",))

    assert corrector.correct("compara orbelion con la alternativa") == (
        "compara orbelion con la alternativa"
    )
    assert corrector.correct("orbita alrededor del planeta") == (
        "orbita alrededor del planeta"
    )


def test_weak_phonetic_match_requires_independent_asr_support() -> None:
    corrector = FuzzyCorrector(("spotify",))

    assert corrector.needs_contextual_support("Open spati")
    assert corrector.correct("Open spati") == "Open spati"
    assert corrector.correct(
        "Open spati",
        alternatives=("Open spotify",),
    ) == "Open spotify"


def test_contextual_support_is_not_requested_for_unrelated_or_strong_text() -> None:
    corrector = FuzzyCorrector(("spotify",))

    assert not corrector.needs_contextual_support("abre la calculadora")
    assert not corrector.needs_contextual_support("Open spotify")


def test_ambiguous_catalog_match_abstains_without_a_clear_margin() -> None:
    corrector = FuzzyCorrector(
        ("orbelion", "orbelian"),
        minimum_margin=20,
    )

    assert corrector.correct("abre orbelien") == "abre orbelien"
