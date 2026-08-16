from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments/stt_quality/semantic_stt_fusion.py"
SPEC = importlib.util.spec_from_file_location("semantic_stt_fusion", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

EVALUATOR_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development.py"
)
EVALUATOR_SPEC = importlib.util.spec_from_file_location(
    "servicenow_semantic_fusion_evaluator", EVALUATOR_PATH
)
assert EVALUATOR_SPEC is not None and EVALUATOR_SPEC.loader is not None
EVALUATOR = importlib.util.module_from_spec(EVALUATOR_SPEC)
sys.modules[EVALUATOR_SPEC.name] = EVALUATOR
EVALUATOR_SPEC.loader.exec_module(EVALUATOR)

V3_PATH = ROOT / "experiments/stt_quality/semantic_stt_fusion_v3.py"
V3_SPEC = importlib.util.spec_from_file_location("semantic_stt_fusion_v3", V3_PATH)
assert V3_SPEC is not None and V3_SPEC.loader is not None
V3 = importlib.util.module_from_spec(V3_SPEC)
sys.modules[V3_SPEC.name] = V3
V3_SPEC.loader.exec_module(V3)

V4_PATH = ROOT / "experiments/stt_quality/semantic_stt_fusion_v4.py"
V4_SPEC = importlib.util.spec_from_file_location("semantic_stt_fusion_v4", V4_PATH)
assert V4_SPEC is not None and V4_SPEC.loader is not None
V4 = importlib.util.module_from_spec(V4_SPEC)
sys.modules[V4_SPEC.name] = V4
V4_SPEC.loader.exec_module(V4)


class StubLexicon:
    _frequencies = {
        "asap": 3.8,
        "jabra": 1.8,
        "workday": 2.9,
    }

    def frequency(self, word: str) -> float:
        return self._frequencies.get(word.casefold(), 0.0)

    def phonetic_candidates(self, word: str) -> tuple[str, ...]:
        if word.casefold() == "cruise":
            return ("cruz",)
        if word.casefold() == "lindse":
            return ("lindsey",)
        return ()


def test_identifier_labels_and_grouped_digits_are_canonicalized() -> None:
    result = MODULE.canonicalize_transcript(
        "Tengo tickets. I de 122755. Uno, ID3 021354 y request E de 60 47 884."
    )

    assert "ID 1227551" in result.text
    assert "ID 3021354" in result.text
    assert "request ID 6047884" in result.text
    assert result.transformations[:2] == ("identifier_label", "structured_digits")


def test_unrelated_address_numbers_are_not_merged() -> None:
    result = MODULE.canonicalize_transcript(
        "Suite 878, 22198 Cruise Bypass, Kentucky 28 816.",
        lexicon=StubLexicon(),
    )

    assert "878, 22198" in result.text
    assert "28816" in result.text


def test_structured_entities_preserve_honest_written_form_alternatives() -> None:
    result = MODULE.canonicalize_transcript(
        "El server de T host usa Work Day. Lo necesito A SAP. Habra headset en Cruise Bypass, "
        "Bradley View, Illinois 71309.",
        lexicon=StubLexicon(),
    )

    assert "T host/Teahost" in result.text
    assert "Work Day/WorkDay" in result.text
    assert "A SAP/ASAP" in result.text
    assert "Habra/Jabra headset" in result.text
    assert "Cruise/Cruz Bypass" in result.text
    assert "Bradley View/BradleyView" in result.text
    assert "Illinois/IL" in result.text
    assert result.requires_clarification


def test_independent_asr_can_preserve_close_address_name_spelling() -> None:
    result = MODULE.canonicalize_transcript(
        "My address is 974 Tamara Lane, South Lindsay, Illinois 71309.",
        alternatives=(
            "my address is nine seven four Tamara Lane South Lindse Illinois seven one three zero nine",
        ),
        lexicon=StubLexicon(),
    )

    assert "Lindsay/Lindsey" in result.text


def test_kb_article_is_recovered_only_in_strong_article_context() -> None:
    result = MODULE.canonicalize_transcript(
        "Seguí los pasos del Cabby Article CAB 0055719, pero sigue fallando."
    )
    untouched = MODULE.canonicalize_transcript("El cabby llegó temprano.")

    assert "KB article KB0055719" in result.text
    assert untouched.text == "El cabby llegó temprano."


def test_plain_language_does_not_manufacture_identifier() -> None:
    result = MODULE.canonicalize_transcript("Y de verdad quiero ir al trabajo hoy.")

    assert result.text == "Y de verdad quiero ir al trabajo hoy."
    assert not result.requires_clarification


def test_secondary_asr_is_reserved_for_structured_postal_addresses() -> None:
    assert EVALUATOR.needs_secondary_hypothesis(
        "My address is 974 Tamara Lane, South Lindsay, Illinois 71309."
    )
    assert not EVALUATOR.needs_secondary_hypothesis(
        "Workday still has my previous address and I need to update it."
    )
    assert not EVALUATOR.needs_secondary_hypothesis(
        "Turn onto Tamara Lane and keep going."
    )


def test_v3_removes_lowercase_morphology_ambiguities_but_keeps_named_entities() -> None:
    result = V3.canonicalize_transcript(
        "Quiero cambiar los datos como dos veces en Service Now y Work Day.",
        lexicon=StubLexicon(),
    )

    assert "cambiar los/cambiarlos" not in result.text
    assert "como dos/comodos" not in result.text
    assert "Service Now" in result.text
    assert "Work Day/WorkDay" in result.text


def test_v4_distinguishes_written_aliases_from_semantic_ambiguity() -> None:
    written_aliases = V4.canonicalize_transcript(
        "Work Day en Illinois y A SAP.",
        lexicon=StubLexicon(),
    )
    semantic_ambiguity = V4.canonicalize_transcript(
        "Habra headset en Cruise Bypass.",
        lexicon=StubLexicon(),
    )

    assert written_aliases.ambiguities
    assert not written_aliases.requires_clarification
    assert semantic_ambiguity.requires_clarification
