"""Build and preregister BAXY's execution-inert R10 blind product holdout.

R10 is the fresh confirmation campaign after the R9 blind failures and their
development repair.  It changes every action envelope, every conversation
marker assignment, entities, and all 94 generic composition orders.  Generic
orders are rejected if already present in R7-R9.  Boundary-aware replacement
again protects the Spanish read verb ``Lee``.
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
from scripts import build_generalization_product_holdout_r9 as r9  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v10.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v10.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r10_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r10_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r10_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r10_product.json"
PRIOR_CORPORA = (*r9.PRIOR_CORPORA, r9.OUTPUT)
POLICY_SOURCES = r9.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r10.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r10.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_product_holdout_r9.py",
    REPO / "scripts/build_generalization_product_holdout_r8.py",
    REPO / "scripts/build_generalization_product_holdout_r7.py",
    REPO / "scripts/build_generalization_product_holdout_r3.py",
    REPO / "scripts/build_generalization_surface_holdout.py",
)
REFERENCES = r9.REFERENCES


_REPLACEMENTS = (
    ("Krita", "VLC"),
    ("7-Zip", "KeePassXC"),
    ("Plan Boreal", "Archivo Litoral"),
    ("Boreal Plan", "Coastal Record"),
    ("pases de tren", "comprobantes de alojamiento"),
    ("train passes", "lodging receipts"),
    ("Paula", "Daniela"),
    ("Martín", "Sebastián"),
    ("Quinn", "Kendall"),
    ("Parker", "Shawn"),
    ("River", "Riley"),
    ("Skyler", "Corey"),
    ("Arcane", "Andor"),
    ("The Good Place", "Slow Horses"),
    ("mariposas monarca", "pingüinos de Humboldt"),
    ("monarch butterflies", "Humboldt penguins"),
    ("molinos manuales de café", "linternas recargables de viaje"),
    ("manual coffee grinders", "rechargeable travel lanterns"),
    ("ciento veintisiete dividido por siete", "doscientos veinticinco dividido por quince"),
    ("one hundred twenty-seven divided by seven", "two hundred twenty-five divided by fifteen"),
    ("ciento twenty-seven divided by seven", "doscientos twenty-five divided by fifteen"),
    ("sopa", "curry"),
    ("soup", "curry"),
    ("noche fría", "tarde soleada"),
    ("cold evening", "sunny afternoon"),
    ("Rocío", "Josefina"),
    ("Luciano", "Renato"),
    ("Abril", "Trinidad"),
    ("Thiago", "Maximiliano"),
    ("Rowan", "Micah"),
    ("Hayden", "Sage"),
    ("Finley", "Marley"),
    ("Blair", "Aubrey"),
    ("Alex", "Chris"),
    ("Julia", "Constanza"),
)


def _replace_token(text: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?<!\w){re.escape(old)}(?!\w)",
        new,
        text,
        flags=re.IGNORECASE,
    )


def _rewrite(text: str) -> str:
    rewritten = text.replace("Pass Lee the update", "Pass Ellis the update")
    for old, new in _REPLACEMENTS:
        rewritten = _replace_token(rewritten, old, new)
    if re.search(r"\b(?:ellis|chris|marley)\s+el\s+message\b", rewritten, re.I):
        raise RuntimeError("R10 entity replacement corrupted an action verb")
    return rewritten


def _request_utterance(value: Utterance, index: int) -> Utterance:
    prefixes = {
        "es": ("Oiga, por favor, ", "Antes que nada, por favor, "),
        "en": ("Could you please ", "Can you please "),
        "spanglish": ("Oye, can you ", "Por favor, can you "),
    }
    body = _rewrite(value.text)
    body = body[:1].lower() + body[1:]
    if value.language == "en" and body.startswith("is "):
        return Utterance(value.language, "Please, listen, " + body)
    mixed_question = re.fullmatch(
        r"est[áa] working ahora (?P<subject>.+)",
        body,
        flags=re.IGNORECASE,
    )
    if value.language == "spanglish" and mixed_question is not None:
        return Utterance(
            value.language,
            "Oye, please check whether "
            + mixed_question.group("subject")
            + " está working ahora",
        )
    return Utterance(value.language, prefixes[value.language][index % 2] + body)


def _conversation_utterance(value: Utterance, index: int) -> Utterance:
    markers = {
        "es": ("Una duda: ", "Por curiosidad: "),
        "en": ("A question: ", "Just curious: "),
        "spanglish": ("Una duda: ", "Just curious: "),
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
        step for step in range(2, len(operations)) if gcd(step, len(operations)) == 1
    )
    prior_sequences = {
        tuple(composition.operations)
        for composition in (
            *r7.COMPOSITIONS,
            *r8.COMPOSITIONS,
            *r9.COMPOSITIONS,
        )
    }
    current: set[tuple[str, ...]] = set()
    languages = ("spanglish", "es", "en")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 3 + (index * 11 + 3) % 6
        language = languages[index % len(languages)]
        selected: tuple[str, ...] | None = None
        for attempt in range(len(operations) * len(steps)):
            step = steps[(index * 5 + attempt // len(operations)) % len(steps)]
            cursor = (index * 13 + attempt * 7 + 9) % len(operations)
            candidate: list[str] = []
            while len(candidate) < size:
                operation = operations[cursor]
                if operation not in candidate:
                    candidate.append(operation)
                cursor = (cursor + step) % len(operations)
            sequence = tuple(candidate)
            if sequence not in prior_sequences and sequence not in current:
                selected = sequence
                current.add(sequence)
                break
        if selected is None:
            raise RuntimeError(f"R10 could not derive novel composition {index}")
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        base = r7._composition_text(language, parts, index + 47)
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
            Utterance("en", "Take a screenshot and use that image to extract its visible words"),
            0,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe"),
        _request_utterance(
            Utterance("es", "Captura el escritorio y usa esa misma imagen para describir la escena"),
            1,
        ),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        _request_utterance(
            Utterance("spanglish", "Take a screen capture; describe la scene y también transcribe its visible words"),
            2,
        ),
    ),
    builder.Composition(
        ("message.recipient.resolve", "message.send", "task.list"),
        _request_utterance(
            Utterance("es", "Por WhatsApp dile a Constanza que salgo en veinte y después muéstrame las tareas abiertas"),
            3,
        ),
    ),
    builder.Composition(
        ("task.list", "capture.screenshot", "ocr.read"),
        _request_utterance(
            Utterance("en", "List the open tasks, then capture the screen and read the text from that capture"),
            4,
        ),
    ),
    builder.Composition(
        ("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"),
        _request_utterance(
            Utterance("spanglish", "Show today's calendar, capture the screen, describe esa view y then read clipboard text"),
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
    builder.CAMPAIGN = "r10"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v10"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v10"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "r7_distribution_with_new_boundary_aware_entities_reassigned_discourse_"
        "markers_new_politeness_stacks_and_generic_orders_absent_from_r7_r9"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Hey Baxy: ",
        "en": "Hey Baxy: ",
        "spanglish": "Hey Baxy: ",
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
