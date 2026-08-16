"""Build and preregister BAXY's execution-inert R9 blind product holdout.

R9 is created only after the R8 blind run and its development repair.  It
preserves the public operation distribution while using contextual entity
rewrites, new request/discourse envelopes, and generic composition orders not
present in R7 or R8.  Replacement is boundary-aware and explicitly protects
the Spanish verb ``Lee`` from the builder defect audited in R8.
"""

from __future__ import annotations

import re
import sys
from math import gcd
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts import build_generalization_product_holdout_r7 as r7  # noqa: E402
from scripts import build_generalization_product_holdout_r8 as r8  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v9.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v9.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r9_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r9_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r9_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r9_product.json"
PRIOR_CORPORA = (*r8.PRIOR_CORPORA, r8.OUTPUT)
POLICY_SOURCES = r8.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r9.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r9.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_product_holdout_r8.py",
    REPO / "scripts/build_generalization_product_holdout_r7.py",
    REPO / "scripts/build_generalization_product_holdout_r3.py",
    REPO / "scripts/build_generalization_surface_holdout.py",
)
REFERENCES = r8.REFERENCES


_REPLACEMENTS = (
    ("Krita", "GIMP"),
    ("7-Zip", "PeaZip"),
    ("Plan Boreal", "Expediente Austral"),
    ("Boreal Plan", "Austral File"),
    ("pases de tren", "confirmaciones de vuelo"),
    ("train passes", "flight confirmations"),
    ("Paula", "Gabriela"),
    ("Martín", "Tomás"),
    ("Quinn", "Sydney"),
    ("Parker", "Logan"),
    ("River", "Jamie"),
    ("Skyler", "Robin"),
    ("Arcane", "Severance"),
    ("The Good Place", "The Bear"),
    ("mariposas monarca", "colibríes migratorios"),
    ("monarch butterflies", "migratory hummingbirds"),
    ("molinos manuales de café", "hornillos portátiles de camping"),
    ("manual coffee grinders", "portable camping stoves"),
    ("ciento veintisiete dividido por siete", "ciento sesenta y ocho dividido por catorce"),
    ("one hundred twenty-seven divided by seven", "one hundred sixty-eight divided by fourteen"),
    ("ciento twenty-seven divided by seven", "ciento sixty-eight divided by fourteen"),
    ("sopa", "risotto"),
    ("soup", "risotto"),
    ("noche fría", "mañana ventosa"),
    ("cold evening", "windy morning"),
    ("Rocío", "Antonia"),
    ("Luciano", "Pedro"),
    ("Abril", "Isidora"),
    ("Thiago", "Agustín"),
    ("Rowan", "Charlie"),
    ("Hayden", "Frankie"),
    ("Finley", "Billie"),
    ("Blair", "Harper"),
    ("Alex", "Drew"),
    ("Julia", "Fernanda"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    # R7 contains both the English person name Lee and the Spanish imperative
    # Lee.  Only the complete person-bearing phrase is eligible for rewriting.
    rewritten = text.replace("Pass Lee the update", "Pass Devon the update")
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Oye, por favor, ", "A ver, por favor, "),
        "en": ("Listen, please, ", "Hey, please, "),
        "spanglish": ("Oye, please, ", "Listen, por favor, "),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    return Utterance(
        value.language,
        prefixes[value.language][index % 2] + body,
    )


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Por curiosidad: ", "Una duda: "),
        "en": ("Just curious: ", "A question: "),
        "spanglish": ("Just curious: ", "Una duda: "),
    }
    return Utterance(
        value.language,
        markers[value.language][index % 2] + _rewrite(value.text),
    )


SCENARIOS: dict[str, Scenario] = {
    family: Scenario(
        scenario.operations,
        tuple(
            _request_utterance(utterance, index)
            for index, utterance in enumerate(scenario.utterances)
        ),
    )
    for family, scenario in r7.SCENARIOS.items()
}

CLARIFICATIONS = Scenario(
    r7.CLARIFICATIONS.operations,
    tuple(
        _request_utterance(utterance, index)
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
    steps = tuple(
        step
        for step in range(2, len(operations))
        if gcd(step, len(operations)) == 1
    )
    if not steps or len(operations) < 8:
        raise RuntimeError("R9 cannot derive bounded composition traversals")
    prior_sequences = {
        tuple(composition.operations)
        for composition in (*r7.COMPOSITIONS, *r8.COMPOSITIONS)
    }
    current_sequences: set[tuple[str, ...]] = set()
    languages = ("en", "spanglish", "es")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 3 + (index * 7 + 1) % 6
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 3 + attempt // len(operations)) % len(steps)]
            cursor = (index * 11 + attempt * 5 + 7) % len(operations)
            candidate: list[str] = []
            while len(candidate) < size:
                operation = operations[cursor]
                if operation not in candidate:
                    candidate.append(operation)
                cursor = (cursor + step) % len(operations)
            sequence = tuple(candidate)
            if sequence not in prior_sequences and sequence not in current_sequences:
                selected = sequence
                current_sequences.add(sequence)
                break
        if selected is None:
            raise RuntimeError(
                f"R9 could not derive a novel composition at index {index}"
            )
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 31)
        rows.append(
            builder.Composition(
                selected,
                _request_utterance(Utterance(language, base), index),
            )
        )
    return tuple(rows)


SPECIAL_COMPOSITIONS = (
    builder.Composition(
        ("capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("es", "Obtén una captura y usa precisamente esa imagen para transcribir sus letras visibles"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("en", "Take a desktop snapshot and use that exact image to describe the scene"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("spanglish", "Capture the screen, describe esa misma image y transcribe its visible text"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance("es", "Por WhatsApp dile a Fernanda que llego en quince y después enséñame las tareas abiertas"),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("en", "Show the open tasks, capture that resulting screen, and read the text in the capture"),
            4,
        ),
    ),
    builder.Composition(
        ("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"),
        _request_utterance(
            Utterance("spanglish", "Display today's calendar, screenshot it, describe esa view y then read clipboard text"),
            5,
        ),
    ),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS

CONVERSATIONS = tuple(
    _conversation_utterance(utterance, index)
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
    builder.CAMPAIGN = "r9"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v9"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v9"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_boundary_aware_entity_rewrites_natural_distinct_"
        "request_and_conversation_envelopes_and_generic_composition_orders_"
        "absent_from_r7_and_r8"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy: ",
        "en": "Baxy: ",
        "spanglish": "Baxy: ",
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
