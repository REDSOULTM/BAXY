"""Build and preregister BAXY's execution-inert R8 blind product holdout.

R8 is a fresh, controlled discourse-robustness population created only after
the R7 development repair.  It keeps the public operation distribution while
changing entities, nested politeness/address envelopes, composition order and
conversation content.  No normalized surface from R2-R7 or the development
corpora is admitted, and every row remains turn-decision-only with zero
execution authority.
"""

from __future__ import annotations

import sys
from math import gcd
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r7 as r7  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v8.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v8.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r8_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r8_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r8_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r8_product.json"
PRIOR_CORPORA = (*r7.PRIOR_CORPORA, r7.OUTPUT)
POLICY_SOURCES = r7.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r8.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r8.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_product_holdout_r7.py",
    REPO / "scripts/build_generalization_product_holdout_r3.py",
    REPO / "scripts/build_generalization_surface_holdout.py",
)
REFERENCES = (
    "https://aclanthology.org/2021.acl-long.341/",
    "https://aclanthology.org/2021.acl-long.192/",
    "https://aclanthology.org/2023.findings-acl.91/",
    "https://aclanthology.org/D18-1300/",
    "https://arxiv.org/abs/1909.02027",
    "https://aclanthology.org/2024.acl-long.36/",
    "https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm",
)


_REPLACEMENTS = (
    ("Krita", "Inkscape"),
    ("7-Zip", "WinRAR"),
    ("Plan Boreal", "Registro Aurora"),
    ("Boreal Plan", "Aurora Ledger"),
    ("pases de tren", "reservas de hotel"),
    ("train passes", "hotel vouchers"),
    ("Paula", "Elena"),
    ("Martín", "Nicolás"),
    ("Quinn", "Morgan"),
    ("Parker", "Taylor"),
    ("River", "Casey"),
    ("Skyler", "Jordan"),
    ("Arcane", "Dark"),
    ("The Good Place", "Wednesday"),
    ("mariposas monarca", "abejas carpinteras"),
    ("monarch butterflies", "carpenter bees"),
    ("molinos manuales de café", "prensas francesas de viaje"),
    ("manual coffee grinders", "travel French presses"),
    ("ciento veintisiete dividido por siete", "ciento cuarenta y cuatro dividido por doce"),
    ("one hundred twenty-seven divided by seven", "one hundred forty-four divided by twelve"),
    ("ciento twenty-seven divided by seven", "ciento forty-four divided by twelve"),
    ("sopa", "pasta"),
    ("soup", "pasta"),
    ("noche fría", "tarde lluviosa"),
    ("cold evening", "rainy afternoon"),
    ("Rocío", "Sofía"),
    ("Luciano", "Mateo"),
    ("Abril", "Valentina"),
    ("Thiago", "Benjamín"),
    ("Rowan", "Avery"),
    ("Lee", "Reese"),
    ("Hayden", "Emerson"),
    ("Finley", "Dakota"),
    ("Blair", "Cameron"),
    ("Alex", "Sam"),
    ("Julia", "Camila"),
)


def _rewrite(text: str) -> str:
    rewritten = text
    for old, new in _REPLACEMENTS:
        rewritten = rewritten.replace(old, new)
    return rewritten


def _fresh_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Por favor, ", "Oye, "),
        "en": ("Please, ", "Could you "),
        "spanglish": ("Please, ", "Oye, "),
    }
    return Utterance(
        value.language,
        prefixes[value.language][index % 2] + _rewrite(value.text),
    )


SCENARIOS: dict[str, Scenario] = {
    family: Scenario(
        scenario.operations,
        tuple(
            _fresh_utterance(utterance, index)
            for index, utterance in enumerate(scenario.utterances)
        ),
    )
    for family, scenario in r7.SCENARIOS.items()
}

CLARIFICATIONS = Scenario(
    r7.CLARIFICATIONS.operations,
    tuple(
        _fresh_utterance(utterance, index)
        for index, utterance in enumerate(r7.CLARIFICATIONS.utterances)
    ),
)

COMPOSITION_PARTS = {
    operation: {
        language: _rewrite(part)
        for language, part in language_parts.items()
    }
    for operation, language_parts in r7.COMPOSITION_PARTS.items()
}


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    candidate_steps = (3, 5, 7, 9, 13, 15, 17, 19)
    steps = tuple(
        step for step in candidate_steps if gcd(step, len(operations)) == 1
    )
    if not steps or len(operations) < 8:
        raise RuntimeError(
            "R8 composition generation needs at least eight operations and "
            "a coprime traversal step"
        )
    languages = ("spanglish", "es", "en")
    rows: list[builder.Composition] = []
    seen_texts: set[str] = set()
    for index in range(94):
        size = 3 + (index * 5 + 2) % 6
        language = languages[index % len(languages)]
        selected: list[str] | None = None
        base: str | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index // 5 + attempt) % len(steps)]
            cursor = (
                index * 7 + index // 3 + attempt + 3
            ) % len(operations)
            candidate: list[str] = []
            while len(candidate) < size:
                operation = operations[cursor]
                if operation not in candidate:
                    candidate.append(operation)
                cursor = (cursor + step) % len(operations)
            parts = [COMPOSITION_PARTS[item][language] for item in candidate]
            candidate_text = r7._composition_text(language, parts, index + 17)
            normalized = builder.normalize_text(candidate_text)
            if normalized not in seen_texts:
                selected = candidate
                base = candidate_text
                seen_texts.add(normalized)
                break
        if selected is None or base is None:
            raise RuntimeError(
                f"R8 could not derive a unique composition at index {index}"
            )
        rows.append(
            builder.Composition(
                tuple(selected),
                _fresh_utterance(Utterance(language, base), index),
            )
        )
    return tuple(rows)


SPECIAL_COMPOSITIONS = tuple(
    builder.Composition(
        composition.operations,
        _fresh_utterance(composition.utterance, index),
    )
    for index, composition in enumerate(r7.SPECIAL_COMPOSITIONS)
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS

CONVERSATIONS = tuple(
    _fresh_utterance(utterance, index)
    for index, utterance in enumerate(r7.CONVERSATIONS)
)


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder.POLICY_SOURCES = POLICY_SOURCES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.CAMPAIGN = "r8"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v8"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v8"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_operation_distribution_with_fresh_entities_nested_discourse_envelopes_"
        "new_composition_orders_and_changed_conversation_content"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Oye Baxy: ",
        "en": "Hey Baxy — ",
        "spanglish": "Baxy, please: ",
    }
    builder.SCENARIOS = SCENARIOS
    builder.CLARIFICATIONS = CLARIFICATIONS
    builder.COMPOSITIONS = COMPOSITIONS
    builder.CONVERSATIONS = CONVERSATIONS


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
